import httpx
from loguru import logger
import configparser

# Load configuration from a file
config = configparser.ConfigParser()
config.read('config.txt')

LOGIN_URL = config.get('Login', 'login_url')
USERNAME = config.get('Login', 'username')
PASSWORD = config.get('Login', 'password')
TEST_URL = config.get('Login', 'test_url')

# Configure the logger
logger.add("debug.log", format="{time} {level} {message}", level="DEBUG")

def login_and_test():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/44.0.2403.155 Safari/537.36"
        ),
        "Cache-Control": "no-cache",
    }

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        # Attempt to login
        login_response = client.post(
            LOGIN_URL,
            data={
                "name": USERNAME,
                "pass": PASSWORD,
                "form_id": "user_login",
                "op": "Log in",
            }
        )
        
        if login_response.status_code == 200:
            logger.info("Login successful. Attempting to access test URL.")
            # Attempt to access a protected resource
            test_response = client.get(TEST_URL)
            if test_response.status_code == 200:
                logger.info("Access to test URL successful.")
                # Log JSON response content if expected to be JSON
                try:
                    json_response = test_response.json()
                    logger.info(f"Test URL JSON response: {json_response}")
                except ValueError:
                    # If not JSON, log as plain text
                    logger.info(f"Test URL response content: {test_response.text}")
                return True
            else:
                logger.error(f"Failed to access test URL. Status code: {test_response.status_code}. Check authentication.")
                return False
        else:
            logger.error(f"Login failed with status code: {login_response.status_code}")
            return False

if __name__ == "__main__":
    if login_and_test():
        logger.info("Test succeeded.")
    else:
        logger.error("Test failed.")
