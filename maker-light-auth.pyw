import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from session_timer import SessionTimerWindow
import datetime
import os
import csv
import json
from loguru import logger
import utils
from drupal_client import DrupalClient

# Load configuration
config = utils.load_config()
debug_mode = config.getboolean('DEFAULT', 'debug_mode', fallback=False)
log_file_path, csv_log_file_path = utils.get_log_file_paths(config)
tool_numerical_id = config.get('Station', 'tool_numerical_id', fallback="0")

# Initialize Logger
utils.initialize_csv_log_file(csv_log_file_path)

# Initialize Drupal Client
drupal_client = DrupalClient(config)

# GUI setup
root = tk.Tk()
root.attributes('-fullscreen', True)
root.attributes("-topmost", True)

if debug_mode:
    debug_box = tk.Text(root, height=10, width=100)
    debug_box.pack(side="bottom")

def add_debug_message(message):
    if debug_mode:
        debug_box.insert(tk.END, message + "\n")
        debug_box.see(tk.END)
        logger.debug(message)

# Function to clear existing reservations display before update
def clear_frame(frame):
    for widget in frame.winfo_children():
        widget.destroy()

def display_upcoming_reservations(master_window, equipment_id):
    reservations_frame = ttk.LabelFrame(master_window, text="Upcoming Reservations", padding="10")
    reservations_frame.pack(fill="both", expand=True, padx=20, pady=20)

    def update_reservations_display():
        clear_frame(reservations_frame)
        reservations_data = drupal_client.fetch_upcoming_reservations(equipment_id)

        if reservations_data:
            for reservation in reservations_data:
                label_text = (
                    f"Asset: {reservation.get('asset', 'Unknown Asset')}\n"
                    f"Time: {reservation.get('range', 'Unknown Time')}\n"
                    f"User: {reservation.get('name', 'Unknown User')}\n"
                    f"Note: {reservation.get('note', 'No Notes')}\n"
                    f"Purpose: {reservation.get('purpose', 'No Purpose Specified')}\n"
                    f"Status: {reservation.get('status', 'Unknown Status')}\n"
                    "-----------------------"
                )
                tk.Label(
                    reservations_frame,
                    text=label_text,
                    wraplength=1000,
                    anchor="w",
                    justify="left",
                    font=("Helvetica", 14)
                ).pack(fill='x', pady=2)
        else:
            tk.Label(
                reservations_frame,
                text="No upcoming reservations.",
                anchor="w",
                font=("Helvetica", 14)
            ).pack(fill='x')

        master_window.after(60000, update_reservations_display)

    update_reservations_display()

def read_last_user_info():
    temp_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_info_temp.json')
    if os.path.exists(temp_json_path):
        try:
            with open(temp_json_path, 'r') as json_file:
                return json.load(json_file)
        except json.JSONDecodeError as e:
            add_debug_message(f"Error reading temp user info: {e}")
    return None

def display_last_user_info(master_window):
    last_user_info = read_last_user_info()
    if last_user_info:
        last_user_text = "Last User: {} {}".format(
            last_user_info.get('first_name', 'Unknown'), 
            last_user_info.get('last_name', 'Unknown'))
    else:
        last_user_text = "Last User: None"
    
    last_user_label = tk.Label(master_window, text=last_user_text, font=("Helvetica", 14))
    last_user_label.pack(pady=10)

def update_message(message):
    message_label.config(text=message)
    root.update()
    add_debug_message(f"Updating message: {message}")

def handle_access(identifier):
    if identifier.lower() == 'exit':
        root.destroy()
        return

    # Attempt login if needed (although drupal_client creates new session, we might want to ensure login)
    # The client handles request, but maybe we need an explicit login check?
    # The original code did: if session is None: login().
    # Here we can just try request. If 403/401, maybe retry login?
    # For now, let's assume the client handles it or we do it once.

    # Actually, the original code called login() inside request_access if session was None.
    # We should probably do an initial login.
    if not hasattr(drupal_client, '_logged_in') or not drupal_client._logged_in:
         if drupal_client.login():
             drupal_client._logged_in = True
         else:
             add_debug_message("Login failed.")
             # We might still try request, maybe it works anonymously or cached? Unlikely.

    # Check input format
    input_format = config.get('Login', 'input_format', fallback='decimal')
    if '@' not in identifier:
         # Always attempt conversion based on input_format
         identifier = drupal_client.convert_to_hexadecimal(identifier, input_format)

    response = drupal_client.request_access(identifier, "@" in identifier)
    
    if response and response.status_code == 200:
        data = response.json()
        if not data:
            # Secondary check
            user_info_response = drupal_client.request_user_info(identifier, "@" in identifier)
            if user_info_response and user_info_response.status_code == 200:
                user_data = user_info_response.json()
                if user_data:
                    process_user_data(user_data, "Denied because account not recognized as in the system.")
                else:
                    update_message("Denied because account not recognized as in the system.")
            else:
                update_message("Failed to contact server or access denied.")
        else:
            process_access_granted(data)
    else:
        update_message("Failed to contact server or access denied.")

    # Re-enable input after a delay
    root.after(3000, request_input)

def request_input():
    # Use simpledialog but ensure we schedule it properly.
    # Since simpledialog is modal, it blocks.
    # To avoid blocking the reservations update, we're stuck unless we make a custom dialog.
    # But sticking to the original design with fixes:
    # We can't really avoid blocking with simpledialog.
    # So we will just call it.

    # Note: in the original code, `capture_input` had a loop `while True`.
    # We want to avoid infinite recursion stack overflow from `root.after` calls inside loop/functions if not careful.

    # We will use `root.after` to schedule the dialog, allowing the main loop to process events (like reservation updates) *between* dialogs?
    # No, while dialog is open, events are processed by dialog's loop. But `after` callbacks from root might not fire if not handled?
    # Actually, Tkinter nested loops usually handle `after` events.

    input_value = simpledialog.askstring("Input", "Scan RFID Tag or Enter Email:", parent=root)
    if input_value:
        handle_access(input_value)
    else:
        # User cancelled or empty input.
        # Check if we should exit or re-prompt.
        # If it's a kiosk, we re-prompt.
        # But maybe give a small delay so we don't spam if something is wrong.
        root.after(500, request_input)

def process_user_data(user_data, default_message):
    if not user_data:
        update_message(default_message)
        return

    access_status = user_data[0].get('access', '').lower()
    
    if "denied" in access_status:
        update_message("Denied because membership is not active.")
    elif "member" in access_status:
        update_message("Denied because does not have badge/permission for this tool.")
    else:
        update_message(default_message)

def process_access_granted(data):
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
    utils.log_session_event("start", user_info, config)
    root.destroy()
    start_user_session(user_info)

def write_user_data_to_temp_json(user_info):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_json_path = os.path.join(script_dir, 'temp_user_data.json')
    with open(temp_json_path, 'w') as json_file:
        json.dump(user_info, json_file)
    add_debug_message(f"User data written to {temp_json_path}")

def start_user_session(user_info):
    enable_timer = config.get('SessionTime', 'enable_timer_window', fallback='false').lower() == 'true'
    if enable_timer:
        session_window = SessionTimerWindow(user_info, log_file_path=log_file_path)
        session_window.run()

# UI Elements
message_label = tk.Label(root, text="Please scan your RFID tag or enter your email to start the session.", font=("Helvetica", 24))
message_label.pack(expand=True, fill=tk.X, pady=(50, 0))

display_upcoming_reservations(root, tool_numerical_id)
display_last_user_info(root)

# Handle Closing
def on_closing():
    add_debug_message("Application closing.")
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

# Start input loop
root.after(100, request_input)

# Single Main Loop
root.mainloop()
