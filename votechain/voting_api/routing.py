from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # This regex matches WebSocket URLs like:
    # ws://your-site.com/ws/dashboard/sigma/
    re_path(
        r'ws/dashboard/(?P<election_id>[\w-]+)/$',
        consumers.DashboardConsumer.as_asgi()
    ),
]