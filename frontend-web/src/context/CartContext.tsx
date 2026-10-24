'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

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
  cartNotice: string | null;
  canReplaceCart: boolean;
  addToCart: (product: Product, quantity?: number) => boolean;
  removeFromCart: (productId: number) => void;
  updateQuantity: (productId: number, delta: number) => void;
  clearCart: () => void;
  replaceCartWithPendingProduct: () => void;
  dismissCartNotice: () => void;
  toggleCart: () => void;
  cartTotal: number;
  itemCount: number;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

export function CartProvider({ children }: { children: ReactNode }) {
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [cartNotice, setCartNotice] = useState<string | null>(null);
  const [pendingProduct, setPendingProduct] = useState<CartItem | null>(null);

  // Load from localStorage on mount
  useEffect(() => {
    const savedCart = localStorage.getItem('shoppingCart');
    if (savedCart) {
      try {
        setCartItems(JSON.parse(savedCart));
      } catch (e) {
        console.error('Failed to parse cart', e);
      }
    }
  }, []);

  // Save to localStorage when cart changes
  useEffect(() => {
    localStorage.setItem('shoppingCart', JSON.stringify(cartItems));
  }, [cartItems]);

  const addToCart = (product: Product, quantity: number = 1) => {
    const existingShopId = cartItems[0]?.product.shop_id;
    const incomingShopId = product.shop_id;
    const maxQuantity = product.stock_available === undefined
      ? 99
      : Math.max(0, product.stock_available);

    if (maxQuantity === 0) {
      setPendingProduct(null);
      setCartNotice(`${product.name} is currently out of stock.`);
      setIsCartOpen(true);
      return false;
    }

    if (
      existingShopId !== undefined &&
      incomingShopId !== undefined &&
      existingShopId !== incomingShopId
    ) {
      setPendingProduct({ product, quantity });
      setCartNotice('Your cart can only contain items from one shop at a time.');
      setIsCartOpen(true);
      return false;
    }

    setPendingProduct(null);
    setCartNotice(null);
    setCartItems(prev => {
      const existing = prev.find(item => item.product.id === product.id);
      if (existing) {
        return prev.map(item =>
          item.product.id === product.id
            ? { ...item, quantity: Math.min(item.quantity + quantity, maxQuantity) }
            : item
        );
      }
      return [...prev, { product, quantity: Math.min(quantity, maxQuantity) }];
    });
    setIsCartOpen(true);
    return true;
  };

  const replaceCartWithPendingProduct = () => {
    if (!pendingProduct) return;
    const maxQuantity = pendingProduct.product.stock_available === undefined
      ? 99
      : Math.max(0, pendingProduct.product.stock_available);
    if (maxQuantity === 0) {
      setPendingProduct(null);
      setCartNotice(`${pendingProduct.product.name} is currently out of stock.`);
      return;
    }

    setCartItems([{
      product: pendingProduct.product,
      quantity: Math.min(Math.max(1, pendingProduct.quantity), maxQuantity),
    }]);
    setPendingProduct(null);
    setCartNotice(null);
  };

  const dismissCartNotice = () => {
    setCartNotice(null);
    setPendingProduct(null);
  };

  const removeFromCart = (productId: number) => {
    setCartItems(prev => prev.filter(item => item.product.id !== productId));
  };

  const updateQuantity = (productId: number, delta: number) => {
    setCartItems(prev => prev.map(item => {
      if (item.product.id === productId) {
        const newQty = item.quantity + delta;
        if (newQty <= 0) return null; // We filter these out below
        const stockLimit = item.product.stock_available === undefined
          ? 99
          : Math.max(0, item.product.stock_available);
        if (stockLimit === 0) return null;
        return { ...item, quantity: Math.min(newQty, stockLimit) };
      }
      return item;
    }).filter(Boolean) as CartItem[]);
  };

  const clearCart = () => {
    setCartItems([]);
    dismissCartNotice();
  };

  const toggleCart = () => {
    setIsCartOpen(prev => !prev);
  };

  const cartTotal = cartItems.reduce((total, item) => total + (item.product.price * item.quantity), 0);
  const itemCount = cartItems.reduce((count, item) => count + item.quantity, 0);

  return (
    <CartContext.Provider value={{
      cartItems,
      isCartOpen,
      cartNotice,
      canReplaceCart: pendingProduct !== null,
      addToCart,
      removeFromCart,
      updateQuantity,
      clearCart,
      replaceCartWithPendingProduct,
      dismissCartNotice,
      toggleCart,
      cartTotal,
      itemCount
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
