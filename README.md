# RFID and Email Access Control Script

This Python-based script (`maker-light-auth.pyw`) facilitates user authentication using RFID or email, interfacing with a Drupal backend to verify access permissions. It provides a graphical user interface (GUI) for user interaction, displaying access statuses promptly.

## Usage

Configure the config file for the specific station and materials. Users can log in via serial number or email, which the script will verify against the configured website.

**Tip**: Type "exit" at the user input screen to close the program.

## Prerequisites

Ensure your system has:

- **Python 3.x**: Version 3.6 or newer. Download from [python.org](https://www.python.org/downloads/).
- **Python Libraries**: Install the `requests`, `httpx`, and `qrcode[pil]` libraries for HTTP requests handling and extended functionalities.

## Installation

To set up the script environment, follow these steps:

1. **Install Python**: Download and install Python from [python.org](https://www.python.org/downloads/). Ensure Python is added to your PATH.

2. **Install Dependencies**: Execute the following commands to install required libraries:

   ```bash
   pip install requests httpx configparser loguru qrcode[pil]


## Workstation Setup for Shared User Account
To configure the script for automatic execution on a workstation with a shared user account:

Script Placement: Place maker-light-auth.pyw in a common directory, such as C:\Users\SharedUser\Scripts\.

Configure Auto Start:

Press Win + R, type shell:startup, and press Enter to open the Startup folder for the current user.
For all users, use shell:common startup.
Create a shortcut in the Startup folder pointing to the script's executable.
Ensure Environment Readiness:

Install Python and all dependencies for the shared user account.
Administrative privileges might be necessary for system-wide installations.
Check Permissions: Verify the shared user account has the necessary permissions to run the script and access network resources.

Conduct a Test: Log in to the workstation with the shared user account to test the autostart functionality. Troubleshoot by checking script permissions, dependency installations, and startup configurations.


