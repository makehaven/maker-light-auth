import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import requests
from PIL import Image, ImageTk, ImageDraw
import qrcode
import configparser
import os
import subprocess
import sys
from datetime import datetime
from io import BytesIO
import csv
import json
window = None

root = tk.Tk()
root.withdraw()  # If you don't want the root window to be visible

# Determine the directory of your script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Build the path to the configuration file
config_path = os.path.join(script_dir, 'config.ini')

# Load configuration
config = configparser.ConfigParser()
config.read(config_path)

# configuration values 
show_ending_window = config.getboolean('EndingPage', 'show_ending_window', fallback=False)
show_experience_scale = config.getboolean('EndingPage', 'show_experience_scale', fallback=False)
end_message = config.get('EndingPage', 'end_message', fallback="Please remember to clean up.")
experience_question = config.get('EndingPage', 'experience_question', fallback="How was your experience?")
high_label = config.get('EndingPage', 'high_label', fallback="Excellent")
low_label = config.get('EndingPage', 'low_label', fallback="Poor")
tool_numerical_id = config.get('Station', 'tool_numerical_id', fallback="0")
custom_message = config.get('EndingPage', 'custom_message', fallback="Thank you for using the station.")
LOG_FILE_PATH = os.path.join(script_dir, 'SessionLog.txt')  # Adjust the filename as necessary
CSV_LOG_FILE_PATH = config.get('Logging', 'csv_log_file_path', fallback=os.path.join(os.path.dirname(os.path.abspath(__file__)), "SessionLog.csv"))

def initialize_csv_log_file():
    if not os.path.exists(CSV_LOG_FILE_PATH):
        with open(CSV_LOG_FILE_PATH, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(["Timestamp", "Action", "First Name", "Last Name", "Permission", "Station", "Duration","Rating", "Details"])

initialize_csv_log_file()


def restart_authentication():
    # Close the current Tkinter window if it exists
    global window
    if window is not None:
        try:
            window.destroy()
        except tk.TclError as e:
            print(f"Error closing window: {e}")
    
    # Restart the authentication process by running maker-light-auth.py script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "maker-light-auth.pyw")
    
    # Use subprocess to run the script in a new process
    subprocess.Popen([sys.executable, script_path])
    
    # Exit the current script to ensure there's no unintended code execution following this function
    sys.exit()

def safe_destroy(window):
    """Safely destroy a Tkinter window."""
    try:
        if window.winfo_exists():
            window.destroy()
    except Exception as e:
        print("Error closing window:", e)

# Function to open URL in a new browser window if possible
def open_url_new_window(url):
    try:
        # Attempt to use system's default browser to open the URL in a new window
        webbrowser.open_new(url)
    except Exception as e:
        print(f"Failed to open URL in a new browser window: {e}")

def log_event_with_comments(action, rating, comments, user_info=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    first_name = user_info.get('first_name', 'Unknown') if user_info else 'Unknown'
    last_name = user_info.get('last_name', 'Unknown') if user_info else 'Unknown'
    # Prepare the CSV log entry with comments
    log_entry_csv = [timestamp, action, first_name, last_name, "", "", "", rating, comments]
    # Prepare the text log entry with comments
    log_entry_text = f"{timestamp} - {action} - {first_name} {last_name}: Rating: {rating}, Comments: {comments}\n"

    # Write to CSV file
    with open(CSV_LOG_FILE_PATH, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(log_entry_csv)

    # Write to text file
    with open(LOG_FILE_PATH, 'a') as log_file:
        log_file.write(log_entry_text)


def show_ending_window(custom_message, show_experience_scale, tool_numerical_id, experience_question, high_label, low_label, user_info):
    global window
    if window:  # If there's an existing window, safely destroy it
        safe_destroy(window)
    window = tk.Toplevel(root)  # Use Toplevel instead of Tk
    window.title("Session Ended")
    window.attributes("-topmost", True)  # Ensure the window stays on top

    # Make window full screen and non-bypassable
    window.overrideredirect(True)
    window.geometry("{0}x{1}+0+0".format(window.winfo_screenwidth(), window.winfo_screenheight()))

    # Layout configurations
    window.grid_rowconfigure(1, weight=1)
    window.grid_columnconfigure(0, weight=1)

    # Custom Message
    tk.Label(window, text=custom_message, font=("Helvetica", 18), pady=20).pack()

    if show_experience_scale:

        # Rating Scale
        rating_frame = tk.LabelFrame(window, text=experience_question, font=("Helvetica", 14))
        rating_frame.pack(pady=10)

        def rate_experience(score):
             # Show message box for the rating
            messagebox.showinfo("Rating", f"You rated {score}/5", parent=root)
            
            # Open a new window to ask for comments
            comment_window = tk.Toplevel(window)
            comment_window.title("Additional Comments")
            comment_window.geometry("400x200")  # Adjust size as necessary

            tk.Label(comment_window, text="Any comments on your experience?", font=("Helvetica", 12)).pack(pady=(20, 10))
            comment_text = tk.Text(comment_window, height=4, width=40)
            comment_text.pack(pady=(0, 20))

            def submit_comments():
                comments = comment_text.get("1.0", "end-1c")
                log_event_with_comments("rating", score, comments, user_info)
                comment_window.destroy()
                
            submit_btn = tk.Button(comment_window, text="Submit", command=submit_comments)
            submit_btn.pack()

            # Disable the rating buttons to prevent multiple submissions
            for btn in rating_buttons:
                btn.config(state=tk.DISABLED)

        rating_buttons = []
        colors = ["#ff4d4d", "#ff9999", "#ffff99", "#99ff99", "#00cc00"]  # Gradient from red to green
        tk.Label(rating_frame, text=low_label, font=("Helvetica", 12)).pack(side=tk.LEFT, padx=5)
        for i, color in enumerate(colors, start=1):
            btn = tk.Button(rating_frame, text=str(i), bg=color, command=lambda i=i: rate_experience(i), font=("Helvetica", 12), width=2)
            btn.pack(side=tk.LEFT, padx=2)
            rating_buttons.append(btn)
        tk.Label(rating_frame, text=high_label, font=("Helvetica", 12)).pack(side=tk.LEFT, padx=5)




    consumables_frame_outer = tk.Frame(window, padx=20)  # Outer frame for padding
    consumables_frame_outer.pack(padx=100, pady=20)  # Pad outer frame to center and limit width

    consumables_frame = tk.LabelFrame(consumables_frame_outer, text="Materials for purchase", font=("Helvetica", 14))
    consumables_frame.pack(fill="both", expand=True) 

    # Assuming a two-column layout for materials
    column_count = 2  # Number of columns
    materials = fetch_consumables(tool_numerical_id)
    for index, material_info in enumerate(materials):
        material = material_info['material']
        label = f"{material['label']} - {material['unit']} - ${material['cost']}"
        row = index // column_count
        column = index % column_count
        # Create button with larger font size
        button = ttk.Button(consumables_frame, text=label, style="Material.TButton", command=lambda m=material: open_payment_link(m))
        button.grid(row=row, column=column, padx=5, pady=5, sticky="ew")

    # Apply a style to make the text bigger
    style = ttk.Style()
    style.configure("Material.TButton", font=("Helvetica", 14))

    # Configure columns to equally share the frame
    for i in range(column_count):
        consumables_frame.grid_columnconfigure(i, weight=1)




    # Reset Station Frame
    reset_station_frame = tk.LabelFrame(window, text="Reset station for next user", font=("Helvetica", 14), padx=10, pady=10)
    reset_station_frame.pack(pady=20, padx=20, fill="both", expand=True)

    # Control Buttons within the LabelFrame
    button_frame = tk.Frame(reset_station_frame)
    button_frame.pack(expand=True)

    # Less prominent button for "left open by someone else"
    btn_left_open = tk.Button(button_frame, text="Not me (reset to login)", command=lambda: [log_event("not_me", "", user_info), safe_destroy(window), restart_authentication()], bg="#add8e6", fg="black", font=("Helvetica", 12))
    btn_left_open.pack(side=tk.BOTTOM, pady=(10, 0))  # Positioned at the bottom, less emphasis

    # Primary actions with more emphasis
    btn_no_charges = tk.Button(button_frame, text="Nothing Due", command=lambda: [log_event("nothing_due", "", user_info), safe_destroy(window), restart_authentication()], bg="#add8e6", fg="black", font=("Helvetica", 12))
    btn_no_charges.pack(side=tk.LEFT, padx=10, expand=True)

    btn_submitted_payments = tk.Button(button_frame, text="I paid", command=lambda: [log_event("payment_submitted", "", user_info), safe_destroy(window), restart_authentication()], bg="#98fb98", fg="black", font=("Helvetica", 12))
    btn_submitted_payments.pack(side=tk.RIGHT, padx=10, expand=True)

    
    window.mainloop()


def open_payment_link(material):
    detail_window = tk.Toplevel()
    detail_window.title(material['label'])

    # Fetch and display the material image
    try:
        image_url = material['image']['src']
        image_response = requests.get(image_url, stream=True)
        image_response.raw.decode_content = True
        material_image = Image.open(image_response.raw)

        # Resize the image while maintaining the aspect ratio
        base_height = 100
        img_ratio = base_height / float(material_image.size[1])
        new_width = int((float(material_image.size[0]) * float(img_ratio)))
        material_image = material_image.resize((new_width, base_height), Image.LANCZOS)

        photo_image = ImageTk.PhotoImage(material_image)
        img_label = tk.Label(detail_window, image=photo_image)
        img_label.image = photo_image  # keep a reference to prevent garbage-collection
        img_label.pack(pady=10)
    except Exception as e:
        print(f"Failed to load image: {e}")

    # Generate QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(material['purchase'])
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGB')

    # Optionally resize QR code (if needed, otherwise comment out the resizing part)
    qr_img_resized = qr_img.resize((100, 100), Image.LANCZOS)
    qr_photo = ImageTk.PhotoImage(image=qr_img_resized)

    # Display QR Code
    qr_label = tk.Label(detail_window, image=qr_photo)
    qr_label.image = qr_photo  # keep a reference!
    qr_label.pack(pady=10)

    # Display Material Info
    material_info = f"{material['label']}\nUnit: {material['unit']}\nPrice: ${material['cost']}"
    tk.Label(detail_window, text=material_info, font=("Helvetica", 12)).pack()

    # "Buy Here" Button for backup
    #buy_button = ttk.Button(detail_window, text="Buy Here", command=lambda: webbrowser.open(material['purchase']))
    #buy_button.pack(pady=10)

    detail_window.mainloop()

def log_event(action, rating, user_info=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    first_name = user_info.get('first_name', 'Unknown') if user_info else 'Unknown'
    last_name = user_info.get('last_name', 'Unknown') if user_info else 'Unknown'
    # Prepare the CSV log entry
    log_entry_csv = [timestamp, action, first_name, last_name," "," "," ", rating]
    # Prepare the text log entry
    log_entry_text = f"{timestamp} - {action} - {first_name} {last_name}: {rating}\n"

    # Write to CSV file
    with open(CSV_LOG_FILE_PATH, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(log_entry_csv)

    # Write to text file
    with open(LOG_FILE_PATH, 'a') as log_file:
        log_file.write(log_entry_text)

def fetch_consumables(tool_numerical_id):
    url = f"https://www.makehaven.org/api/v0/materials/equipment/{tool_numerical_id}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['materials']
    else:
        print(f"Error fetching materials: {response.status_code}")
        return []


if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_info_path = sys.argv[1]
        with open(user_info_path, 'r') as f:
            user_info = json.load(f)
        os.remove(user_info_path)  # Clean up the temporary file
    else:
        user_info = {'first_name': 'Unknown', 'last_name': 'Unknown'}  # Default values

    show_ending_window(custom_message, show_experience_scale, tool_numerical_id, experience_question, high_label, low_label, user_info)
