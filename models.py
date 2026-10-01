    longitude = Column(Float, index=True, nullable=True)
    
    # Location Information
    address = Column(Text)
    address_line1 = Column(String(200))
    address_line2 = Column(String(200))
    location = Column(String(300))
    latitude = Column(Float)
    longitude = Column(Float)
    city = Column(String(100))
    state = Column(String(100))
    postal_code = Column(String(10))
    
    # Essential Payment & Config
    upi_id = Column(String(100))
    upi_ids = Column(Text)  # JSON string
    shop_categories = Column(Text)  # JSON string
    is_online_store_enabled = Column(Boolean, default=False)
    # Online-only service/setup fee charged once per online order. This does
    # not affect in-store POS sales or normal product prices.
    online_setup_fee = Column(Numeric(10, 2), nullable=False, default=0)
    # Marketplace reputation is maintained from verified customer order reviews.
    rating_score = Column(Float, nullable=False, default=0.0)
    rating_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    
    # Additional Business Details
    pan_number = Column(String(50))
    registration_number = Column(String(100))
    contact_person_name = Column(String(100))
    contact_person_phone = Column(String(20))
    contact_person_email = Column(String(100))
    
    # Branding
    color_primary = Column(String(20))
    color_secondary = Column(String(20))
    logo_file_path = Column(String(500))
    logo_version = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shop_settings = relationship("ShopSettings", back_populates="shop_profile", uselist=False, cascade="all, delete-orphan")

class OnlineOrder(Base):
    """Customer orders placed via the separate customer login"""
    __tablename__ = "online_orders"
    
    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(Integer, nullable=False) # In future, link to a CustomerUser table
    order_status = Column(Enum(OnlineOrderStatus, name="online_order_status"), default=OnlineOrderStatus.PENDING)
    total_amount = Column(Numeric(10, 2), nullable=False)
    online_setup_fee = Column(Numeric(10, 2), nullable=False, default=0)
    delivery_address = Column(Text)
    items_json = Column(Text, nullable=False) # JSON: [{product_id, name, qty, price}, ...]
    idempotency_key = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

class ShopReview(Base):
    """Verified customer review attached to a completed online order."""
    __tablename__ = "shop_reviews"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("online_orders.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    shop_id = Column(Integer, ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("online_customers.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)