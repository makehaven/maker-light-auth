# graylog_logging.py
import configparser
import logging
import graypy

def get_graylog_logger(config_path='config.ini'):
    # Load configuration
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Check if 'Graylog' section exists
    if 'Graylog' not in config.sections():
        print("Graylog section not found in the configuration.")
        return None

    graylog_host = config.get('Graylog', 'server_ip', fallback=None)
    graylog_port = config.getint('Graylog', 'server_port', fallback=12201)
    
    if not graylog_host:  # Graylog is not set up
        print("Graylog server IP not configured.")
        return None

    logger = logging.getLogger('graylog_logger')
    logger.setLevel(logging.INFO)
    handler = graypy.GELFUDPHandler(graylog_host, graylog_port)
    logger.addHandler(handler)
    return logger

def log_user_action(action, user_info, graylog_logger=None, extra_fields=None):
    if graylog_logger:
        # Default log message structure
        log_message = {
            'first_name': user_info.get('first_name', 'Unknown'),
            'last_name': user_info.get('last_name', 'Unknown'),
            'permission': user_info.get('permission', 'N/A'),
            'station': user_info.get('station', 'N/A'),
            'action': action
        }
        # Update log message with any additional fields provided
        if extra_fields:
            log_message.update(extra_fields)
        
        graylog_logger.info(f'User action: {action}', extra=log_message)