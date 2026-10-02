

@router.get("/all-stock")
def get_all_stock(
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all products with current stock from backend.
    Frontend should call this to refresh entire inventory cache.
    """
    try:
        products = db.query(Product).filter(
            Product.user_id == user_id,
            Product.is_active == True
        ).all()
        
        return {
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "total_products": len(products),
            "products": [
                {
                    "id": p.id,
                    "product_id": p.id,
                    "product_name": p.product_name,
                    # The frontend historically called this field "barcode".
                    # SKU is the canonical product barcode in the inventory model,
                    # so expose both names to keep clients consistent.
                    "sku": p.sku,
                    "barcode": p.sku,
                    "current_stock": p.current_stock,
                    "min_stock": p.min_stock,
                    "max_stock": p.max_stock,
                    "unit_price": float(p.unit_price),
                    "category": p.category
                }
                for p in products
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get all stock: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get inventory: {str(e)}")


# ==================== HELPER FUNCTIONS ====================

def _trigger_low_stock_alert(
    product_id: int,
    product_name: str,
    current_stock: int,
    min_stock: int,
    user_id: int
):
    """Background task to trigger low stock alert"""
    try:
        # Here you would implement email/SMS notification logic
        logger.warning(f"Low stock alert: {product_name} (ID: {product_id}) - Stock: {current_stock}, Min: {min_stock}")
        # TODO: Integrate with notification service
    except Exception as e: