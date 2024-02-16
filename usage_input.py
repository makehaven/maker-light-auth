import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
import requests
from PIL import Image, ImageTk
import qrcode
import configparser
import os
from loguru import logger
import sys
import math
import csv
import subprocess
from datetime import datetime
import json

# Configuration and Logging Setup
config = configparser.ConfigParser()
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, 'config.ini')
config.read(config_path)

logger.add("debug.log", format="{time} {level} {message}", level="DEBUG")

# Configuration Settings
require_usage_input = config.getboolean('UsageInput', 'require_usage_input', fallback=True)
usage_unit = config.get('UsageInput', 'usage_unit', fallback="units")
material_id = config.get('UsageInput', 'material_id', fallback="")
BASE_URL = config.get('API', 'base_url', fallback="https://www.makehaven.org/api/v0/material/")

# Function to fetch material data
def fetch_material_data(material_id):
    url = f"{BASE_URL}{material_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

# Function to create a QR code
def create_qr_code(url, size=300):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img

def read_user_data_from_temp_json():
    # Define the path to the temporary JSON file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_json_path = os.path.join(script_dir, 'temp_user_data.json')

    # Check if the file exists
    if not os.path.exists(temp_json_path):
        print(f"Temporary JSON file does not exist: {temp_json_path}")
        return None

    # Read user data from the JSON file
    try:
        with open(temp_json_path, 'r') as json_file:
            user_info = json.load(json_file)
            return user_info
    except json.JSONDecodeError as e:
        print(f"Error reading JSON file: {e}")
        return None
    except Exception as e:
        print(f"Failed to load user data: {e}")
        return None

# Example usage
user_data = read_user_data_from_temp_json()
if user_data:
    print("User data loaded successfully:", user_data)
else:
    print("Failed to load user data.")

# Function to display QR code with additional UI elements
def display_qr_code(qr_img):
    detail_window = tk.Toplevel()
    detail_window.title("QR Code for Payment")
    detail_window.protocol("WM_DELETE_WINDOW", lambda: on_close(detail_window))
    
    # Message above the QR code
    tk.Label(detail_window, text="Scan QR code to pay for usage", font=("Helvetica", 14)).pack(pady=10)
    
    # Displaying the QR code
    photo_image = ImageTk.PhotoImage(qr_img)
    qr_label = tk.Label(detail_window, image=photo_image)
    qr_label.image = photo_image  # Keep a reference
    qr_label.pack(pady=20)
    
    # Submit usage and proceed button
    proceed_button = tk.Button(detail_window, text="Submit Usage and Proceed", command=lambda: on_close(detail_window))
    proceed_button.pack(pady=10)

    detail_window.mainloop()

# Function to handle closing behavior
def on_close(window):
    logger.info("Usage submitted. Proceeding to the ending page.")
    window.destroy()
    open_ending_screen()


def open_ending_screen():
    ending_script = os.path.join(script_dir, "ending_window.py")
    subprocess.Popen([sys.executable, ending_script])

# Example variables - replace these with actual data/logic to gather the values
user_data = {}  # Populate this dictionary with actual user data
material_name = "Example Material"
station = user_data.get('station', 'Unknown')  # Example; replace with actual logic to determine station
usage_amount = 1.5  # Example; replace with actual logic to determine usage amount
unit = "Example Unit"


# Assuming script_dir is defined somewhere in your script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define the log_usage_to_csv function
def log_usage_to_csv(first_name, last_name, permission, station, usage, usage_unit):
    csv_log_file = 'SessionLog.csv'  # Example file name, adjust as needed
    csv_file_path = os.path.join(script_dir, csv_log_file)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Ensure the directory for the CSV file exists
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
    
    # Write to CSV
    try:
        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # Write headers if the file is new
            if os.path.getsize(csv_file_path) == 0:
                writer.writerow(["Timestamp", "Action", "First Name", "Last Name", "Permission", "Station", "Usage", "Usage Unit"])
            # Write the usage data
            writer.writerow([timestamp, "Usage", first_name, last_name, permission, station,"", usage, usage_unit])
    except Exception as e:
        print(f"Failed to log usage data: {e}")




# Main script execution
if __name__ == "__main__":
    if require_usage_input:
        material_data = fetch_material_data(material_id)
        if material_data:
            # Hide the root window immediately after creation
            root = tk.Tk()
            root.withdraw()
            
            # Ask user for the amount of usage
            usage_amount = simpledialog.askinteger("Usage Input", f"Enter the amount of {usage_unit} used:", parent=root)
            if usage_amount is not None:
                material_name = material_data['materials'][0]['material']['label']  # Example: Adjust according to your data structure
                unit = usage_unit  # From your config or however you define it# Assuming 'material_data' has the necessary information to construct the PayPal URL
                usage = math.ceil(usage_amount)
                log_usage_to_csv(user_data.get('first_name', 'Unknown'), user_data.get('last_name', 'Unknown'), user_data.get('permission', 'Unknown'), station, usage, unit)

                # Ensure to round up the usage_amount to the nearest whole number
                rounded_usage_amount = math.ceil(usage_amount)

                # Construct PayPal URL with the rounded quantity
                paypal_base_url = material_data['materials'][0]['material']['purchase'] # Ensure this key exists and is correct
                paypal_url_with_quantity = f"{paypal_base_url}&quantity={rounded_usage_amount}"

                # Create QR code with the updated PayPal URL
                qr_img = create_qr_code(paypal_url_with_quantity)

                # Display QR code in a new window without creating an empty root window
                display_qr_code(qr_img)
                
                # Destroy the hidden root window after displaying QR code window
                root.destroy()
            else:
                logger.error("Usage input was cancelled or invalid.")
                # Ensure the root window is destroyed even if no usage amount is entered
                root.destroy()
        else:
            logger.error("Material data could not be fetched.")