'use client';

import { useParams, useRouter } from 'next/navigation';
import { ShoppingCart, X, Minus, Plus, Trash2, ArrowRight } from 'lucide-react';
import { useCart } from '../context/CartContext';

export default function CartDrawer() {
  const { cartItems, isCartOpen, toggleCart, updateQuantity, removeFromCart, cartTotal } = useCart();
  const router = useRouter();
  const params = useParams();
  const shopId = Number(params?.shopId || 8);

  const handleCheckout = () => {
    toggleCart();
    router.push(`/shop/${shopId}/checkout`);
  };

  return (
    <>
      <div
        className="drawer-overlay"
        onClick={toggleCart}
        aria-hidden="true"
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.65)',
          backdropFilter: 'blur(6px)',
          zIndex: 998,
          transition: 'opacity 0.35s ease, visibility 0.35s ease',
          opacity: isCartOpen ? 1 : 0,
          visibility: isCartOpen ? 'visible' : 'hidden',
        }}
      />

      <aside
        className={`cart-drawer ${isCartOpen ? 'open' : ''}`}
        aria-label="Shopping cart"
        role="dialog"
        aria-modal="true"
      >
        <div className="cart-head">
          <div className="cart-head-left">
            <ShoppingCart size={20} />
            <h2 className="cart-head-title">Your Cart</h2>
            {cartItems.length > 0 && (
              <span className="cart-count-pill">{cartItems.reduce((s, i) => s + i.quantity, 0)}</span>
            )}
          </div>
          <button className="cart-close" onClick={toggleCart} aria-label="Close cart">
            <X size={20} />
          </button>
        </div>

        <div className="cart-scroll">
          {cartItems.length === 0 ? (
            <div className="cart-empty">
              <ShoppingCart size={52} style={{ opacity: 0.2 }} />
              <p>Your cart is empty</p>
              <small>Add items from the store to get started</small>
            </div>
          ) : (
            <div className="cart-items-list">
              {cartItems.map(item => (
                <div key={item.product.id} className="cart-item">
                  <div className="cart-item-info">
                    <div className="cart-item-name">{item.product.name}</div>
                    <div className="cart-item-price">₹{(item.product.price * item.quantity).toFixed(2)}</div>
                    <div className="cart-item-unit-price">₹{Number(item.product.price).toFixed(2)} each</div>
                  </div>
                  <div className="qty-controls">
                    <button className="qty-btn" onClick={() => updateQuantity(item.product.id, -1)} aria-label="Decrease">
                      <Minus size={14} />
                    </button>
                    <span className="qty-val">{item.quantity}</span>
                    <button className="qty-btn" onClick={() => updateQuantity(item.product.id, 1)} aria-label="Increase">
                      <Plus size={14} />
                    </button>
                  </div>
                  <button className="cart-item-remove" onClick={() => removeFromCart(item.product.id)} aria-label="Remove item">
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {cartItems.length > 0 && (
          <div className="cart-foot">
            <div className="cart-total-row">
              <span className="cart-total-label">Subtotal</span>
              <span className="cart-total-val">₹{cartTotal.toFixed(2)}</span>
            </div>
            <p className="cart-total-note">Taxes included. Delivery charges calculated at checkout.</p>

            <button className="place-order-btn" onClick={handleCheckout} id="checkout-btn">
              Proceed to Checkout <ArrowRight size={16} />
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
