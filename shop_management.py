"""
Shop Profile & Settings Management Service
Handles all shop profile operations: CRUD, validation, sync
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import json
from datetime import datetime
from fastapi.responses import FileResponse

from db import get_db
from models import User, ShopProfile, ShopSettings
from security import get_current_user as check_current_user

# ==================== SCHEMAS ====================

class ShopProfileCreate:
    def __init__(self, shop_name: str, shop_type: str, phone: str, location: str,
                 email: Optional[str] = None, website: Optional[str] = None, 
                 gst_number: Optional[str] = None, primary_upi_id: Optional[str] = None):
        self.shop_name = shop_name
        self.shop_type = shop_type
        self.phone = phone
        self.location = location
        self.email = email
        self.website = website
        self.gst_number = gst_number
        self.primary_upi_id = primary_upi_id

class ShopSettingsUpdate:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


# ==================== SERIALIZATION HELPERS ====================

def _safe_json_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, dict):
        return [value]
    text = str(value).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
        if isinstance(decoded, list):
            return decoded
        if decoded is None:
            return []
        return [decoded]
    except (TypeError, ValueError, json.JSONDecodeError):
        # Legacy rows may contain a comma-separated value instead of JSON.
        return [item.strip() for item in text.split(",") if item.strip()]


def _profile_payload(profile):
    return {
        "id": profile.id,
        "profile_id": profile.id,
        "shop_id": profile.shop_id,
        "user_id": profile.shop_id,
        "shop_name": profile.shop_name,
        "shop_type": profile.shop_type,
        "phone": profile.phone,
        "phone_number": profile.phone,
        "location": profile.location,
        "email": profile.email,
        "website": profile.website,
        "shop_tagline": profile.shop_tagline,
        "shop_description": profile.shop_description,
        "address": profile.address,
        "address_line1": profile.address_line1,
        "address_line2": profile.address_line2,
        "state": profile.state,
        "city": profile.city,
        "postal_code": profile.postal_code,
        "gst_number": profile.gst_number,
        "primary_upi_id": profile.upi_id,
        "upi_ids": _safe_json_list(profile.upi_ids),
        "shop_categories": _safe_json_list(profile.shop_categories),
        "logo_url": profile.logo_url,
        "color_primary": profile.color_primary,
        "color_secondary": profile.color_secondary,
        "is_online_store_enabled": bool(profile.is_online_store_enabled),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _settings_payload(settings):
    return {
        "business_hours": {
            "monday": {"open": settings.monday_open, "close": settings.monday_close, "closed": settings.monday_closed},
            "tuesday": {"open": settings.tuesday_open, "close": settings.tuesday_close, "closed": settings.tuesday_closed},
            "wednesday": {"open": settings.wednesday_open, "close": settings.wednesday_close, "closed": settings.wednesday_closed},
            "thursday": {"open": settings.thursday_open, "close": settings.thursday_close, "closed": settings.thursday_closed},
            "friday": {"open": settings.friday_open, "close": settings.friday_close, "closed": settings.friday_closed},
            "saturday": {"open": settings.saturday_open, "close": settings.saturday_close, "closed": settings.saturday_closed},
            "sunday": {"open": settings.sunday_open, "close": settings.sunday_close, "closed": settings.sunday_closed},
        },
        "payment_methods": {
            "cash": settings.accept_cash,
            "card": settings.accept_card,
            "upi": settings.accept_upi,
            "bank": settings.accept_bank_transfer,
        },
        "preferences": {
            "language": settings.language,
            "theme": settings.theme_mode,
            "timezone": settings.timezone,
        },
    }


# ==================== SERVICE CLASS ====================

class ShopService:
    """Service for managing shop profiles and settings"""
    
    @staticmethod
    def create_shop_profile(db: Session, user_id: int, data: Dict[str, Any]) -> ShopProfile:
        """Create new shop profile for a user"""
        
        # Check if user already has a shop profile
        existing = db.query(ShopProfile).filter_by(shop_id=user_id).first()
        if existing:
            raise ValueError("User already has a shop profile. Update existing profile instead.")
        
        # Create shop profile
        shop_profile = ShopProfile(
            shop_id=user_id,
            shop_name=data.get("shop_name"),
            shop_type=data.get("shop_type"),
            phone=data.get("phone") or data.get("shop_phone"),
            location=data.get("location"),
            email=data.get("email") or data.get("shop_email"),
            website=data.get("website"),
            gst_number=data.get("gst_number") or data.get("shop_gst") or data.get("gstin"),
            upi_id=data.get("primary_upi_id") or data.get("upi_id"),
            shop_tagline=data.get("shop_tagline"),
            shop_description=data.get("shop_description"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            address_line1=data.get("address_line1"),
            address_line2=data.get("address_line2"),
            city=data.get("city"),
            state=data.get("state"),
            postal_code=data.get("postal_code"),
            pan_number=data.get("pan_number"),
            registration_number=data.get("registration_number"),
            contact_person_name=data.get("contact_person_name"),
            contact_person_phone=data.get("contact_person_phone"),
            contact_person_email=data.get("contact_person_email"),
        )
        
        # Handle categories as JSON
        if data.get("shop_categories"):
            shop_profile.shop_categories = json.dumps(data.get("shop_categories"))
        
        # Handle UPI IDs as JSON
        if data.get("upi_ids"):
            shop_profile.upi_ids = json.dumps(data.get("upi_ids"))
        
        db.add(shop_profile)
        # Create default shop settings in same transaction to avoid orphan profiles
        db.flush()  # Get shop_profile.id without committing
        settings = ShopSettings(shop_id=shop_profile.id)
        db.add(settings)
        try:
            db.commit()
            db.refresh(shop_profile)
        except Exception as e:
            db.rollback()
            raise ValueError(f"Failed to create shop profile: {str(e)}")
        
        return shop_profile
    
    @staticmethod
    def update_shop_profile(db: Session, user_id: int, data: Dict[str, Any]) -> ShopProfile:
        """Update existing shop profile or create if missing"""
        
        shop_profile = db.query(ShopProfile).filter_by(shop_id=user_id).first()
        if not shop_profile:
            # Auto-create profile if missing instead of failing
            shop_profile = ShopProfile(
                shop_id=user_id,
                shop_name=data.get("shop_name", "My Shop")
            )
            db.add(shop_profile)
            db.flush()  # Get id before commit
            
            # Also ensure default settings are created in same transaction
            from models import ShopSettings
            settings = ShopSettings(shop_id=shop_profile.id)
            db.add(settings)
            try:
                db.commit()
                db.refresh(shop_profile)
            except Exception as e:
                db.rollback()
                raise ValueError(f"Failed to auto-create shop profile: {str(e)}")
        
        # Update fields
        for key, value in data.items():
            if key in ["shop_categories", "upi_ids"] and value:
                # Store as JSON
                setattr(shop_profile, key, json.dumps(value))
            elif value is not None:
                # Aliases for better compatibility with mobile client
                if key in ["shop_phone", "phone_number"]: key = "phone"
                if key in ["shop_gst", "gstin"]: key = "gst_number"
                if key == "shop_email": key = "email"
                if key == "primary_upi_id": key = "upi_id"
                
                if hasattr(shop_profile, key):
                    setattr(shop_profile, key, value)
        
        shop_profile.updated_at = datetime.now()
        try:
            db.commit()
            db.refresh(shop_profile)
        except Exception as e:
            db.rollback()
            raise ValueError(f"Failed to update shop profile: {str(e)}")
        
        return shop_profile
    
    @staticmethod
    def get_shop_profile(db: Session, user_id: int) -> ShopProfile:
        """Get shop profile by user_id or create default if missing"""
        
        profile = db.query(ShopProfile).filter_by(shop_id=user_id).first()
        if not profile:
            # Auto-create a real profile for the authenticated owner. Never
            # overwrite an existing profile and never use a shared placeholder.
            user = db.query(User).filter(User.id == user_id).first()
            default_name = (
                (getattr(user, "shop_name", None) or "").strip()
                or (getattr(user, "username", None) or "").strip()
                or "My Shop"
            )
            profile = ShopProfile(shop_id=user_id, shop_name=default_name)
            db.add(profile)
            db.flush()  # Get id before commit
            
            # Auto-create settings in same transaction
            from models import ShopSettings
            settings = ShopSettings(shop_id=profile.id)
            db.add(settings)
            try:
                db.commit()
                db.refresh(profile)
            except Exception as e:
                db.rollback()
                raise ValueError(f"Failed to auto-create profile: {str(e)}")
            
        return profile
    
    @staticmethod
    def update_shop_settings(db: Session, shop_id: int, data: dict) -> ShopSettings:
        """Update shop settings"""
        settings = db.query(ShopSettings).filter_by(shop_id=shop_id).first()
        if not settings:
            settings = ShopSettings(shop_id=shop_id)
            db.add(settings)
            try:
                db.commit()
                db.refresh(settings)
            except Exception as e:
                db.rollback()
                raise ValueError(f"Failed to create shop settings: {str(e)}")
        
        # Update fields
        for key, value in data.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
        
        settings.updated_at = datetime.now()
        try:
            db.commit()
            db.refresh(settings)
        except Exception as e:
            db.rollback()
            raise ValueError(f"Failed to update shop settings: {str(e)}")
        
        return settings
    
    @staticmethod
    def get_shop_settings(db: Session, shop_id: int) -> ShopSettings:
        """Get shop settings, auto-create if missing"""
        settings = db.query(ShopSettings).filter_by(shop_id=shop_id).first()
        if not settings:
            settings = ShopSettings(shop_id=shop_id)
            db.add(settings)
            try:
                db.commit()
                db.refresh(settings)
            except Exception as e:
                db.rollback()
                raise ValueError(f"Failed to create default settings: {str(e)}")
        return settings
    
    @staticmethod
    def delete_shop_profile(db: Session, user_id: int) -> bool:
        """Delete shop profile"""
        
        profile = db.query(ShopProfile).filter_by(shop_id=user_id).first()
        if not profile:
            return False
        
        db.delete(profile)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise ValueError(f"Failed to delete shop profile: {str(e)}")
        return True


# ==================== API ROUTES ====================

router = APIRouter(prefix="/api/shop", tags=["Shop Profile"])


@router.get("/")
def shop_root(user_id: int = Depends(check_current_user)):
    """Simple authenticated root for /api/shop to aid health checks and tests"""
    return {"status": "success", "message": "Shop API root", "user_id": user_id}

@router.post("/create")
def create_shop_profile(data: dict, user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """
    Create a new shop profile
    
    Args:
        user_id: ID of the shop owner
        data: Shop profile data
    
    Returns:
        New shop profile with settings
    """
    try:
        # Verify user exists
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        profile = ShopService.create_shop_profile(db, user_id, data)
        
        return {
            "status": "success",
            "shop_profile": {
                "id": profile.id,
                "shop_name": profile.shop_name,
                "shop_type": profile.shop_type,
                "phone": profile.phone,
                "location": profile.location,
                "email": profile.email,
                "gst_number": profile.gst_number,
                "created_at": profile.created_at
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/profile")
def get_profile(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Return the authenticated owner's canonical shop profile.

    The Bearer token is the only source of identity. Any query-string
    user_id sent by an old client is intentionally ignored.
    """
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        settings = ShopService.get_shop_settings(db, profile.id)
        payload = _profile_payload(profile)
        return {
            "status": "success",
            "shop_id": profile.shop_id,
            "user_id": profile.shop_id,
            "profile_id": profile.id,
            "profile": payload,
            "settings": _settings_payload(settings),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to load shop profile: {str(e)}")


@router.put("/profile")
def update_profile(data: dict, user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Upsert the authenticated owner's profile and return the persisted row."""
    try:
        # Never trust a client supplied user_id. Identity comes from the JWT.
        data = dict(data or {})
        data.pop("user_id", None)
        data.pop("shop_id", None)
        data.pop("profile_id", None)

        profile = ShopService.update_shop_profile(db, user_id, data)
        settings = ShopService.get_shop_settings(db, profile.id)
        payload = _profile_payload(profile)

        return {
            "status": "success",
            "message": "Shop profile updated successfully",
            "shop_id": profile.shop_id,
            "user_id": profile.shop_id,
            "profile_id": profile.id,
            "profile": payload,
            "settings": _settings_payload(settings),
        }
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to persist shop profile: {str(e)}")


@router.delete("/profile")
def delete_profile(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Delete shop profile and all settings"""
    
    try:
        success = ShopService.delete_shop_profile(db, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Shop profile not found")
        
        return {
            "status": "success",
            "message": "Shop profile and settings deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/settings")
def update_settings(data: dict, user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Update shop settings (business hours, tax, payment methods)"""
    
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        settings = ShopService.update_shop_settings(db, profile.id, data)
        
        return {
            "status": "success",
            "message": "Shop settings updated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-logo")
def upload_logo(file: UploadFile = File(...), user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Upload shop logo"""
    
    try:
        import os
        import uuid
        
        # Validate file type — only allow images
        ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
        
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid file type '{file.content_type}'. Only JPEG/PNG/WebP/GIF allowed.")
        
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(status_code=400, detail=f"Invalid file extension '{ext}'.")
        
        # Read content and enforce size limit
        content = file.file.read()
        if len(content) > MAX_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="Logo file too large. Maximum allowed size is 5 MB.")
        
        # Generate unique filename (sanitised — no user-controlled path components)
        filename = f"{user_id}_{uuid.uuid4()}{ext}"
        upload_dir = "static/logos"
        
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Update the canonical profile record with both the stored file path
        # and the public API URL used by customer storefronts.
        profile = ShopService.get_shop_profile(db, user_id)
        profile.logo_file_path = file_path
        profile.logo_url = f"/static/logos/{filename}"
        if profile.logo_version is None:
            profile.logo_version = 0
        profile.logo_version += 1
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            # Remove the uploaded file if DB update fails
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail=f"Failed to update logo: {str(e)}")
        
        return {
            "status": "success",
            "logo_path": file_path,
            "logo_url": profile.logo_url,
            "url": profile.logo_url,
            "shop_id": profile.shop_id,
            "profile_id": profile.id,
            "logo_version": profile.logo_version,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/logo/{shop_id}")
def get_public_shop_logo(shop_id: int, db: Session = Depends(get_db)):
    """Return the current public logo for a shop storefront."""
    try:
        profile = (
            db.query(ShopProfile)
            .filter(ShopProfile.shop_id == shop_id)
            .first()
        )
        if not profile or not profile.logo_file_path:
            raise HTTPException(status_code=404, detail="Shop logo not found")

        import os
        if not os.path.isfile(profile.logo_file_path):
            raise HTTPException(status_code=404, detail="Shop logo file not found")

        return FileResponse(
            profile.logo_file_path,
            media_type="image/*",
            filename=os.path.basename(profile.logo_file_path),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/business-hours")
def get_business_hours(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Get shop business hours for a specific day or all days"""
    
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        settings = ShopService.get_shop_settings(db, profile.id)
        
        hours = {
            "monday": {"open": settings.monday_open, "close": settings.monday_close, "closed": settings.monday_closed},
            "tuesday": {"open": settings.tuesday_open, "close": settings.tuesday_close, "closed": settings.tuesday_closed},
            "wednesday": {"open": settings.wednesday_open, "close": settings.wednesday_close, "closed": settings.wednesday_closed},
            "thursday": {"open": settings.thursday_open, "close": settings.thursday_close, "closed": settings.thursday_closed},
            "friday": {"open": settings.friday_open, "close": settings.friday_close, "closed": settings.friday_closed},
            "saturday": {"open": settings.saturday_open, "close": settings.saturday_close, "closed": settings.saturday_closed},
            "sunday": {"open": settings.sunday_open, "close": settings.sunday_close, "closed": settings.sunday_closed},
        }
        
        return {
            "status": "success",
            "business_hours": hours,
            "timezone": settings.timezone
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/tax-config")
def get_tax_config(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Get tax configuration for calculating taxes on products"""
    
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        settings = ShopService.get_shop_settings(db, profile.id)
        
        return {
            "status": "success",
            "tax_config": {
                "tax_type": settings.tax_type,
                "igst_percentage": settings.igst_percentage,
                "sgst_percentage": settings.sgst_percentage,
                "utgst_percentage": settings.utgst_percentage,
                "flat_tax_percentage": settings.flat_tax_percentage
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))




@router.get("/online-settings")
def get_online_settings(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Return the complete persisted online-store configuration for the owner."""
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        return {
            "is_online_store_enabled": bool(profile.is_online_store_enabled),
            "online_setup_fee": float(getattr(profile, "online_setup_fee", 0) or 0),
            "min_order": float(getattr(profile, "online_min_order", 0) or 0),
            "delivery_fee": float(getattr(profile, "online_delivery_fee", 0) or 0),
            "offer_delivery": bool(getattr(profile, "online_offer_delivery", True)),
            "offer_pickup": bool(getattr(profile, "online_offer_pickup", True)),
            "accept_cod": bool(getattr(profile, "online_accept_cod", True)),
            "accept_online": bool(getattr(profile, "online_accept_online", False)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load online settings: {str(e)}")


@router.put("/online-settings")
def set_online_settings(
    data: dict,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    """Persist all online-store settings in the shop profile."""
    try:
        profile = ShopService.get_shop_profile(db, user_id)

        # The online-store screen is a single source of truth. Persist the
        # publication switch together with the rest of the shop configuration
        # so the Flutter app, customer web, and marketplace cannot drift apart.
        if "is_online_store_enabled" in data:
            profile.is_online_store_enabled = bool(data.get("is_online_store_enabled"))
            if profile.is_online_store_enabled:
                profile.is_active = True

        # Preserve the shop location when the owner enables marketplace
        # discovery from the location-aware configuration screen.
        if data.get("latitude") is not None:
            profile.latitude = float(data["latitude"])
        if data.get("longitude") is not None:
            profile.longitude = float(data["longitude"])

        def money(key: str, default: float) -> float:
            try:
                value = round(float(data.get(key, default)), 2)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"{key} must be a valid number.")
            if value < 0 or value > 100000:
                raise HTTPException(status_code=422, detail=f"{key} must be between ₹0 and ₹100000.")
            return value

        profile.online_setup_fee = money(
            "online_setup_fee", float(getattr(profile, "online_setup_fee", 0) or 0)
        )
        profile.online_min_order = money(
            "min_order", float(getattr(profile, "online_min_order", 0) or 0)
        )
        profile.online_delivery_fee = money(
            "delivery_fee", float(getattr(profile, "online_delivery_fee", 0) or 0)
        )
        profile.online_offer_delivery = bool(
            data.get("offer_delivery", getattr(profile, "online_offer_delivery", True))
        )
        profile.online_offer_pickup = bool(
            data.get("offer_pickup", getattr(profile, "online_offer_pickup", True))
        )
        profile.online_accept_cod = bool(
            data.get("accept_cod", getattr(profile, "online_accept_cod", True))
        )
        profile.online_accept_online = bool(
            data.get("accept_online", getattr(profile, "online_accept_online", False))
        )

        db.commit()
        return {
            "success": True,
            "is_online_store_enabled": bool(profile.is_online_store_enabled),
            "is_active": bool(profile.is_active),
            "online_setup_fee": float(profile.online_setup_fee or 0),
            "min_order": float(profile.online_min_order or 0),
            "delivery_fee": float(profile.online_delivery_fee or 0),
            "offer_delivery": bool(profile.online_offer_delivery),
            "offer_pickup": bool(profile.online_offer_pickup),
            "accept_cod": bool(profile.online_accept_cod),
            "accept_online": bool(profile.online_accept_online),
            "message": "Online store settings saved.",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update online settings: {str(e)}")


@router.get("/publish-status")
def get_publish_status(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Get the shop's online store publishing status"""
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        return {"is_published": profile.is_online_store_enabled or False}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/publish-status")
def set_publish_status(data: dict, user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Set the shop's online store publishing status"""
    try:
        is_published = data.get("is_published", False)
        profile = ShopService.get_shop_profile(db, user_id)
        profile.is_online_store_enabled = is_published
        # Enabling Online Shopping means the shop is intentionally active in
        # the customer marketplace. Repair legacy NULL active flags at the same
        # time so older shop profiles become discoverable immediately.
        if is_published:
            profile.is_active = True
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update publish status: {str(e)}")
        return {
            "success": True, 
            "is_published": is_published, 
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/publish-marketplace")
def publish_marketplace(data: dict, user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Publish the shop to marketplace with coordinates"""
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        profile.latitude = data.get("latitude")
        profile.longitude = data.get("longitude")
        profile.is_online_store_enabled = True
        profile.is_active = True
        
        if data.get("address_nickname"):
            profile.location = data.get("address_nickname")
            
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to publish marketplace: {str(e)}")
        slug = profile.shop_name.lower().replace(" ", "-") if profile.shop_name else str(profile.id)
        return {
            "success": True,
            "shop_id": profile.id,
            "marketplace_url": f"https://shop.retailmind.com/{slug}",
            "published_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/publish-marketplace")
def unpublish_marketplace(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Unpublish the shop from marketplace"""
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        profile.is_online_store_enabled = False
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to unpublish: {str(e)}")
        return {
            "success": True,
            "message": "Your shop is no longer visible to customers."
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


