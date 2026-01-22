import customtkinter as ctk
import requests
import hashlib
from PIL import Image, ImageOps
from io import BytesIO
import threading
import time
import sys
from datetime import datetime

from pirc522 import RFID
import lgpio
import RPi.GPIO as GPIO
from pyfingerprint.pyfingerprint import PyFingerprint

BASE_URL = "https://votechain.tail841e2c.ts.net:8443"
API_KEY = "my_secret_pi_key_123"
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

TM_CLK = 23
TM_DIO = 24
BUZZER_PIN = 17

COLORS = {
    "bg": "#050511",
    "input_bg": "#101020",
    "text": "#E0F7FA",
    "disabled": "#333333",
    "primary": "#00E5FF",
    "primary_hover": "#80F3FF",
    "accent": "#FF9E00",
    "accent_hover": "#FFC45E",
    "danger": "#FF4444",
    "danger_hover": "#FF6666",
    "success": "#00C853",
    "secondary": "#9D4EDD",
    "white": "#FFFFFF"
}

class TM1637:
    def __init__(self, clk, dio, brightness=7):
        self.clk = clk
        self.dio = dio
        self.brightness = brightness
        GPIO.setup(self.clk, GPIO.OUT)
        GPIO.setup(self.dio, GPIO.OUT)
        self.digits = [0x3f, 0x06, 0x5b, 0x4f, 0x66, 0x6d, 0x7d, 0x07, 0x7f, 0x6f]

    def _start(self):
        GPIO.output(self.dio, 0)
        GPIO.output(self.clk, 0)

    def _stop(self):
        GPIO.output(self.dio, 0)
        GPIO.output(self.clk, 1)
        GPIO.output(self.dio, 1)

    def _write_byte(self, b):
        for i in range(8):
            GPIO.output(self.clk, 0)
            GPIO.output(self.dio, (b >> i) & 1)
            GPIO.output(self.clk, 1)
        GPIO.output(self.clk, 0)
        GPIO.output(self.dio, 1)
        GPIO.output(self.clk, 1)
        GPIO.setup(self.dio, GPIO.IN)
        GPIO.output(self.clk, 0)
        GPIO.setup(self.dio, GPIO.OUT)

    def show_number(self, num):
        num = max(0, min(num, 9999))
        s = f"{num:04d}"
        data = [self.digits[int(c)] for c in s]

        self._start()
        self._write_byte(0x40)
        self._stop()

        self._start()
        self._write_byte(0xc0)
        for d in data:
            self._write_byte(d)
        self._stop()

        self._start()
        self._write_byte(0x88 + self.brightness)
        self._stop()

    def clear(self):
        self.show_number(0)

def parse_api_error(response):
    try:
        if response.status_code == 500: return "Server Internal Error (500)."
        if response.status_code == 404: return "Server endpoint not found (404)."
        data = response.json()
    except:
        return f"Connection Error: Status {response.status_code}"

    messages = []
    def extract_messages(obj, field_prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ['detail', 'message', 'error', 'non_field_errors']:
                    extract_messages(v)
                else:
                    extract_messages(v, f"{k}: " if not field_prefix else f"{field_prefix}{k}: ")
        elif isinstance(obj, list):
            for item in obj: extract_messages(item, field_prefix)
        elif isinstance(obj, str):
            messages.append(f"{field_prefix}{obj}")

    extract_messages(data)
    return "\n".join([f"• {m}" for m in messages]) if messages else "Unknown Error Occurred."

class HardwareInterface:
    def __init__(self, app_callback):
        self.app_callback = app_callback
        self.running = True
        self.expecting_rfid = False
        self.expecting_finger_verify = False
        self.enrollment_active = False

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        GPIO.output(BUZZER_PIN, 0)

        try:
            self.display = TM1637(TM_CLK, TM_DIO)
            self.display.show_number(8888)
            time.sleep(0.5)
            self.display.show_number(0)
        except Exception as e:
            print(f"Display Error: {e}")
            self.display = None

        try:
            self.chip = lgpio.gpiochip_open(0)
            self.ROW_PINS = [5, 6, 13, 19]
            self.COL_PINS = [12, 16, 20]
            self.KEYPAD_MAP = [
                ["1", "2", "3"],
                ["4", "5", "6"],
                ["7", "8", "9"],
                ["*", "0", "#"]
            ]
            for r in self.ROW_PINS: lgpio.gpio_claim_output(self.chip, r, 1)
            for c in self.COL_PINS: lgpio.gpio_claim_input(self.chip, c, lgpio.SET_PULL_UP)
        except Exception as e:
            print(f"Keypad Error: {e}")
            self.chip = None

        self.rfid_reader = RFID(pin_mode=GPIO.BCM, pin_rst=25, pin_ce=0, pin_irq=None)

        try:
            self.finger = PyFingerprint('/dev/ttyAMA0', 57600, 0xFFFFFFFF, 0x00000000)
            if not self.finger.verifyPassword():
                self.finger = None
        except Exception as e:
            self.finger = None

        threading.Thread(target=self._rfid_loop, daemon=True).start()
        threading.Thread(target=self._keypad_loop, daemon=True).start()
        threading.Thread(target=self._finger_verify_loop, daemon=True).start()

    def cleanup(self):
        self.running = False
        try:
            if self.chip is not None:
                lgpio.gpiochip_close(self.chip)
            GPIO.cleanup()
        except:
            pass

    def buzz_success(self):
        def _buzz():
            GPIO.output(BUZZER_PIN, 1)
            time.sleep(0.3)
            GPIO.output(BUZZER_PIN, 0)
        threading.Thread(target=_buzz, daemon=True).start()

    def buzz_error(self):
        def _buzz():
            # Beep 1
            GPIO.output(BUZZER_PIN, 1)
            time.sleep(0.1)
            GPIO.output(BUZZER_PIN, 0)
            time.sleep(0.1)
            # Beep 2
            GPIO.output(BUZZER_PIN, 1)
            time.sleep(0.1)
            GPIO.output(BUZZER_PIN, 0)
        threading.Thread(target=_buzz, daemon=True).start()

    def update_vote_count(self, count):
        if self.display:
            try:
                self.display.show_number(int(count))
            except:
                pass

    def stop_enrollment(self):
        self.enrollment_active = False

    def _keypad_loop(self):
        if self.chip is None: return
        last_key = None
        last_time = 0
        while self.running:
            key = self._scan_keypad()
            curr_time = time.time()
            if key and (key != last_key or (curr_time - last_time) > 0.3):
                self.app_callback("KEYPAD", key)
                last_key = key
                last_time = curr_time
            elif not key:
                last_key = None
            time.sleep(0.02)

    def _scan_keypad(self):
        for r_idx, r_pin in enumerate(self.ROW_PINS):
            lgpio.gpio_write(self.chip, r_pin, 0)
            for c_idx, c_pin in enumerate(self.COL_PINS):
                if lgpio.gpio_read(self.chip, c_pin) == 0:
                    lgpio.gpio_write(self.chip, r_pin, 1)
                    k = self.KEYPAD_MAP[r_idx][c_idx]
                    return "BACKSPACE" if k == "*" else ("ENTER" if k == "#" else k)
            lgpio.gpio_write(self.chip, r_pin, 1)
        return None

    def start_rfid_scan(self):
        self.expecting_rfid = True

    def _rfid_loop(self):
        while self.running:
            if self.expecting_rfid and not self.enrollment_active:
                error, _ = self.rfid_reader.request()
                if error == 0:
                    error, uid = self.rfid_reader.anticoll()
                    if error == 0:
                        uid_str = "-".join(f"{x:02X}" for x in uid)
                        self.expecting_rfid = False
                        self.buzz_success()
                        self.app_callback("RFID", uid_str)
            time.sleep(0.1)

    def start_finger_verify(self):
        self.expecting_finger_verify = True

    def _finger_verify_loop(self):
        while self.running:
            if self.expecting_finger_verify and not self.enrollment_active and self.finger:
                try:
                    if self.finger.readImage():
                        self.finger.convertImage(0x01)
                        result = self.finger.searchTemplate()
                        position = result[0]
                        if position != -1:
                            fp_hash = hashlib.sha256(f"FP-{position}".encode()).hexdigest()
                            self.expecting_finger_verify = False
                            self.buzz_success()
                            self.app_callback("FINGER_MATCH", fp_hash)
                        time.sleep(1)
                except:
                    pass
            time.sleep(0.1)

    def start_enrollment(self, status_updater, done_callback):
        self.enrollment_active = True
        threading.Thread(target=self._run_enrollment, args=(status_updater, done_callback), daemon=True).start()

    def _get_good_image(self, buffer_id, update_status):
        start_time = time.time()
        while self.enrollment_active:
            if time.time() - start_time > 60:
                update_status("TIMEOUT - CANCELLED", COLORS["danger"])
                return False
            while not self.finger.readImage():
                if not self.enrollment_active: return False
                if time.time() - start_time > 60:
                    update_status("TIMEOUT", COLORS["danger"])
                    return False
                time.sleep(0.1)

            start_time = time.time()
            try:
                self.finger.convertImage(buffer_id)
                return True
            except Exception:
                update_status("BAD IMAGE - LIFT & TRY AGAIN", COLORS["accent"])
                time.sleep(1.5)
                while self.finger.readImage():
                    if not self.enrollment_active: return False
                    time.sleep(0.1)
                update_status("PLACE FINGER AGAIN", COLORS["accent"])
        return False

    def _run_enrollment(self, update_status, done_callback):
        try:
            if self.finger.getTemplateCount() >= self.finger.getStorageCapacity():
                update_status("STORAGE FULL!", COLORS["danger"])
                self.enrollment_active = False
                done_callback(None, "Sensor Storage Full")
                return

            update_status("CHECKING DATABASE...", COLORS["accent"])

            if not self._get_good_image(0x01, update_status):
                self.enrollment_active = False
                done_callback(None, None)
                return

            result = self.finger.searchTemplate()
            position = result[0]

            # CASE A: REUSE EXISTING FINGER
            if position != -1:
                self.buzz_success()
                update_status(f"FINGER RECOGNIZED (ID #{position})", COLORS["white"]) # White text for success
                time.sleep(1.5)

                existing_hash = hashlib.sha256(f"FP-{position}".encode()).hexdigest()

                update_status("LIFT FINGER TO FINISH", COLORS["white"]) # White text
                while self.finger.readImage():
                    if not self.enrollment_active:
                        done_callback(None, None)
                        return
                    time.sleep(0.1)

                self.enrollment_active = False
                done_callback(existing_hash, None)
                return

            # CASE B: NEW ENROLLMENT
            update_status("FINGER IS NEW. LIFT FINGER...", COLORS["white"])
            while self.finger.readImage():
                if not self.enrollment_active:
                    done_callback(None, None)
                    return
                time.sleep(0.1)
            time.sleep(1)

            new_id = self.finger.getTemplateCount()

            update_status("STEP 1: PLACE FINGER FIRMLY", COLORS["accent"])
            if not self._get_good_image(0x01, update_status):
                self.enrollment_active = False
                done_callback(None, None)
                return

            update_status("LIFT FINGER...", COLORS["accent"])
            while self.finger.readImage():
                if not self.enrollment_active:
                    done_callback(None, None)
                    return
                time.sleep(0.1)
            time.sleep(1)

            update_status("STEP 2: PLACE SAME FINGER", COLORS["accent"])
            if not self._get_good_image(0x02, update_status):
                self.enrollment_active = False
                done_callback(None, None)
                return

            update_status("PROCESSING...", COLORS["primary"])
            if self.finger.compareCharacteristics() == 0:
                update_status("MISMATCH - TRY AGAIN", COLORS["danger"])
                time.sleep(2)
                self.enrollment_active = False
                done_callback(None, "Fingerprint Mismatch - Try Again")
                return

            # --- SAVE ---
            self.finger.createTemplate()
            self.finger.storeTemplate(new_id)

            fp_hash = hashlib.sha256(f"FP-{new_id}".encode()).hexdigest()
            self.buzz_success()
            update_status("ENROLLMENT COMPLETE!", COLORS["white"]) # White text
            time.sleep(1)
            self.enrollment_active = False
            done_callback(fp_hash, None)

        except Exception as e:
            update_status(f"ERROR: {str(e)}", COLORS["danger"])
            self.enrollment_active = False
            done_callback(None, str(e))

class VoteChainTerminal(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VoteChain Terminal")

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f"{screen_width}x{screen_height}+0+0")

        def force_fullscreen():
            self.attributes('-fullscreen', True)
            self.overrideredirect(True)

        self.after(100, force_fullscreen)
        self.after(500, force_fullscreen)
        self.bind("<Escape>", lambda e: self.destroy())

        self.configure(fg_color=COLORS["bg"])

        self.active_entry = None
        self.captured_rfid_hash = None
        self.captured_fp_hash = None
        self.refresh_job = None
        self.vote_poll_job = None

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.hw = HardwareInterface(self.on_hardware_event)
        self.show_startup()

    def on_hardware_event(self, event_type, data):
        if event_type == "KEYPAD":
            self.after(0, lambda: self.handle_keypad_input(data))
        elif event_type == "RFID":
            self.after(0, lambda: self.handle_rfid_success(data))
        elif event_type == "FINGER_MATCH":
            self.after(0, lambda: self.handle_finger_success(data))

    def handle_keypad_input(self, key):
        if not self.active_entry: return
        if key == "BACKSPACE":
            curr = self.active_entry.get()
            self.active_entry.delete(len(curr)-1, "end")
        elif key == "ENTER":
            pass
        else:
            self.active_entry.insert("end", key)

    def handle_rfid_success(self, uid):
        raw_hash = hashlib.sha256(uid.encode()).hexdigest()
        self.captured_rfid_hash = raw_hash
        if hasattr(self, 'btn_scan_rfid') and self.btn_scan_rfid.winfo_exists():
            self.btn_scan_rfid.configure(text="✅ CARD CAPTURED", fg_color=COLORS["success"])

    def handle_finger_success(self, fp_hash):
        self.captured_fp_hash = fp_hash
        if hasattr(self, 'btn_scan_fp') and self.btn_scan_fp.winfo_exists():
            self.btn_scan_fp.configure(text="✅ FINGERPRINT VERIFIED", fg_color=COLORS["success"])

    def create_btn(self, parent, text, cmd, color="primary", width=200, height=50, state="normal"):
        bg = COLORS.get(color, COLORS["primary"])
        hover = COLORS.get(f"{color}_hover", bg)
        text_col = "#000000" if color in ["primary", "accent"] else "white"
        return ctk.CTkButton(parent, text=text, command=cmd, fg_color=bg, hover_color=hover,
                             text_color=text_col, width=width, height=height, font=("Arial", 18, "bold"), state=state)

    def clear_ui(self):
        if hasattr(self, 'hw'): self.hw.stop_enrollment()
        self.active_entry = None
        self.captured_rfid_hash = None
        self.captured_fp_hash = None

        if self.refresh_job:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None

        if self.vote_poll_job:
            self.after_cancel(self.vote_poll_job)
            self.vote_poll_job = None

        for widget in self.container.winfo_children(): widget.destroy()

    def show_startup(self):
        self.clear_ui()
        self.hw.update_vote_count(0)

        logo_image = None
        try:
            pil_img = Image.open("votechain_logo.png")
            logo_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(80, 80))
        except: pass

        ctk.CTkLabel(self.container, text=" VOTECHAIN", image=logo_image, compound="left", font=("Arial", 60, "bold"),
                     text_color=COLORS["primary"]).place(relx=0.5, rely=0.35, anchor="center")
        ctk.CTkLabel(self.container, text="SECURE ELECTION TERMINAL", font=("Arial", 20, "bold"),
                     text_color=COLORS["secondary"]).place(relx=0.5, rely=0.5, anchor="center")
        self.create_btn(self.container, "TAP TO START", self.show_election_list, width=300, height=80).place(relx=0.5, rely=0.7, anchor="center")

    def show_election_list(self):
        self.clear_ui()
        ctk.CTkLabel(self.container, text="SELECT ELECTION", font=("Arial", 24, "bold"),
                     text_color=COLORS["primary"]).pack(pady=15)
        self.election_scroll = ctk.CTkScrollableFrame(self.container, width=700, height=350, fg_color="transparent")
        self.election_scroll.pack(pady=10)

        self.create_btn(self.container, "REFRESH", self.update_election_data, color="secondary", width=120, height=40).place(x=650, y=420)

        self.create_btn(self.container, "BACK", self.show_startup, color="disabled", width=100).place(x=20, y=420)
        self.update_election_data()

    def update_election_data(self):
        def _fetch():
            try:
                resp = requests.get(f"{BASE_URL}/elections", timeout=3, verify=False)
                if resp.status_code == 200:
                    self.after(0, lambda: self._render_election_list(resp.json()))
                else:
                    self.after(0, lambda: self._render_election_list(None))
            except:
                self.after(0, lambda: self._render_election_list(None))

        threading.Thread(target=_fetch, daemon=True).start()
        self.refresh_job = self.after(5000, self.update_election_data)

    def _render_election_list(self, elections):
        if not self.election_scroll.winfo_exists(): return
        for widget in self.election_scroll.winfo_children(): widget.destroy()

        if not elections:
            ctk.CTkLabel(self.election_scroll, text="No Elections Found", text_color="white").pack()
            return

        for el in elections:
            is_active = el.get('is_active', False)
            end_date_str = el.get('end_date')
            if end_date_str:
                try:
                    clean_date = end_date_str.replace("Z", "+00:00")
                    end_date = datetime.fromisoformat(clean_date)
                    if end_date.tzinfo is not None:
                        from datetime import timezone
                        now = datetime.now(timezone.utc)
                    else:
                        now = datetime.now()
                    if now > end_date: is_active = False
                except: pass

            row = ctk.CTkFrame(self.election_scroll, fg_color=COLORS["input_bg"], border_color=COLORS["secondary"], border_width=1)
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=el['name'], font=("Arial", 20, "bold"), text_color=COLORS["white"]).pack(side="left", padx=20, pady=20)

            status = "OPEN" if is_active else "CLOSED"
            col = "primary" if is_active else "disabled"
            btn = self.create_btn(row, status, lambda e=el, a=is_active: self.select_election(e, a), color=col, width=120)
            btn.pack(side="right", padx=10)
            if not is_active: btn.configure(state="disabled")

    def select_election(self, election, is_actually_active):
        if not is_actually_active: return
        self.selected_election = election
        vote_count = election.get('total_votes', election.get('votes_count', 0))
        self.hw.update_vote_count(vote_count)
        self.show_action_menu()

    def poll_live_vote_count(self):
        def _poll():
            try:
                eid = self.selected_election['election_id']
                r = requests.get(f"{BASE_URL}/dashboard/{eid}/", timeout=2, verify=False)
                if r.status_code == 200:
                    data = r.json()
                    total_votes = data.get('stats', {}).get('total_votes', 0)
                    self.hw.update_vote_count(total_votes)
            except: pass

        threading.Thread(target=_poll, daemon=True).start()
        self.vote_poll_job = self.after(3000, self.poll_live_vote_count)

    def show_action_menu(self):
        self.clear_ui()
        self.poll_live_vote_count()

        ctk.CTkLabel(self.container, text=self.selected_election['name'].upper(), font=("Arial", 20),
                     text_color=COLORS["secondary"]).pack(pady=(30, 10))
        ctk.CTkLabel(self.container, text="CHOOSE ACTION", font=("Arial", 30, "bold"),
                     text_color=COLORS["primary"]).pack(pady=10)

        btn_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        btn_frame.pack(pady=30)
        self.create_btn(btn_frame, "REGISTER VOTER", self.show_registration, color="accent", width=300, height=70).pack(pady=10)
        self.create_btn(btn_frame, "CAST VOTE", self.show_auth, color="primary", width=300, height=70).pack(pady=10)
        self.create_btn(self.container, "BACK", self.show_election_list, color="disabled", width=100).place(x=20, y=420)

    def show_registration(self):
        self.clear_ui()
        ctk.CTkLabel(self.container, text="HARDWARE REGISTRATION", font=("Arial", 25, "bold"), text_color=COLORS["accent"]).pack(pady=10)

        ctk.CTkLabel(self.container, text="1. Enter Student ID (Use Keypad):", text_color="gray").pack()
        self.entry_id = ctk.CTkEntry(self.container, placeholder_text="Type ID here...", width=400, height=50, font=("Arial", 20))
        self.entry_id.pack(pady=5)
        self.entry_id.bind("<FocusIn>", lambda e: setattr(self, 'active_entry', self.entry_id))
        self.active_entry = self.entry_id

        self.btn_scan_rfid = self.create_btn(self.container, "SCAN RFID CARD", self.activate_rfid_mode, color="secondary", width=400)
        self.btn_scan_rfid.pack(pady=10)

        self.btn_enroll_fp = self.create_btn(self.container, "ENROLL FINGERPRINT", self.activate_enroll_mode, color="secondary", width=400)
        self.btn_enroll_fp.pack(pady=10)

        self.create_btn(self.container, "LINK DEVICE", self.perform_registration, color="accent", width=300, height=60).pack(pady=20)
        self.create_btn(self.container, "BACK", self.show_action_menu, color="disabled").place(x=20, y=420)

    def activate_rfid_mode(self):
        self.btn_scan_rfid.configure(text="WAITING FOR CARD...", fg_color=COLORS["accent"])
        self.hw.start_rfid_scan()

    def activate_enroll_mode(self):
        self.btn_enroll_fp.configure(text="INITIALIZING...", state="disabled")
        self.hw.start_enrollment(self.update_enroll_btn, self.on_enroll_done)

    def update_enroll_btn(self, text, color):
        if hasattr(self, 'btn_enroll_fp') and self.btn_enroll_fp.winfo_exists():
            self.after(0, lambda: self.btn_enroll_fp.configure(text=text, fg_color=color))

    def on_enroll_done(self, fp_hash, error_msg):
        self.after(0, lambda: self._finalize_enroll(fp_hash, error_msg))

    def _finalize_enroll(self, fp_hash, error_msg):
        if not hasattr(self, 'btn_enroll_fp') or not self.btn_enroll_fp.winfo_exists(): return

        if fp_hash:
            self.captured_fp_hash = fp_hash
            self.btn_enroll_fp.configure(text="✅ FINGERPRINT CAPTURED", fg_color=COLORS["success"], state="normal")
        else:
            self.btn_enroll_fp.configure(text="❌ FAILED - RETRY", fg_color=COLORS["danger"], state="normal")
            if error_msg:
                self.show_error(error_msg)

    def perform_registration(self):
        if not self.entry_id.get() or not self.captured_rfid_hash or not self.captured_fp_hash:
            self.show_error("Please complete all fields (ID, RFID, Fingerprint)")
            return

        def _req():
            payload = {
                "election_id": self.selected_election['election_id'],
                "unique_identifier": self.entry_id.get(),
                "rfid_hash": self.captured_rfid_hash,
                "fingerprint_hash": self.captured_fp_hash
            }
            try:
                r = requests.post(f"{BASE_URL}/register/link-hardware", json=payload, headers=HEADERS, timeout=5, verify=False)
                if r.status_code == 201:
                    # Show Success
                    self.after(0, lambda: self.show_success("Hardware Linked Successfully"))
                else:
                    err = parse_api_error(r)
                    self.after(0, lambda: self.show_error(err))
            except Exception as e:
                self.after(0, lambda: self.show_error(str(e)))

        threading.Thread(target=_req, daemon=True).start()

    def show_success(self, msg):
        self.clear_ui()
        self.hw.buzz_success()
        ctk.CTkLabel(self.container, text="✅ SUCCESS", font=("Arial", 40, "bold"), text_color=COLORS["primary"]).pack(pady=60)
        ctk.CTkLabel(self.container, text=msg, font=("Arial", 20), text_color=COLORS["white"]).pack()
        self.create_btn(self.container, "CONTINUE", self.show_action_menu).pack(pady=40)

    def show_auth(self):
        self.clear_ui()
        ctk.CTkLabel(self.container, text="AUTHENTICATION", font=("Arial", 30, "bold"), text_color=COLORS["primary"]).pack(pady=20)

        self.btn_scan_rfid = self.create_btn(self.container, "TAP RFID CARD", self.activate_rfid_mode, color="secondary", width=400)
        self.btn_scan_rfid.pack(pady=20)

        self.btn_scan_fp = self.create_btn(self.container, "SCAN FINGERPRINT", self.activate_verify_mode, color="secondary", width=400)
        self.btn_scan_fp.pack(pady=20)

        self.create_btn(self.container, "VERIFY & LOGIN", self.verify_voter, color="primary", width=300, height=60).pack(pady=20)
        self.create_btn(self.container, "CANCEL", self.show_action_menu, color="disabled").place(x=20, y=400)

    def activate_verify_mode(self):
        self.btn_scan_fp.configure(text="PLACE FINGER...", fg_color=COLORS["accent"])
        self.hw.start_finger_verify()

    def verify_voter(self):
        if not self.captured_rfid_hash or not self.captured_fp_hash:
            self.show_error("Please complete both scans first.")
            return

        def _req():
            payload = {
                "election_id": self.selected_election['election_id'],
                "rfid_hash": self.captured_rfid_hash,
                "fingerprint_hash": self.captured_fp_hash
            }
            try:
                r = requests.post(f"{BASE_URL}/vote/check-status", json=payload, headers=HEADERS, timeout=5, verify=False)
                if r.status_code == 200:
                    self.current_user_creds = payload
                    self.after(0, self.fetch_ballot)
                else:
                    err = parse_api_error(r)
                    self.after(0, lambda: self.show_error(err))
            except Exception as e:
                self.after(0, lambda: self.show_error(str(e)))

        threading.Thread(target=_req, daemon=True).start()

    def fetch_ballot(self):
        def _fetch():
            try:
                r = requests.get(f"{BASE_URL}/election/{self.selected_election['election_id']}", timeout=5, verify=False)
                self.ballot_data = r.json()
                self.after(0, self.show_ballot)
            except Exception as e:
                self.after(0, lambda: self.show_error(str(e)))
        threading.Thread(target=_fetch, daemon=True).start()

    def show_ballot(self):
        self.clear_ui()
        ctk.CTkLabel(self.container, text="OFFICIAL BALLOT", font=("Arial", 20, "bold"),
                     text_color=COLORS["secondary"]).pack(pady=5)
        main_scroll = ctk.CTkScrollableFrame(self.container, width=780, height=300, fg_color="transparent")
        main_scroll.pack(fill="both", padx=10)

        self.selections = {}
        for pos in self.ballot_data['positions']:
            instruction = f"(Select up to {pos['max_choices']})" if pos['max_choices'] > 1 else "(Select 1)"
            ctk.CTkLabel(main_scroll, text=f"{pos['title']} {instruction}", font=("Arial", 16, "bold"),
                         text_color=COLORS["accent"], anchor="w").pack(fill="x", pady=(15, 5))

            if pos['max_choices'] == 1:
                self.selections[pos['title']] = ctk.StringVar(value="")
            else:
                self.selections[pos['title']] = []

            h_frame = ctk.CTkScrollableFrame(main_scroll, orientation="horizontal", height=280, fg_color="transparent")
            h_frame.pack(fill="x")

            for cand in pos['candidates']:
                card = ctk.CTkFrame(h_frame, width=170, height=260, fg_color=COLORS["input_bg"],
                                    border_color=COLORS["primary"], border_width=1)
                card.pack_propagate(False)
                card.pack(side="left", padx=10, pady=5)

                img_widget = None
                if cand.get('photo'):
                    try:
                        full_url = f"{BASE_URL}{cand['photo']}"
                        response = requests.get(full_url, timeout=1, verify=False)
                        if response.status_code == 200:
                            img_data = Image.open(BytesIO(response.content))
                            img_data = ImageOps.fit(img_data, (130, 130), method=Image.Resampling.LANCZOS)
                            ctk_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(130, 130))
                            img_widget = ctk.CTkLabel(card, text="", image=ctk_img)
                            img_widget.pack(pady=(10, 5))
                    except: pass

                if img_widget is None:
                    placeholder = ctk.CTkFrame(card, width=130, height=130, fg_color=COLORS["disabled"])
                    placeholder.pack(pady=(10, 5))
                    ctk.CTkLabel(placeholder, text="No Photo", text_color="gray").place(relx=0.5, rely=0.5, anchor="center")

                ctk.CTkLabel(card, text=cand['name'], font=("Arial", 14, "bold"), wraplength=160, text_color=COLORS["white"]).pack(pady=(2, 0))
                ctk.CTkLabel(card, text=cand['party'], font=("Arial", 10), text_color="gray").pack()

                if pos['max_choices'] == 1:
                    ctk.CTkRadioButton(card, text="Select", variable=self.selections[pos['title']], value=cand['name'],
                                       fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                                       font=("Arial", 12, "bold")).place(relx=0.5, rely=0.9, anchor="center")
                else:
                    cand_var = ctk.StringVar(value="")
                    self.selections[pos['title']].append(cand_var)
                    ctk.CTkCheckBox(card, text="Select", variable=cand_var, onvalue=cand['name'], offvalue="",
                                    fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                                    font=("Arial", 12, "bold")).place(relx=0.5, rely=0.9, anchor="center")

        action_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        action_frame.pack(pady=10, fill="x", padx=20)

        self.create_btn(action_frame, "BACK", self.show_auth, color="disabled", width=150, height=60).pack(side="left")

        self.create_btn(action_frame, "SUBMIT BALLOT", self.submit_vote, color="primary", width=550, height=60).pack(side="right")

    def submit_vote(self):
        votes = {}
        for pos_title, selection_data in self.selections.items():
            if isinstance(selection_data, ctk.StringVar):
                if selection_data.get(): votes[pos_title] = selection_data.get()
            elif isinstance(selection_data, list):
                selected = [var.get() for var in selection_data if var.get()]
                if selected: votes[pos_title] = selected
        if not votes: return

        def _submit():
            payload = {
                "election_id": self.selected_election['election_id'],
                "rfid_hash": self.current_user_creds['rfid_hash'],
                "fingerprint_hash": self.current_user_creds['fingerprint_hash'],
                "votes": votes
            }
            try:
                r = requests.post(f"{BASE_URL}/vote/cast", json=payload, headers=HEADERS, timeout=5, verify=False)
                if r.status_code == 201:
                    self.after(0, lambda: self.show_receipt(r.json()['transaction_id']))
                else:
                    err = parse_api_error(r)
                    self.after(0, lambda: self.show_error(err))
            except Exception as e:
                self.after(0, lambda: self.show_error(str(e)))

        threading.Thread(target=_submit, daemon=True).start()

    def show_receipt(self, tx_id):
        self.clear_ui()
        self.hw.buzz_success()
        ctk.CTkLabel(self.container, text="✅ VOTE SECURED", font=("Arial", 40, "bold"),
                     text_color=COLORS["primary"]).pack(pady=50)
        ctk.CTkLabel(self.container, text="Blockchain Hash:", text_color=COLORS["secondary"]).pack()
        box = ctk.CTkTextbox(self.container, height=100, width=600, fg_color=COLORS["input_bg"], text_color=COLORS["white"])
        box.insert("0.0", tx_id)
        box.pack(pady=10)
        self.create_btn(self.container, "DONE", self.show_startup, color="primary", width=200, height=60).pack(pady=40)

    def show_error(self, msg):
        self.hw.buzz_error()

        err_win = ctk.CTkToplevel(self)
        err_win.title("")
        width, height = 500, 320
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        err_win.geometry(f"{width}x{height}+{x}+{y}")
        err_win.overrideredirect(True)
        err_win.attributes('-topmost', True)

        bg_frame = ctk.CTkFrame(err_win, fg_color=COLORS["input_bg"], border_color=COLORS["danger"], border_width=3, corner_radius=10)
        bg_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(bg_frame, text="⚠", font=("Arial", 60), text_color=COLORS["danger"]).pack(pady=(20, 0))
        ctk.CTkLabel(bg_frame, text="ACTION FAILED", font=("Arial", 22, "bold"), text_color="white").pack(pady=(0, 10))
        ctk.CTkLabel(bg_frame, text=msg, font=("Arial", 16), text_color="#DDDDDD", wraplength=width-40).pack(pady=10, padx=20)
        ctk.CTkButton(bg_frame, text="ACKNOWLEDGE", fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                      text_color="white", font=("Arial", 16, "bold"), height=50, width=200,
                      command=err_win.destroy).pack(side="bottom", pady=30)

        def safe_grab():
            if err_win.winfo_exists():
                try: err_win.grab_set()
                except: pass
        self.after(100, safe_grab)

    def destroy(self):
        if hasattr(self, 'hw'): self.hw.cleanup()
        super().destroy()

if __name__ == "__main__":
    app = VoteChainTerminal()
    app.mainloop()
