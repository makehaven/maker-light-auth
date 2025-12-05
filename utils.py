import os
import configparser
import csv
import datetime
from graylog_logging import get_graylog_logger, log_user_action

def load_config(config_path=None):
    """Loads the configuration from the specified path or default location."""
    if config_path is None:
        base_path = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_path, 'config.ini')

    config = configparser.ConfigParser()
    config.read(config_path)
    return config

def get_log_file_paths(config):
    """Determines log file paths from configuration."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file_name = "SessionLog.txt"
    log_file_path = config.get('Logging', 'log_file_path', fallback=os.path.join(script_dir, log_file_name))
    csv_log_file_path = log_file_path.replace('.txt', '.csv')
    return log_file_path, csv_log_file_path

def initialize_csv_log_file(csv_log_file_path, headers=None):
    """Initializes the CSV log file with headers if it doesn't exist."""
    if headers is None:
        headers = ["Timestamp", "Action", "First Name", "Last Name", "Permission", "Station", "Duration", "Rating", "Comments"]

    if not os.path.exists(csv_log_file_path):
        try:
            with open(csv_log_file_path, 'w', newline='') as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerow(headers)
        except IOError as e:
            print(f"Error initializing CSV log file: {e}")

def log_session_event(action, user_info, config, duration="", rating="", comments=""):
    """Logs a session event to Text, CSV, and Graylog."""
    log_file_path, csv_log_file_path = get_log_file_paths(config)

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Ensure user_info has defaults
    first_name = user_info.get('first_name', 'Unknown')
    last_name = user_info.get('last_name', 'User')
    permission = user_info.get('permission', 'N/A')
    station = user_info.get('station', 'N/A')

    # CSV Logging
    row = [timestamp, action, first_name, last_name, permission, station, duration, rating, comments]
    try:
        with open(csv_log_file_path, 'a', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(row)
    except IOError as e:
        print(f"Error writing to CSV log: {e}")

    # Text Logging
    try:
        with open(log_file_path, 'a') as logfile:
            logfile.write(f"{timestamp} - Session {action} for {first_name} {last_name}.\n")
    except IOError as e:
        print(f"Error writing to text log: {e}")

    # Graylog Logging
    graylog_enabled = config.getboolean('Graylog', 'enabled', fallback=False)
    if graylog_enabled:
        graylog_logger = get_graylog_logger() # This reads config internally, might be better to pass config or host/port
        if graylog_logger:
             log_user_action(action, user_info, graylog_logger, extra_fields={'timestamp': timestamp})
