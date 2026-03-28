import smtplib
from email.message import EmailMessage

EMAIL = "yasven7545@gmail.com"
APP_PASSWORD = "olnjzafwxzdeblpa"  # NO SPACES

msg = EmailMessage()
msg["From"] = EMAIL
msg["To"] = "uniyash7545@gmail.com"
msg["Subject"] = "SMTP Test"
msg.set_content("SMTP App Password test")

with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(EMAIL, APP_PASSWORD)
    server.send_message(msg)

print("Mail sent successfully")
