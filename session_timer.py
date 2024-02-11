import tkinter as tk
import time
import datetime
import os
import csv
import configparser
import subprocess
import sys
from ending_window import show_ending_window

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.txt')
config.read(config_path)

log_file_path = config.get('Logging', 'log_file_path', fallback=os.path.join(os.path.dirname(os.path.abspath(__file__)), "SessionLog.txt"))

class SessionTimerWindow:
    def __init__(self, user_info=None, log_file_path=log_file_path):
        self.log_file_path = log_file_path  # Store the log file path
        if user_info is None:
            user_info = {'first_name': 'Unregistered', 'last_name': 'User'}
        self.user_info = user_info
        self.root = tk.Tk()
        
        # Remove the standard title bar and make the window always on top
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        
        # Define window size
        window_width = 200
        window_height = 60

        # Custom title bar with user's name
        self.title_bar = tk.Frame(self.root, bg="lightgray", relief="raised", bd=0)
        self.title_bar.pack(fill=tk.X)
        self.title_label = tk.Label(self.title_bar, bg="lightgray", text=f"User: {user_info['first_name']} {user_info['last_name']}", font=("Helvetica", 10))
        self.title_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)  # Ensure label fills the frame for consistent dragging

        # Make the window draggable by binding to both the title bar and the label
        self.draggable_elements = [self.title_bar, self.title_label]
        for element in self.draggable_elements:
            element.bind("<Button-1>", self.start_move)
            element.bind("<ButtonRelease-1>", self.stop_move)
            element.bind("<B1-Motion>", self.do_move)
        
        # Get screen width and height for positioning
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Calculate position for bottom right corner
        position_right = screen_width - window_width
        position_bottom = screen_height - window_height

        # Position the window in the bottom right corner of the screen
        self.root.geometry(f"{window_width}x{window_height}+{position_right}+{position_bottom}")
        
        self.setup_ui()
        self.start_time = time.time()
        self.update_timer()
        
       
    def setup_ui(self):
        # Timer label with larger font size
        self.timer_label = tk.Label(self.root, text="00:00:00", font=("Helvetica", 16))
        self.timer_label.pack(side=tk.LEFT, padx=(5, 10))
        
        # End session button
        self.end_session_btn = tk.Button(self.root, text="End Session", command=self.end_session,
                                 bg='#D35F5F', fg='white', font=('Helvetica', 10, 'bold'),
                                 relief='flat', bd=1)
        self.end_session_btn.pack(side=tk.RIGHT, padx=5)
      

    def update_timer(self):
        if self.root:  # Check if the root window exists
            elapsed_time = time.time() - self.start_time
            formatted_time = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
            self.timer_label.config(text=formatted_time)
            self.after_id = self.root.after(1000, self.update_timer) 

    def end_session(self):
        if hasattr(self, 'after_id'):
            self.root.after_cancel(self.after_id)

        # Log session end
        end_time = time.time()
        session_duration = end_time - self.start_time
        duration_str = str(datetime.timedelta(seconds=int(session_duration)))
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        log_entry = [timestamp, "end", self.user_info['first_name'], self.user_info['last_name'], self.user_info.get('permission', 'N/A'), self.user_info.get('station', 'N/A'), duration_str]
        with open(self.log_file_path.replace('.txt', '.csv'), 'a', newline='') as csvfile:
            csv.writer(csvfile).writerow(log_entry)
        with open(self.log_file_path, 'a') as logfile:
            logfile.write(f"{timestamp} - Session end. Duration: {duration_str}.\n")

        # Destroy the current window
        self.root.destroy()

        # Directly call the ending window script without passing parameters
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ending_window_script_path = os.path.join(script_dir, "ending_window.py")
        subprocess.Popen([sys.executable, ending_window_script_path])


    def start_move(self, event):
        self.root.x = event.x
        self.root.y = event.y

    def stop_move(self, event):
        self.root.x = None
        self.root.y = None

    def do_move(self, event):
        deltax = event.x - self.root.x
        deltay = event.y - self.root.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    user_info = {
        'first_name': 'Test',
        'last_name': 'User',
        'permission': config.get('Login', 'tool_id'),
        'station': config.get('Station', 'workstation_id')
    }
    session_window = SessionTimerWindow(user_info, log_file_path)
    session_window.run()

