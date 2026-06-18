import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from models import User, ShopProfile
from security import hash_password, verify_password, create_access_token, ROLE_OWNER
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

class UserLogin(BaseModel):
    username: str
    password: str

@router.post("/register")
def register(user: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if db.query(User).filter(User.user_name == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Hash password securely
    hashed_password = hash_password(user.password)
    
    # Create new user
    new_user = User(
        user_name=user.username,
        email=user.email,
        password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Auto-create Shop Profile
    shop_profile = ShopProfile(shop_id=new_user.id, shop_name=f"{user.username}'s Shop")
    db.add(shop_profile)
    db.commit()

    # Send Welcome Email with Credentials in the background
    try:
        subject, body = EmailNotificationService.welcome_credentials_template(user.username, user.password, "Shop Owner")
        background_tasks.add_task(
            EmailNotificationService.send_email,
            recipient_email=user.email,
            subject=subject,
            body=body
        )
    except Exception as e:
        logger.error(f"Failed to queue welcome email: {e}")

    return {"msg": "User registered successfully", "user_id": new_user.id}

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
    db_user = db.query(User).filter(User.user_name == user.username).first()
    
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(
        data={"sub": str(db_user.id), "role": ROLE_OWNER}
    )
    
    return {"access_token": access_token, "token_type": "bearer", "role": ROLE_OWNER}
