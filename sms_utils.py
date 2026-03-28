# sms_utils.py
import os
import logging

LOG = logging.getLogger("sms_utils")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    LOG.addHandler(ch)

def send_sms(phone, message):
    """
    Send SMS to `phone` with `message`.
    By default this logs the message to stdout for local testing.

    To enable Twilio, set these environment variables:
      TWILIO_ACCOUNT_SID
      TWILIO_AUTH_TOKEN
      TWILIO_FROM_NUMBER

    NOTE: This function intentionally keeps a simple interface.
    """
    # Basic validation
    if not phone or not message:
        LOG.warning("send_sms called with empty phone or message")
        return False

    # Trim message to a reasonable length (avoid carrier limits)
    msg = str(message).strip()
    if len(msg) > 900:
        msg = msg[:900] + "..."

    # If Twilio is configured, attempt to send
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")

    if sid and token and from_number:
        try:
            from twilio.rest import Client
            client = Client(sid, token)
            client.messages.create(to=phone, from_=from_number, body=msg)
            LOG.info(f"SMS sent to {phone} via Twilio.")
            return True
        except Exception as e:
            LOG.exception("Twilio SMS failed, falling back to console log.")

    # Fallback: log to server console (safe for testing)
    LOG.info(f"SMS to {phone}: {msg}")
    return True
