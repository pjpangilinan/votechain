import os
from django.core.asgi import get_asgi_application

# --- ADDED ---
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import voting_api.routing
# -------------

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# --- This part is CHANGED ---
application = ProtocolTypeRouter({
    
    # 1. Handle standard HTTP requests (your API)
    "http": get_asgi_application(),
    
    # 2. Handle WebSocket requests
    "websocket": AuthMiddlewareStack(
        URLRouter(
            voting_api.routing.websocket_urlpatterns
        )
    ),
})