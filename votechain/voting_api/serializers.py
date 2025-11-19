import hashlib
from rest_framework import serializers
from .models import Election, RegisteredVoter, VoteLedger, PreApprovedVoter, timezone
from django.db import transaction

# --- Helper to hash voter data ---
def hash_voter_data(rfid, fingerprint):
    """Hashes the RFID and Fingerprint to match the database."""
    combined_key = f"{rfid}-{fingerprint}"
    return hashlib.sha256(combined_key.encode('utf-8')).hexdigest()


# --- Serializers for the Raspberry Pi (Vote Casting) ---

class CastBallotSerializer(serializers.Serializer):
    """
    This serializer is used by the Pi to *submit* a vote.
    It validates the incoming data from the Pi.
    """
    # Voter credentials (raw, from the hardware)
    rfid = serializers.CharField(write_only=True)
    fingerprint = serializers.CharField(write_only=True)

    # Ballot data
    election_id = serializers.SlugField()
    votes = serializers.JSONField()  # e.g., {"President": "Alice", "VP": "Dana"}

    def validate(self, data):
        """
        Validates the entire ballot.
        This is where we check our "off-chain" database.
        """
        election_id = data.get('election_id')
        rfid = data.get('rfid')
        fingerprint = data.get('fingerprint')

        # 1. Check if the election exists and is active
        try:
            election = Election.objects.get(election_id=election_id, is_active=True)
            data['election_object'] = election  # Pass the object to the view
        except Election.DoesNotExist:
            raise serializers.ValidationError(
                f"Election '{election_id}' does not exist or is not active."
            )

        # 2. Check the voter's credentials
        voter_hash = hash_voter_data(rfid, fingerprint)
        data['voter_hash'] = voter_hash  # Pass the hash to the view

        try:
            voter = RegisteredVoter.objects.get(
                election=election,
                voter_hash=voter_hash
            )
            data['voter_object'] = voter  # Pass the object to the view
        except RegisteredVoter.DoesNotExist:
            raise serializers.ValidationError("Invalid voter: RFID/Fingerprint not registered for this election.")

        # 3. Check for duplicate vote
        if voter.has_voted:
            raise serializers.ValidationError("Duplicate vote: This voter has already cast a ballot.")

        # 4. TODO: Validate the 'votes' JSON
        # (Check if candidates are valid for the position)
        # We will add this later for simplicity.

        return data


class VoterStatusSerializer(serializers.Serializer):
    """
    Checks if a voter is registered and has not yet voted.
    Used by the Pi *before* fetching the ballot.
    """
    rfid = serializers.CharField(write_only=True)
    fingerprint = serializers.CharField(write_only=True)
    election_id = serializers.SlugField()

    def validate(self, data):
        election_id = data.get('election_id')
        rfid = data.get('rfid')
        fingerprint = data.get('fingerprint')

        # 1. Check if the election exists and is active
        try:
            election = Election.objects.get(election_id=election_id, is_active=True)
        except Election.DoesNotExist:
            raise serializers.ValidationError(
                f"Election '{election_id}' does not exist or is not active."
            )

        # 2. Check the voter's credentials
        voter_hash = hash_voter_data(rfid, fingerprint)
        try:
            voter = RegisteredVoter.objects.get(
                election=election,
                voter_hash=voter_hash
            )
        except RegisteredVoter.DoesNotExist:
            raise serializers.ValidationError("Invalid voter: RFID/Fingerprint not registered for this election.")

        # 3. Check for duplicate vote
        if voter.has_voted:
            raise serializers.ValidationError("Duplicate vote: This voter has already cast a ballot.")

        # 4. All checks passed
        return data


class CheckIDSerializer(serializers.Serializer):
    """
    Checks if a Pre-Approved ID is valid and not yet linked.
    Used by the Pi *before* asking for hardware.
    """
    election_id = serializers.SlugField()
    unique_identifier = serializers.CharField()

    def validate(self, data):
        election_id = data.get('election_id')
        unique_id = data.get('unique_identifier')

        # 1. Check if the election exists and is active
        try:
            election = Election.objects.get(election_id=election_id, is_active=True)
        except Election.DoesNotExist:
            raise serializers.ValidationError(
                f"Election '{election_id}' does not exist or is not active."
            )

        # 2. Check if the ID is pre-approved
        try:
            preapproved_voter = PreApprovedVoter.objects.get(
                election=election,
                unique_identifier=unique_id
            )
        except PreApprovedVoter.DoesNotExist:
            raise serializers.ValidationError("This Unique ID is not pre-approved for this election.")

        # 3. Check if ID is already linked
        if preapproved_voter.is_linked:
            raise serializers.ValidationError("This Unique ID has already been linked to hardware.")

        # 4. All checks passed
        return data

class LinkHardwareSerializer(serializers.Serializer):
    """
    This serializer is used by the Pi to *link* hardware
    to a pre-approved ID.
    """
    rfid = serializers.CharField(write_only=True)
    fingerprint = serializers.CharField(write_only=True)
    election_id = serializers.SlugField()
    unique_identifier = serializers.CharField(write_only=True)  # e.g., "1002"

    def validate(self, data):
        """
        Validates that this linking operation is allowed.
        """
        election_id = data.get('election_id')
        unique_id = data.get('unique_identifier')

        # 1. Find the election
        try:
            election = Election.objects.get(election_id=election_id, is_active=True)
            data['election_object'] = election
        except Election.DoesNotExist:
            raise serializers.ValidationError("Election not found or is not active.")

        # 2. Find the pre-approved ID
        try:
            preapproved_voter = PreApprovedVoter.objects.get(
                election=election,
                unique_identifier=unique_id
            )
            data['preapproved_voter_object'] = preapproved_voter
        except PreApprovedVoter.DoesNotExist:
            raise serializers.ValidationError("This Unique ID is not pre-approved for this election.")

        # 3. Check if ID is already linked
        if preapproved_voter.is_linked:
            raise serializers.ValidationError("This Unique ID has already been linked to hardware.")

        # 4. Check if HARDWARE is already linked
        # This prevents one person from linking their single RFID/FP
        # to multiple different Student IDs.
        voter_hash = hash_voter_data(data.get('rfid'), data.get('fingerprint'))
        if RegisteredVoter.objects.filter(election=election, voter_hash=voter_hash).exists():
            raise serializers.ValidationError(
                "This hardware (RFID/Fingerprint) is already registered to another voter.")

        data['voter_hash'] = voter_hash
        return data

    def save(self):
        """
        Creates the RegisteredVoter and links the PreApprovedVoter.
        """
        # We wrap this in a transaction to ensure both
        # operations succeed or fail together.
        try:
            with transaction.atomic():
                # 1. Get the objects from validated_data
                preapproved_voter = self.validated_data['preapproved_voter_object']
                election = self.validated_data['election_object']
                voter_hash = self.validated_data['voter_hash']

                # 2. Mark the PreApprovedVoter as "linked"
                preapproved_voter.is_linked = True
                preapproved_voter.save()

                # 3. Create the new RegisteredVoter object
                new_voter = RegisteredVoter.objects.create(
                    election=election,
                    voter_hash=voter_hash,
                    has_voted=False  # They are registered, but haven't voted yet
                )
                return new_voter

        except Exception as e:
            # If anything goes wrong, raise a validation error
            raise serializers.ValidationError(f"Database error during linking: {e}")

# --- Serializers for the Public Dashboard ---

# --- THIS IS THE MISSING CLASS ---
class PublicElectionDetailSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the Pi to fetch the ballot structure.
    """

    class Meta:
        model = Election
        fields = ['name', 'election_id', 'positions_json']


# --- ADD THIS NEW SERIALIZER ---
class PublicLedgerSerializer(serializers.ModelSerializer):
    """
    Read-only serializer to format a single vote from the VoteLedger
    for the public, anonymous ledger.
    """
    # We rename 'id' to 'vote_id' to be clearer in the API
    vote_id = serializers.ReadOnlyField(source='id')

    class Meta:
        model = VoteLedger
        # We only expose the fields that are safe for the public to see
        fields = ['vote_id', 'timestamp', 'previous_hash', 'current_hash', 'ballot_data']


class PublicTallySerializer(serializers.Serializer):
    """
    Read-only serializer to format the *aggregated* tally.
    It does not show individual votes.
    """
    position = serializers.CharField()
    candidate = serializers.CharField()
    votes = serializers.IntegerField()


# --- Serializers for the Admin ---

class ElectionSerializer(serializers.ModelSerializer):
    """
    Used by the Admin to create and view elections.
    """

    class Meta:
        model = Election
        fields = ['name', 'election_id', 'positions_json', 'is_active']
        read_only_fields = ['election_id']


class UploadPreApprovedVotersSerializer(serializers.Serializer):
    """
    This serializer is used by the Admin to bulk-upload a list
    of pre-approved voter IDs. It is NOT a ModelSerializer.
    It expects a payload like:
    {
        "election_id": "sigma",
        "identifiers": ["1001", "1002", "1003", "..."]
    }
    """
    election_id = serializers.SlugField()
    identifiers = serializers.ListField(
        child=serializers.CharField()
    )

    def validate_election_id(self, value):
        """
        Check that the election exists and is active.
        """
        try:
            election = Election.objects.get(election_id=value)
        except Election.DoesNotExist:
            raise serializers.ValidationError(f"Election '{value}' does not exist.")
        return election  # Return the Election object

    def create(self, validated_data):
        """
        This is called by serializer.save() in the view.
        It performs the bulk-creation.
        """
        election = validated_data.get('election_id')
        identifiers_list = validated_data.get('identifiers')

        # Create a list of new PreApprovedVoter objects
        voters_to_create = [
            PreApprovedVoter(
                election=election,
                unique_identifier=uid
            )
            for uid in identifiers_list
        ]

        # Use bulk_create for efficiency.
        # ignore_conflicts=True is CRITICAL: it prevents duplicates
        # from crashing the entire transaction.
        try:
            new_voters = PreApprovedVoter.objects.bulk_create(
                voters_to_create,
                ignore_conflicts=True
            )

            # Return the count of *new* voters that were created
            return len(new_voters)

        except Exception as e:
            raise serializers.ValidationError(f"An error occurred during bulk create: {e}")

class PreApprovedVoterSerializer(serializers.ModelSerializer):
    """
    Used by the Admin to bulk-upload a list of unique_identifiers.
    """
    # We are receiving the unique_identifier as a plain string
    unique_identifier = serializers.CharField()

    class Meta:
        model = PreApprovedVoter
        fields = ['unique_identifier']

class RegisteredVoterSerializer(serializers.ModelSerializer):
    """
    Used by the Admin to register voters for an election.
    """

    class Meta:
        model = RegisteredVoter
        fields = ['election', 'voter_hash', 'has_voted']