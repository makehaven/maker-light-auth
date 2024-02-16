import tkinter as tk
import time
import datetime
import os
import csv
import configparser
import subprocess
import sys
import json

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
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
        
        # Correction: Define drag start position
        self._drag_start_x = None
        self._drag_start_y = None


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
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
       
    def setup_ui(self):
        # Timer label with larger font size
        self.timer_label = tk.Label(self.root, text="00:00:00", font=("Helvetica", 16))
        self.timer_label.pack(side=tk.LEFT, padx=(5, 10))
        
        # End session button
        self.end_session_btn = tk.Button(self.root, text="End Session", command=self.end_session,
                                 bg='#D35F5F', fg='white', font=('Helvetica', 10, 'bold'),
                                 relief='flat', bd=1)
        self.end_session_btn.pack(side=tk.RIGHT, padx=5)

        pass
    
    def on_closing(self):
    # 
        pass

    def update_timer(self):
        if self.root:  # Check if the root window exists
            elapsed_time = time.time() - self.start_time
            formatted_time = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
            self.timer_label.config(text=formatted_time)
            self.after_id = self.root.after(1000, self.update_timer) 

            pass

    def end_session(self):
        if hasattr(self, 'after_id'):
            self.root.after_cancel(self.after_id)

        # Log session end
        end_time = time.time()
        session_duration = end_time - self.start_time
        duration_str = str(datetime.timedelta(seconds=int(session_duration)))
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Log entry for CSV
        log_entry = [timestamp, "end", self.user_info['first_name'], self.user_info['last_name'], self.user_info.get('permission', 'N/A'), self.user_info.get('station', 'N/A'), duration_str]
        with open(self.log_file_path.replace('.txt', '.csv'), 'a', newline='') as csvfile:
            csv.writer(csvfile).writerow(log_entry)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        user_info_path = os.path.join(script_dir, "user_info_temp.json")

        # Save user_info to a temporary JSON file for the next scripts to use
        with open(user_info_path, 'w') as file:
            json.dump(self.user_info, file)

        require_usage_input = config.getboolean('UsageInput', 'require_usage_input', fallback=False)

        # Determine the next script to call based on require_usage_input
        next_script_path = os.path.join(script_dir, "usage_input.py") if require_usage_input else os.path.join(script_dir, "ending_window.py")
        
        # Call the determined script, passing the path to the user_info JSON
        subprocess.Popen([sys.executable, next_script_path, user_info_path])
        
        self.root.destroy()  # Close the timer window


    def start_move(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def stop_move(self, event):
        self._drag_start_x = None
        self._drag_start_y = None

    def do_move(self, event):
        if self._drag_start_x is not None and self._drag_start_y is not None:
            deltax = event.x - self._drag_start_x
            deltay = event.y - self._drag_start_y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
    config.read(config_path)

    permission_id = config.get('Login', 'permission_id', fallback='default_permission_id')
    workstation_id = config.get('Station', 'workstation_id', fallback='default_workstation_id')

    user_info = {
        'first_name': 'Unknown',
        'last_name': 'Unknown',
        'permission': permission_id,
        'station': workstation_id
    }

    session_window = SessionTimerWindow(user_info=user_info)

    if session_window.root.winfo_exists():
        session_window.root.protocol("WM_DELETE_WINDOW", session_window.on_closing)

    session_window.run()