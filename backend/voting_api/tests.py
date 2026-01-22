import json
from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from .models import Election, Position, Candidate, RegisteredVoter, VoteLedger, PreApprovedVoter
from .serializers import hash_voter_data


class VoteChainSecurityTests(TestCase):
    def setUp(self):
        # 1. Setup Client with API Key
        self.client = Client()
        # We only put the API Key here. We handle Content-Type in the post() calls.
        self.headers = {
            'HTTP_X_API_KEY': settings.PI_TERMINAL_API_KEY,
        }

        # 2. Create Election (Active & Open)
        self.election = Election.objects.create(
            name="Test Election",
            start_date=timezone.now() - timedelta(hours=1),  # Started 1 hour ago
            end_date=timezone.now() + timedelta(hours=1),  # Ends in 1 hour
            is_active=True
        )

        # 3. Create Positions & Candidates
        self.pos_president = Position.objects.create(
            election=self.election, title="President", max_choices=1, rank=1
        )
        self.cand_alice = Candidate.objects.create(position=self.pos_president, name="Alice")
        self.cand_bob = Candidate.objects.create(position=self.pos_president, name="Bob")

        self.pos_senator = Position.objects.create(
            election=self.election, title="Senator", max_choices=2, rank=2
        )
        self.cand_s1 = Candidate.objects.create(position=self.pos_senator, name="Sen1")
        self.cand_s2 = Candidate.objects.create(position=self.pos_senator, name="Sen2")
        self.cand_s3 = Candidate.objects.create(position=self.pos_senator, name="Sen3")

        # 4. Register a Voter (Linked Hardware)
        self.rfid = "card_123"
        self.fingerprint = "print_abc"
        self.voter_hash = hash_voter_data(self.rfid, self.fingerprint)

        self.voter = RegisteredVoter.objects.create(
            election=self.election,
            voter_hash=self.voter_hash,
            has_voted=False
        )

    # --- TEST 1: The "Happy Path" ---
    def test_valid_vote_cast(self):
        """Should successfully cast a vote and return a transaction ID."""
        payload = {
            "election_id": self.election.election_id,
            "rfid": self.rfid,
            "fingerprint": self.fingerprint,
            "votes": {
                "President": "Alice",
                "Senator": ["Sen1", "Sen2"]
            }
        }
        # FIX: json.dumps(payload) and explicit content_type
        response = self.client.post(
            '/vote/cast',
            data=json.dumps(payload),
            content_type='application/json',
            **self.headers
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("transaction_id", response.json())

        # Check Ledger
        self.assertEqual(VoteLedger.objects.count(), 1)
        self.assertTrue(RegisteredVoter.objects.get(id=self.voter.id).has_voted)

    # --- TEST 2: Security - Invalid API Key ---
    def test_missing_api_key(self):
        """Should reject request without the Pi's Secret Key."""
        payload = {"election_id": "test"}
        # Send without headers (no API key)
        response = self.client.post(
            '/vote/cast',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)  # Forbidden

    # --- TEST 3: Validation - Overvoting (Pick 2, Tried 3) ---
    def test_overvoting_limit(self):
        """Should reject ballot if user picks too many candidates."""
        payload = {
            "election_id": self.election.election_id,
            "rfid": self.rfid,
            "fingerprint": self.fingerprint,
            "votes": {
                "Senator": ["Sen1", "Sen2", "Sen3"]  # Max is 2!
            }
        }
        response = self.client.post(
            '/vote/cast',
            data=json.dumps(payload),
            content_type='application/json',
            **self.headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Too many selections", str(response.content))

    # --- TEST 4: Validation - Fake Candidate ---
    def test_invalid_candidate(self):
        """Should reject ballot if user votes for 'Mickey Mouse'."""
        payload = {
            "election_id": self.election.election_id,
            "rfid": self.rfid,
            "fingerprint": self.fingerprint,
            "votes": {
                "President": "Mickey Mouse"  # Doesn't exist
            }
        }
        response = self.client.post(
            '/vote/cast',
            data=json.dumps(payload),
            content_type='application/json',
            **self.headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("not a valid candidate", str(response.content))

    def test_double_voting_prevention(self):
        """Should reject a second attempt to vote."""
        # Vote 1 (Success)
        self.voter.has_voted = True
        self.voter.save()

        # Vote 2 (Attempt)
        payload = {
            "election_id": self.election.election_id,
            "rfid": self.rfid,
            "fingerprint": self.fingerprint,
            "votes": {"President": "Alice"}
        }
        response = self.client.post(
            '/vote/cast',
            data=json.dumps(payload),
            content_type='application/json',
            **self.headers
        )

        # CHANGED: We now accept 400 because the Serializer catches it first
        self.assertEqual(response.status_code, 400)
        self.assertIn("Duplicate vote", str(response.content))

    # --- TEST 6: Workflow - Linking Hardware ---
    def test_link_hardware_flow(self):
        """Should successfully link a new RFID to a Student ID."""
        # Create a Pre-Approved ID
        PreApprovedVoter.objects.create(election=self.election, unique_identifier="STUDENT_999")

        payload = {
            "election_id": self.election.election_id,
            "unique_identifier": "STUDENT_999",
            "rfid": "new_card",
            "fingerprint": "new_thumb"
        }
        response = self.client.post(
            '/register/link-hardware',
            data=json.dumps(payload),
            content_type='application/json',
            **self.headers
        )
        self.assertEqual(response.status_code, 201)

        # Verify it created a RegisteredVoter
        new_hash = hash_voter_data("new_card", "new_thumb")
        self.assertTrue(RegisteredVoter.objects.filter(voter_hash=new_hash).exists())

        # Verify ID is now linked
        self.assertTrue(PreApprovedVoter.objects.get(unique_identifier="STUDENT_999").is_linked)

    # --- TEST 7: Blockchain - Chain Integrity ---
    def test_blockchain_hashing(self):
        """Should verify that votes are linked by hash."""
        # Cast Vote 1
        VoteLedger.objects.create(
            election=self.election,
            ballot_data={"President": "Alice"}
        )

        # Cast Vote 2
        vote2 = VoteLedger.objects.create(
            election=self.election,
            ballot_data={"President": "Bob"}
        )

        # Fetch votes
        all_votes = VoteLedger.objects.filter(election=self.election).order_by('timestamp')
        v1 = all_votes[0]
        v2 = all_votes[1]

        # Verify Genesis Block
        self.assertEqual(v1.previous_hash, "0" * 64)

        # Verify Link (Chain)
        self.assertEqual(v2.previous_hash, v1.current_hash)

        # Verify Data Integrity
        self.assertEqual(v2.current_hash, v2.calculate_hash())

    # --- TEST 8: Automation - Closed Election ---
    def test_voting_closed_election(self):
        """Should reject votes if election is expired."""
        self.election.end_date = timezone.now() - timedelta(minutes=1)  # Ended 1 min ago
        self.election.save()

        payload = {
            "election_id": self.election.election_id,
            "rfid": self.rfid,
            "fingerprint": self.fingerprint,
            "votes": {"President": "Alice"}
        }
        response = self.client.post(
            '/vote/cast',
            data=json.dumps(payload),
            content_type='application/json',
            **self.headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("closed", str(response.content))