from rest_framework import generics, views, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.http import Http404
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Election, RegisteredVoter, VoteLedger, Position, Candidate
from .serializers import (
    CastBallotSerializer, PublicTallySerializer, PublicLedgerSerializer,
    LinkHardwareSerializer, PublicElectionDetailSerializer, LedgerSerializer,
    ElectionListSerializer, VoterStatusSerializer, CheckIDSerializer
)
from .permissions import IsPiTerminal


@api_view(['GET'])
@permission_classes([AllowAny])
def election_dashboard_data(request, election_id):
    """
    Returns ALL data needed for the Cyberpunk Dashboard in one optimized call.
    """
    election = get_object_or_404(Election, election_id=election_id)

    # 1. Calculate Global Stats
    total_votes = VoteLedger.objects.filter(election=election).count()
    total_voters = RegisteredVoter.objects.filter(election=election).count()

    turnout_percentage = 0.0
    if total_voters > 0:
        turnout_percentage = round((total_votes / total_voters) * 100, 1)

    # 2. Process Results (Positions & Candidates)
    # We fetch all positions and candidates for this election
    positions = Position.objects.filter(election=election).order_by('rank')

    # We fetch the entire ledger ONCE to avoid hitting the DB 100 times
    # (For massive scale, we would use a cached Counter, but this is perfect for Thesis)
    all_ballots = VoteLedger.objects.filter(election=election).values_list('ballot_data', flat=True)

    positions_data = []

    for pos in positions:
        candidates = Candidate.objects.filter(position=pos)
        cand_list = []

        for cand in candidates:
            # Count how many ballots selected this candidate for this position
            # Ballot format: {"President": "Alice", ...}
            vote_count = 0
            for ballot in all_ballots:
                selection = ballot.get(pos.title)
                if selection:
                    if isinstance(selection, list):
                        if cand.name in selection: vote_count += 1
                    elif selection == cand.name:
                        vote_count += 1

            # Calculate % for this specific candidate
            vote_share = 0.0
            if total_votes > 0:
                vote_share = round((vote_count / total_votes) * 100, 1)

            cand_list.append({
                "id": cand.id,
                "name": cand.name,
                "party": cand.party,
                "photo": cand.photo.url if cand.photo else None,
                "votes": vote_count,
                "percentage": vote_share
            })

        # Sort: Winner first
        cand_list.sort(key=lambda x: x['votes'], reverse=True)

        positions_data.append({
            "id": pos.id,
            "title": pos.title,
            "candidates": cand_list
        })

    # 3. Get Recent Ledger Blocks (Limit to last 20 for performance)
    recent_blocks = VoteLedger.objects.filter(election=election).order_by('-timestamp')[:20]
    ledger_data = LedgerSerializer(recent_blocks, many=True).data

    return Response({
        "metadata": {
            "name": election.name,
            "description": election.description,
            "end_date": election.end_date,
            "is_active": election.is_active,
        },
        "stats": {
            "total_votes": total_votes,
            "turnout": turnout_percentage,
            "blocks_mined": total_votes,
        },
        "positions": positions_data,
        "ledger": ledger_data
    })

# --- Helper Function for Broadcasting ---
def _get_tally_data(election):
    """
    Calculates tally by iterating through Position/Candidate models.
    """
    # 1. Build the Skeleton (Zero votes for everyone)
    tally_map = {}  # Key: "Position|Candidate", Value: Count

    positions = Position.objects.filter(election=election).prefetch_related('candidates')

    # Structure for the frontend
    results = []

    # Initialize counts to 0
    for pos in positions:
        for cand in pos.candidates.all():
            key = f"{pos.title}|{cand.name}"
            tally_map[key] = 0

    # 2. Count the Votes (The Ledger is the source of truth)
    votes = VoteLedger.objects.filter(election=election).values_list('ballot_data', flat=True)

    for ballot in votes:
        # ballot is {"President": "Alice", "Senator": ["Bob", "Charlie"]}
        for position_title, selection in ballot.items():

            # Normalize to list
            if not isinstance(selection, list):
                selection = [selection]

            for candidate_name in selection:
                key = f"{position_title}|{candidate_name}"

                # Only count if it matches a valid candidate in our skeleton
                if key in tally_map:
                    tally_map[key] += 1

    # 3. Format Output
    for key, count in tally_map.items():
        pos_title, cand_name = key.split('|')
        results.append({
            "position": pos_title,
            "candidate": cand_name,
            "votes": count
        })

    tally_serializer = PublicTallySerializer(results, many=True)
    ledger_serializer = PublicLedgerSerializer(
        VoteLedger.objects.filter(election=election).order_by('timestamp'),
        many=True
    )

    return {
        'election_name': election.name,
        'tally': tally_serializer.data,
        'ledger': ledger_serializer.data
    }


# --- API Endpoints ---

class ElectionListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    queryset = Election.objects.all().order_by('-id')
    serializer_class = ElectionListSerializer


class CastVoteView(views.APIView):
    """
    Handles secure vote casting with Race Condition protection.
    """
    permission_classes = [IsPiTerminal]
    serializer_class = CastBallotSerializer

    def post(self, request, *args, **kwargs):
        # 1. Basic Validation (Checks data format, existing vote status strictly via read)
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        election = data['election_object']

        try:
            # 2. THE LOCK (Critical Security Fix)
            with transaction.atomic():
                # We re-fetch the voter using 'select_for_update'.
                # This locks the row in the DB. No other request can touch this voter
                # until this block finishes.
                voter_id = data['voter_object'].id
                locked_voter = RegisteredVoter.objects.select_for_update().get(id=voter_id)

                # Double-check status INSIDE the lock
                if locked_voter.has_voted:
                    return Response(
                        {"error": "Security Alert: Duplicate vote attempt detected and blocked."},
                        status=status.HTTP_409_CONFLICT
                    )

                # 3. Create Ledger Entry
                vote_entry = VoteLedger.objects.create(
                    election=election,
                    ballot_data=data['clean_ballot']
                )

                # 4. Mark Voted
                locked_voter.has_voted = True
                locked_voter.save()

            # 5. Broadcast (Outside the lock for speed)
            try:
                group_name = f'dashboard_{election.election_id}'
                channel_layer = get_channel_layer()
                new_data = _get_tally_data(election)

                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {"type": "dashboard.update", "payload": new_data}
                )
            except Exception as e:
                print(f"Broadcast Error: {e}")

            # 6. Success Receipt
            return Response({
                "status": "success",
                "message": "Vote cast and confirmed.",
                "transaction_id": vote_entry.current_hash
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VerifyChainView(views.APIView):
    """
    Iterates through the entire blockchain to verify integrity.
    """
    permission_classes = [AllowAny]

    def get(self, request, election_id):
        try:
            election = Election.objects.get(election_id=election_id)
        except Election.DoesNotExist:
            raise Http404("Election not found")

        ledger = VoteLedger.objects.filter(election=election).order_by('timestamp')

        previous_hash = "0" * 64
        errors = []

        for block in ledger:
            # 1. Check Link
            if block.previous_hash != previous_hash:
                errors.append(f"Broken Link at Block ID {block.id}")

            # 2. Check Data Integrity
            if block.current_hash != block.calculate_hash():
                errors.append(f"Data Tampered at Block ID {block.id}")

            previous_hash = block.current_hash

        if errors:
            return Response({"status": "CORRUPTED", "errors": errors}, status=400)
        else:
            return Response({
                "status": "CLEAN",
                "message": f"Verified {len(ledger)} blocks. Chain is healthy."
            }, status=200)


class PublicElectionDetailView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request, election_id, *args, **kwargs):
        try:
            election = Election.objects.get(election_id=election_id)
            if not election.is_open:
                return Response(
                    {"detail": "Election is not currently open for voting."},
                    status=status.HTTP_403_FORBIDDEN
                )
            serializer = PublicElectionDetailSerializer(election)
            return Response(serializer.data)
        except Election.DoesNotExist:
            raise Http404("Election not found.")


class PublicTallyView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request, election_id, *args, **kwargs):
        try:
            election = Election.objects.get(election_id=election_id)
            return Response(_get_tally_data(election))
        except Election.DoesNotExist:
            raise Http404("Election not found.")


class LinkHardwareView(views.APIView):
    permission_classes = [IsPiTerminal]
    serializer_class = LinkHardwareSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response({"status": "success", "message": "Hardware linked."}, status=status.HTTP_201_CREATED)


class CheckVoterStatusView(views.APIView):
    permission_classes = [IsPiTerminal]
    serializer_class = VoterStatusSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            return Response({"status": "success", "message": "Valid."}, status=200)
        return Response(serializer.errors, status=400)


class CheckIDView(views.APIView):
    permission_classes = [IsPiTerminal]
    serializer_class = CheckIDSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            return Response({"status": "success", "message": "Valid."}, status=200)
        return Response(serializer.errors, status=400)

class SearchVoteView(views.APIView):
    """
    Public endpoint to verify a vote by its Transaction Hash (Receipt).
    """
    permission_classes = [AllowAny]

    def get(self, request, tx_hash):
        try:
            # We look up the block using the 'current_hash' field
            vote = VoteLedger.objects.get(current_hash=tx_hash)
            serializer = PublicLedgerSerializer(vote)
            return Response({
                "status": "found",
                "block_data": serializer.data
            })
        except VoteLedger.DoesNotExist:
            return Response({
                "status": "not_found",
                "detail": f"No vote found with hash: {tx_hash}"
            }, status=404)