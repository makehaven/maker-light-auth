import tkinter as tk
from tkinter import ttk
import webbrowser
import requests
import qrcode
from PIL import Image, ImageTk
import configparser
import os

def show_ending_window(custom_message, show_experience_scale, tool_numerical_id):
    try:
        window = tk.Tk()
        window.title("Session Ended")

        # Custom Message
        if custom_message:
            print("Displaying custom message...")
            tk.Label(window, text=custom_message, font=("Helvetica", 14), pady=10).pack()

        # Consumables Section (simplified for this example)
        print("Fetching consumables...")
        materials = fetch_consumables(tool_numerical_id)
        if materials:
            tk.Label(window, text="Materials Used:", font=("Helvetica", 12), pady=5).pack()
        for material in materials:
            label = material["material"]["label"]
            purchase_link = material["material"]["purchase"]
            print(f"Displaying QR for {label}")

            # Simplified QR code generation and display
            qr = qrcode.make(purchase_link)
            qr_image = ImageTk.PhotoImage(qr)
            qr_label = ttk.Label(window, image=qr_image)
            qr_label.image = qr_image  # keep a reference!
            qr_label.pack(pady=5)

            button = tk.Button(window, text=label, command=lambda link=purchase_link: webbrowser.open(link))
            button.pack()

        print("Showing window...")
        window.mainloop()
    except Exception as e:
        print(f"Error: {e}")

def fetch_consumables(tool_numerical_id):
    # Simplified to return dummy data for testing
    return [{
        "material": {
            "label": "Test Material",
            "purchase": "https://example.com"
        }
    }]

if __name__ == "__main__":
    show_ending_window("Thank you for using the workstation.", True, 424)
