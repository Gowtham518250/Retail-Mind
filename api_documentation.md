# 📚 Retail Mind Complete API Documentation

This document contains all 185 available endpoints and their required payload schemas.

## 🔹 Authentication
### `[POST] /auth/register`
**Description:** Register

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | ✅ Yes | Username |
| `password` | string | ✅ Yes | Password |
| `email` | string | ✅ Yes | Email |
| `user_type` | string | ❌ No | User Type |

---

### `[POST] /auth/send-otp`
**Description:** Send Otp

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | ✅ Yes | Email |
| `purpose` | string | ❌ No | Purpose |

---

### `[POST] /auth/verify-otp`
**Description:** Verify Otp

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | ✅ Yes | Email |
| `otp` | string | ✅ Yes | Otp |

---

### `[POST] /auth/login`
**Description:** Login

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | ✅ Yes | Email |
| `password` | string | ✅ Yes | Password |

---

### `[GET] /auth/sales`
**Description:** Get Sales

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |

---

### `[POST] /auth/sales`
**Description:** Create Sale Legacy

---

## 🔹 Authentication Hardened
### `[POST] /api/auth-hardened/register`
**Description:** Register User

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | ✅ Yes | Email |
| `password` | string | ✅ Yes | Password |
| `user_name` | string | ✅ Yes | User Name |

---

### `[POST] /api/auth-hardened/login`
**Description:** Login User

---

### `[POST] /api/auth-hardened/refresh`
**Description:** Refresh Token

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refresh_token` | string | ✅ Yes | Refresh Token |

---

### `[POST] /api/auth-hardened/logout`
**Description:** Logout User

---

### `[POST] /api/auth-hardened/logout-all`
**Description:** Logout All Devices

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |

---

### `[GET] /api/auth-hardened/active-sessions/{user_id}`
**Description:** Get Active Sessions

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | path | ✅ Yes | integer |

---

## 🔹 Session Management
### `[POST] /api/session/refresh`
**Description:** Refresh Token

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refresh_token` | string | ✅ Yes | Refresh Token |
| `device_id` | string | ❌ No | Device Id |

---

### `[POST] /api/session/logout`
**Description:** Logout

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `access_token` | string | ✅ Yes | Access Token |

---

### `[POST] /api/session/logout-all`
**Description:** Logout All Devices

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | integer | ✅ Yes | User Id |

---

### `[GET] /api/session/active/{user_id}`
**Description:** Get Active Sessions

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | path | ✅ Yes | integer |

---

### `[POST] /api/session/offline/queue`
**Description:** Sync Offline Data

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | integer | ✅ Yes | User Id |
| `data_type` | string | ✅ Yes | Data Type |
| `payload` | object | ✅ Yes | Payload |

---

### `[POST] /api/session/offline/sync`
**Description:** Sync All Offline Data

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | integer | ✅ Yes | User Id |

---

## 🔹 Bill Generation
### `[POST] /bill/Generate/Bill`
**Description:** Bill Generte

---

### `[GET] /bill/scan/{bill_id}`
**Description:** Get Bill

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `bill_id` | path | ✅ Yes | string |

---

### `[GET] /bill/qr/{bill_id}`
**Description:** Get Qr Image

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `bill_id` | path | ✅ Yes | string |

---

## 🔹 Inventory Management
### `[POST] /api/inventory/products`
**Description:** Create Product

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_name` | string | ✅ Yes | Product Name |
| `sku` | string | ✅ Yes | Sku |
| `description` | string | ❌ No | Description |
| `current_stock` | integer | ❌ No | Current Stock |
| `min_stock` | integer | ❌ No | Min Stock |
| `max_stock` | integer | ❌ No | Max Stock |
| `reorder_level` | integer | ❌ No | Reorder Level |
| `unit_price` | number | ✅ Yes | Unit Price |
| `category` | string | ❌ No | Category |

---

### `[GET] /api/inventory/products`
**Description:** Get Products

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `category` | query | ❌ No | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /api/inventory/products/{product_id}`
**Description:** Get Product

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `product_id` | path | ✅ Yes | integer |

---

### `[PUT] /api/inventory/products/{product_id}`
**Description:** Update Product

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_name` | string | ❌ No | Product Name |
| `description` | string | ❌ No | Description |
| `min_stock` | string | ❌ No | Min Stock |
| `max_stock` | string | ❌ No | Max Stock |
| `reorder_level` | string | ❌ No | Reorder Level |
| `unit_price` | string | ❌ No | Unit Price |
| `category` | string | ❌ No | Category |

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `product_id` | path | ✅ Yes | integer |

---

### `[DELETE] /api/inventory/products/{product_id}`
**Description:** Delete Product

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `product_id` | path | ✅ Yes | integer |

---

### `[POST] /api/inventory/stock-movement`
**Description:** Create Stock Movement

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_id` | integer | ✅ Yes | Product Id |
| `movement_type` | string | ✅ Yes | Movement Type |
| `quantity` | integer | ✅ Yes | Quantity |
| `reason` | string | ❌ No | Reason |
| `reference_id` | string | ❌ No | Reference Id |

---

### `[GET] /api/inventory/stock-movements/{product_id}`
**Description:** Get Stock Movements

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `product_id` | path | ✅ Yes | integer |
| `days` | query | ❌ No | integer |

---

### `[GET] /api/inventory/low-stock`
**Description:** Get Low Stock Products

---

### `[GET] /api/inventory/stock-alerts`
**Description:** Get Stock Alerts

---

### `[POST] /api/inventory/batches`
**Description:** Create Batch

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_id` | integer | ✅ Yes | Product Id |
| `batch_number` | string | ✅ Yes | Batch Number |
| `manufacture_date` | string | ❌ No | Manufacture Date |
| `expiry_date` | string | ❌ No | Expiry Date |
| `quantity` | integer | ✅ Yes | Quantity |

---

### `[GET] /api/inventory/batches/{product_id}`
**Description:** Get Batches

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `product_id` | path | ✅ Yes | integer |

---

### `[GET] /api/inventory/expiring-batches`
**Description:** Get Expiring Batches

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |
| `days` | query | ❌ No | integer |

---

### `[GET] /api/inventory/analytics/stock-value`
**Description:** Get Stock Value

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |

---

### `[GET] /api/inventory/analytics/inventory-status`
**Description:** Get Inventory Status

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |

---

## 🔹 Inventory Sync Service
### `[POST] /api/inventory-sync/deduct-stock`
**Description:** Deduct Stock With Idempotency

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_id` | integer | ✅ Yes | Product Id |
| `quantity` | integer | ✅ Yes | Quantity |
| `reason` | string | ❌ No | Reason |
| `reference_id` | string | ✅ Yes | Reference Id |
| `idempotency_key` | string | ✅ Yes | Idempotency Key |

---

### `[POST] /api/inventory-sync/deduct-stock-batch`
**Description:** Deduct Stock Batch

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `updates` | array | ✅ Yes | Updates |

---

### `[POST] /api/inventory-sync/reconcile`
**Description:** Reconcile Inventory

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `local_inventory` | array | ✅ Yes | Local Inventory |

---

### `[GET] /api/inventory-sync/current-stock/{product_id}`
**Description:** Get Current Stock

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `product_id` | path | ✅ Yes | integer |

---

### `[GET] /api/inventory-sync/all-stock`
**Description:** Get All Stock

---

## 🔹 Inventory Reconciliation
### `[POST] /api/inventory-reconcile/full-reconciliation`
**Description:** Full Inventory Reconciliation

---

### `[POST] /api/inventory-reconcile/correct-stock`
**Description:** Correct Stock Manually

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_id` | integer | ✅ Yes | Product Id |
| `correct_stock` | integer | ✅ Yes | Correct Stock |
| `reason` | string | ✅ Yes | Reason |

---

### `[GET] /api/inventory-reconcile/audit-trail/{product_id}`
**Description:** Get Stock Audit Trail

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `product_id` | path | ✅ Yes | integer |
| `days` | query | ❌ No | integer |

---

### `[POST] /api/inventory-reconcile/auto-fix-discrepancies`
**Description:** Auto Fix Discrepancies

---

## 🔹 Sales Restoration
### `[POST] /api/sales-restore/restore-all`
**Description:** Restore All Sales

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start_date` | string | ❌ No | Start Date |
| `end_date` | string | ❌ No | End Date |
| `include_stock_impact` | boolean | ❌ No | Include Stock Impact |

---

### `[GET] /api/sales-restore/restore-summary`
**Description:** Get Restore Summary

---

### `[POST] /api/sales-restore/restore-customers`
**Description:** Restore Customers

---

## 🔹 Attendance Management
### `[POST] /api/attendance/workers`
**Description:** Create Worker

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ Yes | Name |
| `phone` | string | ❌ No | Phone |
| `address` | string | ❌ No | Address |
| `salary` | number | ❌ No | Salary |
| `assigned_work` | string | ❌ No | Assigned Work |
| `position` | string | ❌ No | Position |
| `pin` | string | ❌ No | Pin |

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |

---

### `[GET] /api/attendance/workers`
**Description:** Get Workers

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |

---

### `[PUT] /api/attendance/workers/{worker_id}`
**Description:** Update Worker

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ❌ No | Name |
| `phone` | string | ❌ No | Phone |
| `address` | string | ❌ No | Address |
| `salary` | string | ❌ No | Salary |
| `assigned_work` | string | ❌ No | Assigned Work |
| `position` | string | ❌ No | Position |
| `pin` | string | ❌ No | Pin |

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `worker_id` | path | ✅ Yes | integer |

---

### `[DELETE] /api/attendance/workers/{worker_id}`
**Description:** Delete Worker

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `worker_id` | path | ✅ Yes | integer |

---

### `[POST] /api/attendance/check-in`
**Description:** Employee Check In

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `employee_id` | query | ✅ Yes | integer |

---

### `[POST] /api/attendance/check-out`
**Description:** Employee Check Out

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `employee_id` | query | ✅ Yes | integer |

---

### `[POST] /api/attendance/record-manual`
**Description:** Record Manual Attendance

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `employee_id` | integer | ✅ Yes | Employee Id |
| `attendance_date` | string | ✅ Yes | Attendance Date |
| `status` | string | ✅ Yes | Status |
| `notes` | string | ❌ No | Notes |

---

### `[GET] /api/attendance/employee/{employee_id}`
**Description:** Get Employee Attendance

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `employee_id` | path | ✅ Yes | integer |
| `from_date` | query | ❌ No | string |
| `to_date` | query | ❌ No | string |

---

### `[GET] /api/attendance/date/{date_str}`
**Description:** Get Attendance By Date

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `date_str` | path | ✅ Yes | string |

---

### `[POST] /api/attendance/leave-request`
**Description:** Request Leave

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `employee_id` | integer | ✅ Yes | Employee Id |
| `leave_type` | string | ✅ Yes | Leave Type |
| `from_date` | string | ✅ Yes | From Date |
| `to_date` | string | ✅ Yes | To Date |
| `reason` | string | ❌ No | Reason |

---

### `[GET] /api/attendance/leave-requests`
**Description:** Get Leave Requests

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `employee_id` | query | ❌ No | string |
| `status` | query | ❌ No | string |

---

### `[PUT] /api/attendance/leave-request/{leave_id}/approve`
**Description:** Approve Leave

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `leave_id` | path | ✅ Yes | integer |

---

### `[PUT] /api/attendance/leave-request/{leave_id}/reject`
**Description:** Reject Leave

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `leave_id` | path | ✅ Yes | integer |

---

### `[GET] /api/attendance/analytics/summary`
**Description:** Get Attendance Summary

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `days` | query | ❌ No | integer |

---

### `[GET] /api/attendance/analytics/employee/{employee_id}`
**Description:** Get Employee Analytics

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `employee_id` | path | ✅ Yes | integer |
| `days` | query | ❌ No | integer |

---

## 🔹 Invoices & Billing
### `[POST] /api/invoices/sync`
**Description:** Sync Offline Invoice

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `invoice_number` | string | ✅ Yes | Invoice Number |
| `offline_id` | string | ❌ No | Offline Id |
| `customer_phone` | string | ❌ No | Customer Phone |
| `customer_name` | string | ❌ No | Customer Name |
| `total_amount` | number | ✅ Yes | Total Amount |
| `paid_amount` | number | ❌ No | Paid Amount |
| `tax` | number | ❌ No | Tax |
| `payment_status` | string | ❌ No | Payment Status |
| `line_items` | array | ✅ Yes | Line Items |
| `invoice_date` | string | ✅ Yes | Invoice Date |
| `notes` | string | ❌ No | Notes |

---

### `[GET] /api/invoices/`
**Description:** Get Invoices

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `status` | query | ❌ No | string |
| `payment_status` | query | ❌ No | string |
| `source` | query | ❌ No | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /api/invoices/{invoice_id}`
**Description:** Get Invoice

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `invoice_id` | path | ✅ Yes | integer |

---

### `[DELETE] /api/invoices/{invoice_id}`
**Description:** Delete Invoice

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `invoice_id` | path | ✅ Yes | integer |

---

### `[POST] /api/invoices/create`
**Description:** Create Invoice

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `invoice_number` | string | ✅ Yes | Invoice Number |
| `offline_id` | string | ❌ No | Offline Id |
| `customer_phone` | string | ❌ No | Customer Phone |
| `customer_name` | string | ❌ No | Customer Name |
| `total_amount` | number | ✅ Yes | Total Amount |
| `paid_amount` | number | ❌ No | Paid Amount |
| `tax` | number | ❌ No | Tax |
| `payment_status` | string | ❌ No | Payment Status |
| `line_items` | array | ✅ Yes | Line Items |
| `invoice_date` | string | ✅ Yes | Invoice Date |
| `notes` | string | ❌ No | Notes |

---

### `[GET] /api/invoices/overdue`
**Description:** Get Overdue Invoices

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `days_overdue` | query | ❌ No | integer |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /api/invoices/payments`
**Description:** Get Invoice Payments

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `invoice_id` | query | ❌ No | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /api/invoices/analytics/summary`
**Description:** Get Invoice Analytics

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `start_date` | query | ❌ No | string |
| `end_date` | query | ❌ No | string |

---

## 🔹 Customer Management
### `[POST] /api/customers/`
**Description:** Create Customer

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_name` | string | ✅ Yes | Customer Name |
| `email` | string | ❌ No | Email |
| `phone` | string | ✅ Yes | Phone |
| `whatsapp_number` | string | ❌ No | Whatsapp Number |
| `address` | string | ❌ No | Address |
| `city` | string | ❌ No | City |
| `state` | string | ❌ No | State |
| `postal_code` | string | ❌ No | Postal Code |
| `credit_limit` | number | ❌ No | Credit Limit |
| `payment_terms` | string | ❌ No | Payment Terms |
| `contact_preference` | string | ❌ No | Contact Preference |

---

### `[GET] /api/customers/`
**Description:** Get Customers

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `city` | query | ❌ No | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /api/customers/{customer_id}`
**Description:** Get Customer

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `customer_id` | path | ✅ Yes | integer |

---

### `[PUT] /api/customers/{customer_id}`
**Description:** Update Customer

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_name` | string | ❌ No | Customer Name |
| `email` | string | ❌ No | Email |
| `phone` | string | ❌ No | Phone |
| `whatsapp_number` | string | ❌ No | Whatsapp Number |
| `address` | string | ❌ No | Address |
| `city` | string | ❌ No | City |
| `state` | string | ❌ No | State |
| `postal_code` | string | ❌ No | Postal Code |
| `credit_limit` | string | ❌ No | Credit Limit |
| `payment_terms` | string | ❌ No | Payment Terms |
| `contact_preference` | string | ❌ No | Contact Preference |

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `customer_id` | path | ✅ Yes | integer |

---

### `[POST] /api/customers/{customer_id}/set-contact-preference`
**Description:** Set Contact Preference

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `customer_id` | path | ✅ Yes | integer |
| `preference` | query | ✅ Yes | string |

---

### `[GET] /api/customers/search/by-phone`
**Description:** Search By Phone

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `phone` | query | ✅ Yes | string |

---

### `[GET] /api/customers/search/by-name`
**Description:** Search By Name

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `name` | query | ✅ Yes | string |

---

## 🔹 Legacy Features
### `[DELETE] /api/customers/{customer_id}`
**Description:** Soft Delete Customer

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `customer_id` | path | ✅ Yes | integer |

---

### `[POST] /api/counter/authenticate`
**Description:** Authenticate Counter

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `billing_pin` | string | ✅ Yes | Billing Pin |

---

### `[POST] /api/delivery/create`
**Description:** Create Delivery

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_id` | integer | ✅ Yes | Customer Id |
| `invoice_id` | integer | ✅ Yes | Invoice Id |
| `delivery_address` | string | ✅ Yes | Delivery Address |
| `delivery_date` | string | ❌ No | Delivery Date |
| `special_instructions` | string | ❌ No | Special Instructions |

---

### `[GET] /api/delivery/today`
**Description:** Get Today Deliveries

---

### `[POST] /api/delivery/{delivery_id}/update-status`
**Description:** Update Delivery

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | ✅ Yes | Status |
| `notes` | string | ❌ No | Notes |

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `delivery_id` | path | ✅ Yes | integer |

---

### `[POST] /api/loyalty/earn`
**Description:** Earn Points

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_id` | integer | ✅ Yes | Customer Id |
| `invoice_id` | integer | ✅ Yes | Invoice Id |
| `amount` | number | ✅ Yes | Amount |

---

### `[POST] /api/loyalty/redeem`
**Description:** Redeem Points

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_id` | integer | ✅ Yes | Customer Id |
| `points` | integer | ✅ Yes | Points |
| `invoice_id` | integer | ✅ Yes | Invoice Id |

---

### `[GET] /api/festivals/upcoming`
**Description:** Get Upcoming Festivals

---

### `[GET] /api/occasions/today`
**Description:** Get Today Occasions

---

### `[GET] /api/collections/today-summary`
**Description:** Get Upi Summary

---

### `[GET] /api/templates`
**Description:** Get Templates

---

### `[POST] /api/templates/save`
**Description:** Save Template

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `template_name` | string | ✅ Yes | Template Name |
| `template_items` | array | ✅ Yes | Template Items |

---

### `[GET] /api/credit-score/{customer_id}`
**Description:** Get Credit Score

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `customer_id` | path | ✅ Yes | integer |

---

### `[GET] /api/reports/daily`
**Description:** Generate Daily Report

---

### `[POST] /api/flash-sale/setup`
**Description:** Setup Flash Sale

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | ✅ Yes | Category |
| `discount_pct` | number | ✅ Yes | Discount Pct |
| `hours` | integer | ✅ Yes | Hours |

---

### `[GET] /api/analytics/churn-risk`
**Description:** Get Churn Risk

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `days` | query | ❌ No | integer |

---

### `[GET] /api/inventory/generate-purchase-orders`
**Description:** Get Supplier Pos

---

### `[GET] /api/khata/{customer_phone}`
**Description:** Get Khata Balance

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `customer_phone` | path | ✅ Yes | string |

---

### `[GET] /api/khata/customers`
**Description:** Get Khata Customers

---

### `[POST] /api/khata/update`
**Description:** Update Khata Balance

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_phone` | string | ✅ Yes | Customer Phone |
| `amount` | number | ✅ Yes | Amount |
| `transaction_type` | string | ✅ Yes | Transaction Type |
| `reference_id` | string | ✅ Yes | Reference Id |

---

### `[POST] /api/expenses/create`
**Description:** Create Expense

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | ✅ Yes | Category |
| `amount` | number | ✅ Yes | Amount |
| `description` | string | ✅ Yes | Description |
| `date` | string | ❌ No | Date |

---

### `[GET] /api/expenses`
**Description:** Get Expenses

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /api/khata-history/{customer_phone}`
**Description:** Get Khata Transaction History

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `customer_phone` | path | ✅ Yes | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /api/expenses/history`
**Description:** Get Expense History

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `category` | query | ❌ No | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /api/transactions/recent`
**Description:** Get Recent Transactions

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `limit` | query | ❌ No | integer |

---

### `[GET] /api/transactions/online-payments`
**Description:** Get Online Payments

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `days` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /api/data/backup/export`
**Description:** Export Data Backup

---

### `[GET] /api/data/integrity-check`
**Description:** Verify Data Integrity

---

### `[POST] /api/sync/sales`
**Description:** Sync Sales Batch

---

### `[POST] /api/sync/invoices`
**Description:** Sync Invoices Batch

---

### `[POST] /api/sync/khata-balances`
**Description:** Sync Khata Batch

---

### `[POST] /api/sync/expenses`
**Description:** Sync Expenses Batch

---

### `[POST] /api/sync/invoices/chunked`
**Description:** Sync Invoices Chunked

---

### `[DELETE] /api/products/{product_id}`
**Description:** Soft Delete Product

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `product_id` | path | ✅ Yes | integer |

---

## 🔹 Shop Management
### `[POST] /api/shop/create`
**Description:** Create Shop Profile

---

### `[GET] /api/shop/profile`
**Description:** Get Profile

---

### `[PUT] /api/shop/profile`
**Description:** Update Profile

---

### `[DELETE] /api/shop/profile`
**Description:** Delete Profile

---

### `[PUT] /api/shop/settings`
**Description:** Update Settings

---

### `[POST] /api/shop/upload-logo`
**Description:** Upload Logo

---

### `[GET] /api/shop/business-hours`
**Description:** Get Business Hours

---

### `[GET] /api/shop/tax-config`
**Description:** Get Tax Config

---

## 🔹 Shop Settings
### `[GET] /shop/profile`
**Description:** Get Shop Profile

---

### `[PUT] /shop/profile`
**Description:** Update Shop Profile

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `shop_name` | string | ❌ No | Shop Name |
| `address` | string | ❌ No | Address |
| `phone` | string | ❌ No | Phone |
| `upi_id` | string | ❌ No | Upi Id |
| `gst_number` | string | ❌ No | Gst Number |
| `logo_url` | string | ❌ No | Logo Url |
| `is_online_store_enabled` | string | ❌ No | Is Online Store Enabled |
| `latitude` | string | ❌ No | Latitude |
| `longitude` | string | ❌ No | Longitude |
| `city` | string | ❌ No | City |

---

### `[POST] /shop/profile`
**Description:** Create Shop Profile

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `shop_name` | string | ✅ Yes | Shop Name |
| `address` | string | ❌ No | Address |
| `phone` | string | ❌ No | Phone |
| `upi_id` | string | ❌ No | Upi Id |
| `gst_number` | string | ❌ No | Gst Number |
| `logo_url` | string | ❌ No | Logo Url |

---

### `[GET] /shop/upi-qr`
**Description:** Get Upi Qr

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `amount` | query | ❌ No | string |

---

### `[POST] /shop/toggle-online-store`
**Description:** Toggle Online Store

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `enable` | query | ✅ Yes | boolean |

---

### `[GET] /shop/public/{shop_id}`
**Description:** Get Public Shop Info

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `shop_id` | path | ✅ Yes | integer |

---

## 🔹 Khata Ledger
### `[POST] /khata/credit`
**Description:** Add Khata Credit

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_phone` | string | ✅ Yes | Customer Phone |
| `customer_name` | string | ❌ No | Customer Name |
| `amount` | number | ✅ Yes | Amount |
| `description` | string | ❌ No | Description |

---

### `[POST] /khata/repayment`
**Description:** Record Repayment

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_phone` | string | ✅ Yes | Customer Phone |
| `amount` | number | ✅ Yes | Amount |
| `description` | string | ❌ No | Description |

---

### `[GET] /khata/customers`
**Description:** List Khata Customers

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /khata/history/{customer_phone}`
**Description:** Get Customer Khata History

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `customer_phone` | path | ✅ Yes | string |

---

### `[GET] /khata/whatsapp-reminder/{customer_phone}`
**Description:** Get Whatsapp Reminder Url

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `customer_phone` | path | ✅ Yes | string |

---

## 🔹 Purchase Orders
### `[POST] /purchase-orders/`
**Description:** Create Purchase Order

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `supplier_name` | string | ✅ Yes | Supplier Name |
| `expected_delivery` | string | ❌ No | Expected Delivery |
| `items` | array | ✅ Yes | Items |
| `notes` | string | ❌ No | Notes |

---

### `[GET] /purchase-orders/`
**Description:** List Purchase Orders

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `status` | query | ❌ No | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[POST] /purchase-orders/{po_id}/mark-delivered`
**Description:** Mark Po Delivered

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `po_id` | path | ✅ Yes | integer |

---

### `[POST] /purchase-orders/{po_id}/cancel`
**Description:** Cancel Purchase Order

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `po_id` | path | ✅ Yes | integer |

---

## 🔹 Online Store
### `[POST] /store/customer/register`
**Description:** Register Customer

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ Yes | Name |
| `email` | string | ✅ Yes | Email |
| `phone` | string | ✅ Yes | Phone |
| `password` | string | ✅ Yes | Password |
| `city` | string | ❌ No | City |
| `address` | string | ❌ No | Address |

---

### `[POST] /store/customer/login`
**Description:** Customer Login

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | ✅ Yes | Email |
| `password` | string | ✅ Yes | Password |

---

### `[GET] /store/shops/nearby`
**Description:** Find Nearby Shops

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `city` | query | ❌ No | string |
| `lat` | query | ❌ No | string |
| `lng` | query | ❌ No | string |
| `radius_km` | query | ❌ No | number |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /store/shops/{shop_id}/products`
**Description:** Browse Shop Products

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `shop_id` | path | ✅ Yes | integer |
| `category` | query | ❌ No | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[POST] /store/order`
**Description:** Place Order

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `shop_id` | integer | ✅ Yes | Shop Id |
| `items` | array | ✅ Yes | Items |
| `delivery_address` | string | ✅ Yes | Delivery Address |

---

### `[GET] /store/my-orders`
**Description:** Get My Orders

---

### `[GET] /store/order/{order_id}/track`
**Description:** Track Order

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `order_id` | path | ✅ Yes | integer |

---

### `[GET] /store/owner/orders`
**Description:** Get Incoming Orders

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `status` | query | ❌ No | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[POST] /store/owner/orders/{order_id}/action`
**Description:** Update Order Status

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `order_id` | path | ✅ Yes | integer |
| `action` | query | ✅ Yes | string |

---

## 🔹 Enterprise Intelligence
### `[POST] /expenses`
**Description:** Add Expense

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | ✅ Yes | Category |
| `amount` | number | ✅ Yes | Amount |
| `description` | string | ❌ No | Description |
| `expense_date` | string | ✅ Yes | Expense Date |
| `payment_method` | string | ❌ No | Payment Method |

---

### `[GET] /expenses`
**Description:** List Expenses

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `start_date` | query | ❌ No | string |
| `end_date` | query | ❌ No | string |
| `category` | query | ❌ No | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /workers`
**Description:** List Workers

---

### `[POST] /workers`
**Description:** Add Worker

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ Yes | Name |
| `phone` | string | ❌ No | Phone |
| `address` | string | ❌ No | Address |
| `salary` | number | ❌ No | Salary |
| `assigned_work` | string | ❌ No | Assigned Work |
| `position` | string | ❌ No | Position |
| `pin` | string | ❌ No | Pin |

---

### `[PUT] /workers/{worker_id}`
**Description:** Update Worker

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `salary` | string | ❌ No | Salary |
| `assigned_work` | string | ❌ No | Assigned Work |
| `position` | string | ❌ No | Position |
| `status` | string | ❌ No | Status |
| `pin` | string | ❌ No | Pin |

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `worker_id` | path | ✅ Yes | integer |

---

### `[POST] /workers/{worker_id}/pay-salary`
**Description:** Pay Worker Salary

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `worker_id` | path | ✅ Yes | integer |
| `month` | query | ✅ Yes | string |

---

### `[POST] /bank-recon`
**Description:** Add Reconciliation

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `recon_date` | string | ✅ Yes | Recon Date |
| `expected_upi_amount` | number | ❌ No | Expected Upi Amount |
| `actual_bank_deposit` | number | ❌ No | Actual Bank Deposit |
| `notes` | string | ❌ No | Notes |

---

### `[GET] /bank-recon`
**Description:** List Reconciliations

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `start_date` | query | ❌ No | string |
| `end_date` | query | ❌ No | string |

---

### `[GET] /enterprise/pnl`
**Description:** Get Profit And Loss

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `start_date` | query | ❌ No | string |
| `end_date` | query | ❌ No | string |

---

### `[GET] /enterprise/transactions`
**Description:** Get All Transactions

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `tx_type` | query | ❌ No | string |
| `category` | query | ❌ No | string |
| `start_date` | query | ❌ No | string |
| `end_date` | query | ❌ No | string |
| `skip` | query | ❌ No | integer |
| `limit` | query | ❌ No | integer |

---

### `[GET] /retail/stock-analysis`
**Description:** Stock Analysis

---

## 🔹 GST & Gift Cards
### `[POST] /gift-cards`
**Description:** Issue Gift Card

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `card_code` | string | ✅ Yes | Card Code |
| `initial_balance` | number | ✅ Yes | Initial Balance |
| `issued_to` | string | ❌ No | Issued To |
| `expiry_date` | string | ❌ No | Expiry Date |

---

### `[POST] /gift-cards/redeem`
**Description:** Redeem Gift Card

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `card_code` | string | ✅ Yes | Card Code |
| `amount_to_deduct` | number | ✅ Yes | Amount To Deduct |

---

### `[GET] /gst/export-gstr1`
**Description:** Export Gstr1

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `month` | query | ✅ Yes | integer |
| `year` | query | ✅ Yes | integer |

---

## 🔹 Caching System
### `[GET] /cache/api/cache/stats`
**Description:** Get Cache Stats

---

### `[POST] /cache/api/cache/warm/products`
**Description:** Warm Product Cache

---

### `[POST] /cache/api/cache/warm/analytics`
**Description:** Warm Analytics Cache

---

### `[DELETE] /cache/api/cache/clear/{pattern}`
**Description:** Clear Cache Pattern

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `pattern` | path | ✅ Yes | string |

---

### `[DELETE] /cache/api/cache/clear-all`
**Description:** Clear All Cache

---

## 🔹 Batch Operations
### `[POST] /batch/api/batch/products/import`
**Description:** Bulk Import Products

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |
| `overwrite` | query | ❌ No | boolean |

---

### `[POST] /batch/api/batch/products/export`
**Description:** Bulk Export Products

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |

---

### `[POST] /batch/api/batch/customers/import`
**Description:** Bulk Import Customers

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |

---

### `[GET] /batch/api/batch/status/{operation_id}`
**Description:** Get Batch Status

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `operation_id` | path | ✅ Yes | integer |

---

### `[GET] /batch/api/batch/history`
**Description:** Get Batch History

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `user_id` | query | ✅ Yes | integer |
| `limit` | query | ❌ No | integer |

---

## 🔹 Rate Limiting
### `[GET] /api/rate-limit/status/{endpoint}`
**Description:** Get Rate Limit Status

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `endpoint` | path | ✅ Yes | string |

---

## 🔹 Security Hardening
### `[POST] /api/security/check-input`
**Description:** Check Input Security

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `input_data` | string | ✅ Yes | Input Data |
| `check_type` | string | ✅ Yes | Check Type |

---

### `[GET] /api/security/rate-limit-status`
**Description:** Get Rate Limit Status

---

### `[POST] /api/security/validate-password`
**Description:** Validate Password Strength

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `password` | query | ✅ Yes | string |

---

### `[GET] /api/security/security-headers`
**Description:** Get Security Headers

---

### `[POST] /api/security/sanitize-batch`
**Description:** Sanitize Batch Inputs

---

### `[GET] /api/security/csrf-token`
**Description:** Get Csrf Token

---

### `[GET] /api/security/check-sql-injection`
**Description:** Check Sql Injection Pattern

**Parameters (URL/Query):**
| Name | In | Required | Type |
|------|----|----------|------|
| `query` | query | ✅ Yes | string |

---

## 🔹 Observability
### `[GET] /api/observability/health`
**Description:** Health Check

---

### `[GET] /api/observability/ready`
**Description:** Readiness Check

---

### `[GET] /api/observability/metrics`
**Description:** Get Metrics

---

### `[POST] /api/observability/log`
**Description:** Log Event

**Required Payload Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `level` | string | ✅ Yes | Level |
| `message` | string | ✅ Yes | Message |
| `context` | string | ❌ No | Context |
| `timestamp` | string | ✅ Yes | Timestamp |

---

### `[POST] /api/observability/error`
**Description:** Log Error

---

### `[GET] /api/observability/performance/summary`
**Description:** Get Performance Summary

---

### `[GET] /api/observability/performance/database`
**Description:** Get Database Performance

---

### `[GET] /api/observability/business/overview`
**Description:** Get Business Overview

---

## 🔹 System
### `[GET] /`
**Description:** Root

---

### `[GET] /health`
**Description:** Health Check

---
