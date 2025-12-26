import smtplib
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Optional

logger = logging.getLogger(__name__)

class Mailer:
    def __init__(self, smtp_server: str, smtp_port: int, user_email: str, user_password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.user_email = user_email
        self.user_password = user_password

    def send_email(self, to_email: str, subject: str, body: str, attachment_path: Optional[str] = None) -> bool:
        """Sends an email with an optional attachment."""
        if not to_email:
            logger.warning("No recipient email provided.")
            return False

        msg = MIMEMultipart()
        msg['From'] = self.user_email
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        if attachment_path and os.path.exists(attachment_path):
            try:
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(part)
            except Exception as e:
                logger.error(f"Failed to attach file {attachment_path}: {e}")

        try:
            logger.info(f"Connecting to SMTP server {self.smtp_server}...")
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.user_email, self.user_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
