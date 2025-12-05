import requests
import uuid
import json
from loguru import logger

class DrupalClient:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.login_url = config.get('Login', 'login_url')
        self.username = config.get('Login', 'username')
        self.password = config.get('Login', 'password')
        self.permission_id = config.get('Login', 'permission_id')
        self.workstation_id = config.get('Station', 'workstation_id')
        self.api_url_template = config.get('Login', 'api_url')
        self.debug_mode = config.getboolean('DEFAULT', 'debug_mode', fallback=False)
        self._logged_in = False

        # Set default headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.155 Safari/537.36",
            "cache-control": "private, max-age=0, no-cache",
        }
        self.session.headers.update(headers)

    def login(self):
        try:
            data = {
                "name": self.username,
                "pass": self.password,
                "form_id": "user_login",
                "op": "Log in",
            }
            response = self.session.post(self.login_url, data=data)
            if response.status_code == 200:
                self._logged_in = True
                return True
        except requests.RequestException as e:
            if self.debug_mode:
                logger.error(f"Login failed: {e}")
        return False

    def request_access(self, identifier, is_email):
        # Determine the endpoint based on the type of request (email or serial)
        endpoint = "email" if is_email else "serial"

        # Construct the API URL with additional parameters
        api_url = self.api_url_template.format(endpoint=endpoint, identifier=identifier, permission_id=self.permission_id)
        api_url += f"?source={self.workstation_id}&method=MakerAuth"

        # Headers are already set in session, but we can override/add specific ones if needed
        # The original code added explicit headers here as well.
        headers = {
            "User-Agent": "curl/7.68.0",  # Mimic curl's behavior
            "Accept": "*/*",
            "Cache-Control": "no-cache",  # Ensure fresh data
        }

        try:
            # Use self.session.get to maintain session cookies
            response = self.session.get(api_url, headers=headers)
            if self.debug_mode:
                 logger.debug(f"Request URL: {api_url}")
                 logger.debug(f"Response status: {response.status_code}")
            return response
        except requests.RequestException as e:
            if self.debug_mode:
                logger.error(f"Access request failed: {e}")
            return None

    def request_user_info(self, identifier, is_email):
        endpoint = "email" if is_email else "serial"
        api_url = f"https://makehaven.org/api/v0/{endpoint}/{identifier}/user"
        try:
            return self.session.get(api_url)
        except requests.RequestException as e:
            if self.debug_mode:
                logger.error(f"User info request failed: {e}")
            return None

    def fetch_upcoming_reservations(self, equipment_id):
        api_url = f"https://makehaven.org/api/v0/reservation/upcoming/equipment/{equipment_id}?nocache={uuid.uuid4()}"
        headers = {
            "User-Agent": "curl/7.68.0",
            "Accept": "*/*",
            "Cache-Control": "no-cache",
        }
        try:
            # Use self.session.get
            response = self.session.get(api_url, headers=headers)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        return data.get("reservations", [])
                    elif isinstance(data, list):
                        return data
                except json.JSONDecodeError as e:
                    if self.debug_mode:
                        logger.error(f"Error decoding JSON: {e}")
            elif self.debug_mode:
                 logger.warning(f"Error fetching reservation data: {response.status_code}")
        except requests.RequestException as e:
            if self.debug_mode:
                logger.error(f"Error fetching reservation data: {e}")
        return []

    def fetch_consumables(self, tool_numerical_id):
        url = f"https://www.makehaven.org/api/v0/materials/equipment/{tool_numerical_id}"
        try:
            # Use self.session.get
            response = self.session.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                 if self.debug_mode:
                    logger.warning(f"Error fetching materials: {response.status_code}")
        except (requests.RequestException, json.JSONDecodeError) as e:
             if self.debug_mode:
                logger.error(f"Error fetching materials: {e}")
        return []

    @staticmethod
    def convert_to_hexadecimal(identifier, input_format):
        # Check if the input needs conversion based on format
        # Logic: If input_format is 'decimal', we assume identifier is decimal and convert to Hex.
        # If identifier is already hex, this conversion might fail or produce wrong result if interpreted as int.
        # But we only try to convert if input_format is 'decimal'.
        if input_format == 'decimal':
            try:
                converted = hex(int(identifier)).lstrip('0x').upper()
                return converted
            except ValueError:
                return identifier.upper()
        # If input_format is 'hexadecimal', we assume it is already hex, so just return uppercase.
        return identifier.upper()
