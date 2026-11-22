import os
import imaplib
import smtplib
import email
from email.message import EmailMessage

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")

def send_email(subject: str, body: str, attachments: list = None):
    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject
    msg.set_content(body)

    for path in attachments or []:
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
            msg.add_attachment(data, maintype="image", subtype="png", filename=os.path.basename(path))

    with smtplib.SMTP_SSL("://gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASS)
        smtp.send_message(msg)

def check_latest_command(subject_filter: str):
    mail = imaplib.IMAP4_SSL("://gmail.com")
    mail.login(GMAIL_USER, GMAIL_PASS)
    mail.select("inbox")
    _, data = mail.search(None, f'(SUBJECT "{subject_filter}")')
    ids = data[0].split()
    if not ids:
        mail.logout()
        return None
    _, msg_data = mail.fetch(ids[-1], "(RFC822)")
    raw = email.message_from_bytes(msg_data[0][1])
    body = ""
    if raw.is_multipart():
        for part in raw.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode(errors="ignore")
                break
    else:
        body = raw.get_payload(decode=True).decode(errors="ignore")
    mail.logout()
    return body.strip()
