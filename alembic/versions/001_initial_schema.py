"""Initial schema migration

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-06-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_details table
    op.create_table(
        'user_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('password', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    # Create sales table
    op.create_table(
        'sales',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shopkeeper_id', sa.Integer(), nullable=False),
        sa.Column('product_name', sa.String(length=100), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('sale_date', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['shopkeeper_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sales_sale_date'), 'sales', ['sale_date'], unique=False)
    op.create_index(op.f('ix_sales_shopkeeper_id'), 'sales', ['shopkeeper_id'], unique=False)
    
    # Create products table
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_name', sa.String(length=100), nullable=False),
        sa.Column('sku', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('current_stock', sa.Integer(), nullable=True),
        sa.Column('min_stock', sa.Integer(), nullable=True),
        sa.Column('max_stock', sa.Integer(), nullable=True),
        sa.Column('reorder_level', sa.Integer(), nullable=True),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('purchase_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'sku', name='uix_user_sku')
    )
    op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)
    op.create_index(op.f('ix_products_user_id'), 'products', ['user_id'], unique=False)
    
    # Create stock_movements table
    op.create_table(
        'stock_movements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('movement_type', sa.Enum('IN', 'OUT', 'ADJUSTMENT', name='movement_type'), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('reference_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create product_batches table
    op.create_table(
        'product_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('batch_number', sa.String(length=100), nullable=True),
        sa.Column('manufacture_date', sa.Date(), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('batch_number')
    )
    
    # Create attendance table
    op.create_table(
        'attendance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('attendance_date', sa.Date(), nullable=False),
        sa.Column('check_in_time', sa.DateTime(), nullable=True),
        sa.Column('check_out_time', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('PRESENT', 'ABSENT', 'LEAVE', 'HALF_DAY', 'LATE', name='attendance_status'), nullable=True),
        sa.Column('working_hours', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['employee_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create leave_requests table
    op.create_table(
        'leave_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('leave_type', sa.Enum('VACATION', 'SICK', 'PERSONAL', name='leave_type'), nullable=False),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('to_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='leave_status'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['employee_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create customers table
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('customer_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('whatsapp_number', sa.String(length=20), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(length=50), nullable=True),
        sa.Column('credit_limit', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('payment_terms', sa.String(length=50), nullable=True),
        sa.Column('contact_preference', sa.Enum('EMAIL', 'WHATSAPP', 'CALL', 'SMS', name='contact_preference'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_phone'), 'customers', ['phone'], unique=False)
    op.create_index(op.f('ix_customers_user_id'), 'customers', ['user_id'], unique=False)
    
    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('customer_name', sa.String(length=100), nullable=True),
        sa.Column('customer_phone', sa.String(length=20), nullable=True),
        sa.Column('invoice_number', sa.String(length=50), nullable=False),
        sa.Column('invoice_date', sa.Date(), server_default=sa.text('now()'), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('tax', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('paid_amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('status', sa.Enum('DRAFT', 'SENT', 'PAID', 'OVERDUE', 'PARTIAL', 'CANCELLED', name='invoice_status'), nullable=True),
        sa.Column('payment_status', sa.Enum('UNPAID', 'PARTIAL', 'PAID', 'OVERDUE', name='payment_status'), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'invoice_number', name='uix_user_invoice_number')
    )
    op.create_index(op.f('ix invoices_invoice_date'), 'invoices', ['invoice_date'], unique=False)
    op.create_index(op.f('ix invoices_payment_status'), 'invoices', ['payment_status'], unique=False)
    op.create_index(op.f('ix invoices_user_id'), 'invoices', ['user_id'], unique=False)
    
    # Create invoice_line_items table
    op.create_table(
        'invoice_line_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('line_total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('payment_method', sa.Enum('CASH', 'CARD', 'TRANSFER', 'CHEQUE', 'ONLINE', name='payment_method'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('payment_date', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('notification_type', sa.Enum('PAYMENT_REMINDER', 'INVOICE_SENT', 'PAYMENT_RECEIVED', 'OVERDUE_ALERT', 'LOW_STOCK', name='notification_type'), nullable=False),
        sa.Column('channel', sa.Enum('EMAIL', 'WHATSAPP', 'SMS', 'CALL', name='notification_channel'), nullable=False),
        sa.Column('recipient', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'SENT', 'FAILED', name='notification_status'), nullable=True),
        sa.Column('attempted_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create agent_escalations table
    op.create_table(
        'agent_escalations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('escalation_reason', sa.String(length=200), nullable=True),
        sa.Column('escalation_level', sa.Integer(), nullable=True),
        sa.Column('priority', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='escalation_priority'), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'RESOLVED', 'FAILED', name='escalation_status'), nullable=True),
        sa.Column('call_initiated', sa.Boolean(), nullable=True),
        sa.Column('call_timestamp', sa.DateTime(), nullable=True),
        sa.Column('call_duration', sa.Integer(), nullable=True),
        sa.Column('call_status', sa.Enum('NOT_CALLED', 'RINGING', 'ANSWERED', 'DECLINED', 'FAILED', name='call_status'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('resolution_date', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['user_details.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create password_resets table
    op.create_table(
        'password_resets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reset_token', sa.String(length=255), nullable=False),
        sa.Column('token_expiry', sa.DateTime(), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reset_token')
    )
    
    # Create tokens table
    op.create_table(
        'tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    
    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    
    # Create session_tokens table
    op.create_table(
        'session_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('access_token', sa.String(length=500), nullable=False),
        sa.Column('refresh_token_id', sa.Integer(), nullable=True),
        sa.Column('device_id', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_activity', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['refresh_token_id'], ['refresh_tokens.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('access_token')
    )
    
    # Create offline_data_queue table
    op.create_table(
        'offline_data_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('data_type', sa.String(length=50), nullable=True),
        sa.Column('data_payload', sa.Text(), nullable=True),
        sa.Column('synced', sa.Boolean(), nullable=True),
        sa.Column('sync_timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create shop_profiles table
    op.create_table(
        'shop_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('shop_name', sa.String(length=200), nullable=False),
        sa.Column('shop_tagline', sa.String(length=500), nullable=True),
        sa.Column('shop_description', sa.Text(), nullable=True),
        sa.Column('shop_type', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('website', sa.String(length=200), nullable=True),
        sa.Column('gst_number', sa.String(length=50), nullable=True),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('location', sa.String(length=300), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('postal_code', sa.String(length=10), nullable=True),
        sa.Column('upi_id', sa.String(length=100), nullable=True),
        sa.Column('is_online_store_enabled', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['shop_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('shop_id')
    )
    
    # Create shop_settings table
    op.create_table(
        'shop_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('monday_open', sa.String(length=10), nullable=True),
        sa.Column('monday_close', sa.String(length=10), nullable=True),
        sa.Column('monday_closed', sa.Boolean(), nullable=True),
        sa.Column('tuesday_open', sa.String(length=10), nullable=True),
        sa.Column('tuesday_close', sa.String(length=10), nullable=True),
        sa.Column('tuesday_closed', sa.Boolean(), nullable=True),
        sa.Column('wednesday_open', sa.String(length=10), nullable=True),
        sa.Column('wednesday_close', sa.String(length=10), nullable=True),
        sa.Column('wednesday_closed', sa.Boolean(), nullable=True),
        sa.Column('thursday_open', sa.String(length=10), nullable=True),
        sa.Column('thursday_close', sa.String(length=10), nullable=True),
        sa.Column('thursday_closed', sa.Boolean(), nullable=True),
        sa.Column('friday_open', sa.String(length=10), nullable=True),
        sa.Column('friday_close', sa.String(length=10), nullable=True),
        sa.Column('friday_closed', sa.Boolean(), nullable=True),
        sa.Column('saturday_open', sa.String(length=10), nullable=True),
        sa.Column('saturday_close', sa.String(length=10), nullable=True),
        sa.Column('saturday_closed', sa.Boolean(), nullable=True),
        sa.Column('sunday_open', sa.String(length=10), nullable=True),
        sa.Column('sunday_close', sa.String(length=10), nullable=True),
        sa.Column('sunday_closed', sa.Boolean(), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=True),
        sa.Column('tax_type', sa.String(length=20), nullable=True),
        sa.Column('igst_percentage', sa.Float(), nullable=True),
        sa.Column('sgst_percentage', sa.Float(), nullable=True),
        sa.Column('utgst_percentage', sa.Float(), nullable=True),
        sa.Column('flat_tax_percentage', sa.Float(), nullable=True),
        sa.Column('accept_cash', sa.Boolean(), nullable=True),
        sa.Column('accept_card', sa.Boolean(), nullable=True),
        sa.Column('accept_upi', sa.Boolean(), nullable=True),
        sa.Column('accept_bank_transfer', sa.Boolean(), nullable=True),
        sa.Column('accept_cheque', sa.Boolean(), nullable=True),
        sa.Column('accept_wallet', sa.Boolean(), nullable=True),
        sa.Column('card_payment_gateway', sa.String(length=50), nullable=True),
        sa.Column('upi_merchant_id', sa.String(length=100), nullable=True),
        sa.Column('currency_code', sa.String(length=3), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('theme_mode', sa.String(length=20), nullable=True),
        sa.Column('receipt_format', sa.String(length=20), nullable=True),
        sa.Column('low_stock_alert_threshold', sa.Integer(), nullable=True),
        sa.Column('send_email_on_sale', sa.Boolean(), nullable=True),
        sa.Column('send_sms_on_sale', sa.Boolean(), nullable=True),
        sa.Column('send_notification_on_order', sa.Boolean(), nullable=True),
        sa.Column('enable_inventory_tracking', sa.Boolean(), nullable=True),
        sa.Column('enable_customer_loyalty', sa.Boolean(), nullable=True),
        sa.Column('enable_batch_tracking', sa.Boolean(), nullable=True),
        sa.Column('enable_multi_branch', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['shop_id'], ['shop_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('shop_id')
    )
    
    # Create loyalty_tiers table
    op.create_table(
        'loyalty_tiers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tier_name', sa.String(length=50), nullable=False),
        sa.Column('tier_level', sa.Integer(), nullable=False),
        sa.Column('min_points', sa.Integer(), nullable=True),
        sa.Column('discount_percentage', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create customer_loyalty table
    op.create_table(
        'customer_loyalty',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('total_points', sa.Integer(), nullable=True),
        sa.Column('points_redeemed', sa.Integer(), nullable=True),
        sa.Column('available_points', sa.Integer(), nullable=True),
        sa.Column('current_tier_id', sa.Integer(), nullable=True),
        sa.Column('tier_updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_tier_bump_notified', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['current_tier_id'], ['loyalty_tiers.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create loyalty_transactions table
    op.create_table(
        'loyalty_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_loyalty_id', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.Enum('EARN', 'REDEEM', 'ADJUST', 'EXPIRE', name='loyalty_transaction_type'), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('reference_id', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['customer_loyalty_id'], ['customer_loyalty.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create upi_ledger table
    op.create_table(
        'upi_ledger',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=True),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('upi_id', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('upi_reference', sa.String(length=100), nullable=True),
        sa.Column('customer_upi', sa.String(length=100), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'CONFIRM', 'FAILED', 'REFUND', name='upi_status'), nullable=True),
        sa.Column('payment_date', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shop_id'], ['shop_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('upi_reference')
    )
    
    # Create deliveries table
    op.create_table(
        'deliveries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('delivery_address', sa.Text(), nullable=False),
        sa.Column('delivery_date', sa.Date(), nullable=True),
        sa.Column('delivery_time', sa.String(length=20), nullable=True),
        sa.Column('assigned_to', sa.String(length=100), nullable=True),
        sa.Column('special_instructions', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shop_id'], ['shop_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create delivery_tracking table
    op.create_table(
        'delivery_tracking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('delivery_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'OUT', 'DELIVERED', 'FAILED', 'RETURNED', name='delivery_status'), nullable=False),
        sa.Column('status_timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('staff_name', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('location_lat', sa.Float(), nullable=True),
        sa.Column('location_lng', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['delivery_id'], ['deliveries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create billing_templates table
    op.create_table(
        'billing_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('template_name', sa.String(length=100), nullable=False),
        sa.Column('template_data', sa.Text(), nullable=True),
        sa.Column('last_used', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create billing_counters table
    op.create_table(
        'billing_counters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('staff_name', sa.String(length=100), nullable=False),
        sa.Column('counter_number', sa.Integer(), nullable=False),
        sa.Column('billing_pin', sa.String(length=4), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create sales_by_counter table
    op.create_table(
        'sales_by_counter',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=True),
        sa.Column('counter_id', sa.Integer(), nullable=True),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('staff_name', sa.String(length=100), nullable=True),
        sa.Column('counter_number', sa.Integer(), nullable=True),
        sa.Column('sale_date', sa.Date(), nullable=True),
        sa.Column('sale_amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.ForeignKeyConstraint(['counter_id'], ['billing_counters.id']),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shop_id'], ['shop_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create customer_credit_scores table
    op.create_table(
        'customer_credit_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('credit_score', sa.Integer(), nullable=True),
        sa.Column('score_badge', sa.Enum('CAUTION', 'REGULAR', 'TRUSTED', name='credit_badge'), nullable=True),
        sa.Column('suggested_credit_limit', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('total_purchases', sa.Integer(), nullable=True),
        sa.Column('on_time_payments', sa.Integer(), nullable=True),
        sa.Column('late_payments', sa.Integer(), nullable=True),
        sa.Column('days_since_last_purchase', sa.Integer(), nullable=True),
        sa.Column('avg_days_to_pay', sa.Float(), nullable=True),
        sa.Column('last_calculated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create customer_occasions table
    op.create_table(
        'customer_occasions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('occasion_type', sa.Enum('BIRTHDAY', 'ANNIVERSARY', 'WEDDING', 'CUSTOM', name='occasion_type'), nullable=False),
        sa.Column('occasion_date', sa.Date(), nullable=False),
        sa.Column('discount_percentage', sa.Float(), nullable=True),
        sa.Column('last_notification_sent', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create daily_reports table
    op.create_table(
        'daily_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('total_revenue', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('total_expenses', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('total_profit', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('bill_count', sa.Integer(), nullable=True),
        sa.Column('top_product_id', sa.Integer(), nullable=True),
        sa.Column('top_product_name', sa.String(length=100), nullable=True),
        sa.Column('top_product_qty', sa.Integer(), nullable=True),
        sa.Column('cash_collected', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('upi_collected', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('card_collected', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('whatsapp_sent', sa.Boolean(), nullable=True),
        sa.Column('whatsapp_sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['top_product_id'], ['products.id'),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create festival_events table
    op.create_table(
        'festival_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('festival_name', sa.String(length=100), nullable=False),
        sa.Column('festival_date', sa.Date(), nullable=False),
        sa.Column('festival_year', sa.Integer(), nullable=False),
        sa.Column('days_until', sa.Integer(), nullable=True),
        sa.Column('top_products_last_year', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create chatbot_context table
    op.create_table(
        'chatbot_context',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('shop_name', sa.String(length=100), nullable=True),
        sa.Column('shop_type', sa.String(length=100), nullable=True),
        sa.Column('location', sa.String(length=300), nullable=True),
        sa.Column('top_5_products', sa.Text(), nullable=True),
        sa.Column('last_10_sales', sa.Text(), nullable=True),
        sa.Column('total_customers', sa.Integer(), nullable=True),
        sa.Column('avg_sale_value', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('last_updated', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create workers table
    op.create_table(
        'workers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shopkeeper_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('salary', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('assigned_work', sa.String(length=200), nullable=True),
        sa.Column('position', sa.String(length=100), nullable=True),
        sa.Column('join_date', sa.Date(), server_default=sa.text('now()'), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('pin', sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(['shopkeeper_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create khata_balances table
    op.create_table(
        'khata_balances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('customer_phone', sa.String(length=20), nullable=False),
        sa.Column('customer_name', sa.String(length=100), nullable=True),
        sa.Column('khata_balance', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('last_transaction', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['shop_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('shop_id', 'customer_phone', name='uix_shop_customer_khata')
    )
    op.create_index(op.f('ix_khata_balances_customer_phone'), 'khata_balances', ['customer_phone'], unique=False)
    op.create_index(op.f('ix_khata_balances_shop_id'), 'khata_balances', ['shop_id'], unique=False)
    
    # Create khata_history table
    op.create_table(
        'khata_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('khata_id', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.Enum('INVOICE', 'PAYMENT', 'ADJUSTMENT', name='khata_transaction_type'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('reference_id', sa.String(length=100), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('transaction_date', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['khata_id'], ['khata_balances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create shop_expenses table
    op.create_table(
        'shop_expenses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['shop_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create online_orders table
    op.create_table(
        'online_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('order_status', sa.Enum('PENDING', 'ACCEPTED', 'DISPATCHED', 'DELIVERED', 'REJECTED', name='order_status'), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('delivery_address', sa.Text(), nullable=True),
        sa.Column('items_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['shop_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create purchase_orders table
    op.create_table(
        'purchase_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('supplier_name', sa.String(length=100), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'SENT', 'DELIVERED', 'CANCELLED', name='po_status'), nullable=True),
        sa.Column('total_cost', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('items_json', sa.Text(), nullable=False),
        sa.Column('expected_delivery', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['shop_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create bank_reconciliations table
    op.create_table(
        'bank_reconciliations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('recon_date', sa.Date(), nullable=False),
        sa.Column('expected_upi_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('actual_bank_deposit', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('status', sa.Enum('MATCHED', 'DISCREPANCY', 'PENDING', name='recon_status'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['shop_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create universal_transactions table
    op.create_table(
        'universal_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('tx_type', sa.Enum('INCOME', 'EXPENSE', name='tx_type'), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('reference_id', sa.String(length=100), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('tx_date', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['shop_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create gift_cards table
    op.create_table(
        'gift_cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('card_code', sa.String(length=50), nullable=False),
        sa.Column('initial_balance', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('current_balance', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('issued_to', sa.String(length=100), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['shop_id'], ['user_details.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('card_code')
    )


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table('gift_cards')
    op.drop_table('universal_transactions')
    op.drop_table('bank_reconciliations')
    op.drop_table('purchase_orders')
    op.drop_table('online_orders')
    op.drop_table('shop_expenses')
    op.drop_table('khata_history')
    op.drop_table('khata_balances')
    op.drop_table('workers')
    op.drop_table('chatbot_context')
    op.drop_table('festival_events')
    op.drop_table('daily_reports')
    op.drop_table('customer_occasions')
    op.drop_table('customer_credit_scores')
    op.drop_table('sales_by_counter')
    op.drop_table('billing_counters')
    op.drop_table('billing_templates')
    op.drop_table('delivery_tracking')
    op.drop_table('deliveries')
    op.drop_table('upi_ledger')
    op.drop_table('loyalty_transactions')
    op.drop_table('customer_loyalty')
    op.drop_table('loyalty_tiers')
    op.drop_table('shop_settings')
    op.drop_table('shop_profiles')
    op.drop_table('offline_data_queue')
    op.drop_table('session_tokens')
    op.drop_table('refresh_tokens')
    op.drop_table('tokens')
    op.drop_table('password_resets')
    op.drop_table('agent_escalations')
    op.drop_table('notifications')
    op.drop_table('payments')
    op.drop_table('invoice_line_items')
    op.drop_table('invoices')
    op.drop_table('customers')
    op.drop_table('leave_requests')
    op.drop_table('attendance')
    op.drop_table('product_batches')
    op.drop_table('stock_movements')
    op.drop_table('products')
    op.drop_table('sales')
    op.drop_table('user_details')
