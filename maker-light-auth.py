import requests
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from session_timer import SessionTimerWindow
import datetime
import os
import csv
import configparser
from loguru import logger

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
config.read(config_path)

# Accessing Config Values
login_url = config.get('Login', 'login_url')
username = config.get('Login', 'username')
password = config.get('Login', 'password')
debug_mode = config.getboolean('DEFAULT', 'debug_mode', fallback=False)
permission_id = config.get('Login', 'permission_id')
workstation_id = config.get('Station', 'workstation_id')
api_url_template = config.get('Login', 'api_url')  # Make sure 'API' section exists in your config file
tool_numerical_id = config.get('Station', 'tool_numerical_id', fallback="0")

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

# Function to fetch and display upcoming reservations
def display_upcoming_reservations(master_window, equipment_id):
    # Fetch reservations data
    reservations_data = fetch_upcoming_reservations(equipment_id)
    # Create a frame for displaying reservations
    reservations_frame = ttk.LabelFrame(master_window, text="Upcoming Reservations", padding="10")
    reservations_frame.pack(fill="both", expand=True, padx=20, pady=20)
    # Adding an invisible label with a specific width and height to enforce minimum size
    invisible_label = tk.Label(reservations_frame, text="", width=100, height=5)
    invisible_label.pack()


    if reservations_data:
        for reservation in reservations_data:
            reservation_info = reservation["reservation"]  # Adjusted according to your JSON structure
            label_text = f"{reservation_info['asset']} - {reservation_info['range']} - {reservation_info['name']}"
            reservation_label = tk.Label(reservations_frame, text=label_text, wraplength=1000, anchor="w", justify="center", font=("Helvetica", 14))
            reservation_label.pack(fill='x', pady=2)
            reservation_label.config(font=("Helvetica", 14))
    else:
        no_reservations_label = tk.Label(reservations_frame, text="No upcoming reservations.", anchor="w")
        no_reservations_label.pack(fill='x')
        no_reservations_label.config(font=("Helvetica", 14))

def fetch_upcoming_reservations(equipment_id):
    api_url = f"https://makehaven.org/api/v0/reservation/upcoming/equipment/{equipment_id}"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            return data["reservations"]  # Adjust according to actual JSON structure
        else:
            print(f"Error fetching reservation data: {response.status_code}")
    except requests.RequestException as e:
        print(f"Error fetching reservation data: {e}")
    return []

def update_message(message):
    message_label.config(text=message)
    root.update()
    if debug_mode:
        add_debug_message(f"Updating message: {message}")

# Global session for persistent login state
session = None

def login_to_drupal():
    global session
    session = requests.Session()
    login_url = config.get('Login', 'login_url')
    username = config.get('Login', 'username')
    password = config.get('Login', 'password')

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.155 Safari/537.36",
        "cache-control": "private, max-age=0, no-cache",
    }

    session.headers.update(headers)

    try:
        response = session.post(login_url, data={"name": username, "pass": password, "form_id": "user_login", "op": "Log in",})
        if response.status_code == 200:
            return True
    except Exception as e:
        print(f"Login failed: {e}")
    return False

def request_access(identifier, is_email):
    global session  # Ensure session is recognized as global if not already defined
    if session is None:
        if not login_to_drupal():
            if debug_mode:
                add_debug_message("Login failed. Please check credentials.")
            return None
    endpoint = "email" if is_email else "serial"
    api_url = api_url_template.format(endpoint=endpoint, identifier=identifier, permission_id=permission_id)

    response = session.get(api_url)
    
    # Debug messages should be logged before any return statement to ensure they execute
    if debug_mode:
        add_debug_message(f"Request URL: {api_url}")
        add_debug_message(f"Access request for {identifier}: {response.status_code}")
        if response.status_code == 200:
            try:
                response_data = response.json()
                add_debug_message(f"Response JSON: {response_data}")
            except ValueError:
                add_debug_message("Response body could not be converted to JSON.")
        else:
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
                'permission': config.get('Login', 'permission_id'),  # Added the missing comma here
                'station': config.get('Station', 'workstation_id'),  # Assuming you store workstation_id under [Station]
            }
            update_message(f"Access Granted. Welcome, {user_info['first_name']} {user_info['last_name']}.")

            # Pass user_info and log file path to close_and_start_session function
            root.after(1500, lambda: close_and_start_session(user_info))

        else:
            update_message("Access Denied. Please try again.")
            root.after(3000, lambda: capture_input(True))  
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
            writer.writerow(["Timestamp", "Action", "First Name", "Last Name", "Permission", "Station", "Duration", "Rating", "Comments"])

def log_session(action, user_info, log_file_path):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = [
        timestamp, 
        action, 
        user_info.get('first_name', 'Unknown'), 
        user_info.get('last_name', 'User'), 
        user_info.get('permission', 'N/A'),  # Permission typically holds permission_id
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
    def on_input_close():
        if not input_received[0]:  # Re-prompt if input was not received
            root.after(100, capture_input)
    
    input_received = [False]  # Use a list to modify it inside nested function
    
    while True:
        input_value = simpledialog.askstring("Input", "Scan RFID Tag or Enter Email:", parent=root)
        if input_value:
            input_received[0] = True  # Mark that input was received
            handle_access(input_value)  # Your existing logic to handle the access based on input
            break
        else:
            messagebox.showerror("Input Required", "Please scan your RFID tag or enter your email.")
            continue  # Ensure the loop continues until valid input is received
    
    root.protocol("WM_DELETE_WINDOW", on_input_close)  # Modify window closing behavior

# Display reservations in the main window
display_upcoming_reservations(root, tool_numerical_id)

# Ensure the input dialog is displayed after a short delay to allow the main window to initialize
root.after(100, capture_input)

root.mainloop()

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
