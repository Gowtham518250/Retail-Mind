import logging
from typing import Optional, List
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db
from models import WhatsappOrder, WhatsappOrderStatus, ShopProfile
from security import owner_only, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp-orders", tags=["WhatsApp Orders"])

# =====================
# SCHEMAS
# =====================
class CreateWhatsappOrder(BaseModel):
    raw_text: str = Field(..., min_length=1)
    sender_number: Optional[str] = None
    parsed_items_json: Optional[str] = None
    total_amount: Optional[float] = 0.0

class WhatsappOrderResponse(BaseModel):
    id: int
    shop_id: int
    sender_number: Optional[str]
    raw_text: str
    parsed_items_json: Optional[str]
    status: str
    total_amount: float
    created_at: str

    class Config:
        from_attributes = True

# =====================
# ENDPOINTS
# =====================
@router.post("", response_model=WhatsappOrderResponse)
def create_whatsapp_order(
    data: CreateWhatsappOrder,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Save a pending WhatsApp order received from the app's sharing intent."""
    shop_id = current_user
    
    order = WhatsappOrder(
        shop_id=shop_id,
        sender_number=data.sender_number,
        raw_text=data.raw_text,
        parsed_items_json=data.parsed_items_json,
        status=WhatsappOrderStatus.PENDING,
        total_amount=data.total_amount,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    # Format created_at for Pydantic response
    resp = order.__dict__.copy()
    resp['created_at'] = order.created_at.isoformat()
    return resp

@router.get("", response_model=List[WhatsappOrderResponse])
def get_whatsapp_orders(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Get all WhatsApp orders for the shop (Pending Queue)."""
    shop_id = current_user
    
    q = db.query(WhatsappOrder).filter(WhatsappOrder.shop_id == shop_id)
    if status:
        try:
            status_enum = WhatsappOrderStatus(status.upper())
            q = q.filter(WhatsappOrder.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
            
    orders = q.order_by(WhatsappOrder.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for o in orders:
        o_dict = o.__dict__.copy()
        o_dict['created_at'] = o.created_at.isoformat()
        result.append(o_dict)
    return result

@router.put("/{order_id}/status")
def update_whatsapp_order_status(
    order_id: int,
    status: str = Query(..., description="ACCEPTED, COMPLETED, REJECTED"),
    parsed_items_json: Optional[str] = Query(None, description="Updated parsed items if modified during acceptance"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Update the status of a WhatsApp order."""
    shop_id = current_user
    
    order = db.query(WhatsappOrder).filter(
        WhatsappOrder.id == order_id,
        WhatsappOrder.shop_id == shop_id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    try:
        new_status = WhatsappOrderStatus(status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    order.status = new_status
    if parsed_items_json is not None:
        order.parsed_items_json = parsed_items_json
        
    db.commit()
    
    return {"message": "Status updated successfully", "status": order.status.value}
