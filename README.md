
# VOTECHAIN: Voting Optimization Through Encrypted Blockchain

VOTECHAIN is a secure, IoT-based electronic voting system designed to eliminate electoral fraud, "ghost voting," and data manipulation. By integrating physical biometric authentication with a private, permissioned blockchain, the system ensures that every vote is immutable, verifiable, and transparent


## Key Features

- Multi-Factor Authentication (MFA): Enforces a "one person, one vote" policy using a physical "handshake" between an RFID card and a fingerprint scan.
- Immutable Ledger: Utilizes a custom Python-based blockchain where every vote is cryptographically hashed (SHA-256) and linked to the previous block, making data alteration detectable.
- Real-Time Transparency: A public web application broadcasts vote tallies and ledger updates instantly via WebSockets, allowing anyone to audit the election without compromising voter privacy.

## Hardware Architecture
The system is built around a Raspberry Pi 5 controller acting as the central processing unit.
- Authentication: AS608 Optical Fingerprint Sensor & MFRC522 RFID Reader.
- Interface: 5-inch Touchscreen Display for the ballot UI & 4x3 Matrix Keypad for ID entry.
- Feedback: TM1637 4-Digit 7-Segment Display (for physical vote counting) & Active Buzzer.

## Tech Stack
- Voting Kiosk: Python with Custom Tkinter for the touchscreen interface.
- Backend: Django Channels (WebSockets) for real-time data streaming.
- Frontend Web App: React and Tailwind CSS for the public transparency dashboard.
- Blockchain: Custom Python implementation using SHA-256 hashing.

## User Workflow
    1. Authentication: The voter taps their RFID card and scans their fingerprint. The system validates the credentials against the central database.
    2. Voting: Once authenticated, the user selects candidates via the touchscreen interface.
    3. Blockchain Submission: The vote is encrypted, hashed, and appended to the blockchain. A unique "Digital Receipt" (transaction hash) is displayed to the voter.
    4. Public Verification: The vote count updates instantly on the public web dashboard, where users can verify their transaction hash against the public ledger.
