import requests
import subprocess
import time
import socket
import os
import shutil

class BitwardenAPI:
    BASE_URL = "http://localhost:8087"

    def __init__(self):
        self.server_process = None
        self._ensure_server_running()

    def _is_port_open(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((host, port)) == 0

    def _ensure_server_running(self):
        if self._is_port_open("localhost", 8087):
            return

        bw_path = shutil.which("bw")
        if not bw_path:
            print("Error: 'bw' executable not found.")
            return

        print("Starting Bitwarden server (bw serve)...")
        # Start bw serve in background
        self.server_process = subprocess.Popen(
            [bw_path, "serve", "--nointeraction"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        # Wait for it to start
        for _ in range(10):
            if self._is_port_open("localhost", 8087):
                return
            time.sleep(0.5)
        print("Warning: Timed out waiting for bw serve to start.")

    def get_status(self):
        try:
            resp = requests.get(f"{self.BASE_URL}/status", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                # data['status'] can be 'unlocked', 'locked', 'unauthenticated'
                # data['data']['template'] might exist
                # The CLI serve response structure usually wraps the result in 'data' or returns it directly
                # Let's handle both standard CLI output forms
                if 'data' in data:
                    return data['data'].get('template', {}).get('status') or data.get('status')
                return data.get('status', 'unknown')
        except requests.RequestException:
            return "unavailable"
        return "unknown"

    def unlock(self, password):
        try:
            resp = requests.post(f"{self.BASE_URL}/unlock", json={"password": password}, timeout=5)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('success'):
                    return True, "Unlocked"
                return False, result.get('message', "Failed to unlock")
            return False, f"Error: {resp.status_code} {resp.text}"
        except Exception as e:
            return False, str(e)

    def lock(self):
        try:
            requests.post(f"{self.BASE_URL}/lock", timeout=2)
        except:
            pass

    def sync(self):
        try:
            requests.post(f"{self.BASE_URL}/sync", timeout=10)
            return True
        except:
            return False

    def search_items(self, query):
        try:
            # bw serve allows ?search=...
            # Endpoint: /list/object/items
            params = {}
            if query:
                params['search'] = query
            
            resp = requests.get(f"{self.BASE_URL}/list/object/items", params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                # 'bw serve' output is usually { success: true, data: [...] }
                if data.get('success') and 'data' in data:
                    items = data['data'].get('data', [])
                    # Sometimes data['data'] is the list directly
                    if isinstance(data['data'], list):
                        items = data['data']
                    
                    # Map to simple dicts
                    results = []
                    for item in items:
                        # Extract useful fields
                        login = item.get('login', {})
                        name = item.get('name', 'Unknown')
                        username = login.get('username', '')
                        password = login.get('password', '')
                        uris = login.get('uris', [])
                        url = uris[0]['uri'] if uris else ''
                        
                        results.append({
                            'name': name,
                            'username': username,
                            'password': password,
                            'url': url,
                            'id': item.get('id')
                        })
                    return results
            return []
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def generate_password(self, length=16, special=True, numbers=True):
        """Generate a password using bw CLI."""
        try:
            cmd = ['bw', 'generate', '--length', str(length)]
            if not special:
                cmd.append('--nospecial')
            if numbers:
                cmd.append('--numbers')

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            print(f"Password generation error: {e}")
            return None

    def get_totp(self, item_id):
        """Get TOTP code for an item using bw CLI."""
        try:
            result = subprocess.run(
                ['bw', 'get', 'totp', item_id],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            print(f"TOTP error: {e}")
            return None

    def search_items_advanced(self, query, item_type=None):
        """Search items with support for all types (login, note, card, identity)."""
        try:
            params = {}
            if query:
                params['search'] = query

            resp = requests.get(f"{self.BASE_URL}/list/object/items", params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') and 'data' in data:
                    items = data['data'].get('data', [])
                    if isinstance(data['data'], list):
                        items = data['data']

                    results = []
                    for item in items:
                        item_result = self._parse_item_advanced(item)
                        if item_result:
                            # Filter by type if specified
                            if item_type is None or item_result['item_type'] == item_type:
                                results.append(item_result)
                    return results
            return []
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def _parse_item_advanced(self, item):
        """Parse any Bitwarden item type."""
        item_type = item.get('type')  # 1=login, 2=note, 3=card, 4=identity
        name = item.get('name', 'Unknown')
        item_id = item.get('id')

        result = {
            'name': name,
            'id': item_id,
            'item_type': item_type,
            'favorite': item.get('favorite', False)
        }

        if item_type == 1:  # Login
            login = item.get('login', {})
            result['username'] = login.get('username', '')
            result['password'] = login.get('password', '')
            uris = login.get('uris', [])
            result['url'] = uris[0]['uri'] if uris else ''
            result['has_totp'] = bool(login.get('totp'))
            result['type_name'] = 'login'

        elif item_type == 2:  # Secure Note
            notes = item.get('notes', '')
            result['notes'] = notes
            result['type_name'] = 'note'

        elif item_type == 3:  # Card
            card = item.get('card', {})
            result['cardholder'] = card.get('cardholderName', '')
            result['brand'] = card.get('brand', '')
            # Mask card number
            number = card.get('number', '')
            if len(number) > 4:
                result['number_masked'] = '••••••••••••' + number[-4:]
            else:
                result['number_masked'] = number
            result['number_full'] = number
            result['exp_month'] = card.get('expMonth', '')
            result['exp_year'] = card.get('expYear', '')
            result['code'] = card.get('code', '')
            result['type_name'] = 'card'

        elif item_type == 4:  # Identity
            identity = item.get('identity', {})
            result['first_name'] = identity.get('firstName', '')
            result['last_name'] = identity.get('lastName', '')
            result['email'] = identity.get('email', '')
            result['phone'] = identity.get('phone', '')
            result['address'] = f"{identity.get('address1', '')} {identity.get('address2', '')}".strip()
            result['type_name'] = 'identity'

        # Parse custom fields
        fields = item.get('fields', [])
        if fields:
            result['custom_fields'] = [
                {'name': f.get('name'), 'value': f.get('value'), 'type': f.get('type')}
                for f in fields
            ]

        return result

    def close(self):
        if self.server_process:
            self.server_process.terminate()
