import hashlib
import json
from django.db import models, transaction
from django.utils.text import slugify
from django.utils import timezone  # <-- Import timezone


# --- Model 1: The Election ---
# This is the main object for an election.

class Election(models.Model):
    """
    Stores the high-level details for a single election.
    e.g., "2025 Mayoral Race"
    """
    name = models.CharField(max_length=255, unique=True,
                            help_text="The human-readable name of the election.")

    # This election_id is what we'll use in API URLs
    election_id = models.SlugField(max_length=255, unique=True, blank=True,
                                   help_text="A unique ID for use in URLs.")

    # Stores the structure: {"President": ["Alice", "Bob"], "VP": ["Charlie", "Dana"]}
    positions_json = models.JSONField(
        help_text="JSON object defining positions and their candidates."
    )

    is_active = models.BooleanField(default=False,
                                    help_text="Marks if this election is open for voting.")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Automatically create the URL-friendly election_id from the name
        if not self.election_id:
            self.election_id = slugify(self.name)
        super().save(*args, **kwargs)


# --- Model 2: The Voter List ---
# This implements our "Event-Based" voter registration.

class RegisteredVoter(models.Model):
    """
    Links a hashed voter ID to a specific election.
    This is the "check-off" list.
    """
    election = models.ForeignKey(Election, on_delete=models.CASCADE,
                                 related_name="voters")

    # This is the SHA-256 hash of the voter's (RFID + Fingerprint)
    voter_hash = models.CharField(max_length=64, db_index=True)

    has_voted = models.BooleanField(default=False,
                                    help_text="Set to True when this person's ballot is cast.")

    class Meta:
        # Ensures a voter can only be registered for an election ONCE.
        unique_together = ('election', 'voter_hash')

    def __str__(self):
        return f"Voter (hash ending ...{self.voter_hash[-6:]}) for {self.election.name}"


class PreApprovedVoter(models.Model):
    """
    Stores the list of unique identifiers (e.g., student IDs)
    that are pre-approved by an admin to vote in an election.
    """
    election = models.ForeignKey(Election, on_delete=models.CASCADE,
                                 related_name="preapproved_voters")

    # This is the Student ID, Employee ID, etc.
    unique_identifier = models.CharField(max_length=255, db_index=True)

    # This flips to True after they link their hardware,
    # preventing this ID from being used again.
    is_linked = models.BooleanField(default=False)

    class Meta:
        # A unique ID can only be in the list once per election
        unique_together = ('election', 'unique_identifier')

    def __str__(self):
        return f"ID: {self.unique_identifier} for {self.election.name} (Linked: {self.is_linked})"


# --- Model 3: The Blockchain (The Vote Ledger) ---
# This is our "True Chain" (Option B).

class VoteLedger(models.Model):
    """
    The "True Chain." Each row is a single, confirmed ballot that
    is cryptographically linked to the one before it.
    """
    election = models.ForeignKey(Election, on_delete=models.PROTECT,
                                 related_name="ledger",
                                 help_text="The election this vote belongs to.")

    # Stores the actual vote: {"President": "Alice", "VP": "Dana"}
    ballot_data = models.JSONField()

    # --- CHANGED ---
    # Removed 'auto_now_add=True' so we can set it manually *before* hashing.
    # 'editable=False' hides it from admin forms.
    timestamp = models.DateTimeField(db_index=True, editable=False)

    # The "chain" links
    previous_hash = models.CharField(max_length=64, blank=True,
                                     help_text="Hash of the previous block/vote in this election's chain.")

    current_hash = models.CharField(max_length=64, unique=True, db_index=True,
                                    help_text="Hash of this vote's data.")

    class Meta:
        # Orders the votes by time, making it a chain
        ordering = ['timestamp']

    def __str__(self):
        return f"Vote {self.id} for {self.election.name} at {self.timestamp}"

    def calculate_hash(self):
        """Helper function to create the hash for this specific vote."""
        # We must serialize the JSON to a consistent string
        ballot_str = json.dumps(self.ballot_data, sort_keys=True)

        # --- CHANGED ---
        # Ensure timestamp is in a consistent string format (ISO 8601)
        # This is critical for the hash to be reproducible.
        data_to_hash = (
                str(self.election.id) +
                ballot_str +
                self.timestamp.isoformat() +
                self.previous_hash
        )

        return hashlib.sha256(data_to_hash.encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs):
        """
        Overrides the save() method to implement the "True Chain" logic.
        """
        # We wrap this in a database transaction to ensure data integrity.
        # This prevents a "race condition" where two votes try to get the
        # same previous_hash at the exact same time.
        with transaction.atomic():
            # --- CHANGED ---
            # Use 'self.pk is None' instead of 'not self.id'.
            # This is the standard Django way and fixes linter warnings.
            if self.pk is None:  # Only on creation

                # --- ADDED ---
                # 1. Set the timestamp *before* hashing
                if not self.timestamp:
                    self.timestamp = timezone.now()

                # 2. Get the last vote in the chain *for this election*
                last_vote = VoteLedger.objects.filter(election=self.election).order_by('-timestamp').first()

                if last_vote:
                    # We have a chain, so link to it
                    self.previous_hash = last_vote.current_hash
                else:
                    # This is the first vote (the "Genesis Block" for this election)
                    self.previous_hash = "0" * 64  # Genesis hash

                # --- CHANGED ---
                # 3. Calculate the hash for *this* vote
                # We now call our consistent 'calculate_hash' method.
                self.current_hash = self.calculate_hash()

        super().save(*args, **kwargs)