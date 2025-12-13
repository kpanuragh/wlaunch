"""
Bitwarden API implementation without CLI tool.
Uses Bitwarden REST API with personal access token.

To get your API token:
1. Go to https://vault.bitwarden.com/#/settings/security/security-keys
2. Create a new API key (personal API key)
3. Save client_id and client_secret
4. Add to ~/.config/wlaunch/config.json:
   {
     "bitwarden_client_id": "user.xxxxx",
     "bitwarden_client_secret": "xxxxx"
   }
"""

import requests
import time
import os
import json
from core.config import load_config, save_config

class BitwardenAPIClient:
    """Bitwarden API client without CLI dependency."""

    IDENTITY_URL = "https://identity.bitwarden.com"
    API_URL = "https://api.bitwarden.com"

    def __init__(self):
        self.access_token = None
        self.token_expires = 0
        self.config = load_config()

    def _get_credentials(self):
        """Get API credentials from config."""
        client_id = self.config.get("bitwarden_client_id")
        client_secret = self.config.get("bitwarden_client_secret")
        return client_id, client_secret

    def _ensure_authenticated(self):
        """Ensure we have a valid access token."""
        # Check if token is still valid
        if self.access_token and time.time() < self.token_expires:
            return True

        # Get new token
        client_id, client_secret = self._get_credentials()

        if not client_id or not client_secret:
            return False

        try:
            # Request access token
            response = requests.post(
                f"{self.IDENTITY_URL}/connect/token",
                data={
                    "grant_type": "client_credentials",
                    "scope": "api",
                    "client_id": client_id,
                    "client_secret": client_secret
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                # Token typically expires in 3600 seconds
                self.token_expires = time.time() + data.get("expires_in", 3600) - 60
                return True
            else:
                print(f"Auth error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"Authentication error: {e}")
            return False

    def get_status(self):
        """Check if credentials are configured and valid."""
        client_id, client_secret = self._get_credentials()

        if not client_id or not client_secret:
            return "unconfigured"

        if self._ensure_authenticated():
            return "unlocked"
        else:
            return "authentication_failed"

    def search_items(self, query=""):
        """Search vault items."""
        if not self._ensure_authenticated():
            return []

        try:
            response = requests.get(
                f"{self.API_URL}/list/object/items",
                headers={
                    "Authorization": f"Bearer {self.access_token}"
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("data", [])

                # Filter by query if provided
                if query:
                    query_lower = query.lower()
                    items = [
                        item for item in items
                        if query_lower in item.get("name", "").lower()
                    ]

                # Map to simple format
                results = []
                for item in items:
                    result = self._parse_item(item)
                    if result:
                        results.append(result)

                return results
            else:
                print(f"Search error: {response.status_code}")
                return []

        except Exception as e:
            print(f"Search exception: {e}")
            return []

    def _parse_item(self, item):
        """Parse Bitwarden item."""
        item_type = item.get("type")
        name = item.get("name", "Unknown")
        item_id = item.get("id")

        result = {
            "name": name,
            "id": item_id,
            "item_type": item_type,
            "favorite": item.get("favorite", False)
        }

        if item_type == 1:  # Login
            login = item.get("login", {})
            result["username"] = login.get("username", "")
            result["password"] = login.get("password", "")
            uris = login.get("uris", [])
            result["url"] = uris[0].get("uri", "") if uris else ""
            result["has_totp"] = bool(login.get("totp"))
            result["totp_seed"] = login.get("totp", "")
            result["type_name"] = "login"

        elif item_type == 2:  # Secure Note
            result["notes"] = item.get("notes", "")
            result["type_name"] = "note"

        elif item_type == 3:  # Card
            card = item.get("card", {})
            result["cardholder"] = card.get("cardholderName", "")
            result["brand"] = card.get("brand", "")
            number = card.get("number", "")
            if len(number) > 4:
                result["number_masked"] = "••••••••••••" + number[-4:]
            else:
                result["number_masked"] = number
            result["number_full"] = number
            result["exp_month"] = card.get("expMonth", "")
            result["exp_year"] = card.get("expYear", "")
            result["code"] = card.get("code", "")
            result["type_name"] = "card"

        elif item_type == 4:  # Identity
            identity = item.get("identity", {})
            result["first_name"] = identity.get("firstName", "")
            result["last_name"] = identity.get("lastName", "")
            result["email"] = identity.get("email", "")
            result["phone"] = identity.get("phone", "")
            result["address"] = f"{identity.get('address1', '')} {identity.get('address2', '')}".strip()
            result["type_name"] = "identity"

        # Custom fields
        fields = item.get("fields", [])
        if fields:
            result["custom_fields"] = [
                {"name": f.get("name"), "value": f.get("value"), "type": f.get("type")}
                for f in fields
            ]

        return result

    def search_items_advanced(self, query="", item_type=None):
        """Search items with type filtering."""
        items = self.search_items(query)

        if item_type is not None:
            items = [item for item in items if item.get("item_type") == item_type]

        return items

    def generate_password(self, length=16):
        """Generate a random password locally."""
        import random
        import string

        # Character sets
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special = "!@#$%^&*()_+-=[]{}|;:,.<>?"

        # Ensure at least one of each type
        password = [
            random.choice(lowercase),
            random.choice(uppercase),
            random.choice(digits),
            random.choice(special)
        ]

        # Fill remaining length
        all_chars = lowercase + uppercase + digits + special
        password.extend(random.choice(all_chars) for _ in range(length - 4))

        # Shuffle
        random.shuffle(password)

        return ''.join(password)

    def get_totp(self, totp_seed):
        """Generate TOTP code from seed (if available)."""
        if not totp_seed:
            return None

        try:
            import pyotp
            totp = pyotp.TOTP(totp_seed)
            return totp.now()
        except ImportError:
            # pyotp not available, try basic implementation
            return self._generate_totp_basic(totp_seed)
        except Exception as e:
            print(f"TOTP error: {e}")
            return None

    def _generate_totp_basic(self, secret):
        """Basic TOTP implementation without pyotp."""
        try:
            import hmac
            import hashlib
            import struct
            import base64

            # Decode secret
            secret = secret.replace(" ", "").upper()
            secret_bytes = base64.b32decode(secret)

            # Current time counter (30 second intervals)
            counter = int(time.time() // 30)

            # HMAC-SHA1
            hmac_hash = hmac.new(
                secret_bytes,
                struct.pack(">Q", counter),
                hashlib.sha1
            ).digest()

            # Dynamic truncation
            offset = hmac_hash[-1] & 0x0F
            code = struct.unpack(">I", hmac_hash[offset:offset+4])[0]
            code = (code & 0x7FFFFFFF) % 1000000

            return str(code).zfill(6)
        except Exception as e:
            print(f"Basic TOTP error: {e}")
            return None

    def unlock(self, password=None):
        """
        API key mode doesn't require unlock.
        This is for compatibility with the UI.
        """
        return self._ensure_authenticated(), "Using API key mode"

    def close(self):
        """Cleanup (nothing needed for API mode)."""
        pass
