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
  shop_phone?: string;
  shop_address?: string;
  products: ShopProduct[];
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
