-- ==========================================
-- RAG_APP Database Initialization
-- PostgreSQL Setup for Data_Analytics
-- ==========================================

-- Connect to the database created by Docker
\c Data_Analytics;

-- ==========================================
-- Extensions
-- ==========================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ==========================================
-- Users Table
-- ==========================================
CREATE TABLE IF NOT EXISTS user_details (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_email ON user_details(email);

-- ==========================================
-- Sales Table
-- ==========================================
CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    shopkeeper_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    product_name VARCHAR(100) NOT NULL,
    price NUMERIC(10, 2) NOT NULL CHECK (price > 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    total NUMERIC(10, 2) NOT NULL CHECK (total > 0),
    sale_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_total CHECK (total = price * quantity)
);

CREATE INDEX IF NOT EXISTS idx_sales_shopkeeper_id ON sales(shopkeeper_id);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_name);

-- ==========================================
-- Documents Table (RAG)
-- ==========================================
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    shopkeeper_id INTEGER REFERENCES user_details(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_size INTEGER,
    file_hash VARCHAR(64) UNIQUE,
    content_preview TEXT,
    page_count INTEGER,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_doc_shopkeeper_id ON documents(shopkeeper_id);
CREATE INDEX IF NOT EXISTS idx_doc_status ON documents(status);

-- ==========================================
-- Audit Logs
-- ==========================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES user_details(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_logs(user_id);

-- ==========================================
-- Shop Profiles Table
-- ==========================================
CREATE TABLE IF NOT EXISTS shop_profiles (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL UNIQUE REFERENCES user_details(id) ON DELETE CASCADE,
    shop_name VARCHAR(200) NOT NULL,
    shop_tagline VARCHAR(500),
    shop_description TEXT,
    shop_type VARCHAR(100) DEFAULT 'General',
    phone VARCHAR(20),
    email VARCHAR(100),
    website VARCHAR(200),
    gst_number VARCHAR(50),
    logo_url VARCHAR(500),
    address TEXT,
    location VARCHAR(300),
    latitude FLOAT,
    longitude FLOAT,
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(10),
    upi_id VARCHAR(100),
    is_online_store_enabled BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_shop_profiles_shop_id ON shop_profiles(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_profiles_active ON shop_profiles(is_active);

-- ==========================================
-- Products Table
-- ==========================================
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    product_name VARCHAR(100) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    description TEXT,
    current_stock INTEGER DEFAULT 0,
    min_stock INTEGER DEFAULT 10,
    max_stock INTEGER DEFAULT 100,
    reorder_level INTEGER DEFAULT 20,
    unit_price NUMERIC(10, 2) NOT NULL,
    purchase_price NUMERIC(10, 2) DEFAULT 0,
    category VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, sku)
);

CREATE INDEX IF NOT EXISTS idx_products_user_id ON products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- ==========================================
-- Customers Table
-- ==========================================
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    customer_name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(20) NOT NULL,
    whatsapp_number VARCHAR(20),
    address TEXT,
    city VARCHAR(50),
    credit_limit NUMERIC(10, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_customers_user_id ON customers(user_id);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);

-- ==========================================
-- Attendance Table
-- ==========================================
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    check_in_time TIMESTAMP,
    check_out_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ABSENT',
    working_hours FLOAT DEFAULT 0.0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attendance_employee_id ON attendance(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(attendance_date);

-- ==========================================
-- Online Orders Table
-- ==========================================
CREATE TABLE IF NOT EXISTS online_orders (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL,
    order_status VARCHAR(50) DEFAULT 'PENDING',
    total_amount NUMERIC(10, 2) NOT NULL,
    delivery_address TEXT,
    items_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_online_orders_shop_id ON online_orders(shop_id);
CREATE INDEX IF NOT EXISTS idx_online_orders_status ON online_orders(order_status);

-- ==========================================
-- Default Admin User
-- ==========================================
INSERT INTO user_details (user_name, email, password)
VALUES (
    'Admin User',
    'admin@rag-app.local',
    '$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jKMm'
)
ON CONFLICT (email) DO NOTHING;