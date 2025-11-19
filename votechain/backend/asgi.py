import os
import django

# 1. Set the default settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# 2. Initialize Django FIRST
django.setup()

# 3. Now it is safe to import other parts of the app
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import voting_api.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            voting_api.routing.websocket_urlpatterns
        )
    ),
})
