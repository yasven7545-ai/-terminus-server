import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

class MMSMailer:
    """
    High-level Mailer for on-demand notifications (Breakdowns, Assignments, Escalations).
    """
    def __init__(self):
        self.server = "smtp.gmail.com"
        self.port = 587
        self.sender = "maintenance.slnterminus@gmail.com"
        self.password = "hguoeztcfmfvqbum" # App Password

    def send_notification(self, subject, title, message, priority="Normal"):
        """
        Generic high-end HTML mailer for SLN Terminus.
        """
        # Set border color based on priority
        accent_color = "#3b82f6" # Blue
        if priority.lower() == "critical": accent_color = "#ef4444" # Red
        if priority.lower() == "warning": accent_color = "#f59e0b" # Yellow

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"MMS ALERT: {subject}"
        msg['From'] = f"SLN MMS <{self.sender}>"
        msg['To'] = self.sender # Sending to the same corporate account

        html = f"""
        <html>
            <body style="font-family: sans-serif; background-color: #0f172a; padding: 20px; color: #f8fafc;">
                <div style="max-width: 600px; margin: auto; background: #1e293b; border-top: 4px solid {accent_color}; border-radius: 8px; overflow: hidden; padding: 40px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: {accent_color}; font-size: 24px; margin: 0; letter-spacing: 2px;">SLN TERMINUS</h1>
                        <p style="color: #64748b; font-size: 10px; text-transform: uppercase;">Infrastructure Management System</p>
                    </div>
                    
                    <h2 style="color: #ffffff; font-size: 18px; border-bottom: 1px solid #334155; padding-bottom: 10px;">{title}</h2>
                    <p style="color: #94a3b8; line-height: 1.6; font-size: 14px;">{message}</p>
                    
                    <div style="margin-top: 30px; padding: 20px; background: rgba(255,255,255,0.05); border-radius: 8px; text-align: center;">
                        <p style="font-size: 12px; color: #64748b; margin-bottom: 15px;">Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <a href="http://localhost:5000" style="background: {accent_color}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 13px;">VIEW IN DASHBOARD</a>
                    </div>
                    
                    <p style="text-align: center; color: #475569; font-size: 10px; margin-top: 30px;">
                        This is an automated neural notification from the SLN Terminus MMS Engine.
                    </p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))

        try:
            with smtplib.SMTP(self.server, self.port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
                return True
        except Exception as e:
            print(f"Neural Mailer Error: {e}")
            return False

# Functional wrapper for easy imports
def send_maintenance_email(subject, body, priority="Normal"):
    mailer = MMSMailer()
    return mailer.send_notification(subject, subject, body, priority)