import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from models import User, ShopProfile
from security import hash_password, verify_password, create_access_token, ROLE_OWNER, get_current_user, check_login_lockout, record_login_failure, record_login_success
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
    user_type: Optional[str] = "OWNER"
    role: Optional[str] = "OWNER"
    is_active: Optional[bool] = True

class UserLogin(BaseModel):
    email: str
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/register")
def register(user: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Check username uniqueness — return 409 Conflict (not 400) so clients can distinguish
    if db.query(User).filter(User.user_name == user.username).first():
        raise HTTPException(status_code=409, detail="Username already registered. Please choose a different name.")
    
    if not user.email or user.email.strip() == "":
        raise HTTPException(status_code=400, detail="Email is required")

    from sqlalchemy import func
    # Check email uniqueness (case-insensitive) — return 409 Conflict
    if db.query(User).filter(func.lower(User.email) == user.email.strip().lower()).first():
        raise HTTPException(status_code=409, detail="This email is already registered. Please login instead.")
    
    # Hash password securely
    hashed_password = hash_password(user.password)
    
    # Create new user
    new_user = User(
        user_name=user.username,
        email=user.email.strip().lower(),  # Store email in lowercase for consistency
        password=hashed_password,
        user_type=user.user_type.upper() if user.user_type else "OWNER",
        is_active=user.is_active if user.is_active is not None else True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Auto-create Shop Profile only if they are an OWNER
    if new_user.user_type == "OWNER":
        shop_profile = ShopProfile(shop_id=new_user.id, shop_name=f"{user.username}'s Shop")
        db.add(shop_profile)
        db.commit()

    # Send Welcome Email with Credentials in the background
    try:
        subject, body = EmailNotificationService.welcome_credentials_template(user.username, "[HIDDEN FOR SECURITY]", "Shop Owner")
        background_tasks.add_task(
            EmailNotificationService.send_email,
            recipient_email=user.email,
            subject=subject,
            body=body
        )
    except Exception as e:
        logger.error(f"Failed to queue welcome email: {e}")

    # Generate access token for immediate login after registration
    access_token = create_access_token(
        data={"sub": str(new_user.id), "role": new_user.user_type, "user_type": new_user.user_type}
    )

    return {
        "msg": "User registered successfully",
        "user_id": new_user.id,
        "access_token": access_token,
        "token_type": "bearer",
        "role": new_user.user_type,
        "user_type": new_user.user_type,
        "username": new_user.user_name
    }

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
        logger.info(f"OTP generation request for {request.email}") # Log event, NOT the OTP code
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
def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    try:
        ip = request.client.host
        check_login_lockout(ip)
        
        # Case-insensitive email lookup
        db_user = db.query(User).filter(User.email.ilike(user.email)).first()
        
        if not db_user or not verify_password(user.password, db_user.password):
            record_login_failure(ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        if not db_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Please contact support.",
            )
            
        record_login_success(ip)

        # Get user role from database
        user_role = getattr(db_user, 'user_type', ROLE_OWNER) or ROLE_OWNER

        # Create access token with user role
        access_token = create_access_token(
            data={"sub": str(db_user.id), "role": user_role, "user_type": user_role}
        )
        
        # Create refresh token for secure token renewal
        from security import create_refresh_token
        refresh_token = create_refresh_token(db_user.id, user_role)
        
        return {
            "access_token": access_token, 
            "refresh_token": refresh_token,
            "token_type": "bearer", 
            "role": user_role,
            "user_type": user_role,
            "user_id": db_user.id,
            "username": db_user.user_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed unexpectedly for {user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again."
        )

@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token.
    This implements secure token renewal without requiring re-login.
    """
    try:
        from security import decode_token, create_access_token, create_refresh_token
        
        # Decode refresh token
        payload = decode_token(request.refresh_token)
        
        # Validate it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=401,
                detail="Invalid token type. Expected refresh token."
            )
        
        # Extract user_id and role
        user_id = int(payload.get("sub"))
        role = payload.get("role")
        
        # Verify user still exists and is active
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user or not db_user.is_active:
            raise HTTPException(
                status_code=401,
                detail="User not found or inactive"
            )
        
        # Create new access token
        new_access_token = create_access_token(
            data={"sub": str(db_user.id), "role": role, "user_type": role}
        )
        
        # Create new refresh token (rotate refresh tokens for security)
        new_refresh_token = create_refresh_token(db_user.id, role)
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "role": role,
            "user_type": role,
            "user_id": db_user.id
        }
        
    except JWTError as e:
        logger.error(f"JWTError on refresh: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )
    except Exception as e:
        logger.error(f"Token refresh failed unexpectedly: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


class FCMTokenRequest(BaseModel):
    fcm_token: str

@router.post("/fcm-token")
def register_fcm_token(request: FCMTokenRequest, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """Register device FCM token for push notifications"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.fcm_token = request.fcm_token
    db.commit()
    
    return {"msg": "FCM token registered successfully"}
@router.get("/sales")
def get_sales(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
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
            # Flatten invoices into legacy sales objects expected by the frontend
            line_items = db.query(InvoiceLineItem).filter(
                InvoiceLineItem.invoice_id == invoice.id
            ).all()

            if not line_items:
                # If there are no line items, just create a placeholder
                sales_record = {
                    'id': invoice.id,
                    'sale_id': invoice.invoice_number,
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'customer_name': invoice.customer_name,
                    'product_name': 'Unknown Product',
                    'product': 'Unknown Product',
                    'price': float(invoice.total_amount),
                    'quantity': 1,
                    'total': float(invoice.total_amount),
                    'totalAmount': float(invoice.total_amount),
                    'date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                    'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
                    'payment_status': invoice.payment_status,
                }
                sales_data.append(sales_record)
            else:
                for idx, item in enumerate(line_items):
                    sales_record = {
                        'id': f"{invoice.id}_{idx}", # Unique ID for the flattened item
                        'sale_id': invoice.invoice_number, # CRUCIAL: Frontend groups bills using sale_id!
                        'invoice_id': invoice.id,
                        'invoice_number': invoice.invoice_number,
                        'customer_name': invoice.customer_name,
                        'product_name': item.description or 'Unknown',
                        'product': item.description or 'Unknown',
                        'item': item.description or 'Unknown',
                        'price': float(item.unit_price),
                        'quantity': item.quantity,
                        'total': float(item.line_total),
                        'totalAmount': float(item.line_total),
                        'final_amount': float(item.line_total),
                        'date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                        'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
                        'payment_status': invoice.payment_status,
                    }
                    sales_data.append(sales_record)
        
        return sales_data
    except Exception as e:
        logger.error(f"Error fetching sales: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch sales: {str(e)}")

from fastapi import Form
@router.post("/sales")
def create_sale_legacy(
    user_id: int = Depends(get_current_user),
    product_name: str = Form(None),
    product: str = Form(None),
    item: str = Form(None),
    itemName: str = Form(None),
    price: float = Form(0.0),
    quantity: int = Form(1),
    total: float = Form(0.0),
    date: str = Form(None),
    sale_id: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    Handle legacy frontend sales sync.
    """
    try:
        from models import sales, Invoice, InvoiceLineItem
        from datetime import datetime, date as date_obj
        
        sale_date = datetime.now().date()
        if date:
            try:
                sale_date = datetime.strptime(date, "%Y-%m-%d").date()
            except:
                pass
        
        # Resolve the product name from any of the fields the frontend might send
        actual_product_name = product_name or product or item or itemName or "Unknown Product"
                
        # Also create an Invoice so it shows up correctly in the new system
        invoice_number = sale_id if sale_id else f"INV-{int(time.time())}"
        
        from models import ShopProfile
        shop = db.query(ShopProfile).filter(ShopProfile.shop_id == user_id).first()
        shop_id = shop.id if shop else None
        
        # Check if invoice already exists to deduplicate
        existing_invoice = db.query(Invoice).filter(
            Invoice.user_id == user_id, 
            Invoice.invoice_number == str(invoice_number)
        ).first()
        
        if existing_invoice:
            # Check if this exact line item is already in the invoice
            existing_line = db.query(InvoiceLineItem).filter(
                InvoiceLineItem.invoice_id == existing_invoice.id,
                InvoiceLineItem.description == actual_product_name,
                InvoiceLineItem.unit_price == price,
                InvoiceLineItem.quantity == quantity
            ).first()
            
            if not existing_line:
                # Add new line item to existing invoice
                new_line = InvoiceLineItem(
                    invoice_id=existing_invoice.id,
                    description=actual_product_name,
                    quantity=quantity,
                    unit_price=price,
                    line_total=total
                )
                db.add(new_line)
                
                # Update invoice total
                existing_invoice.total_amount = float(existing_invoice.total_amount) + total
                existing_invoice.paid_amount = float(existing_invoice.paid_amount) + total
                
                # Deduct inventory based on product name
                from models import Product, StockMovement
                from sqlalchemy import func
                product_match = db.query(Product).with_for_update().filter(
                    Product.user_id == user_id,
                    func.lower(Product.product_name) == actual_product_name.lower()
                ).first()
                
                if product_match:
                    if (product_match.current_stock or 0) < quantity:
                        db.rollback()
                        raise HTTPException(400, f"Insufficient stock for {actual_product_name}")
                    product_match.current_stock -= quantity
                    movement = StockMovement(
                        product_id=product_match.id,
                        movement_type="OUT",
                        quantity=quantity,
                        reason="Sale via Sync (Merged)",
                        reference_id=str(invoice_number)
                    )
                    db.add(movement)
                
                db.commit()
            
            return {"msg": "Sale synced (merged into existing invoice)", "invoice_id": existing_invoice.id}
        
        # Otherwise, create a new invoice
        new_invoice = Invoice(
            user_id=user_id,
            invoice_number=str(invoice_number),
            total_amount=total,
            paid_amount=total,
            payment_status="PAID",
            payment_method="CASH",
            invoice_date=sale_date
        )
        db.add(new_invoice)
        db.flush()
        
        new_line = InvoiceLineItem(
            invoice_id=new_invoice.id,
            description=actual_product_name,
            quantity=quantity,
            unit_price=price,
            line_total=total
        )
        db.add(new_line)
        
        # Deduct inventory based on product name
        from models import Product, StockMovement
        from sqlalchemy import func
        product_match = db.query(Product).with_for_update().filter(
            Product.user_id == user_id,
            func.lower(Product.product_name) == actual_product_name.lower()
        ).first()
        
        if product_match:
            if (product_match.current_stock or 0) < quantity:
                db.rollback()
                raise HTTPException(400, f"Insufficient stock for {actual_product_name}")
            product_match.current_stock -= quantity
            movement = StockMovement(
                product_id=product_match.id,
                movement_type="OUT",
                quantity=quantity,
                reason="Sale via Sync",
                reference_id=str(invoice_number)
            )
            db.add(movement)
        
        db.commit()
        
        return {"msg": "Sale saved successfully", "invoice_id": new_invoice.id}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating sale: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create sale: {str(e)}")
