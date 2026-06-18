import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger(__name__)

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")


def send_email(to: str, subject: str, body: str) -> bool:
    """Send email via Gmail SMTP. Falls back to console log if not configured."""

    # Always log to console
    print(f"\n[EMAIL ALERT]")
    print(f"  To: {to}")
    print(f"  Subject: {subject}")
    print(f"  Body: {body[:200]}...")
    print(f"  Sent at: {datetime.utcnow()}\n")

    # Send via Gmail if configured
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("[EMAIL] Gmail not configured — logged to console only")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = GMAIL_USER
        msg["To"] = to

        html_body = f"""
        <html><body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">DocIQ Deadline Alert</h2>
            <p>{body}</p>
            <hr>
            <p style="color: #6b7280; font-size: 12px;">
                Sent by DocIQ — Document Intelligence Platform
            </p>
        </div>
        </body></html>
        """

        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, to, msg.as_string())

        print(f"[EMAIL] Sent successfully to {to}")
        return True

    except Exception as e:
        print(f"[EMAIL] Failed to send: {e}")
        return False


def send_deadline_alert(
    to_email: str,
    document_name: str,
    alert_title: str,
    deadline_date: datetime,
    days_until: int
) -> bool:
    subject = f"DocIQ Alert: '{alert_title}' deadline in {days_until} day(s)"
    body = (
        f"This is a reminder that the following deadline is approaching:\n\n"
        f"Document: {document_name}\n"
        f"Alert: {alert_title}\n"
        f"Deadline: {deadline_date.strftime('%B %d, %Y')}\n"
        f"Days remaining: {days_until}\n\n"
        f"Please log in to DocIQ to review this document."
    )
    return send_email(to_email, subject, body)