# Asterisk Integration for CRM

This documentation provides details on how to integrate Asterisk with the CRM system for automatic call campaigns.

## Overview

The CRM system integrates with Asterisk through a webhook API that handles various call events. The API receives event notifications from Asterisk and updates the call status in the CRM database accordingly.

## Files in this Package

1. `asterisk_webhook_api.md` - Complete API documentation
2. `asterisk_api_notifier.py` - Python script to be installed on the Asterisk server
3. `asterisk_dialplan_example.conf` - Example Asterisk dialplan configuration

## Setup Instructions

### 1. CRM Server Setup

The CRM server is already configured to handle incoming webhook requests from Asterisk. All call events should be sent to:

```
https://your-crm-domain.com/api/asterisk/call-event/
```

### 2. Asterisk Server Setup

1. Copy the `asterisk_api_notifier.py` script to your Asterisk server
   - Recommended location: `/usr/local/bin/`
   - Make it executable: `chmod +x /usr/local/bin/asterisk_api_notifier.py`

2. Edit the script to set the correct API URL and API key:
   ```python
   API_URL = "https://your-crm-domain.com/api/asterisk/call-event/"
   API_KEY = "your-api-key-here"
   ```

3. Create a log directory:
   ```bash
   mkdir -p /var/log/asterisk
   chown asterisk:asterisk /var/log/asterisk
   ```

4. Modify your Asterisk dialplan to call the API notifier script at appropriate points
   - See `asterisk_dialplan_example.conf` for examples

### 3. Testing the Integration

1. Make a test call using the Asterisk CLI:
   ```
   asterisk -rx "channel originate SIP/test_extension application Playback hello-world"
   ```

2. Check the API notifier logs:
   ```
   tail -f /var/log/asterisk/api_notifications.log
   ```

3. Check the CRM logs for incoming webhook events

## Event Types

The following event types are supported by the API:

1. `call_initiated` - When a call is first initiated (Status: calling)
2. `customer_answer` - When a customer answers the call (Status: answered)
3. `customer_hung_up_pre_ivr` - When a customer hangs up before IVR (Status: answered_no_ivr)
4. `customer_dtmf` - When a customer presses a key during IVR (Status maintained)
5. `customer_entered_queue` - When a customer enters a queue (Status: in_queue)
6. `customer_hung_up_in_queue` - When a customer hangs up while in queue (Status: hung_up_in_queue)
7. `agent_answer` - When an agent answers the call (Status maintained, agent assigned)
8. `call_end` - When the call ends completely (Status: answered_ivr)
9. Failure status types:
   - `customer_busy` (Status: busy)
   - `customer_no_answer` (Status: not_answered)
   - `call_rejected` (Status: failed)
   - `call_failed` (Status: failed)

See `asterisk_webhook_api.md` for detailed API documentation.

## Troubleshooting

1. **Webhook not receiving events**
   - Check network connectivity between Asterisk and CRM servers
   - Verify API key is correct
   - Check firewall settings

2. **Events not updating CRM**
   - Make sure `uniqueid` in events matches `queue_session_id` in CRM
   - Check that phone numbers are formatted consistently

3. **Missing call data**
   - Verify all required Asterisk dialplan triggers are in place
   - Check the API notifier script logs

## Support

For issues with this integration, please contact the system administrator.
