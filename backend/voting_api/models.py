import uuid
import hashlib
import json
from PIL import Image
from django.db import models, transaction
from django.utils.text import slugify
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


# --- Model 1: The Election ---

class Election(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, help_text="A brief description of the election.")

    election_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # --- AUTOMATION & CONTROL ---
    start_date = models.DateTimeField(help_text="When voting automatically opens.")
    end_date = models.DateTimeField(help_text="When voting automatically closes.")

    is_active = models.BooleanField(default=False,
                                    help_text="Master switch. Must be TRUE *and* within dates for voting to happen.")

    def __str__(self):
        return f"{self.name} ({str(self.election_id)[:8]})"

    @property
    def is_open(self):
        now = timezone.now()
        return self.is_active and (self.start_date <= now <= self.end_date)

# --- Model 1b: Positions & Candidates (The New Structure) ---

class Position(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="positions")
    title = models.CharField(max_length=255)  # e.g., "Senator"

    max_choices = models.PositiveIntegerField(default=1,
                                              help_text="How many candidates can be selected? (e.g., 1 for Pres, 7 for Senator)")

    rank = models.PositiveIntegerField(default=0, help_text="Order to display on the ballot (0 = top).")

    class Meta:
        ordering = ['rank']
        unique_together = ('election', 'title')

    def __str__(self):
        return f"{self.title} ({self.election.name})"


class Candidate(models.Model):
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name="candidates")
    name = models.CharField(max_length=255)

    # Requires 'Pillow' library: pip install Pillow
    photo = models.ImageField(upload_to='candidates/', blank=True, null=True)

    party = models.CharField(max_length=255, blank=True, help_text="e.g., Independent, Green Party")
    bio = models.TextField(blank=True, help_text="Short campaign manifesto.")

    def __str__(self):
        return f"{self.name} - {self.position.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.photo:
            try:
                img = Image.open(self.photo.path)

                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.photo.path)
            except Exception as e:
                print(f"Error resizing image: {e}")

# --- Model 2: The Voter List ---

class RegisteredVoter(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="voters")

    # Combined hash for authentication (RFID + FP)
    voter_hash = models.CharField(max_length=64, db_index=True)

    # --- INDIVIDUAL HASHES FOR UNIQUENESS ---
    rfid_hash = models.CharField(max_length=64, db_index=True, null=True, blank=True)
    fingerprint_hash = models.CharField(max_length=64, db_index=True, null=True, blank=True)

    has_voted = models.BooleanField(default=False)

    class Meta:
        # Enforce that neither RFID nor Fingerprint can be reused in this election
        unique_together = [
            ('election', 'voter_hash'),
            ('election', 'rfid_hash'),
            ('election', 'fingerprint_hash')  # <--- Added this rule
        ]


class PreApprovedVoter(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="preapproved_voters")
    unique_identifier = models.CharField(max_length=255, db_index=True)
    is_linked = models.BooleanField(default=False)

    class Meta:
        unique_together = ('election', 'unique_identifier')


# --- Model 3: The Blockchain (Ledger) ---

class VoteLedger(models.Model):
    election = models.ForeignKey(Election, on_delete=models.PROTECT, related_name="ledger")

    # Stores: {"President": "Alice", "Senator": ["Bob", "Charlie"]}
    ballot_data = models.JSONField()

    timestamp = models.DateTimeField(db_index=True, editable=False)
    previous_hash = models.CharField(max_length=64, blank=True)
    current_hash = models.CharField(max_length=64, unique=True, db_index=True)

    class Meta:
        ordering = ['timestamp']

    def calculate_hash(self):
        ballot_str = json.dumps(self.ballot_data, sort_keys=True)
        data_to_hash = (
                str(self.election.id) +
                ballot_str +
                self.timestamp.isoformat() +
                self.previous_hash
        )
        return hashlib.sha256(data_to_hash.encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk is None:
                if not self.timestamp:
                    self.timestamp = timezone.now()

                last_vote = VoteLedger.objects.filter(election=self.election).order_by('-timestamp').first()
                if last_vote:
                    self.previous_hash = last_vote.current_hash
                else:
                    self.previous_hash = "0" * 64

                self.current_hash = self.calculate_hash()
        super().save(*args, **kwargs)

@receiver(post_save, sender=Election)
def broadcast_election_update(sender, instance, created, **kwargs):
    """
    Whenever an admin creates or edits an Election, tell the 'election_lobby' group.
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "election_lobby",  # Must match the group name in consumers.py
        {
            "type": "election.update", # Must match the function name in consumers.py (underscores become dots)
        }
    )
