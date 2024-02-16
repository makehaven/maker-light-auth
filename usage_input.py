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

# Configuration and Logging Setup
config = configparser.ConfigParser()
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, 'config.ini')
config.read(config_path)

logger.add("debug.log", format="{time} {level} {message}", level="DEBUG")

# Configuration Settings
require_usage_input = config.getboolean('UsageInput', 'require_usage_input', fallback=True)
usage_unit = config.get('UsageInput', 'usage_unit', fallback="minutes")
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

def log_usage_to_csv(user_info_path, usage, usage_unit):
    # Assuming user_info_path is the path to the JSON file containing user data
    try:
        with open(user_info_path, 'r') as f:
            user_data = json.load(f)  # Load and parse the JSON data into a dictionary
    except Exception as e:
        print(f"Failed to load user data: {e}")
        return  # Exit the function if user data could not be loaded

    # Continue with your logging logic
    csv_log_file = config.get('Logging', 'csv_log_file', fallback='usage_log.csv')
    csv_file_path = os.path.join(script_dir, csv_log_file)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Extract user information from user_data
    first_name = user_data.get("first_name", "Unknown")
    last_name = user_data.get("last_name", "Unknown")
    permission = user_data.get("permission", "Unknown")
    station = user_data.get("station", "Unknown")

    # Ensure the CSV file directory exists
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
    
    with open(csv_file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Check if file is empty to write headers
        if os.path.getsize(csv_file_path) == 0:
            writer.writerow(["Timestamp", "Action", "First Name", "Last Name", "Permission", "Station", "Duration", "Rating", "Comments", "Usage", "Usage Unit"])
        # Log the usage data
        writer.writerow([timestamp, "Usage", first_name, last_name, permission, station, "N/A", "N/A", "N/A", usage, usage_unit])

# Example usage
user_info_path = 'path_to_user_info.json'  # Update this path as needed
usage = 5  # Example usage amount
usage_unit = 'hours'  # Example usage unit
log_usage_to_csv(user_info_path, usage, usage_unit)

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
                log_usage_to_csv(material_name, unit, math.ceil(usage_amount)) 
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