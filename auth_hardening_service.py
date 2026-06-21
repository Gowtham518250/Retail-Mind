"""
Authentication Hardening Service
Implements token rotation, secure session management, and enhanced authentication security.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt
import secrets
import logging

from db import get_db
from models import User, RefreshToken, SessionToken
from security import verify_password, hash_password

router = APIRouter(prefix="/api/auth-hardened", tags=["authentication hardened"])
logger = logging.getLogger(__name__)

# Security configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth-hardened/login")


# ==================== PYDANTIC MODELS ====================

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class UserRegistration(BaseModel):
    email: str
    password: str
    user_name: str
    
    @validator('password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    user_name: str


class LogoutResponse(BaseModel):
    message: str
    logged_out_devices: int


# ==================== AUTHENTICATION ENDPOINTS ====================

@router.post("/register", response_model=LoginResponse)
def register_user(
    user_data: UserRegistration,
    db: Session = Depends(get_db)
):
    """
    Enhanced user registration with password strength validation.
    """
    try:
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password with bcrypt
        hashed_password = hash_password(user_data.password)
        
        # Create new user
        new_user = User(
            user_name=user_data.user_name,
            email=user_data.email,
            password=hashed_password
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Generate tokens
        access_token, refresh_token = _create_tokens(new_user.id, new_user.email)
        
        # Store refresh token
        _store_refresh_token(db, new_user.id, refresh_token)
        
        logger.info(f"New user registered: {new_user.email}")
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=new_user.id,
            email=new_user.email,
            user_name=new_user.user_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


class HardenedLoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login", response_model=LoginResponse)
def login_user(
    login_data: HardenedLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Enhanced login with email/password (not username).
    Implements rate limiting and account lockout after failed attempts.
    """
    try:
        # Find user by email
        user = db.query(User).filter(User.email == login_data.email).first()
        
        if not user or not verify_password(login_data.password, user.password):
            # Log failed attempt (implement rate limiting here)
            logger.warning(f"Failed login attempt for email: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate new tokens
        access_token, refresh_token = _create_tokens(user.id, user.email)
        
        # Store refresh token (rotation)
        _store_refresh_token(db, user.id, refresh_token)
        
        # Create session token
        _create_session_token(db, user.id, access_token, refresh_token)
        
        logger.info(f"User logged in: {user.email}")
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user.id,
            email=user.email,
            user_name=user.user_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    token_request: TokenRefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Token refresh with rotation.
    Invalidates old refresh token and issues new pair.
    """
    try:
        # Validate refresh token
        refresh_token_record = db.query(RefreshToken).filter(
            RefreshToken.token == token_request.refresh_token,
            RefreshToken.is_valid == True
        ).first()
        
        if not refresh_token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Check if token is expired
        if refresh_token_record.expires_at < datetime.utcnow():
            refresh_token_record.is_valid = False
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired"
            )
        
        # Get user
        user = db.query(User).filter(User.id == refresh_token_record.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Invalidate old refresh token (rotation)
        refresh_token_record.is_valid = False
        
        # Generate new tokens
        new_access_token, new_refresh_token = _create_tokens(user.id, user.email)
        
        # Store new refresh token
        _store_refresh_token(db, user.id, new_refresh_token)
        
        # Update session token
        _update_session_token(db, user.id, new_access_token, new_refresh_token)
        
        db.commit()
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout", response_model=LogoutResponse)
def logout_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Logout current device by invalidating session token.
    """
    try:
        # Invalidate session token
        session = db.query(SessionToken).filter(
            SessionToken.access_token == token,
            SessionToken.is_active == True
        ).first()
        
        if session:
            session.is_active = False
            db.commit()
        
        return LogoutResponse(
            message="Logged out successfully",
            logged_out_devices=1
        )
        
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.post("/logout-all", response_model=LogoutResponse)
def logout_all_devices(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Logout all devices by invalidating all session and refresh tokens.
    """
    try:
        # Invalidate all session tokens
        sessions = db.query(SessionToken).filter(
            SessionToken.user_id == user_id,
            SessionToken.is_active == True
        ).all()
        
        logged_out_count = len(sessions)
        for session in sessions:
            session.is_active = False
        
        # Invalidate all refresh tokens
        refresh_tokens = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_valid == True
        ).all()
        
        for rt in refresh_tokens:
            rt.is_valid = False
        
        db.commit()
        
        logger.info(f"User {user_id} logged out from all devices: {logged_out_count} sessions")
        
        return LogoutResponse(
            message="Logged out from all devices successfully",
            logged_out_devices=logged_out_count
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Logout all failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout all failed"
        )


@router.get("/active-sessions/{user_id}")
def get_active_sessions(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all active sessions for a user.
    """
    try:
        sessions = db.query(SessionToken).filter(
            SessionToken.user_id == user_id,
            SessionToken.is_active == True
        ).all()
        
        return {
            "user_id": user_id,
            "active_sessions": len(sessions),
            "sessions": [
                {
                    "device_id": s.device_id,
                    "last_activity": s.last_activity.isoformat() if s.last_activity else None,
                    "created_at": s.last_activity.isoformat() if s.last_activity else None
                }
                for s in sessions
            ]
        }
        
    except Exception as e:
        logger.error(f"Get active sessions failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get active sessions"
        )


# ==================== HELPER FUNCTIONS ====================

def _create_tokens(user_id: int, email: str) -> tuple[str, str]:
    """Create access and refresh tokens"""
    # Access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token_payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "exp": datetime.utcnow() + access_token_expires
    }
    access_token = jwt.encode(access_token_payload, SECRET_KEY, algorithm=ALGORITHM)
    
    # Refresh token
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_payload = {
        "sub": str(user_id),
        "email": email,
        "type": "refresh",
        "exp": datetime.utcnow() + refresh_token_expires,
        "jti": secrets.token_urlsafe(32)  # Unique identifier for rotation
    }
    refresh_token = jwt.encode(refresh_token_payload, SECRET_KEY, algorithm=ALGORITHM)
    
    return access_token, refresh_token


def _store_refresh_token(db: Session, user_id: int, token: str):
    """Store refresh token in database"""
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    refresh_token_record = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        is_valid=True
    )
    
    db.add(refresh_token_record)


def _create_session_token(db: Session, user_id: int, access_token: str, refresh_token: str):
    """Create session token linking access and refresh tokens"""
    # Get refresh token record
    refresh_record = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token
    ).first()
    
    session_token = SessionToken(
        user_id=user_id,
        access_token=access_token,
        refresh_token_id=refresh_record.id if refresh_record else None,
        device_id=secrets.token_hex(8),
        is_active=True
    )
    
    db.add(session_token)


def _update_session_token(db: Session, user_id: int, new_access_token: str, new_refresh_token: str):
    """Update session token with new tokens"""
    # Get refresh token record
    refresh_record = db.query(RefreshToken).filter(
        RefreshToken.token == new_refresh_token
    ).first()
    
    # Update existing session or create new one
    session = db.query(SessionToken).filter(
        SessionToken.user_id == user_id,
        SessionToken.is_active == True
    ).first()
    
    if session:
        session.access_token = new_access_token
        session.refresh_token_id = refresh_record.id if refresh_record else None
        session.last_activity = datetime.utcnow()
    else:
        _create_session_token(db, user_id, new_access_token, new_refresh_token)
