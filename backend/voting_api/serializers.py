import hashlib
from rest_framework import serializers
from .models import Election, RegisteredVoter, VoteLedger, PreApprovedVoter, Position, Candidate
from django.db import transaction
from django.utils import timezone

# --- Helper to hash voter data ---
def hash_voter_data(rfid_hash, fingerprint_hash):
    combined_key = f"{rfid_hash}-{fingerprint_hash}"
    return hashlib.sha256(combined_key.encode('utf-8')).hexdigest()


class CandidateSerializer(serializers.ModelSerializer):
    # We add this field so the frontend knows how many votes they got
    vote_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Candidate
        fields = ['id', 'name', 'party', 'photo', 'bio', 'vote_count']


class PositionSerializer(serializers.ModelSerializer):
    candidates = CandidateSerializer(many=True, read_only=True)

    class Meta:
        model = Position
        fields = ['id', 'title', 'max_choices', 'rank', 'candidates']


class LedgerSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField()

    class Meta:
        model = VoteLedger
        fields = ['current_hash', 'timestamp', 'ballot_data']

    def get_timestamp(self, obj):
        return obj.timestamp.strftime("%H:%M:%S")

# --- 1. Public List Serializer (WAS MISSING) ---
class ElectionListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing all elections on the landing page.
    """

    class Meta:
        model = Election
        fields = ['name', 'election_id', 'is_active', 'start_date', 'end_date']


# --- 2. Public Election Details (Nested Structure) ---

class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = ['id', 'name', 'party', 'photo', 'bio']


class PositionSerializer(serializers.ModelSerializer):
    candidates = CandidateSerializer(many=True, read_only=True)

    class Meta:
        model = Position
        fields = ['id', 'title', 'max_choices', 'candidates', 'rank']


class PublicElectionDetailSerializer(serializers.ModelSerializer):
    """Used by the Pi to get the full ballot structure."""
    positions = PositionSerializer(many=True, read_only=True)

    class Meta:
        model = Election
        fields = ['name', 'description', 'election_id', 'start_date', 'end_date', 'positions']


# --- 3. Vote Casting (The "Gatekeeper") ---

class CastBallotSerializer(serializers.Serializer):
    rfid_hash = serializers.CharField(write_only=True)
    fingerprint_hash = serializers.CharField(write_only=True)
    election_id = serializers.CharField()
    votes = serializers.JSONField()

    def validate(self, data):
        election_id = data.get('election_id')

        r_hash = data.get('rfid_hash')
        f_hash = data.get('fingerprint_hash')
        votes_submitted = data.get('votes')

        try:
            election = Election.objects.get(election_id=election_id)
            if not election.is_open:
                raise serializers.ValidationError("TIME_EXPIRED: The voting window has closed.")
            data['election_object'] = election
        except Election.DoesNotExist:
            raise serializers.ValidationError(f"Election '{election_id}' does not exist.")

        voter_master_hash = hash_voter_data(r_hash, f_hash)
        data['voter_hash'] = voter_master_hash

        try:
            voter = RegisteredVoter.objects.get(election=election, voter_hash=voter_master_hash)
            if voter.has_voted:
                raise serializers.ValidationError("Duplicate vote: Voter has already cast a ballot.")
            data['voter_object'] = voter
        except RegisteredVoter.DoesNotExist:
            raise serializers.ValidationError("Invalid voter credentials.")

        valid_positions = Position.objects.filter(election=election)
        position_map = {p.title: p for p in valid_positions}
        clean_ballot = {}

        for pos in valid_positions:
            if pos.title not in votes_submitted:
                raise serializers.ValidationError(f"You must cast a vote for {pos.title}.")
            selection = votes_submitted[pos.title]
            if not selection:
                raise serializers.ValidationError(f"You must select a candidate for {pos.title}.")

        for position_title, selection in votes_submitted.items():
            if position_title not in position_map: continue
            position_obj = position_map[position_title]
            if not isinstance(selection, list): selection = [selection]

            if len(selection) > position_obj.max_choices:
                raise serializers.ValidationError(f"Too many selections for {position_title}.")

            valid_names = set(Candidate.objects.filter(position=position_obj).values_list('name', flat=True))
            valid_selection = [name for name in selection if name in valid_names]

            if len(valid_selection) != len(selection):
                raise serializers.ValidationError(f"Invalid candidate selection for {position_title}.")

            clean_ballot[position_title] = valid_selection[0] if position_obj.max_choices == 1 else valid_selection

        data['clean_ballot'] = clean_ballot
        return data


# --- 4. Hardware Linking & Checks (WAS MISSING) ---

class VoterStatusSerializer(serializers.Serializer):
    rfid_hash = serializers.CharField(write_only=True)
    fingerprint_hash = serializers.CharField(write_only=True)
    election_id = serializers.CharField()

    def validate(self, data):
        election_id = data.get('election_id')
        r_hash = data.get('rfid_hash')
        f_hash = data.get('fingerprint_hash')

        try:
            election = Election.objects.get(election_id=election_id)
        except Election.DoesNotExist:
            raise serializers.ValidationError("Election not found.")

        voter_master_hash = hash_voter_data(r_hash, f_hash)

        try:
            voter = RegisteredVoter.objects.get(election=election, voter_hash=voter_master_hash)
        except RegisteredVoter.DoesNotExist:
            raise serializers.ValidationError("Invalid voter: Not registered.")

        if voter.has_voted:
            raise serializers.ValidationError("Duplicate vote: Already voted.")

        return data


class CheckIDSerializer(serializers.Serializer):
    """
    Checks if a Pre-Approved ID is valid and not yet linked.
    """
    election_id = serializers.SlugField()
    unique_identifier = serializers.CharField()

    def validate(self, data):
        election_id = data.get('election_id')
        unique_id = data.get('unique_identifier')

        try:
            election = Election.objects.get(election_id=election_id)
        except Election.DoesNotExist:
            raise serializers.ValidationError(f"Election '{election_id}' does not exist.")

        try:
            preapproved_voter = PreApprovedVoter.objects.get(
                election=election,
                unique_identifier=unique_id
            )
        except PreApprovedVoter.DoesNotExist:
            raise serializers.ValidationError("This Unique ID is not pre-approved.")

        if preapproved_voter.is_linked:
            raise serializers.ValidationError("This Unique ID has already been linked to hardware.")

        return data


class LinkHardwareSerializer(serializers.Serializer):
    rfid_hash = serializers.CharField(write_only=True)
    fingerprint_hash = serializers.CharField(write_only=True)
    election_id = serializers.CharField()
    unique_identifier = serializers.CharField(write_only=True)

    def validate(self, data):
        election_id = data.get('election_id')
        unique_id = data.get('unique_identifier')

        # We now receive Hashes directly
        r_hash = data.get('rfid_hash')
        f_hash = data.get('fingerprint_hash')

        try:
            election = Election.objects.get(election_id=election_id)
            if not election.is_open:
                raise serializers.ValidationError("Registration is closed.")
            data['election_object'] = election
        except Election.DoesNotExist:
            raise serializers.ValidationError("Election not found.")

        try:
            preapproved = PreApprovedVoter.objects.get(election=election, unique_identifier=unique_id)
            if preapproved.is_linked:
                raise serializers.ValidationError("ID already linked.")
            data['preapproved_voter_object'] = preapproved
        except PreApprovedVoter.DoesNotExist:
            raise serializers.ValidationError("ID not authorized.")

        # 1. Check Uniqueness (Using the hash directly)
        if RegisteredVoter.objects.filter(election=election, rfid_hash=r_hash).exists():
            raise serializers.ValidationError("Security Alert: This RFID card is already in use.")

        if RegisteredVoter.objects.filter(election=election, fingerprint_hash=f_hash).exists():
            raise serializers.ValidationError("Security Alert: This fingerprint is already in use.")

        # 2. Prepare Data
        data['rfid_hash'] = r_hash
        data['fingerprint_hash'] = f_hash
        data['voter_hash'] = hash_voter_data(r_hash, f_hash)

        return data

    def save(self):
        with transaction.atomic():
            pre = self.validated_data['preapproved_voter_object']
            pre.is_linked = True
            pre.save()
            return RegisteredVoter.objects.create(
                election=self.validated_data['election_object'],
                voter_hash=self.validated_data['voter_hash'],
                rfid_hash=self.validated_data['rfid_hash'],
                fingerprint_hash=self.validated_data['fingerprint_hash']
            )

    def save(self):
        with transaction.atomic():
            pre = self.validated_data['preapproved_voter_object']
            pre.is_linked = True
            pre.save()

            return RegisteredVoter.objects.create(
                election=self.validated_data['election_object'],
                voter_hash=self.validated_data['voter_hash'],
                rfid_hash=self.validated_data['rfid_hash'],
                fingerprint_hash=self.validated_data['fingerprint_hash']  # Save it!
            )

# --- 5. Ledger & Tally Serializers ---

class PublicLedgerSerializer(serializers.ModelSerializer):
    vote_id = serializers.ReadOnlyField(source='id')
    timestamp = serializers.SerializerMethodField()

    class Meta:
        model = VoteLedger
        fields = ['vote_id', 'timestamp', 'previous_hash', 'current_hash', 'ballot_data']

    def get_timestamp(self, obj):
        local_time = timezone.localtime(obj.timestamp)
        return local_time.strftime("%Y-%m-%d %H:00")


class PublicTallySerializer(serializers.Serializer):
    position = serializers.CharField()
    candidate = serializers.CharField()
    votes = serializers.IntegerField()


class PreApprovedVoterSerializer(serializers.ModelSerializer):
    """
    Used for viewing lists of IDs.
    """

    class Meta:
        model = PreApprovedVoter
        fields = ['unique_identifier', 'is_linked']
        # SAFETY: Ensure API users cannot set 'is_linked' to False/True manually
        read_only_fields = ['is_linked']


class RegisteredVoterSerializer(serializers.ModelSerializer):
    """
    Used for viewing registered voters.
    """

    class Meta:
        model = RegisteredVoter
        fields = ['election', 'voter_hash', 'has_voted']
        # SAFETY: Ensure API users cannot set 'has_voted' manually
        read_only_fields = ['has_voted', 'voter_hash', 'election']


class UploadPreApprovedVotersSerializer(serializers.Serializer):
    """
    Bulk Upload. Creates voters with is_linked=False by default.
    """
    election_id = serializers.SlugField()
    identifiers = serializers.ListField(child=serializers.CharField())

    def validate_election_id(self, value):
        try:
            return Election.objects.get(election_id=value)
        except Election.DoesNotExist:
            raise serializers.ValidationError(f"Election '{value}' does not exist.")

    def create(self, validated_data):
        election = validated_data.get('election_id')
        identifiers = validated_data.get('identifiers')

        # We use bulk_create to enforce efficient, clean creation
        # is_linked defaults to False in the model, so we don't even set it here.
        objs = [
            PreApprovedVoter(election=election, unique_identifier=uid)
            for uid in identifiers
        ]
        try:
            created = PreApprovedVoter.objects.bulk_create(objs, ignore_conflicts=True)
            return len(created)
        except Exception as e:
            raise serializers.ValidationError(str(e))

