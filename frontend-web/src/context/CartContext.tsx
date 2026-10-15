'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export interface Product {
  id: number;
  name: string;
  price: number;
  description?: string;
  stock_available?: number;
  category?: string;
  image_url?: string;
  shop_id?: number;
}

export interface CartItem {
  product: Product;
  quantity: number;
}

interface CartContextType {
  cartItems: CartItem[];
  isCartOpen: boolean;
  cartMessage: string;
  addToCart: (product: Product, quantity?: number) => void;
  removeFromCart: (productId: number) => void;
  updateQuantity: (productId: number, delta: number) => void;
  clearCart: () => void;
  clearCartMessage: () => void;
  setCartMessage: (message: string) => void;
  toggleCart: () => void;
  cartTotal: number;
  itemCount: number;
}

const CartContext = createContext<CartContextType | undefined>(undefined);
const UNKNOWN_STOCK_LIMIT = 99;

function readStock(product: Product): number | undefined {
  if (product.stock_available === undefined || product.stock_available === null) return undefined;
  const stock = Number(product.stock_available);
  return Number.isFinite(stock) ? Math.max(0, Math.floor(stock)) : undefined;
}

/** Validate persisted browser data before using it. Local storage is not authoritative. */
function normalizeCart(value: unknown): CartItem[] {
  if (!Array.isArray(value)) return [];

  const normalized: CartItem[] = [];
  for (const candidate of value) {
    if (!candidate || typeof candidate !== 'object') continue;
    const entry = candidate as { product?: Partial<Product>; quantity?: unknown };
    const source = entry.product;
    if (!source || typeof source !== 'object') continue;

    const id = Number(source.id);
    const price = Number(source.price);
    const quantity = Math.floor(Number(entry.quantity));
    const name = typeof source.name === 'string' ? source.name.trim() : '';
    if (!Number.isSafeInteger(id) || id <= 0 || !name || !Number.isFinite(price) || price < 0 || !Number.isFinite(quantity) || quantity < 1) continue;

    const rawShopId = Number(source.shop_id);
    const product: Product = {
      id,
      name,
      price,
      description: typeof source.description === 'string' ? source.description : undefined,
      category: typeof source.category === 'string' ? source.category : undefined,
      image_url: typeof source.image_url === 'string' ? source.image_url : undefined,
      shop_id: Number.isSafeInteger(rawShopId) && rawShopId > 0 ? rawShopId : undefined,
      stock_available: readStock(source as Product),
    };
    const stock = readStock(product);
    const safeQuantity = stock === undefined || stock === 0 ? quantity : Math.min(quantity, stock);
    const existingIndex = normalized.findIndex((item) => item.product.id === id);
    if (existingIndex >= 0) {
      const existing = normalized[existingIndex];
      if (existing.product.shop_id !== product.shop_id) continue;
      const combined = existing.quantity + safeQuantity;
      normalized[existingIndex] = {
        product,
        quantity: stock === undefined ? Math.min(combined, UNKNOWN_STOCK_LIMIT) : stock === 0 ? combined : Math.min(combined, stock),
      };
    } else {
      normalized.push({ product, quantity: safeQuantity });
    }
  }

  // A cart must represent one shop because checkout submits one shop_id.
  const shopIds = new Set(normalized.map((item) => item.product.shop_id).filter((id): id is number => id !== undefined));
  if (shopIds.size > 1) return [];
  return normalized;
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [cartMessage, setCartMessage] = useState('');
  const [hydrated, setHydrated] = useState(false);

  // Hydrate before saving; otherwise the first empty render can overwrite a saved cart.
  useEffect(() => {
    try {
      const savedCart = localStorage.getItem('shoppingCart');
      if (savedCart) setCartItems(normalizeCart(JSON.parse(savedCart)));
    } catch {
      setCartItems([]);
      setCartMessage('Your saved cart could not be loaded. Start a new cart below.');
    } finally {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem('shoppingCart', JSON.stringify(cartItems));
    } catch {
      setCartMessage('Your browser could not save this cart. Keep this tab open while shopping.');
    }
  }, [cartItems, hydrated]);

  const addToCart = (product: Product, quantity = 1) => {
    const id = Number(product?.id);
    const shopId = Number(product?.shop_id);
    const price = Number(product?.price);
    if (!Number.isSafeInteger(id) || id <= 0 || !Number.isSafeInteger(shopId) || shopId <= 0 || !Number.isFinite(price) || price < 0) {
      setCartMessage('We could not verify this product. Open it from a shop page and try again.');
      setIsCartOpen(true);
      return;
    }

    const stock = readStock(product);
    if (stock === 0) {
      setCartMessage('This product is currently out of stock. It cannot be added to your cart.');
      setIsCartOpen(true);
      return;
    }

    const currentShopId = cartItems[0]?.product.shop_id;
    if (cartItems.length && currentShopId !== shopId) {
      setCartMessage('Your cart contains items from another shop. Finish or clear that cart before shopping here.');
      setIsCartOpen(true);
      return;
    }

    const requestedQuantity = Math.max(1, Math.floor(Number(quantity) || 1));
    const maximum = stock ?? UNKNOWN_STOCK_LIMIT;
    const existing = cartItems.find((item) => item.product.id === id);
    const nextQuantity = Math.min((existing?.quantity || 0) + requestedQuantity, maximum);
    setCartItems((previous) => {
      const found = previous.find((item) => item.product.id === id);
      if (found) {
        return previous.map((item) => item.product.id === id
          ? { product: { ...item.product, ...product, id, shop_id: shopId }, quantity: Math.min(item.quantity + requestedQuantity, maximum) }
          : item);
      }
      return [...previous, { product: { ...product, id, shop_id: shopId }, quantity: Math.min(requestedQuantity, maximum) }];
    });
    setCartMessage(nextQuantity === maximum && ((existing?.quantity || 0) + requestedQuantity > maximum)
      ? `Only ${maximum} unit(s) are currently available. Your cart quantity was adjusted.`
      : '');
    setIsCartOpen(true);
  };

  const removeFromCart = (productId: number) => {
    setCartItems((previous) => previous.filter((item) => item.product.id !== productId));
    setCartMessage('');
  };

  const updateQuantity = (productId: number, delta: number) => {
    const item = cartItems.find((candidate) => candidate.product.id === productId);
    if (!item || !Number.isFinite(delta) || delta === 0) return;
    const stock = readStock(item.product);
    if (stock === 0) {
      setCartMessage('This product is out of stock. Remove it from the cart before checkout.');
      return;
    }
    const requested = item.quantity + Math.trunc(delta);
    const nextQuantity = Math.min(requested, stock ?? UNKNOWN_STOCK_LIMIT);
    if (requested > (stock ?? UNKNOWN_STOCK_LIMIT)) {
      setCartMessage(`Only ${stock ?? UNKNOWN_STOCK_LIMIT} unit(s) can be added for this product.`);
    } else {
      setCartMessage('');
    }
    setCartItems((previous) => previous.flatMap((entry) => {
      if (entry.product.id !== productId) return [entry];
      if (requested <= 0) return [];
      return [{ ...entry, quantity: Math.max(1, nextQuantity) }];
    }));
  };

  const clearCart = () => {
    setCartItems([]);
    setCartMessage('');
  };

  const toggleCart = () => setIsCartOpen((previous) => !previous);
  const clearCartMessage = () => setCartMessage('');

  // This subtotal is only a client-side estimate; the backend determines checkout totals.
  const cartTotal = cartItems.reduce((total, item) => total + (Number(item.product.price) * item.quantity), 0);
  const itemCount = cartItems.reduce((count, item) => count + item.quantity, 0);

  return (
    <CartContext.Provider value={{
      cartItems,
      isCartOpen,
      cartMessage,
      addToCart,
      removeFromCart,
      updateQuantity,
      clearCart,
      clearCartMessage,
      setCartMessage,
      toggleCart,
      cartTotal,
      itemCount,
    }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const context = useContext(CartContext);
  if (context === undefined) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
}
