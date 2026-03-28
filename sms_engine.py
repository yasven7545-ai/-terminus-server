# sms_engine.py
import os

# Simple SMS abstraction. By default it prints (dev).
# To integrate Twilio, set environment TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM

def send_sms(phone, message):
    phone = str(phone)
    # minimal normalization
    if not phone:
        return False
    # If Twilio env is present, attempt to send (optional)
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM")
    if sid and token and from_number:
        try:
            from twilio.rest import Client
            client = Client(sid, token)
            client.messages.create(body=message, from_=from_number, to=phone)
            return True
        except Exception as e:
            print("Twilio send failed:", e)
            return False
    # fallback: print to console
    print(f"[SMS] -> {phone}: {message}")
    return True
