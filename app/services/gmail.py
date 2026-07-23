import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Tuple
from app.config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, RECIPIENT_EMAIL
from app.services import db

logger = logging.getLogger("tech-agent.gmail")


def send_email(
    subject: str,
    html_content: str,
    sent_urls_and_titles: List[Tuple[str, str]],
    recipient_override: str = None
) -> bool:
    """
    Sends an HTML email via Gmail SMTP (SSL over port 465).
    On success, records sent URLs in the database to prevent duplicate emails tomorrow.
    """
    recipient = recipient_override or RECIPIENT_EMAIL
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD and recipient):
        logger.error("Email configuration incomplete (GMAIL_ADDRESS, GMAIL_APP_PASSWORD, or RECIPIENT_EMAIL missing). Cannot send email.")
        return False

    logger.info("Preparing to send email '%s' to %s...", subject, recipient)

    # Create multipart message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Tech Intelligence Agent <{GMAIL_ADDRESS}>"
    msg["To"] = recipient

    # Attach HTML payload
    html_part = MIMEText(html_content, "html")
    msg.attach(html_part)

    context = ssl.create_default_context()
    
    try:
        # Try SSL on port 465 first
        logger.info("Connecting to smtp.gmail.com:465 via SSL...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=20) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, recipient, msg.as_string())

        logger.info("Email delivered successfully to %s!", recipient)

        # Record sent URLs in database
        if sent_urls_and_titles:
            db.add_seen_urls(sent_urls_and_titles)

        return True

    except Exception as ssl_err:
        logger.warning("SMTP SSL connection failed (%s). Retrying with STARTTLS on port 587...", ssl_err)
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
                server.starttls(context=context)
                server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                server.sendmail(GMAIL_ADDRESS, recipient, msg.as_string())

            logger.info("Email delivered successfully via STARTTLS to %s!", recipient)
            if sent_urls_and_titles:
                db.add_seen_urls(sent_urls_and_titles)
            return True

        except Exception as tls_err:
            logger.error("Failed to send email via Gmail SMTP: %s", tls_err)
            return False
