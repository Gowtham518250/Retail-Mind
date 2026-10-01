):
    """Send a backend-generated OTP to the customer's registered email before delivery."""
    shop_id = current_user["user_id"]
    order = db.query(OnlineOrder).filter(
        OnlineOrder.id == order_id,
        OnlineOrder.shop_id == shop_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.order_status != "DISPATCHED":
        raise HTTPException(
            status_code=409,
            detail="Customer delivery OTP can only be requested for a dispatched order.",
        )

    # Legacy/guest orders can point at an inactive customer placeholder. The
    # delivery challenge is tied to the order's customer ID, so do not reject
    # the record solely because is_active is false.
    customer = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.id == order.customer_id,
    ).first()
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer account record for this order could not be found.",
        )

    customer_email = (customer.email or "").strip().lower()
    if (
        not customer_email
        or customer_email.endswith("@example.com")
        or customer_email.startswith("guest_")
    ):
        raise HTTPException(
            status_code=409,
            detail="This customer account has no verified email for delivery OTP. Ask the customer to add a real email address before delivery.",
        )
    if not EmailNotificationService:
        raise HTTPException(
            status_code=503,
            detail="Email delivery is not configured on the server.",
        )

    now = datetime.utcnow()
    latest = db.query(OnlineOrderDeliveryOtp).filter(
        OnlineOrderDeliveryOtp.order_id == order.id,
        OnlineOrderDeliveryOtp.customer_id == customer.id,
        OnlineOrderDeliveryOtp.used == False,
    ).order_by(OnlineOrderDeliveryOtp.id.desc()).first()
    if latest and latest.created_at and now - latest.created_at < timedelta(seconds=60):
        remaining = 60 - int((now - latest.created_at).total_seconds())
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {max(1, remaining)} seconds before requesting another delivery OTP.",
        )

    # Invalidate every older challenge for this order before issuing a new one.
    db.query(OnlineOrderDeliveryOtp).filter(
        OnlineOrderDeliveryOtp.order_id == order.id,
        OnlineOrderDeliveryOtp.customer_id == customer.id,
        OnlineOrderDeliveryOtp.used == False,
    ).update({"used": True}, synchronize_session=False)

    otp = f"{secrets.randbelow(900000) + 100000:06d}"