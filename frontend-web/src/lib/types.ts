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
