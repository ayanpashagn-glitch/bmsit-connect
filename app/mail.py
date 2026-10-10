"""SMTP delivery; no development bypass or OTP logging."""
import smtplib
import ssl
from email.message import EmailMessage
from .config import settings

def send_email(email: str, subject: str, body: str):
    if not settings.smtp_host or not settings.smtp_from:
        raise RuntimeError('Email delivery is not configured')
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = settings.smtp_from
    message['To'] = email
    message.set_content(body)
    factory = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
    kwargs = {'context': ssl.create_default_context()} if settings.smtp_ssl else {}
    with factory(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds, **kwargs) as smtp:
        if settings.smtp_starttls and not settings.smtp_ssl:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)

def send_otp(email,code):
    send_email(email,'Your BMSIT Connect verification code',f'Your registration code is {code}. It expires in 10 minutes. Do not share it. If you did not request this, ignore this email.')

def send_password_reset(email,url):
    send_email(email,'Reset your BMSIT Connect password',f'Open this link to reset your password: {url}\nIt expires in 30 minutes and works once. If you did not request this, ignore this email.')
