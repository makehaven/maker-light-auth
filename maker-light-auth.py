
import requests
import tkinter as tk
from tkinter import simpledialog
from session_timer import SessionTimerWindow
import datetime
import os
import csv
import configparser

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.txt')
config.read(config_path)

# Accessing Config Values
login_url = config.get('Login', 'login_url')
username = config.get('Login', 'username')
password = config.get('Login', 'password')
debug_mode = config.getboolean('DEFAULT', 'debug_mode', fallback=False)
tool_id = config.get('Login', 'tool_id')
workstation_id = config.get('Station', 'workstation_id')
api_url_template = config.get('Login', 'api_url')  # Make sure 'API' section exists in your config file

# Determine log file paths based on configuration
script_dir = os.path.dirname(os.path.abspath(__file__))  # Added for clarity
log_file_name = "SessionLog.txt"  # This line seems to be missing in your script
LOG_FILE_PATH = config.get('Logging', 'log_file_path', fallback=os.path.join(script_dir, log_file_name))
CSV_LOG_FILE_PATH = LOG_FILE_PATH.replace('.txt', '.csv')



def initialize_csv_log_file():
    if not os.path.exists(CSV_LOG_FILE_PATH):
        with open(CSV_LOG_FILE_PATH, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(["Timestamp", "Action", "First Name", "Last Name", "Permission", "Station", "Duration"])

# Initialize CSV log file after configuration and paths are set
initialize_csv_log_file()

# GUI setup
root = tk.Tk()
root.attributes('-fullscreen', True)

# Debug box setup based on configuration
debug_mode = config.getboolean('DEFAULT', 'debug_mode', fallback=False)

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
    # Re-access configuration settings within the function
    login_url = config.get('Login', 'login_url')
    username = config.get('Login', 'username')
    password = config.get('Login', 'password')
    # Proceed with the login attempt
    credentials = {"name": username, "pass": password}
    response = session.post(login_url, data=credentials)
    if debug_mode:
        add_debug_message(f"Login attempt: {response.status_code}")
    return response.status_code == 200

def request_access(identifier, is_email):
    if not login_to_drupal():
        update_message("Login failed. Please check credentials.")
        return None
    endpoint = "email" if is_email else "serial"
    api_url = api_url_template.format(endpoint=endpoint, identifier=identifier, tool_id=tool_id)  # Updated to use variables
    if debug_mode:
        add_debug_message(f"Request URL: {api_url}")
    response = session.get(api_url)
    if debug_mode:
        add_debug_message(f"Access request for {identifier}: {response.status_code}")
        add_debug_message(f"Response body: {response.text}")
    return response


def handle_access(identifier):
    is_email = "@" in identifier
    response = request_access(identifier, is_email)
    if response and response.status_code == 200:
        data = response.json()
        if data and data[0]['access'] == "true":
            # Extract user information
            user_info = {
                'first_name': data[0].get('first_name'),
                'last_name': data[0].get('last_name'),
                # Include tool and workstation information directly in user_info for simplicity
                'permission': config.get('Login', 'tool_id'),  # Added the missing comma here
                'station': config.get('Station', 'workstation_id'),  # Assuming you store workstation_id under [Station]
            }
            update_message(f"Access Granted. Welcome, {user_info['first_name']} {user_info['last_name']}.")

            # Pass user_info and log file path to close_and_start_session function
            root.after(1500, lambda: close_and_start_session(user_info))

        else:
            update_message("Access Denied. Please try again.")
            root.after(3000, lambda: capture_input(True))  # Retry on denial
    else:
        update_message("Failed to contact server or access denied.")
        root.after(3000, lambda: capture_input(True))  # Retry on failure

def close_and_start_session(user_info):
    # Log the session start
    log_session("start", user_info, LOG_FILE_PATH)
    
    # Close the authentication window
    root.destroy()
    
    # Start the session timer window
    start_user_session(user_info)
    
def start_user_session(user_info):
    enable_timer = config.get('SessionTime', 'enable_timer_window', fallback='false').lower() == 'true'
    if enable_timer:
        # This will directly run the session timer window without threading
        session_window = SessionTimerWindow(user_info, log_file_path=LOG_FILE_PATH)
        session_window.run()


def initialize_log_file(log_file_path):
    # Check if the log file exists
    if not os.path.exists(log_file_path):
        with open(log_file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            # Updated headers
            writer.writerow(["Timestamp", "Action", "First Name", "Last Name", "Permission", "Station", "Duration"])

def log_session(action, user_info, log_file_path):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = [
        timestamp, 
        action, 
        user_info.get('first_name', 'Unknown'), 
        user_info.get('last_name', 'User'), 
        user_info.get('permission', 'N/A'),  # Permission typically holds tool_id
        user_info.get('station', 'N/A'),  # Station typically holds workstation_id
        ""  # Duration is empty for session start
    ]
    
    # Write to CSV log file
    with open(log_file_path.replace('.txt', '.csv'), 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(row)
    
    # Also write to the plain text log file for backward compatibility
    with open(log_file_path, 'a') as logfile:
        logfile.write(f"{timestamp} - Session {action} for {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', 'User')}.\n")


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
