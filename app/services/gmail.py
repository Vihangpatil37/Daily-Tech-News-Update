import os
import smtplib
import ssl
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Tuple
from app.config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, RECIPIENT_EMAIL
from app.services import db

logger = logging.getLogger("tech-agent.gmail")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()


def send_email(
    subject: str,
    html_content: str,
    sent_urls_and_titles: List[Tuple[str, str]],
    recipient_override: str = None
) -> bool:
    """
    Sends an HTML email via Resend HTTPS API (port 443 - unblocked on cloud hosts like Render)
    or Gmail SMTP (SSL over port 465 / STARTTLS port 587).
    On success, records sent URLs in the database to prevent duplicate emails tomorrow.
    """
    recipients_raw = recipient_override or RECIPIENT_EMAIL
    if not recipients_raw:
        logger.error("No recipient email specified.")
        return False

    recipient_list = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    # Method 1: Try Resend HTTPS REST API (Port 443 - works on Render free tier without SMTP blocking)
    if RESEND_API_KEY:
        try:
            logger.info("Sending email via Resend HTTPS API (port 443) to %s...", recipient_list)
            res = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": "Tech Intelligence Agent <onboarding@resend.dev>",
                    "to": recipient_list,
                    "subject": subject,
                    "html": html_content
                },
                timeout=15
            )
            if res.status_code in [200, 201]:
                logger.info("Email delivered successfully via Resend HTTPS API to %s!", recipient_list)
                if sent_urls_and_titles:
                    db.add_seen_urls(sent_urls_and_titles)
                return True
            else:
                logger.warning("Resend API returned status %d: %s. Falling back to SMTP...", res.status_code, res.text)
        except Exception as e:
            logger.warning("Resend HTTPS API delivery failed (%s). Falling back to SMTP...", e)

    # Method 2: Gmail SMTP Delivery (SSL on port 465 or STARTTLS on port 587)
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD):
        logger.error("Email configuration incomplete (neither RESEND_API_KEY nor GMAIL credentials provided).")
        return False

    for recipient in recipient_list:
        logger.info("Preparing to send email '%s' via Gmail SMTP to %s...", subject, recipient)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Tech Intelligence Agent <{GMAIL_ADDRESS}>"
        msg["To"] = recipient

        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        context = ssl.create_default_context()
        sent_successfully = False

        # Try SSL on port 465
        try:
            logger.info("Connecting to smtp.gmail.com:465 via SSL...")
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=20) as server:
                server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                server.sendmail(GMAIL_ADDRESS, recipient, msg.as_string())
            logger.info("Email delivered successfully to %s!", recipient)
            sent_successfully = True
        except Exception as ssl_err:
            logger.warning("SMTP SSL connection failed (%s). Retrying with STARTTLS on port 587...", ssl_err)
            try:
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
                    server.starttls(context=context)
                    server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                    server.sendmail(GMAIL_ADDRESS, recipient, msg.as_string())
                logger.info("Email delivered successfully via STARTTLS to %s!", recipient)
                sent_successfully = True
            except Exception as tls_err:
                logger.error("Failed to send email via Gmail SMTP to %s: %s", recipient, tls_err)

    if sent_successfully and sent_urls_and_titles:
        db.add_seen_urls(sent_urls_and_titles)

    return sent_successfully
