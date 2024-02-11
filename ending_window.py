import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import requests
from PIL import Image, ImageTk
import qrcode
import configparser
import os
import subprocess
import sys

window = None

# Determine the directory of your script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Build the path to the configuration file
config_path = os.path.join(script_dir, 'config.txt')

# Load configuration
config = configparser.ConfigParser()
config.read(config_path)

# Nconfiguration values 
show_ending_window = config.getboolean('EndingPage', 'show_ending_window', fallback=False)
end_message = config.get('EndingPage', 'end_message', fallback="Please remember to clean up.")
show_experience_scale = config.getboolean('EndingPage', 'show_experience_scale', fallback=False)
api_material_url = config.get('EndingPage', 'api_material_url', fallback="https://default-url.com/materials")
experience_question = config.get('EndingPage', 'experience_question', fallback="How was your experience?")
high_label = config.get('EndingPage', 'high_label', fallback="Excellent")
low_label = config.get('EndingPage', 'low_label', fallback="Poor")


def restart_authentication():
    global window
    try:
        if window is not None:
            window.destroy()
            window = None  # Ensure to clear the reference
    except tk.TclError:
        print("Window was already destroyed.")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "maker-light-auth.py")
    subprocess.Popen([sys.executable, script_path])
    sys.exit() 

def show_ending_window(custom_message, show_experience_scale, tool_numerical_id, experience_question, excellent_label, low_label):
    global window
    window = tk.Tk()
    window.title("Session Ended")
    window.geometry("800x600")  # Adjusted window size for better content visibility

    # Layout configurations
    window.grid_rowconfigure(1, weight=1)
    window.grid_columnconfigure(0, weight=1)

    # Custom Message
    tk.Label(window, text=custom_message, font=("Helvetica", 18), pady=20).pack()

    # Rating Scale
    rating_frame = tk.LabelFrame(window, text=experience_question, font=("Helvetica", 14))
    rating_frame.pack(pady=10)

    def rate_experience(score):
        messagebox.showinfo("Rating", f"You rated {score}/5")
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

    # Consumables Section
    consumables_frame = tk.LabelFrame(window, text="Materials Used", font=("Helvetica", 14))
    consumables_frame.pack(fill="both", expand="yes", padx=20, pady=10)

    # Dummy data for materials
    materials = fetch_consumables(tool_numerical_id)
    for material in materials:
        material_button = ttk.Button(consumables_frame, text=f"{material['label']} - {material['unit']} - ${material['cost']}", command=lambda link=material['purchase']: webbrowser.open(link))
        material_button.pack(pady=5, fill="x")

    # Control Buttons
    button_frame = tk.Frame(window)
    button_frame.pack(pady=20)
    tk.Button(button_frame, text="I did not incur any charges", command=window.destroy, bg="#f0f0f0", font=("Helvetica", 12)).pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="Someone left this open, I'm closing on their behalf", command=window.destroy, bg="#f0f0f0", font=("Helvetica", 12)).pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="I have submitted all payments", command=lambda: [window.destroy(), restart_authentication()], bg="#90ee90", font=("Helvetica", 12)).pack(side=tk.LEFT, padx=10)

    window.mainloop()

    # Display consumables with more details
    consumables_frame = tk.LabelFrame(window, text="Materials Used", font=("Helvetica", 14))
    consumables_frame.pack(fill="both", expand="yes", padx=20, pady=10)

    canvas = tk.Canvas(consumables_frame)
    scrollbar = ttk.Scrollbar(consumables_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    materials = fetch_consumables(tool_numerical_id)
    for material in materials:
        ttk.Button(scrollable_frame, text=material["label"], command=lambda m=material: open_payment_link(m)).pack(pady=2)


def open_payment_link(material):
    detail_window = tk.Toplevel()
    detail_window.title(material["label"])

    # Generate QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(material["purchase_link"])
    qr.make(fit=True)
    qr_img = qr.make_image(fill='black', back_color='white')
    img = ImageTk.PhotoImage(qr_img)
    qr_label = tk.Label(detail_window, image=img)
    qr_label.image = img  # keep reference to image
    qr_label.pack(pady=10)

    # Display Material Info
    material_info = f"{material['label']}\nUnit: {material['unit']}\nPrice: ${material['cost']}"
    tk.Label(detail_window, text=material_info, font=("Helvetica", 12)).pack(pady=10)

    # Buy Here Button
    ttk.Button(detail_window, text="Buy Here", command=lambda: webbrowser.open(material["purchase_link"])).pack()

    detail_window.mainloop()

    # Control Buttons
    button_frame = tk.Frame(window)
    button_frame.pack(pady=20)
    tk.Button(button_frame, text="I did not incur any charges", command=window.destroy, bg="#f0f0f0", font=("Helvetica", 12)).pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="Someone left this open, I'm closing on their behalf", command=window.destroy, bg="#f0f0f0", font=("Helvetica", 12)).pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="I have submitted all payments", command=lambda: [window.destroy(), restart_authentication()], bg="#90ee90", font=("Helvetica", 12)).pack(side=tk.LEFT, padx=10)

    detail_window.mainloop()

def fetch_consumables(tool_numerical_id):
    # Placeholder for actual fetch logic; returning dummy data for demonstration
    return [{
        "label": "Laserable Plywood",
        "unit": "12x12 inches",
        "cost": "5.00",
        "purchase": "https://example.com/plywood"
    }, {
        "label": "Acrylic Sheet",
        "unit": "24x24 inches",
        "cost": "10.00",
        "purchase": "https://example.com/acrylic"
    }]

if __name__ == "__main__":
    # Example usage
    custom_message = "Thank you for using the workstation. Please review any materials used."
    show_experience_scale = True
    tool_numerical_id = 424
    experience_question = "How was your experience today?"
    excellent_label = "Excellent"
    low_label = "Poor"
    show_ending_window(custom_message, show_experience_scale, tool_numerical_id, experience_question, high_label, low_label)

