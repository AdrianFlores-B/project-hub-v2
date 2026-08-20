import smtplib
from email.message import EmailMessage

from app.config import settings


def send_share_email(to: str, project_name: str, join_url: str) -> None:
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = f'Invitation to the project "{project_name}"'
    message.set_content(
        f'You were invited to join the project "{project_name}".\n\n'
        f"Open this link to accept (you need an account):\n\n{join_url}\n"
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.send_message(message)
