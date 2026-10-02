"""
Email Notification Service
Handles sending emails for alerts, notifications, and business events
Supports HTTPS transactional email via Brevo for Render and SMTP as a local/paid-host fallback
"""

import logging
import os
from datetime import datetime
import smtplib
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
from db import Base
from typing import List, Optional
import asyncio
from enum import Enum as PythonEnum


class EmailNotificationType(str, PythonEnum):
    """Types of email notifications — renamed from NotificationType to avoid conflict with models.py"""
    STOCK_ALERT = "STOCK_ALERT"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    INVOICE_GENERATED = "INVOICE_GENERATED"
    LOW_INVENTORY = "LOW_INVENTORY"
    DELIVERY_REMINDER = "DELIVERY_REMINDER"
    CUSTOMER_REGISTRATION = "CUSTOMER_REGISTRATION"
    BULK_IMPORT = "BULK_IMPORT"
    BACKUP_COMPLETE = "BACKUP_COMPLETE"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    DAILY_REPORT = "DAILY_REPORT"


class EmailNotification(Base):
    """Model to store email notifications"""
    __tablename__ = "email_notifications"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_details.id"), nullable=False)
    recipient_email = Column(String(100), nullable=False)
    notification_type = Column(String(50), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    html_body = Column(Text, nullable=True)
    is_sent = Column(Boolean, default=False)
    send_attempts = Column(Integer, default=0)
    last_attempt = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])


class EmailNotificationService:
    """Service for sending email notifications.

    Render Free blocks outbound SMTP ports, so production can use the Brevo
    HTTPS API instead. SMTP remains available for local development or hosts
    where SMTP egress is allowed.
    """

    logger = logging.getLogger(__name__)

    # SMTP/local configuration.
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_TIMEOUT = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
    SENDER_EMAIL = os.getenv("SENDER_EMAIL", os.getenv("SMTP_USER", ""))
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", os.getenv("SMTP_PASSWORD", ""))
    FROM_EMAIL = os.getenv("EMAIL_FROM", SENDER_EMAIL)

    # HTTPS transactional email configuration for Render.
    # Set EMAIL_PROVIDER=brevo and BREVO_API_KEY on Render.
    EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "auto").strip().lower()
    BREVO_API_URL = os.getenv(
        "BREVO_API_URL",
        "https://api.brevo.com/v3/smtp/email",
    )
    BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
    BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "").strip()
    BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "Retail Mind").strip()
    EMAIL_TIMEOUT = float(os.getenv("EMAIL_HTTP_TIMEOUT_SECONDS", "10"))

    @classmethod
    def _send_via_brevo(
        cls,
        recipient_email: str,
        subject: str,
        body: str,
        html_body: str = None,
    ) -> bool:
        """Send a transactional email through Brevo's HTTPS API."""
        if not cls.BREVO_API_KEY:
            cls.logger.error(
                "Brevo email provider selected but BREVO_API_KEY is missing. "
                "To=%s Subject=%s",
                recipient_email,
                subject,
            )
            return False

        sender_email = cls.BREVO_SENDER_EMAIL or cls.FROM_EMAIL or cls.SENDER_EMAIL
        if not sender_email:
            cls.logger.error(
                "Brevo email provider selected but no sender email is configured."
            )
            return False

        payload = {
            "sender": {
                "name": cls.BREVO_SENDER_NAME,
                "email": sender_email,
            },
            "to": [{"email": recipient_email}],
            "subject": subject,
        }

        # Brevo expects one message body type when sending inline content.
        if html_body and html_body.strip():
            payload["htmlContent"] = html_body
        else:
            payload["textContent"] = body

        try:
            response = httpx.post(
                cls.BREVO_API_URL,
                headers={
                    "accept": "application/json",
                    "api-key": cls.BREVO_API_KEY,
                    "content-type": "application/json",
                },
                json=payload,
                timeout=httpx.Timeout(
                    connect=min(5.0, cls.EMAIL_TIMEOUT),
                    read=cls.EMAIL_TIMEOUT,
                    write=cls.EMAIL_TIMEOUT,
                    pool=cls.EMAIL_TIMEOUT,
                ),
            )

            if 200 <= response.status_code < 300:
                cls.logger.info(
                    "Email sent successfully through Brevo: To=%s Subject=%s",
                    recipient_email,
                    subject,
                )
                return True

            cls.logger.error(
                "Brevo email send failed: status=%s body=%s To=%s Subject=%s",
                response.status_code,
                response.text[:1000],
                recipient_email,
                subject,
            )
            return False
        except Exception as e:
            cls.logger.error(
                "Brevo email request failed: %s",
                e,
                exc_info=True,
                extra={"recipient_email": recipient_email, "subject": subject},
            )
            return False

    @classmethod
    def _send_via_smtp(
        cls,
        recipient_email: str,
        subject: str,
        body: str,
        html_body: str = None,
    ) -> bool:
        """Send an email using SMTP where outbound SMTP is permitted."""
        if not cls.SENDER_EMAIL or not cls.SENDER_PASSWORD:
            cls.logger.error(
                "SMTP email not configured: SENDER_EMAIL or SENDER_PASSWORD is missing. "
                "To=%s Subject=%s",
                recipient_email,
                subject,
            )
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cls.FROM_EMAIL
        msg["To"] = recipient_email
        msg.attach(MIMEText(body, "plain"))

        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(
                cls.SMTP_SERVER,
                cls.SMTP_PORT,
                timeout=cls.SMTP_TIMEOUT,
            ) as server:
                server.starttls()
                server.login(cls.SENDER_EMAIL, cls.SENDER_PASSWORD)
                server.send_message(msg)

            cls.logger.info(
                "Email sent successfully through SMTP: To=%s Subject=%s",
                recipient_email,
                subject,
            )
            return True
        except Exception as e:
            cls.logger.error(
                "SMTP email send error: %s",
                e,
                exc_info=True,
                extra={"recipient_email": recipient_email, "subject": subject},
            )
            return False

    @classmethod
    def send_email(
        cls,
        recipient_email: str,
        subject: str,
        body: str,
        html_body: str = None,
    ) -> bool:
        """Send an email using the configured provider.

        Provider modes:
          - brevo: use Brevo HTTPS API only.
          - smtp: use SMTP only.
          - auto (default): use Brevo when BREVO_API_KEY is present,
            otherwise use SMTP.
        """
        provider = cls.EMAIL_PROVIDER

        if provider == "brevo" or (provider == "auto" and cls.BREVO_API_KEY):
            return cls._send_via_brevo(
                recipient_email, subject, body, html_body
            )

        # Render free web services cannot reach SMTP ports 25/465/587.
        # Do not silently fall back to SMTP in production, because that makes
        # the API appear to work while the message is never delivered.
        if provider == "auto" and (
            os.getenv("RENDER_SERVICE_ID")
            or os.getenv("RENDER")
            or os.getenv("RENDER_SERVICE_NAME")
        ):
            cls.logger.error(
                "No HTTPS email provider is configured for Render. "
                "Set EMAIL_PROVIDER=brevo and BREVO_API_KEY/BREVO_SENDER_EMAIL."
            )
            return False

        if provider == "smtp":
            return cls._send_via_smtp(
                recipient_email, subject, body, html_body
            )

        cls.logger.error(
            "No usable email provider configured. EMAIL_PROVIDER=%r BREVO_API_KEY=%s",
            provider,
            "configured" if cls.BREVO_API_KEY else "missing",
        )
        return False

    @classmethod
    def create_notification(
        cls,
        db: Session,
        user_id: int,
        recipient_email: str,
        notification_type: EmailNotificationType,
        subject: str,
        body: str,
        html_body: str = None,
        send_immediately: bool = True
    ) -> EmailNotification:
        """Create and optionally send a notification"""
        
        notification = EmailNotification(
            user_id=user_id,
            recipient_email=recipient_email,
            notification_type=notification_type,
            subject=subject,
            body=body,
            html_body=html_body
        )
        
        db.add(notification)
        db.commit()
        
        if send_immediately:
            success = cls.send_email(
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                html_body=html_body
            )
            
            if success:
                notification.is_sent = True
                notification.sent_at = datetime.utcnow()
            else:
                notification.send_attempts += 1
                notification.last_attempt = datetime.utcnow()
            
            db.commit()
        
        return notification
    
    # ===== TEMPLATE GENERATORS =====
    
    @staticmethod
    def stock_alert_template(product_name: str, current_stock: int, min_stock: int) -> tuple:
        """Generate stock alert email"""
        subject = f"⚠️ Low Stock Alert: {product_name}"
        body = f"""
Stock Alert Notification

Product: {product_name}
Current Stock: {current_stock}
Minimum Stock: {min_stock}

Please reorder this product to maintain inventory levels.
        """
        
        html = f"""
<html>
<body style="font-family: Arial, sans-serif;">
    <h2 style="color: #ff6b6b;">⚠️ Low Stock Alert</h2>
    <p><strong>Product:</strong> {product_name}</p>
    <p><strong>Current Stock:</strong> {current_stock}</p>
    <p><strong>Minimum Stock:</strong> {min_stock}</p>
    <p>Please reorder this product to maintain inventory levels.</p>
</body>
</html>
        """
        return subject, body, html
    
    @staticmethod
    def payment_received_template(amount: float, invoice_id: str, customer_name: str) -> tuple:
        """Generate payment received email"""
        subject = f"✅ Payment Received - Invoice {invoice_id}"
        body = f"""
Payment Confirmation

Amount: ₹{amount:,.2f}
Invoice ID: {invoice_id}
Customer: {customer_name}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Thank you for the payment.
        """
        
        html = f"""
<html>
<body style="font-family: Arial, sans-serif;">
    <h2 style="color: #10b981;">✅ Payment Received</h2>
    <p><strong>Amount:</strong> ₹{amount:,.2f}</p>
    <p><strong>Invoice ID:</strong> {invoice_id}</p>
    <p><strong>Customer:</strong> {customer_name}</p>
    <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>Thank you for the payment.</p>
</body>
</html>
        """
        return subject, body, html
    
    @classmethod
    def welcome_credentials_template(cls, username: str, password: str, role: str) -> tuple:
        """Generate welcome email with credentials"""
        subject = f"Welcome to AI Shop Enterprise! Here are your credentials"
        body = f"""
        Hello {username},
        
        Your {role} account has been successfully created.
        Please keep these credentials safe.
        
        Username: {username}
        Password: {password}
        
        You can now log into your mobile or web app using these credentials.
        
        Best Regards,
        The AI Shop Enterprise Team
        """
        return subject, body

    @classmethod
    def send_otp_template(cls, otp: str, purpose: str = "Verification") -> tuple:
        """Generate OTP email"""
        subject = f"{otp} is your AI Shop {purpose} OTP"
        body = f"""
        Your One-Time Password (OTP) for {purpose} is:
        
        {otp}
        
        This OTP is valid for the next 10 minutes. 
        Do not share this code with anyone.
        
        Best Regards,
        The AI Shop Enterprise Team
        """
        return subject, body

    @classmethod
    def backup_complete_template(timestamp: str, records_backed_up: int) -> tuple:
        """Generate backup complete email"""
        subject = "✅ Database Backup Complete"
        body = f"""
Backup Notification

Backup Time: {timestamp}
Records Backed Up: {records_backed_up}
Status: SUCCESS

Your data is safely backed up.
        """
        
        html = f"""
<html>
<body style="font-family: Arial, sans-serif;">
    <h2 style="color: #10b981;">✅ Backup Complete</h2>
    <p><strong>Backup Time:</strong> {timestamp}</p>
    <p><strong>Records Backed Up:</strong> {records_backed_up:,}</p>
    <p><strong>Status:</strong> SUCCESS</p>
    <p>Your data is safely backed up.</p>
</body>
</html>
        """
        return subject, body, html

