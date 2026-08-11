"""
🤖 AI Endpoints — AI Shop Pro Enterprise Backend
"""
import math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from db import get_db
from models import Product, Sales, UniversalTransaction
from security import owner_only

router = APIRouter(prefix="/ai", tags=["AI Features"])

@router.get("/predict-inventory")
def predict_inventory(
    days_to_forecast: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only)
):
    shop_id = current_user
    products = db.query(Product).filter(Product.user_id == shop_id, Product.is_active == True).all()
    predictions = []
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    for p in products:
        if p.current_stock <= 0:
            continue
            
        sold = db.query(func.sum(Sales.quantity)).filter(
            Sales.product_name == p.product_name,
            Sales.user_id == shop_id,
            Sales.created_at >= thirty_days_ago
        ).scalar() or 0
        
        velocity = float(sold) / 30.0
        if velocity <= 0.01:
            continue
            
        days_until_empty = p.current_stock / velocity
        if days_until_empty <= days_to_forecast:
            predictions.append({
                "product_id": p.id,
                "product_name": p.product_name,
                "current_stock": p.current_stock,
                "sales_velocity_per_day": round(velocity, 2),
                "estimated_days_remaining": round(days_until_empty, 1),
                "recommended_order_quantity": int(math.ceil(velocity * 14))
            })
            
    predictions.sort(key=lambda x: x["estimated_days_remaining"])
    return {
        "forecast_window_days": days_to_forecast,
        "items_at_risk": len(predictions),
        "predictions": predictions
    }

@router.post("/conversational-query")
def query_analytics(
    query: str = Query(..., description="E.g., 'What was my revenue yesterday?'"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only)
):
    shop_id = current_user
    q_lower = query.lower()
    
    response_text = "I'm sorry, I couldn't understand that query. Try asking about 'revenue', 'expenses', or 'top products'."
    data_payload = None
    
    if "revenue" in q_lower or "sales" in q_lower:
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        revenue = db.query(func.sum(UniversalTransaction.amount)).filter(
            UniversalTransaction.shop_id == shop_id,
            UniversalTransaction.tx_type == "INCOME",
            UniversalTransaction.tx_date >= today_start
        ).scalar() or 0
        
        response_text = f"Your total revenue today is ₹{revenue:.2f}."
        data_payload = {"metric": "daily_revenue", "value": float(revenue)}
        
    elif "expense" in q_lower or "spent" in q_lower:
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        expenses = db.query(func.sum(UniversalTransaction.amount)).filter(
            UniversalTransaction.shop_id == shop_id,
            UniversalTransaction.tx_type == "EXPENSE",
            UniversalTransaction.tx_date >= today_start
        ).scalar() or 0
        
        response_text = f"Your total expenses today are ₹{expenses:.2f}."
        data_payload = {"metric": "daily_expenses", "value": float(expenses)}
        
    elif "top" in q_lower and "product" in q_lower:
        top_sales = (
            db.query(Sales.product_name, func.sum(Sales.quantity).label("total_qty"))
            .filter(Sales.user_id == shop_id)
            .group_by(Sales.product_name)
            .order_by(func.sum(Sales.quantity).desc())
            .limit(3)
            .all()
        )
        if top_sales:
            items = ", ".join([f"{r.product_name} ({r.total_qty} sold)" for r in top_sales])
            response_text = f"Your top 3 products are: {items}."
            data_payload = {"metric": "top_products", "items": [{"name": r.product_name, "qty": r.total_qty} for r in top_sales]}
        else:
            response_text = "You haven't sold any products yet."
            
    return {
        "query": query,
        "response": response_text,
        "data": data_payload
    }
