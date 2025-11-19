from rest_framework import generics, views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from django.db import transaction, models
from django.http import Http404

# --- ADDED LIBRARIES ---
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
# ---------------------

from .models import Election, RegisteredVoter, VoteLedger, PreApprovedVoter
from .serializers import (
    CastBallotSerializer,
    PublicTallySerializer,
    ElectionSerializer,
    UploadPreApprovedVotersSerializer,
    PublicElectionDetailSerializer,
    LinkHardwareSerializer,
    VoterStatusSerializer,
    CheckIDSerializer,
    PublicLedgerSerializer
)
from .permissions import IsPiTerminal


# ---
# Helper Function for Broadcasting
# ---
def _get_tally_data(election):
    """
    A helper function to get the full dashboard payload.
    This can be called from anywhere.
    """
    # 1. Get the Tally
    tally = {}
    for position, candidates in election.positions_json.items():
        tally[position] = {candidate: 0 for candidate in candidates}

    votes = VoteLedger.objects.filter(election=election).values_list('ballot_data', flat=True)
    for ballot in votes:
        for position, candidate in ballot.items():
            if position in tally and candidate in tally[position]:
                tally[position][candidate] += 1

    # Format the tally results
    tally_results = []
    for position, candidates in tally.items():
        for candidate, count in candidates.items():
            tally_results.append({
                "position": position,
                "candidate": candidate,
                "votes": count
            })

    # 2. Get the Ledger
    ledger_entries = VoteLedger.objects.filter(election=election).order_by('timestamp')

    # Serialize both parts
    tally_serializer = PublicTallySerializer(tally_results, many=True)
    ledger_serializer = PublicLedgerSerializer(ledger_entries, many=True)

    # Return the final payload
    return {
        'tally': tally_serializer.data,
        'ledger': ledger_serializer.data
    }


# ---
# API Endpoint 1: Cast Vote (For the Raspberry Pi)
# ---
class CastVoteView(views.APIView):
    """
    This is the single, critical endpoint for the Raspberry Pi.
    It takes a ballot, validates it, and if valid,
    instantly writes it to the VoteLedger chain.

    Permissions:
    - Must be a Pi Terminal (valid API Key).
    """
    permission_classes = [IsPiTerminal]
    serializer_class = CastBallotSerializer

    def post(self, request, *args, **kwargs):
        # 1. Validate the incoming data
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 2. Get the validated data
        validated_data = serializer.validated_data
        election = validated_data.get('election_object')
        voter = validated_data.get('voter_object')
        ballot_data = validated_data.get('votes')

        try:
            # 3. Use a database transaction
            with transaction.atomic():
                # 4. Create the VoteLedger entry.
                VoteLedger.objects.create(
                    election=election,
                    ballot_data=ballot_data
                )

                # 5. Mark the voter as "voted"
                voter.has_voted = True
                voter.save()

            # --- 6. BROADCAST THE UPDATE ---
            try:
                print(f"[Broadcast] Vote cast for {election.election_id}, sending update...")
                # Get the "group name" for this election
                group_name = f'dashboard_{election.election_id}'
                # Get the channel layer
                channel_layer = get_channel_layer()

                # Get the new, complete dashboard payload
                new_dashboard_data = _get_tally_data(election)

                # Broadcast the full payload to the group
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "dashboard.update",  # MUST match function in consumers.py
                        "payload": new_dashboard_data  # Send the full data
                    }
                )
                print("[Broadcast] Update sent successfully.")
            except Exception as e:
                # Log this error, but don't fail the vote
                print(f"[Broadcast Error] Could not send update: {e}")
            # -------------------------------------

            # 7. Success!
            return Response(
                {"status": "success", "message": "Vote cast and confirmed."},
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            # Catch any unexpected database errors
            return Response(
                {"status": "error", "message": f"An internal error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ---
# API Endpoint 2: Check Voter Status (Pi "Fail-Fast")
# ---
class CheckVoterStatusView(views.APIView):
    """
    This is a "pre-check" endpoint for the Pi Terminal.
    It checks if a voter is valid *before* they are
    shown a ballot.

    Permissions:
    - Must be a Pi Terminal (valid API Key).
    """
    permission_classes = [IsPiTerminal]
    serializer_class = VoterStatusSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            # If invalid (not registered, already voted), send error
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # If we get here, the voter is valid and clear to vote
        return Response(
            {"status": "success", "message": "Voter is valid and clear to vote."},
            status=status.HTTP_200_OK
        )


# ---
# API Endpoint 3: Check Pre-Approved ID (Pi "Fail-Fast")
# ---
class CheckIDView(views.APIView):
    """
    This is a "pre-check" endpoint for the Pi Terminal
    during registration.

    Permissions:
    - Must be a Pi Terminal (valid API Key).
    """
    permission_classes = [IsPiTerminal]
    serializer_class = CheckIDSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            # If invalid (ID not found, already linked), send error
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # If we get here, the ID is valid and clear to link
        return Response(
            {"status": "success", "message": "Unique ID is valid and ready to link hardware."},
            status=status.HTTP_200_OK
        )


# ---
# API Endpoint 4: Link Hardware (Pi Self-Registration)
# ---
class LinkHardwareView(views.APIView):
    """
    This is the "self-registration" endpoint for the Pi Terminal.
    It links hardware to a pre-approved ID.

    Permissions:
    - Must be a Pi Terminal (valid API Key).
    """
    permission_classes = [IsPiTerminal]
    serializer_class = LinkHardwareSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # --- THIS IS THE FIX ---
        # We were missing this line!
        # This calls the new .save() method we just wrote.
        serializer.save()
        # -------------------------

        # If we get here, all is good.
        return Response(
            {"status": "success", "message": "Hardware successfully linked to Unique ID."},
            status=status.HTTP_201_CREATED
        )
# ---
# API Endpoint 5: Public Tally (For the Dashboard)
# ---
class PublicTallyView(views.APIView):
    """
    A public, read-only endpoint for the real-time dashboard.
    Returns both the final tally and the anonymous ledger.

    Permissions:
    - AllowAny: Anyone can view this.
    """
    permission_classes = [AllowAny]

    def get(self, request, election_id, *args, **kwargs):
        # 1. Get the election
        try:
            election = Election.objects.get(election_id=election_id)
        except Election.DoesNotExist:
            raise Http404("Election not found.")

        # 2. Get the complete dashboard data
        payload = _get_tally_data(election)

        # 3. Send the payload
        return Response(payload, status=status.HTTP_200_OK)


# ---
# API Endpoint 6: Public Election Detail (For Pi)
# ---
class PublicElectionDetailView(views.APIView):
    """
    A public, read-only endpoint for the Pi to fetch
    the ballot structure (positions and candidates).

    Permissions:
    - AllowAny: Anyone can view this.
    """
    permission_classes = [AllowAny]

    def get(self, request, election_id, *args, **kwargs):

        # --- DEBUGGING PRINT STATEMENT ---
        print(f"\n[SERVER] API trying to find election with ID: '{election_id}'")

        try:
            # 1. Get the election
            election = Election.objects.get(election_id=election_id)

            # 2. Check if it's active
            if not election.is_active:
                print(f"[SERVER] Found election '{election_id}', but it is NOT active.")
                raise Http404("This election is not active.")

            # 3. Serialize and return the data
            print(f"[SERVER] Success! Found active election: {election.name}")
            serializer = PublicElectionDetailSerializer(election)
            return Response(serializer.data)

        except Election.DoesNotExist:
            print(f"[SERVER] FAILED. No election found with ID: '{election_id}'")
            raise Http404("Election not found.")


# ---
# API Endpoints 7 & 8: Admin (For the Admin Dashboard)
# ---
class CreateElectionView(generics.ListCreateAPIView):
    """
    Admin-only endpoint to create a new election or list existing ones.
    """
    permission_classes = [IsAdminUser]
    queryset = Election.objects.all()
    serializer_class = ElectionSerializer


class UploadPreApprovedVotersView(generics.CreateAPIView):
    """
    Admin-only endpoint to "bulk" upload a list of
    pre-approved voter IDs for a specific election.
    """
    permission_classes = [IsAdminUser]
    serializer_class = UploadPreApprovedVotersSerializer

    # We override the 'create' method to handle the custom payload
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Call the 'create' method we defined in the serializer
        count = serializer.save()

        headers = self.get_success_headers(serializer.data)
        return Response(
            {"status": "success", "message": f"Successfully created {count} new pre-approved voters."},
            status=status.HTTP_201_CREATED,
            headers=headers
        )