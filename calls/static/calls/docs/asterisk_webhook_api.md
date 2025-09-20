# Asterisk Webhook API Documentation

This document describes how to integrate Asterisk with the CRM system using the webhook API.

## API Endpoint

All call events should be sent to:

```
/api/asterisk/call-event/
```

## Authentication

The API uses a Bearer token for authentication. Include the following header in all requests:

```
Authorization: Bearer YOUR_API_KEY
```

## Request Format

All requests must be sent as POST requests with a JSON body in the following format:

```json
{
  "event_type": "EVENT_TYPE",
  "timestamp": UNIX_TIMESTAMP,
  "call_data": {
    "uniqueid": "ASTERISK_CALL_UNIQUEID",
    "customer_number": "PHONE_NUMBER",
    ... additional fields depending on event type
  }
}
```

## Event Types and Call Statuses

**Call Statuses in CRM:**
- `waiting`: Call is waiting to be made
- `calling`: Call is in progress but not yet answered
- `answered`: Call was answered by customer (initial answer)
- `not_answered`: Call was not answered
- `answered_no_ivr`: Call was answered but customer did not go through IVR (call ended)
- `answered_ivr`: Call was answered and customer went through IVR (call ended)
- `busy`: Line was busy
- `failed`: Call failed for technical reasons or was rejected
- `in_queue`: Customer entered a call queue
- `hung_up_in_queue`: Customer hung up while waiting in queue

The API supports the following event types:

### 1. call_initiated

When a call is first initiated to a customer.

**Additional call_data fields:**
- `customer_number`: Customer's phone number
- `call_direction`: Either "inbound" or "outbound"

**Example:**
```json
{
  "event_type": "call_initiated",
  "timestamp": 1632150000,
  "call_data": {
    "uniqueid": "1632150000.123",
    "customer_number": "09123456789",
    "call_direction": "outbound"
  }
}
```

### 2. customer_answer

When a customer answers the call.

**Additional call_data fields:**
- `customer_number`: Customer's phone number

**Example:**
```json
{
  "event_type": "customer_answer",
  "timestamp": 1632150010,
  "call_data": {
    "uniqueid": "1632150000.123",
    "customer_number": "09123456789"
  }
}
```

### 3. customer_hung_up_pre_ivr

When a customer hangs up before going through the IVR system.

**Additional call_data fields:**
- `customer_number`: Customer's phone number

**Example:**
```json
{
  "event_type": "customer_hung_up_pre_ivr",
  "timestamp": 1632150020,
  "call_data": {
    "uniqueid": "1632150000.123",
    "customer_number": "09123456789"
  }
}
```

### 4. customer_dtmf

When a customer presses a key during the IVR prompt.

**Additional call_data fields:**
- `customer_number`: Customer's phone number
- `digit_pressed`: The DTMF digit pressed by the customer

**Example:**
```json
{
  "event_type": "customer_dtmf",
  "timestamp": 1632150030,
  "call_data": {
    "uniqueid": "1632150000.123",
    "customer_number": "09123456789",
    "digit_pressed": "1"
  }
}
```

### 5. customer_entered_queue

When a customer enters a queue waiting for an agent.

**Additional call_data fields:**
- `customer_number`: Customer's phone number
- `queue_extension`: The queue extension number

**Example:**
```json
{
  "event_type": "customer_entered_queue",
  "timestamp": 1632150040,
  "call_data": {
    "uniqueid": "1632150000.123",
    "customer_number": "09123456789",
    "queue_extension": "2000"
  }
}
```

### 6. customer_hung_up_in_queue

When a customer hangs up while waiting in the queue.

**Additional call_data fields:**
- `customer_number`: Customer's phone number
- `duration`: Duration of the call in seconds

**Example:**
```json
{
  "event_type": "customer_hung_up_in_queue",
  "timestamp": 1632150100,
  "call_data": {
    "uniqueid": "1632150000.123",
    "customer_number": "09123456789",
    "duration": "60"
  }
}
```

### 7. agent_answer

When an agent answers the call.

**Additional call_data fields:**
- `customer_number`: Customer's phone number
- `agent_number`: Agent's extension number

**Example:**
```json
{
  "event_type": "agent_answer",
  "timestamp": 1632150050,
  "call_data": {
    "uniqueid": "1632150000.123",
    "customer_number": "09123456789",
    "agent_number": "1001"
  }
}
```

### 8. call_end

When the call is completed successfully.

**Additional call_data fields:**
- `customer_number`: Customer's phone number
- `agent_number`: Agent's extension number
- `duration`: Duration of the call in seconds

**Example:**
```json
{
  "event_type": "call_end",
  "timestamp": 1632150200,
  "call_data": {
    "uniqueid": "1632150000.123",
    "customer_number": "09123456789",
    "agent_number": "1001",
    "duration": "190"
  }
}
```

### 9. Failure Status Types

Various types of call failures:

- `customer_busy`: When the customer's line is busy
- `customer_no_answer`: When the customer doesn't answer
- `call_rejected`: When the call is rejected
- `call_failed`: When the call fails due to technical issues

**Additional call_data fields:**
- `customer_number`: Customer's phone number

**Example:**
```json
{
  "event_type": "customer_busy",
  "timestamp": 1632150010,
  "call_data": {
    "uniqueid": "1632150000.123",
    "customer_number": "09123456789"
  }
}
```

## Response Format

The API will respond with a JSON object indicating success or failure:

### Success response

```json
{
  "success": true,
  "message": "EVENT_TYPE event processed"
}
```

### Error response

```json
{
  "success": false,
  "error": "ERROR_MESSAGE"
}
```

## Integration with Asterisk API Notifier

This webhook API is designed to work with the Asterisk API Notifier script. To configure the script to work with this API:

1. Update the `API_URL` in the script to point to your CRM's webhook endpoint:
   ```python
   API_URL = "https://your-crm-domain.com/api/asterisk/call-event/"
   ```

2. Set the `API_KEY` to your assigned API key:
   ```python
   API_KEY = "your-api-key-here"
   ```

3. Ensure the script has permissions to make outbound HTTPS requests.

4. Verify that the Asterisk dialplan is properly configured to call the API Notifier script at the appropriate points.

## Testing

You can test the API by sending a simple event using curl:

```bash
curl -X POST \
  https://your-crm-domain.com/api/asterisk/call-event/ \
  -H 'Authorization: Bearer your-api-key-here' \
  -H 'Content-Type: application/json' \
  -d '{
  "event_type": "call_initiated",
  "timestamp": 1632150000,
  "call_data": {
    "uniqueid": "test-123",
    "customer_number": "09123456789",
    "call_direction": "outbound"
  }
}'
```

## Troubleshooting

1. Check the API logs for errors:
   - Look for errors in the CRM logs
   - Check the API Notifier script logs at `/var/log/asterisk/api_notifications.log`

2. Common issues:
   - Authentication failure: Verify your API key
   - Invalid JSON: Check the format of your request
   - Call/queue not found: Verify that the `uniqueid` matches the `queue_session_id` in the CRM

3. For assistance, contact the system administrator.
