import tkinter as tk
import time
import datetime
import os

# Default log file path in the same directory as the script
default_log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SessionLog.txt")

config = {}  # A dictionary to hold config values
with open("config.txt", 'r') as config_file:
    for line in config_file:
        key, value = line.strip().split('=', 1)
        config[key] = value

# Override the default log file path if specified in the config
log_file_path = config.get("log_file_path", default_log_file_path)

class SessionTimerWindow:
    def __init__(self, user_info=None, log_file_path=None):
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
        elapsed_time = time.time() - self.start_time
        formatted_time = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        self.timer_label.config(text=formatted_time)
        self.root.after(1000, self.update_timer)

    def end_session(self):
        # Calculate session duration
        end_time = time.time()
        session_duration_seconds = end_time - self.start_time
        session_duration = datetime.timedelta(seconds=int(session_duration_seconds))
    
        # Format the duration as HH:MM:SS
        formatted_duration = str(session_duration)
    
        # Current timestamp for logging
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
        # Directly use the provided first name and last name without modification
        full_name = f"{self.user_info.get('first_name', 'Unknown')} {self.user_info.get('last_name', 'User')}"
    
        # Prepare log entry for session end
        log_entry = f"{timestamp} - Session end for {full_name}. Duration: {formatted_duration}.\n"
    
        # Write log entry to file
        with open(self.log_file_path, 'a') as log_file:
           log_file.write(log_entry)
    
        print(f"Session ended for {full_name}. Duration: {formatted_duration}.")  # Optional: Confirmation message in console
        self.root.destroy()


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
    user_info = {'first_name': 'Test', 'last_name': 'User'}
    session_window = SessionTimerWindow(user_info, log_file_path)
    session_window.run()

