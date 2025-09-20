#!/usr/bin/env python3
# API Notifier for Asterisk Call Events
# This script sends HTTP notifications to an API for important call events

import requests
import sys
import json
import os
import time
from datetime import datetime

# Configuration
API_URL = "https://your-crm-domain.com/api/asterisk/call-event/"  # Update with your actual CRM domain
API_KEY = "your-api-key-here"                          # Update with your actual API key
ENABLE_LOGGING = True
LOG_FILE = "/var/log/asterisk/api_notifications.log"

def log_message(message):
    """Log a message to the log file if logging is enabled."""
    if ENABLE_LOGGING:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, 'a') as log:
            log.write(f"{timestamp} - {message}\n")

def send_notification(event_type, call_data):
    """
    Send a notification to the API.
    
    Parameters:
    - event_type: The type of event (customer_answer, customer_dtmf, agent_answer, call_end)
    - call_data: Dictionary containing call details
    
    Returns:
    - True if the notification was sent successfully, False otherwise
    """
    
    # Add standard fields
    payload = {
        "event_type": event_type,
        "timestamp": int(time.time()),
        "call_data": call_data
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    try:
        log_message(f"Sending {event_type} notification with data: {json.dumps(call_data)}")
        response = requests.post(API_URL, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            log_message(f"Successfully sent {event_type} notification. Response: {response.text}")
            return True
        else:
            log_message(f"Failed to send {event_type} notification. Status code: {response.status_code}. Response: {response.text}")
            return False
            
    except Exception as e:
        log_message(f"Error sending {event_type} notification: {str(e)}")
        return False

def main():
    """Main function to handle CLI arguments and send the appropriate notification."""
    if len(sys.argv) < 3:
        log_message("Usage: api_notifier.py <event_type> <uniqueid> [additional params]")
        return 1
    
    event_type = sys.argv[1]
    uniqueid = sys.argv[2]
    
    # Base call data that all events will include
    call_data = {
        "uniqueid": uniqueid
    }
    
    # Process additional arguments based on event type
    if event_type == "call_initiated":
        if len(sys.argv) >= 4:
            call_data["customer_number"] = sys.argv[3]
            call_data["call_direction"] = sys.argv[4] if len(sys.argv) >= 5 else "outbound"
    
    elif event_type == "customer_answer":
        if len(sys.argv) >= 4:
            call_data["customer_number"] = sys.argv[3]
    
    elif event_type == "customer_hung_up_pre_ivr":
        if len(sys.argv) >= 4:
            call_data["customer_number"] = sys.argv[3]
    
    elif event_type == "customer_dtmf":
        if len(sys.argv) >= 5:
            call_data["customer_number"] = sys.argv[3]
            call_data["digit_pressed"] = sys.argv[4]
    
    elif event_type == "customer_entered_queue":
        if len(sys.argv) >= 5:
            call_data["customer_number"] = sys.argv[3]
            call_data["queue_extension"] = sys.argv[4]
    
    elif event_type == "customer_hung_up_in_queue":
        if len(sys.argv) >= 5:
            call_data["customer_number"] = sys.argv[3]
            call_data["duration"] = sys.argv[4]
    
    elif event_type == "agent_answer":
        if len(sys.argv) >= 5:
            call_data["customer_number"] = sys.argv[3]
            call_data["agent_number"] = sys.argv[4]
    
    elif event_type == "call_end":
        if len(sys.argv) >= 6:
            call_data["customer_number"] = sys.argv[3]
            call_data["agent_number"] = sys.argv[4]
            call_data["duration"] = sys.argv[5]
    
    # Additional failure status types
    elif event_type in ["customer_busy", "customer_no_answer", "call_rejected", "call_failed"]:
        if len(sys.argv) >= 4:
            call_data["customer_number"] = sys.argv[3]
    
    send_notification(event_type, call_data)
    return 0

if __name__ == "__main__":
    sys.exit(main())
