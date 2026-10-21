import requests
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from session_timer import SessionTimerWindow
import datetime
import os
import csv
import configparser
from loguru import logger
import json
import uuid
from urllib.parse import quote
from graylog_logging import get_graylog_logger, log_user_action

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
config.read(config_path)

# Accessing Config Values
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
root.attributes('-fullscreen', True)  # Keep the window in fullscreen mode
root.attributes("-topmost", True)     # Make the window always stay on top

# Debug box setup based on configuration
debug_mode = config.getboolean('DEFAULT', 'debug_mode', fallback=False)

if debug_mode:
    debug_box = tk.Text(root, height=10, width=100)
    debug_box.pack(side="bottom")

def add_debug_message(message):
    if debug_mode:
        debug_box.insert(tk.END, message + "\n")
        debug_box.see(tk.END)

# Seconds to wait on the website before giving up, so a network outage
# can't freeze the station.
REQUEST_TIMEOUT = 10

# Shared session for every website call. It carries the device key the
# website expects on /api/v0 lookups (MakeHaven SEC-001).
session = requests.Session()
api_key = config.get('Login', 'api_key', fallback='').strip()
if api_key:
    session.headers["X-API-Key"] = api_key

# Function to clear existing reservations display before update
def clear_frame(frame):
    for widget in frame.winfo_children():
        widget.destroy()
    print("Cleared frame.")  # Debugging

def display_upcoming_reservations(master_window, equipment_id):
    # Create a frame for displaying reservations
    reservations_frame = ttk.LabelFrame(master_window, text="Upcoming Reservations", padding="10")
    reservations_frame.pack(fill="both", expand=True, padx=20, pady=20)

    def update_reservations_display():
        # Clear existing content in the frame
        clear_frame(reservations_frame)

        # Fetch reservations data
        reservations_data = fetch_upcoming_reservations(equipment_id)

        print(f"Number of reservations to display: {len(reservations_data)}")  # Debugging

        if reservations_data:
            for index, reservation in enumerate(reservations_data):
                print(f"Processing reservation {index}: {reservation}")  # Debugging
                
                # Build label text with default values if keys are missing
                label_text = (
                    f"Asset: {reservation.get('asset', 'Unknown Asset')}\n"
                    f"Time: {reservation.get('range', 'Unknown Time')}\n"
                    f"User: {reservation.get('name', 'Unknown User')}\n"
                    f"Note: {reservation.get('note', 'No Notes')}\n"
                    f"Purpose: {reservation.get('purpose', 'No Purpose Specified')}\n"
                    f"Status: {reservation.get('status', 'Unknown Status')}\n"
                    "-----------------------"
                )

                # Add the label to the frame
                tk.Label(
                    reservations_frame,
                    text=label_text,
                    wraplength=1000,
                    anchor="w",
                    justify="left",
                    font=("Helvetica", 14)
                ).pack(fill='x', pady=2)
        else:
            # Show a message if no reservations are available
            tk.Label(
                reservations_frame,
                text="No upcoming reservations.",
                anchor="w",
                font=("Helvetica", 14)
            ).pack(fill='x')

        # Schedule the next update in 60000 milliseconds (1 minute)
        master_window.after(60000, update_reservations_display)

    # Start the first update
    update_reservations_display()

def fetch_upcoming_reservations(equipment_id):
    api_url = f"https://www.makehaven.org/api/v0/reservation/upcoming/equipment/{equipment_id}?nocache={uuid.uuid4()}"
    headers = {
        "User-Agent": "curl/7.68.0",  # Mimic curl's behavior
        "Accept": "*/*",
        "Cache-Control": "no-cache",  # Ensure fresh data
    }
    try:
        response = session.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT)
        
        # Debugging: Print the raw response
        print("Raw response text:", response.text)
        
        if response.status_code == 200:
            # Attempt to parse the JSON
            try:
                data = response.json()
                print("Parsed JSON data:", data)
                print("Type of data:", type(data))
                
                # If the response is a dictionary, extract reservations if present
                if isinstance(data, dict):
                    reservations = data.get("reservations", [])
                    print("Extracted reservations:", reservations)
                    return reservations
                
                # If the response is already a list, return it directly
                if isinstance(data, list):
                    print("Data is a list, returning as is.")
                    return data
                
                # Handle unexpected data formats
                print("Unexpected data format:", data)
                return []
            
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                return []
        else:
            print(f"Error fetching reservation data: {response.status_code}")
    except requests.RequestException as e:
        print(f"Error fetching reservation data: {e}")
    return []



def read_last_user_info():
    """Reads and returns the last user's information from the temporary JSON file."""
    temp_json_path = 'user_info_temp.json'  # Update the path as necessary
    
    if os.path.exists(temp_json_path):
        try:
            with open(temp_json_path, 'r') as json_file:
                user_info = json.load(json_file)
                return user_info
        except json.JSONDecodeError as e:
            print(f"Error reading or parsing the temporary user info file: {e}")
    return None

def display_last_user_info(master_window):
    """Displays the last user's information in the application's UI."""
    last_user_info = read_last_user_info()
    
    if last_user_info:
        # Construct the display string using the info from last_user_info
        last_user_text = "Last User: {} {}".format(
            last_user_info.get('first_name', 'Unknown'), 
            last_user_info.get('last_name', 'Unknown'))
    else:
        last_user_text = "Last User: None"

    
    # Create and pack a label in master_window to display the last user's information
    last_user_label = tk.Label(master_window, text=last_user_text, font=("Helvetica", 14))
    last_user_label.pack(pady=10)



def update_message(message):
    message_label.config(text=message)
    root.update()
    if debug_mode:
        add_debug_message(f"Updating message: {message}")

def request_access(identifier, is_email):
    # Determine the endpoint based on the type of request (email or serial)
    endpoint = "email" if is_email else "serial"

    # Construct the API URL with additional parameters
    api_url = api_url_template.format(endpoint=endpoint, identifier=quote(identifier, safe=''), permission_id=permission_id)
    api_url += f"?source={workstation_id}&method=MakerAuth"

    # Add headers
    headers = {
        "User-Agent": "curl/7.68.0",  # Mimic curl's User-Agent
        "Accept": "*/*",              # Match curl's Accept header
        "Cache-Control": "no-cache",  # Ensure fresh data
    }

    try:
        response = session.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        add_debug_message(f"Request failed: {e}")
        return None

    # Debugging outputs
    if debug_mode:
        add_debug_message(f"Request URL: {api_url}")
        add_debug_message(f"Response status code: {response.status_code}")
        add_debug_message(f"Response text: {response.text}")

    return response


def denial_reason(response):
    """The website explains a 403/404 in {"error": "..."}; fall back to a generic message."""
    try:
        reason = response.json().get('error')
    except (ValueError, AttributeError):
        reason = None
    if response.status_code == 404:
        return "Denied: account not recognized. Check your email or card."
    if reason:
        return f"Denied: {reason}"
    return "Access denied."


def convert_to_hexadecimal(identifier, input_format):
    add_debug_message(f"Converting identifier: {identifier} with input format: {input_format}")  # Debugging
    if input_format == 'decimal':
        try:
            # Attempt conversion
            converted = hex(int(identifier)).lstrip('0x').upper()
            add_debug_message(f"Converted identifier: {converted}")  # Debugging
            return converted
        except ValueError as e:
            # Log conversion error
            add_debug_message(f"Error converting identifier: {e}")
            return identifier.upper()  # Return the original identifier in upper case if conversion fails
    else:
        return identifier.upper()


def handle_access(identifier):
    identifier = identifier.strip()

    # Check if the input is the secret keyword 'exit' to close the application
    if identifier.lower() == 'exit':  # Use lower() to make it case-insensitive
        root.destroy()  # Close the application
        return  # Exit the function early

    try:
        response = request_access(identifier, "@" in identifier)
        if response is None:
            update_message("Can't reach the website. Please try again in a moment.")
        elif response.status_code == 200:
            data = response.json()
            if data:
                process_access_granted(data)
                return
            update_message("Access denied.")
        elif response.status_code == 401:
            # The website refused this station, not the member: its api_key in
            # config.ini is missing or out of date. Stays locked; tell staff why.
            update_message("This station's website key is missing or out of date. Please tell staff.")
        elif response.status_code in (403, 404):
            update_message(denial_reason(response))
        else:
            update_message("Failed to contact server or access denied.")
    except Exception as e:
        # Never leave the station without a login prompt.
        add_debug_message(f"Error handling access: {e}")
        update_message("Something went wrong. Please try again.")

    # Always allow retry regardless of the outcome
    root.after(3000, lambda: capture_input(True))

def process_access_granted(data):
    """Handle processing for users granted access."""
    user_info = {
        'first_name': data[0].get('first_name'),
        'last_name': data[0].get('last_name'),
        'permission': config.get('Login', 'permission_id'),
        'station': config.get('Station', 'workstation_id'),
    }
    update_message(f"Access Granted. Welcome, {user_info['first_name']} {user_info['last_name']}.")
    write_user_data_to_temp_json(user_info)
    root.after(1500, lambda: close_and_start_session(user_info))


def close_and_start_session(user_info):
    # Log the session start
    log_session("start", user_info, LOG_FILE_PATH)
    
    # Close the authentication window
    root.destroy()
    
    # Start the session timer window
    start_user_session(user_info)

def write_user_data_to_temp_json(user_info):
    # Define a path for the temporary JSON file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_json_path = os.path.join(script_dir, 'temp_user_data.json')

    # Write user data to the temporary JSON file
    with open(temp_json_path, 'w') as json_file:
        json.dump(user_info, json_file)

    # Optionally, log that user data has been written
    print(f"User data written to {temp_json_path}")  # or use logger.info() if you're using Loguru


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
            writer.writerow(["Timestamp", "Action", "First Name", "Last Name", "Permission", "Station", "Duration", "Rating", "Comments", "Usage", "Usage Unit"])

def log_session(action, user_info, log_file_path, extra_fields=None):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = [
        timestamp, 
        action, 
        user_info.get('first_name', 'Unknown'), 
        user_info.get('last_name', 'User'), 
        user_info.get('permission', 'N/A'),
        user_info.get('station', 'N/A'),
        ""  # Placeholder for Duration as it's empty for session start
    ]
    
    # CSV logging
    with open(log_file_path.replace('.txt', '.csv'), 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(row)
    
    # Plain text logging
    with open(log_file_path, 'a') as logfile:
        logfile.write(f"{timestamp} - Session {action} for {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', 'User')}.\n")
    
    # Graylog logging
    graylog_logger = get_graylog_logger()  # Ensure get_graylog_logger() correctly handles config_path internally if needed
    if graylog_logger:
        # Merge extra_fields with the core log data
        log_data = {
            'timestamp': timestamp,
            'action': action,
            'first_name': user_info.get('first_name', 'Unknown'),
            'last_name': user_info.get('last_name', 'User'),
            'permission': user_info.get('permission', 'N/A'),
            'station': user_info.get('station', 'N/A'),
            **(extra_fields or {})  # Unpack extra_fields if provided, otherwise use empty dict
        }
        log_user_action(action, log_data, graylog_logger)

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

display_last_user_info(root)  # Display the last user's in 

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
