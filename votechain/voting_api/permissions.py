from rest_framework.permissions import BasePermission
from django.conf import settings


# ---
# IMPORTANT: Add this line to your 'backend/settings.py' file.
# This is the secret key your Pi will use.
#
# PI_TERMINAL_API_KEY = "YOUR_VERY_LONG_AND_SECRET_API_KEY_GOES_HERE"
# ---

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

        # Use a secure 'compare_digest' to prevent timing attacks
        # (This is safer than a simple '==' string comparison)
        try:
            from hmac import compare_digest
            return compare_digest(key, settings.PI_TERMINAL_API_KEY)
        except ImportError:
            # Fallback for older systems (less secure)
            return key == settings.PI_TERMINAL_API_KEY