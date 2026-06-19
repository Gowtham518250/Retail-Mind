import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from db import get_db
from models import User, ShopProfile
from security import (
    hash_password, verify_password, create_access_token,
    ROLE_OWNER, normalize_email, normalize_role,
)
from email_notifications import EmailNotificationService
import random
import time
from typing import Optional

router = APIRouter()
logger = logging.getLogger(__name__)

class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    user_type: Optional[str] = ROLE_OWNER

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/register")
def register(user: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    email = normalize_email(user.email)
    role = normalize_role(user.user_type)
    logger.info(f"Registration attempt: email={email}, role={role}")

    # Email uniqueness check (case-insensitive). The email is the real identity
    # across all roles, so an existing email is the only hard conflict.
    if db.query(User).filter(func.lower(User.email) == email).first():
        logger.info(f"Registration rejected: email already exists ({email})")
        raise HTTPException(status_code=409, detail="This email already has an account. Please log in instead.")

    hashed_password = hash_password(user.password)
    new_user = User(
        user_name=user.username,
        email=email,
        password=hashed_password,
        user_type=role,
    )
    db.add(new_user)
    try:
        db.flush()
        # Owners get an auto-created shop profile; other roles do not.
        if role == ROLE_OWNER:
            db.add(ShopProfile(shop_id=new_user.id, shop_name=f"{user.username}'s Shop"))
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        logger.warning(f"Registration race/integrity error for email={email}")
        raise HTTPException(status_code=409, detail="This email already has an account. Please log in instead.")

    logger.info(f"Registration success: user_id={new_user.id}, email={email}, role={role}")

    # Send Welcome Email with Credentials in the background (best-effort)
    try:
        subject, body = EmailNotificationService.welcome_credentials_template(user.username, user.password, role.title())
        background_tasks.add_task(
            EmailNotificationService.send_email,
            recipient_email=email,
            subject=subject,
            body=body
        )
    except Exception as e:
        logger.error(f"Failed to queue welcome email: {e}")

    return {"msg": "User registered successfully", "user_id": new_user.id, "role": role}

class SendOTPRequest(BaseModel):
    email: str
    purpose: Optional[str] = "Verification"

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str

otp_cache = {}

@router.post("/send-otp")
def send_otp(request: SendOTPRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    otp_code = str(random.randint(100000, 999999))
    
    # Store in memory for 10 minutes
    otp_cache[request.email] = {
        "otp": otp_code,
        "expires_at": time.time() + 600
    }
    
    # Send email in the background to prevent slow loading times
    try:
        subject, body = EmailNotificationService.send_otp_template(otp_code, request.purpose)
        background_tasks.add_task(
            EmailNotificationService.send_email,
            recipient_email=request.email,
            subject=subject,
            body=body
        )
        print(f" OTP generation request for {request.email}: {otp_code}") # Log OTP for debugging/Render logs
    except Exception as e:
        logger.error(f"Failed to queue OTP email: {e}")
        
    return {"msg": "OTP sent successfully (Check your Render console logs if the email does not arrive)"}

@router.post("/verify-otp")
def verify_otp(request: VerifyOTPRequest):
    record = otp_cache.get(request.email)
    
    if not record:
        raise HTTPException(status_code=400, detail="OTP not requested or expired")
    
    if time.time() > record["expires_at"]:
        del otp_cache[request.email]
        raise HTTPException(status_code=400, detail="OTP expired")
        
    if record["otp"] != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
        
    # Clear OTP after successful verification
    del otp_cache[request.email]
    
    return {"msg": "OTP verified successfully"}

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    email = normalize_email(user.email)
    db_user = db.query(User).filter(func.lower(User.email) == email).first()
    
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Role comes from the stored account type, NOT from this endpoint, so each
    # user lands on the correct dashboard (owner/customer/worker/delivery).
    role = normalize_role(db_user.user_type)
    access_token = create_access_token(
        data={"sub": str(db_user.id), "role": role}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": role,
        "user_id": db_user.id,
        "user_type": role,
    }


@router.get("/sales")
def get_sales(user_id: int, db: Session = Depends(get_db)):
    """
    Get all sales/invoices for a user to restore when app data is cleared.
    This endpoint is used by the frontend to download sales history from the cloud.
    """
    try:
        from models import Invoice, InvoiceLineItem
        from sqlalchemy import desc
        
        # Get all invoices for this user
        invoices = db.query(Invoice).filter(
            Invoice.user_id == user_id
        ).order_by(desc(Invoice.created_at)).all()
        
        sales_data = []
        for invoice in invoices:
            # Get line items for this invoice
            line_items = db.query(InvoiceLineItem).filter(
                InvoiceLineItem.invoice_id == invoice.id
            ).all()
            
            sales_record = {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'customer_name': invoice.customer_name,
                'customer_phone': invoice.customer_phone,
                'total_amount': float(invoice.total_amount),
                'paid_amount': float(invoice.paid_amount),
                'payment_status': invoice.payment_status,
                'invoice_date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
                'line_items': [
                    {
                        'product_id': item.product_id,
                        'product_name': item.description,
                        'quantity': item.quantity,
                        'unit_price': float(item.unit_price),
                        'line_total': float(item.line_total),
                    }
                    for item in line_items
                ]
            }
            sales_data.append(sales_record)
        
        return sales_data
    except Exception as e:
        logger.error(f"Error fetching sales: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch sales: {str(e)}")
