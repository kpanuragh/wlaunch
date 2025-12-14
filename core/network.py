import subprocess
import shutil
import time

class NetworkBackend:
    def scan(self):
        """Returns list of dicts: {'ssid': str, 'signal': int, 'security': str, 'in_use': bool}"""
        raise NotImplementedError
    
    def connect(self, ssid, password=None):
        """Connects to a network. Returns (success, message)."""
        raise NotImplementedError

    def disconnect(self):
        """Disconnects current wifi. Returns (success, message)."""
        raise NotImplementedError

    def toggle_wifi(self, enable):
        """Enable or disable wifi. Returns (success, message)."""
        raise NotImplementedError

    def get_connection_details(self, interface=None):
        """Returns dict with 'ip', 'gateway', 'interface'."""
        raise NotImplementedError

class NMCLIBackend(NetworkBackend):
    def scan(self):
        try:
            # -t: terse (colon separated)
            # -f: fields
            cmd = ['nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY,BARS', 'device', 'wifi', 'list']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            networks = []
            seen_ssids = set()
            
            for line in result.stdout.strip().split('\n'):
                if not line: continue
                # nmcli escapes colons in values with backslash, but usually SSID doesn't have colons. 
                # For simplicity in this CLI tool context, simple split is often enough, 
                # but let's be slightly careful.
                parts = line.split(':')
                if len(parts) < 4: continue
                
                in_use = parts[0] == '*'
                ssid = parts[1]
                
                # Skip duplicates or empty SSIDs
                if not ssid or ssid in seen_ssids:
                    continue
                seen_ssids.add(ssid)
                
                signal = parts[2]
                security = parts[3]
                bars = parts[4] if len(parts) > 4 else ""
                
                networks.append({
                    'ssid': ssid,
                    'signal': signal, # 0-100
                    'security': security,
                    'bars': bars,
                    'in_use': in_use,
                    'backend': 'nmcli'
                })
            return networks
        except Exception as e:
            print(f"NMCLI scan error: {e}")
            return []

    def connect(self, ssid, password=None):
        try:
            cmd = ['nmcli', 'device', 'wifi', 'connect', ssid]
            if password:
                cmd.extend(['password', password])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if result.returncode == 0:
                return True, "Connected successfully"
            else:
                return False, result.stderr.strip() or result.stdout.strip()
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        # nmcli device disconnect wlan0 (or find interface)
        # Easier: nmcli radio wifi off (but that kills wifi). 
        # nmcli device disconnect is better. Need interface name.
        # Find interface: nmcli device | grep wifi
        try:
            # Find wifi interface
            cmd_dev = ['nmcli', '-t', '-f', 'DEVICE,TYPE', 'device']
            res_dev = subprocess.run(cmd_dev, capture_output=True, text=True)
            interface = None
            for line in res_dev.stdout.split('\n'):
                if ':wifi' in line:
                    interface = line.split(':')[0]
                    break
            
            if not interface:
                return False, "No wifi interface found"

            cmd = ['nmcli', 'device', 'disconnect', interface]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0, result.stderr or "Disconnected"
        except Exception as e:
            return False, str(e)

    def toggle_wifi(self, enable):
        state = 'on' if enable else 'off'
        try:
            subprocess.run(['nmcli', 'radio', 'wifi', state], check=True)
            return True, f"Wifi turned {state}"
        except Exception as e:
            return False, str(e)

    def get_connection_details(self, interface=None):
        details = {'ip': 'N/A', 'gateway': 'N/A', 'interface': interface or 'N/A'}
        try:
            # 1. Get Interface if not provided
            if not interface:
                cmd_dev = ['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'device']
                res_dev = subprocess.run(cmd_dev, capture_output=True, text=True)
                for line in res_dev.stdout.split('\n'):
                    if ':wifi:connected' in line:
                        interface = line.split(':')[0]
                        details['interface'] = interface
                        break
            
            if not interface:
                return details

            # 2. Get IP
            cmd_ip = ['ip', '-4', 'addr', 'show', interface]
            res_ip = subprocess.run(cmd_ip, capture_output=True, text=True)
            for line in res_ip.stdout.split('\n'):
                if 'inet ' in line:
                    details['ip'] = line.strip().split()[1] # e.g. 192.168.1.10/24
                    break
            
            # 3. Get Gateway
            cmd_gw = ['ip', 'route', 'show', 'dev', interface]
            res_gw = subprocess.run(cmd_gw, capture_output=True, text=True)
            for line in res_gw.stdout.split('\n'):
                if 'default via' in line:
                    details['gateway'] = line.split('via')[1].strip().split()[0]
                    break
                    
            return details

        except Exception as e:
            print(f"Error getting connection details: {e}")
            return details


class NetworkManager:
    def __init__(self):
        self.backend = None
        if shutil.which('nmcli'):
            self.backend = NMCLIBackend()
        # elif shutil.which('iwctl'):
        #     self.backend = IwdBackend()
    
    def is_available(self):
        return self.backend is not None

    def scan(self):
        if self.backend:
            return self.backend.scan()
        return []

    def connect(self, ssid, password=None):
        if self.backend:
            return self.backend.connect(ssid, password)
        return False, "No backend available"

    def toggle_wifi(self, enable):
        if self.backend:
            return self.backend.toggle_wifi(enable)
        return False, "No backend available"

    def get_connection_details(self):
        if self.backend:
            return self.backend.get_connection_details()
        return {}
