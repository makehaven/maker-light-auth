import requests
import tkinter as tk
from tkinter import simpledialog
import datetime
import os

# Script directory and log file setup
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file_name = "SessionLog.txt"
CONFIG_FILE_PATH = os.path.join(script_dir, "config.txt")
LOG_FILE_PATH = os.path.join(script_dir, log_file_name)

# Load configuration
config = {}
with open(CONFIG_FILE_PATH, 'r') as config_file:
    for line in config_file:
        key, value = line.strip().split('=', 1)
        config[key] = value

# Determine debug mode
debug_mode = config.get("debug_mode", "false").lower() == "true"


# GUI setup
root = tk.Tk()
root.attributes('-fullscreen', True)

# Debug box setup
if debug_mode:
    debug_box = tk.Text(root, height=10, width=100)
    debug_box.pack(side="bottom")

def add_debug_message(message):
    if debug_mode:
        debug_box.insert(tk.END, message + "\n")
        debug_box.see(tk.END)

# Session for persistent login state
session = requests.Session()

def update_message(message):
    message_label.config(text=message)
    root.update()
    if debug_mode:
        add_debug_message(f"Updating message: {message}")

def login_to_drupal():
    login_url = config['login_url']
    credentials = {"name": config['username'], "pass": config['password']}
    response = session.post(login_url, data=credentials)
    if debug_mode:
        add_debug_message(f"Login attempt: {response.status_code}")
    return response.status_code == 200

def request_access(identifier, is_email):
    if not login_to_drupal():
        update_message("Login failed. Please check credentials.")
        return None
    endpoint = "email" if is_email else "serial"
    api_url = config['api_url'].format(endpoint=endpoint, identifier=identifier, tool_id=config['tool_id'])
    if debug_mode:
        add_debug_message(f"Request URL: {api_url}")
    response = session.get(api_url)
    if debug_mode:
        add_debug_message(f"Access request for {identifier}: {response.status_code}")
        add_debug_message(f"Response body: {response.text}")  # Add this line to log the response body
    return response


def handle_access(identifier):
    is_email = "@" in identifier
    response = request_access(identifier, is_email)
    if response and response.status_code == 200:
        data = response.json()
        if data and data[0]['access'] == "true":
            user_info = data[0]
            update_message(f"Access Granted. Welcome, {user_info['first_name']} {user_info['last_name']}.")
            log_session("start", user_info)
            root.after(5000, root.destroy)  # Close the window after a short delay
        else:
            update_message("Access Denied. Please try again.")
            root.after(3000, lambda: capture_input(True))  # Retry on denial
    else:
        update_message("Failed to contact server or access denied.")
        root.after(3000, lambda: capture_input(True))  # Retry on failure

def log_session(action, user_info=None):
    with open(LOG_FILE_PATH, 'a') as log_file:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_file.write(f"{timestamp} - Session {action} for {user_info.get('first_name', '')} {user_info.get('last_name', '')}\n")


# Message label for instructions
message_label = tk.Label(root, text="Please scan your RFID tag or enter your email to start the session.", font=("Helvetica", 24))
message_label.pack(expand=True, fill=tk.X, pady=(50, 0))

# Input capture function
def capture_input(retry=False):
    if retry:
        message_label.config(text="Please try again. Scan your RFID tag or enter your email:")
    else:
        message_label.config(text="Please scan your RFID tag or enter your email to start the session.")
    root.update()
    identifier = simpledialog.askstring("Input", "Scan RFID Tag or Enter Email:", parent=root)
    if identifier:
        handle_access(identifier)
    else:
        update_message("No input detected. Please scan your RFID tag or enter your email.")
        root.after(3000, lambda: capture_input(True))

# Closing function
def on_closing():
    if debug_mode:
        add_debug_message("Application closing.")
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

# Start the application
capture_input()

# Main loop
root.mainloop()
