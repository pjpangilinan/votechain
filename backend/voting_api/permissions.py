from rest_framework.permissions import BasePermission
from django.conf import settings

class IsPiTerminal(BasePermission):
    """
    Allows access only to requests that contain the valid
    Pi Terminal API Key in their headers.
    """

    def has_permission(self, request, view):
        # We check for a custom header: 'X-API-Key'
        key = request.headers.get('x-api-key')

        if not key:
            return False

        # If PI_TERMINAL_API_KEY is not set in settings, block everything for safety
        if not hasattr(settings, 'PI_TERMINAL_API_KEY'):
            print("WARNING: PI_TERMINAL_API_KEY missing in settings.py")
            return False

        # Simple string comparison (for now)
        return key == settings.PI_TERMINAL_API_KEY