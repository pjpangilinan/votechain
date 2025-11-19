import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .views import _get_tally_data  # We import the helper from views
from .models import Election


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    This is the "Best of Both Worlds" consumer:
    1. It's Asynchronous (scales to many users)
    2. It sends the full data on first connect.
    3. It pushes the full, updated data (not just a signal)
       when an update is broadcast.
    """

    # --- Helper function ---
    # We need this to safely call Django's database (which is sync)
    # from within this async consumer.
    @sync_to_async
    def get_initial_data(self):
        """
        Fetches the current election data from the database.
        """
        try:
            # Get the election object
            election = Election.objects.get(election_id=self.election_id)
            # Re-use the helper function from our views.py
            return _get_tally_data(election)
        except Election.DoesNotExist:
            print(f"[WebSocket Error] Consumer could not find election: {self.election_id}")
            return None

    # --- Main Functions ---
    async def connect(self):
        # 1. Get the 'election_id' from the URL
        self.election_id = self.scope['url_route']['kwargs']['election_id']

        # 2. Define a unique "group" name for this election's dashboard
        self.group_name = f'dashboard_{self.election_id}'

        # 3. "Subscribe" this user to the group.
        #    They will now receive all messages broadcast to this group.
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # 4. Accept the WebSocket connection
        await self.accept()

        # 5. --- Send initial data on connect ---
        #    (This was your good idea)
        print(f"[WebSocket] Client connecting to {self.group_name}...")
        initial_data = await self.get_initial_data()

        if initial_data:
            # Send the full, current data
            await self.send(text_data=json.dumps(initial_data))
            print(f"[WebSocket] Sent initial data to {self.group_name}.")
        else:
            # If election doesn't exist, close the connection
            print(f"[WebSocket] Error: Could not get initial data for {self.group_name}.")
            await self.close()

    async def disconnect(self, close_code):
        # Unsubscribe this user from the group when they close the page
        print(f"[WebSocket] Client disconnecting from {self.group_name}.")
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # --- This is the "Push" handler ---
    # This function is called by the 'group_send' in views.py
    # The name *must* match the "type" in group_send
    # (e.g., "dashboard.update" -> dashboard_update())
    async def dashboard_update(self, event):
        # 1. Get the new, full data payload from the event
        payload = event['payload']

        # 2. Send the full payload to the browser
        await self.send(text_data=json.dumps(payload))
        print(f"[WebSocket] Pushed update to {self.group_name}.")