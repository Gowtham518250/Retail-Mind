"""
Shop Profile & Settings Management Service
Handles all shop profile operations: CRUD, validation, sync
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import json
from datetime import datetime

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
            primary_upi_id=data.get("primary_upi_id") or data.get("upi_id"),
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
        db.commit()
        db.refresh(shop_profile)
        
        # Create default shop settings
        settings = ShopSettings(shop_id=shop_profile.id)
        db.add(settings)
        db.commit()
        
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
            db.flush()
            
            # Also ensure default settings are created
            from models import ShopSettings
            settings = ShopSettings(shop_id=shop_profile.id)
            db.add(settings)
            db.commit()
            db.refresh(shop_profile)
        
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
        db.commit()
        db.refresh(shop_profile)
        
        return shop_profile
    
    @staticmethod
    def get_shop_profile(db: Session, user_id: int) -> ShopProfile:
        """Get shop profile by user_id or create default if missing"""
        
        profile = db.query(ShopProfile).filter_by(shop_id=user_id).first()
        if not profile:
            # Auto-create default profile
            profile = ShopProfile(shop_id=user_id, shop_name="My Shop")
            db.add(profile)
            db.flush()
            
            # Auto-create settings
            from models import ShopSettings
            settings = ShopSettings(shop_id=profile.id)
            db.add(settings)
            db.commit()
            db.refresh(profile)
            
        return profile
    
    @staticmethod
    def update_shop_settings(db: Session, shop_id: int, data: Dict[str, Any]) -> ShopSettings:
        """Update shop settings"""
        
        settings = db.query(ShopSettings).filter_by(shop_id=shop_id).first()
        if not settings:
            raise ValueError("Shop settings not found")
        
        # Update fields
        for key, value in data.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
        
        settings.updated_at = datetime.now()
        db.commit()
        db.refresh(settings)
        
        return settings
    
    @staticmethod
    def get_shop_settings(db: Session, shop_id: int) -> ShopSettings:
        """Get shop settings"""
        
        settings = db.query(ShopSettings).filter_by(shop_id=shop_id).first()
        if not settings:
            raise ValueError("Shop settings not found")
        
        return settings
    
    @staticmethod
    def delete_shop_profile(db: Session, user_id: int) -> bool:
        """Delete shop profile"""
        
        profile = db.query(ShopProfile).filter_by(shop_id=user_id).first()
        if not profile:
            return False
        
        db.delete(profile)
        db.commit()
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
    """Get shop profile with all settings"""
    
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        settings = ShopService.get_shop_settings(db, profile.id)
        
        # Parse JSON fields
        categories = json.loads(profile.shop_categories) if profile.shop_categories else []
        upi_ids = json.loads(profile.upi_ids) if profile.upi_ids else []
        
        return {
            "status": "success",
            "profile": {
                "id": profile.id,
                "shop_name": profile.shop_name,
                "shop_type": profile.shop_type,
                "phone": profile.phone,
                "phone_number": profile.phone,
                "location": profile.location,
                "email": profile.email,
                "website": profile.website,
                "gst_number": profile.gst_number,
                "primary_upi_id": profile.upi_id,
                "upi_ids": upi_ids,
                "shop_categories": categories,
                "logo_url": profile.logo_url,
                "color_primary": profile.color_primary,
                "color_secondary": profile.color_secondary,
                "is_online_store_enabled": profile.is_online_store_enabled or False,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at
            },
            "settings": {
                "business_hours": {
                    "monday": {"open": settings.monday_open, "close": settings.monday_close, "closed": settings.monday_closed},
                    "tuesday": {"open": settings.tuesday_open, "close": settings.tuesday_close, "closed": settings.tuesday_closed},
                    "wednesday": {"open": settings.wednesday_open, "close": settings.wednesday_close, "closed": settings.wednesday_closed},
                    "thursday": {"open": settings.thursday_open, "close": settings.thursday_close, "closed": settings.thursday_closed},
                    "friday": {"open": settings.friday_open, "close": settings.friday_close, "closed": settings.friday_closed},
                    "saturday": {"open": settings.saturday_open, "close": settings.saturday_close, "closed": settings.saturday_closed},
                    "sunday": {"open": settings.sunday_open, "close": settings.sunday_close, "closed": settings.sunday_closed},
                },
                "tax_config": {
                    "tax_type": settings.tax_type,
                    "igst": settings.igst_percentage,
                    "sgst": settings.sgst_percentage,
                    "utgst": settings.utgst_percentage,
                    "flat_rate": settings.flat_tax_percentage
                },
                "payment_methods": {
                    "cash": settings.accept_cash,
                    "card": settings.accept_card,
                    "upi": settings.accept_upi,
                    "bank": settings.accept_bank_transfer
                },
                "preferences": {
                    "language": settings.language,
                    "theme": settings.theme_mode,
                    "timezone": settings.timezone
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/profile")
def update_profile(data: dict, user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Update shop profile"""
    
    try:
        profile = ShopService.update_shop_profile(db, user_id, data)
        settings = ShopService.get_shop_settings(db, profile.id)
        
        # Parse JSON fields
        categories = json.loads(profile.shop_categories) if profile.shop_categories else []
        upi_ids = json.loads(profile.upi_ids) if profile.upi_ids else []
        
        return {
            "status": "success",
            "message": "Shop profile updated successfully",
            "shop_id": profile.id,
            "profile": {
                "id": profile.id,
                "shop_name": profile.shop_name,
                "shop_type": profile.shop_type,
                "phone": profile.phone,
                "phone_number": profile.phone,
                "location": profile.location,
                "email": profile.email,
                "website": profile.website,
                "gst_number": profile.gst_number,
                "primary_upi_id": profile.upi_id,
                "upi_ids": upi_ids,
                "shop_categories": categories,
                "logo_url": profile.logo_url,
                "color_primary": profile.color_primary,
                "color_secondary": profile.color_secondary,
                "is_online_store_enabled": profile.is_online_store_enabled or False,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at
            },
            "settings": {
                "business_hours": {
                    "monday": {"open": settings.monday_open, "close": settings.monday_close, "closed": settings.monday_closed},
                    "tuesday": {"open": settings.tuesday_open, "close": settings.tuesday_close, "closed": settings.tuesday_closed},
                    "wednesday": {"open": settings.wednesday_open, "close": settings.wednesday_close, "closed": settings.wednesday_closed},
                    "thursday": {"open": settings.thursday_open, "close": settings.thursday_close, "closed": settings.thursday_closed},
                    "friday": {"open": settings.friday_open, "close": settings.friday_close, "closed": settings.friday_closed},
                    "saturday": {"open": settings.saturday_open, "close": settings.saturday_close, "closed": settings.saturday_closed},
                    "sunday": {"open": settings.sunday_open, "close": settings.sunday_close, "closed": settings.sunday_closed}
                },
                "receipt_settings": {
                    "header": settings.receipt_header,
                    "footer": settings.receipt_footer,
                    "show_tax": settings.show_tax_on_receipt,
                    "print_size": settings.default_print_size
                },
                "taxes": {
                    "default_rate": settings.default_tax_rate,
                    "is_inclusive": settings.tax_inclusive
                },
                "loyalty": {
                    "enabled": settings.loyalty_enabled,
                    "points_per_amount": settings.points_per_amount
                }
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
        
        # Generate unique filename
        filename = f"{user_id}_{uuid.uuid4()}_{file.filename}"
        upload_dir = "static/logos"
        
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(file.file.read())
        
        # Update profile with logo path
        profile = ShopService.get_shop_profile(db, user_id)
        profile.logo_file_path = file_path
        profile.logo_version += 1
        db.commit()
        
        return {
            "status": "success",
            "logo_path": file_path,
            "url": f"/static/logos/{filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
        db.commit()
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
        
        if data.get("address_nickname"):
            profile.location = data.get("address_nickname")
            
        db.commit()
        slug = profile.shop_name.lower().replace(" ", "-")
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
        db.commit()
        return {
            "success": True,
            "message": "Your shop is no longer visible to customers."
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


