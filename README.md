 RFID and Email Access Control Script

This Python-based script (`maker-light-auth.py`) enables user authentication via RFID or email, leveraging a Drupal backend for access permissions verification. It features a graphical user interface (GUI) for user interaction, displaying access status promptly.

## Prerequisites

Ensure your system has:

- **Python 3.x**: Specifically Python 3.6 or newer. Available for download at [python.org](https://www.python.org/downloads/).
- **Requests library**: Utilized for HTTP requests handling.
- **Additional libraries**: `httpx` and `qrcode[pil]` for extended functionalities.

## Installation

To set up the script environment, follow these steps:

1. **Python Installation**: Download and install Python from [python.org](https://www.python.org/downloads/), making sure to add Python to your PATH.

2. **Dependencies Installation**: Run the following command in your command prompt or terminal to install the necessary Python packages:

   ```bash
   pip install requests httpx qrcode[pil]


##Workstation Setup for Shared User Account

To configure the script for automatic execution on a workstation under a shared user account:

1. Script Placement: Copy maker-light-auth.py to a commonly accessible directory on the workstation, e.g., C:\Users\SharedUser\Scripts\.

2. Configure Autostart:

Create a shortcut to maker-light-auth.py.
Place it in the Startup folder of the shared user account, typically found at C:\Users\SharedUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup.

3. Ensure Environment Readiness:

Install Python and all required dependencies for the shared user account.
Admin privileges may be needed for system-wide installations.

4. Check Permissions: Confirm that the shared user account has appropriate permissions to run the script and access necessary network resources or APIs.

5. Conduct a Test: Log into the workstation with the shared user account to test the script's autostart functionality. Address any issues by verifying the script's permissions, dependency installations, and startup configuration.


