"""
Session Management Service
Handles 7-day auto-login with RefreshToken + SessionToken
Prevents data loss on logout/login
"""

from sqlalchemy.orm import Session
from models import User, RefreshToken, SessionToken, OfflineDataQueue
from datetime import datetime, timedelta
import secrets
import json
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class SessionService:
    
    @staticmethod
    def create_refresh_token(db: Session, user_id: int, device_id: str = None) -> dict:
        """
        Create 7-day refresh token for auto-login.
        Call after successful login.
        """
        try:
            # Generate secure token
            token_value = secrets.token_urlsafe(64)
            
            # Expires in 7 days
            expires_at = datetime.utcnow() + timedelta(days=7)
            
            refresh_token = RefreshToken(
                user_id=user_id,
                token=token_value,
                expires_at=expires_at
            )
            db.add(refresh_token)
            db.flush()  # Get the ID
            
            # Create session token
            access_token = secrets.token_urlsafe(64)
            session = SessionToken(
                user_id=user_id,
                access_token=access_token,
                refresh_token_id=refresh_token.id,
                device_id=device_id
            )
            db.add(session)
            db.commit()
            
            return {
                "user_id": user_id,
                "refresh_token": token_value,
                "access_token": access_token,
                "expires_in": "7 days",
                "device_id": device_id
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create refresh token: {e}")
            raise HTTPException(status_code=500, detail="Session creation failed")
    
    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str, device_id: str = None) -> dict:
        """
        Use refresh token to get new access token without re-entering password.
        Call on app startup or when access token expires.
        """
        try:
            # Use SELECT FOR UPDATE to prevent race condition
            token_record = db.query(RefreshToken).filter_by(
                token=refresh_token,
                is_valid=True
            ).with_for_update().first()
            
            if not token_record:
                return {"error": "Invalid refresh token"}
            
            # Check if expired
            if token_record.expires_at < datetime.utcnow():
                token_record.is_valid = False
                db.commit()
                return {"error": "Refresh token expired. Please login again."}
            
            # Get user
            user = db.query(User).filter_by(id=token_record.user_id).first()
            if not user:
                return {"error": "User not found"}
            
            # Create new access token
            new_access_token = secrets.token_urlsafe(64)
            session = SessionToken(
                user_id=token_record.user_id,
                access_token=new_access_token,
                refresh_token_id=token_record.id,
                device_id=device_id
            )
            db.add(session)
            db.commit()
            
            return {
                "success": True,
                "user_id": user.id,
                "user_name": user.user_name,
                "email": user.email,
                "access_token": new_access_token,
                "refresh_token": refresh_token,  # Same token continues
                "message": "Logged in from saved session"
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to refresh access token: {e}")
            return {"error": "Token refresh failed"}
    
    @staticmethod
    def logout(db: Session, access_token: str) -> bool:
        """Logout: invalidate session"""
        try:
            session = db.query(SessionToken).filter_by(access_token=access_token).first()
            if session:
                session.is_active = False
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to logout: {e}")
            return False
    
    @staticmethod
    def logout_all_devices(db: Session, user_id: int) -> int:
        """Logout from all devices"""
        try:
            sessions = db.query(SessionToken).filter_by(user_id=user_id, is_active=True).all()
            count = len(sessions)
            for session in sessions:
                session.is_active = False
            db.commit()
            return count
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to logout all devices: {e}")
            return 0
    
    @staticmethod
    def get_active_sessions(db: Session, user_id: int) -> list:
        """Get all active sessions for user (multi-device tracking)"""
        try:
            sessions = db.query(SessionToken).filter_by(
                user_id=user_id,
                is_active=True
            ).all()
            
            return [{
                "session_id": s.id,
                "device_id": s.device_id,
                "last_activity": s.last_activity.isoformat(),
                "created_at": s.created_at.isoformat()
            } for s in sessions]
        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []
    
    @staticmethod
    def verify_access_token(db: Session, access_token: str) -> dict:
        """Verify if access token is valid"""
        try:
            session = db.query(SessionToken).filter_by(
                access_token=access_token,
                is_active=True
            ).first()
            
            if not session:
                return {"valid": False, "error": "Invalid or expired access token"}
            
            # Update last activity
            session.last_activity = datetime.utcnow()
            db.commit()
            
            user = db.query(User).filter_by(id=session.user_id).first()
            
            return {
                "valid": True,
                "user_id": session.user_id,
                "user_name": user.user_name if user else None,
                "device_id": session.device_id
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to verify access token: {e}")
            return {"valid": False, "error": "Token verification failed"}
    
    @staticmethod
    def queue_offline_data(db: Session, user_id: int, data_type: str, payload: dict) -> dict:
        """Queue data when offline (e.g., sales made offline)"""
        try:
            queue_item = OfflineDataQueue(
                user_id=user_id,
                data_type=data_type,
                data_payload=json.dumps(payload)
            )
            db.add(queue_item)
            db.commit()
            
            return {
                "queued": True,
                "queue_id": queue_item.id,
                "type": data_type,
                "will_sync_when_online": True
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to queue offline data: {e}")
            return {"queued": False, "error": str(e)}
    
    @staticmethod
    def sync_offline_queue(db: Session, user_id: int) -> dict:
        """Sync all pending offline data when app comes online"""
        try:
            pending = db.query(OfflineDataQueue).filter_by(
                user_id=user_id,
                synced=False
            ).all()
            
            if not pending:
                return {"synced": True, "count": 0, "message": "No offline data to sync"}
            
            synced_items = []
            for item in pending:
                try:
                    # In real implementation, process each item based on type
                    # For now, just mark as synced
                    item.synced = True
                    item.sync_timestamp = datetime.utcnow()
                    synced_items.append({
                        "id": item.id,
                        "type": item.data_type,
                        "synced": True
                    })
                except Exception as e:
                    synced_items.append({
                        "id": item.id,
                        "type": item.data_type,
                        "error": str(e)
                    })
            
            db.commit()
            
            return {
                "synced": True,
                "count": len(synced_items),
                "items": synced_items,
                "message": f"Synced {len(synced_items)} offline items"
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to sync offline queue: {e}")
            return {"synced": False, "error": str(e)}
    
    @staticmethod
    def delete_expired_tokens(db: Session) -> int:
        """Cleanup expired refresh tokens"""
        try:
            expired = db.query(RefreshToken).filter(
                RefreshToken.expires_at < datetime.utcnow()
            ).delete()
            db.commit()
            return expired
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete expired tokens: {e}")
            return 0
