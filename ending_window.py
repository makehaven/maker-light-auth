import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import requests
from PIL import Image, ImageTk
import qrcode
import os
import subprocess
import sys
import json
import csv
from datetime import datetime
import utils
from drupal_client import DrupalClient

window = None

root = tk.Tk()
root.withdraw()

# Load configuration
config = utils.load_config()
drupal_client = DrupalClient(config)
log_file_path, csv_log_file_path = utils.get_log_file_paths(config)

show_ending_window_flag = config.getboolean('EndingPage', 'show_ending_window', fallback=False)
show_experience_scale = config.getboolean('EndingPage', 'show_experience_scale', fallback=False)
end_message = config.get('EndingPage', 'end_message', fallback="Thank you for using the station.")
experience_question = config.get('EndingPage', 'experience_question', fallback="How was your experience?")
high_label = config.get('EndingPage', 'high_label', fallback="Excellent")
low_label = config.get('EndingPage', 'low_label', fallback="Poor")
tool_numerical_id = config.get('Station', 'tool_numerical_id', fallback="0")

utils.initialize_csv_log_file(csv_log_file_path, ["Timestamp", "Action", "First Name", "Last Name", "Permission", "Station", "Duration", "Rating", "Comments"])

def restart_authentication():
    global window
    if window is not None:
        try:
            window.destroy()
        except tk.TclError as e:
            print(f"Error closing window: {e}")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "maker-light-auth.pyw")
    subprocess.Popen([sys.executable, script_path])
    sys.exit()

def safe_destroy(window):
    try:
        if window.winfo_exists():
            window.destroy()
    except Exception as e:
        print("Error closing window:", e)

def open_url_new_window(url):
    try:
        webbrowser.open_new(url)
    except Exception as e:
        print(f"Failed to open URL in a new browser window: {e}")

def log_event_with_comments(action, rating, comments, user_info=None):
    if user_info is None:
        user_info = {}
    utils.log_session_event(action, user_info, config, rating=rating, comments=comments)

def show_ending_window_func(end_message, show_experience_scale, tool_numerical_id, experience_question, high_label, low_label, user_info):
    global window
    if window:
        safe_destroy(window)
    window = tk.Toplevel(root)
    window.title("Session Ended")
    window.attributes("-topmost", True)
    window.overrideredirect(True)
    window.geometry("{0}x{1}+0+0".format(window.winfo_screenwidth(), window.winfo_screenheight()))

    window.grid_rowconfigure(1, weight=1)
    window.grid_columnconfigure(0, weight=1)

    tk.Label(window, text=end_message, font=("Helvetica", 18), pady=20).pack()

    if show_experience_scale:
        rating_frame = tk.LabelFrame(window, text=experience_question, font=("Helvetica", 14))
        rating_frame.pack(pady=10)

        def rate_experience(score):
            comment_window = tk.Toplevel(window)
            comment_window.title("Additional Comments")
            comment_window.geometry("400x200")
            comment_window.attributes("-topmost", True)

            rating_display = f"Your rating: {score}/5"
            tk.Label(comment_window, text=rating_display, font=("Helvetica", 12)).pack(pady=(10, 5))

            tk.Label(comment_window, text="Any comments on your experience?", font=("Helvetica", 12)).pack(pady=(5, 10))
            comment_text = tk.Text(comment_window, height=4, width=40)
            comment_text.pack(pady=(0, 20))

            def submit_comments():
                comments = comment_text.get("1.0", "end-1c")
                log_event_with_comments("rating", score, comments, user_info)
                comment_window.destroy()

            submit_btn = tk.Button(comment_window, text="Submit", command=submit_comments)
            submit_btn.pack()

            for btn in rating_buttons:
                btn.config(state=tk.DISABLED)

        rating_buttons = []
        colors = ["#ff4d4d", "#ff9999", "#ffff99", "#99ff99", "#00cc00"]
        tk.Label(rating_frame, text=low_label, font=("Helvetica", 12)).pack(side=tk.LEFT, padx=5)
        for i, color in enumerate(colors, start=1):
            btn = tk.Button(rating_frame, text=str(i), bg=color, command=lambda i=i: rate_experience(i), font=("Helvetica", 12), width=2)
            btn.pack(side=tk.LEFT, padx=2)
            rating_buttons.append(btn)
        tk.Label(rating_frame, text=high_label, font=("Helvetica", 12)).pack(side=tk.LEFT, padx=5)

    consumables_frame_outer = tk.Frame(window, padx=20)
    consumables_frame_outer.pack(padx=100, pady=20)

    consumables_frame = tk.LabelFrame(consumables_frame_outer, text="Materials for purchase", font=("Helvetica", 14))
    consumables_frame.pack(fill="both", expand=True)

    column_count = 2
    materials = drupal_client.fetch_consumables(tool_numerical_id)

    for index, material in enumerate(materials):
        label = f"{material['label']} - {material['unit']} - ${material['cost']}"
        row = index // column_count
        column = index % column_count

        button = ttk.Button(
            consumables_frame,
            text=label,
            style="Material.TButton",
            command=lambda m=material: open_payment_link(m),
        )
        button.grid(row=row, column=column, padx=5, pady=5, sticky="ew")

    style = ttk.Style()
    style.configure("Material.TButton", font=("Helvetica", 14))

    for i in range(column_count):
        consumables_frame.grid_columnconfigure(i, weight=1)

    reset_station_frame = tk.LabelFrame(window, text="Reset station for next user", font=("Helvetica", 14), padx=10, pady=10)
    reset_station_frame.pack(pady=20, padx=20, fill="both", expand=True)

    button_frame = tk.Frame(reset_station_frame)
    button_frame.pack(expand=True)

    btn_left_open = tk.Button(button_frame, text="Not me (reset to login)", command=lambda: [log_event("not_me", "", user_info), safe_destroy(window), restart_authentication()], bg="#add8e6", fg="black", font=("Helvetica", 12))
    btn_left_open.pack(side=tk.BOTTOM, pady=(10, 0))

    btn_no_charges = tk.Button(button_frame, text="Nothing Due", command=lambda: [log_event("nothing_due", "", user_info), safe_destroy(window), restart_authentication()], bg="#add8e6", fg="black", font=("Helvetica", 12))
    btn_no_charges.pack(side=tk.LEFT, padx=10, expand=True)

    btn_submitted_payments = tk.Button(button_frame, text="I paid", command=lambda: [log_event("payment_submitted", "", user_info), safe_destroy(window), restart_authentication()], bg="#98fb98", fg="black", font=("Helvetica", 12))
    btn_submitted_payments.pack(side=tk.RIGHT, padx=10, expand=True)

    window.mainloop()

def open_payment_link(material):
    detail_window = tk.Toplevel()
    detail_window.title(material['label'])
    detail_window.attributes("-topmost", True)

    try:
        image_src = material['image'].split('src="')[1].split('"')[0]
        image_url = f"https://www.makehaven.org{image_src}"
        image_response = requests.get(image_url, stream=True)
        image_response.raw.decode_content = True
        material_image = Image.open(image_response.raw)

        base_height = 100
        img_ratio = base_height / float(material_image.size[1])
        new_width = int((float(material_image.size[0]) * float(img_ratio)))
        material_image = material_image.resize((new_width, base_height), Image.LANCZOS)

        photo_image = ImageTk.PhotoImage(material_image)
        img_label = tk.Label(detail_window, image=photo_image)
        img_label.image = photo_image
        img_label.pack(pady=10)
    except Exception as e:
        print(f"Failed to load image: {e}")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(material['purchase'])
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGB')

    qr_img_resized = qr_img.resize((100, 100), Image.LANCZOS)
    qr_photo = ImageTk.PhotoImage(image=qr_img_resized)
    qr_label = tk.Label(detail_window, image=qr_photo)
    qr_label.image = qr_photo
    qr_label.pack(pady=10)

    material_info = f"{material['label']}\nUnit: {material['unit']}\nPrice: ${material['cost']}"
    tk.Label(detail_window, text=material_info, font=("Helvetica", 12)).pack()

    detail_window.mainloop()

def log_event(action, rating, user_info=None):
    if user_info is None:
        user_info = {}
    utils.log_session_event(action, user_info, config, rating=rating)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_info_path = sys.argv[1]
        try:
            with open(user_info_path, 'r') as f:
                user_info = json.load(f)
            os.remove(user_info_path)
        except Exception as e:
            print(f"Error loading user info: {e}")
            user_info = {'first_name': 'Unknown', 'last_name': 'Unknown'}
    else:
        user_info = {'first_name': 'Unknown', 'last_name': 'Unknown'}

    show_ending_window_func(end_message, show_experience_scale, tool_numerical_id, experience_question, high_label, low_label, user_info)
