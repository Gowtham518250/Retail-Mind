export interface ShopProduct {
  id: number;
  name: string;
  price: number;
  original_price?: number;
  discount_pct?: number;
  flash_sale_active?: boolean;
  stock_available?: number;
  description?: string;
  category?: string;
  image_url?: string;
}

export interface ShopResponse {
  shop_name: string;
  shop_tagline?: string;
  shop_description?: string;
  shop_type?: string;
  shop_phone?: string;
  shop_email?: string;
  shop_website?: string;
  shop_address?: string;
  shop_city?: string;
  shop_state?: string;
  shop_postal_code?: string;
  shop_logo_url?: string;
  shop_categories?: string;
  rating?: number;
  rating_count?: number;
  products: ShopProduct[];
  online_setup_fee?: number;
  min_order?: number;
  delivery_fee?: number;
  offer_delivery?: boolean;
  offer_pickup?: boolean;
  accept_cod?: boolean;
  accept_online?: boolean;
}

export interface GuestOrderPayload {
  shop_id: number;
  customer_name: string;
  phone: string;
  delivery_address: string;
  items: { product_id: number; quantity: number }[];
}

export interface PlacedOrder {
  order_id: number;
  shop_name: string;
  total_amount: number;
  status: string;
  payment_method: 'COD' | 'UPI' | 'CARD';
  customer_name: string;
  phone: string;
  delivery_address: string;
  items: { name: string; quantity: number; price: number }[];
  placed_at: string;
}
