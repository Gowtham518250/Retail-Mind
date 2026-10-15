'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShoppingBag,
  Store,
  PlusCircle,
  ExternalLink,
  Share2,
  Package,
  Sparkles,
  Trophy,
  LogOut,
  X,
  CheckCircle,
  Tag,
  Boxes,
  DollarSign,
  FileText,
  Image as ImageIcon,
  ArrowRight,
  TrendingUp,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { API_BASE } from '../../lib/api';
import styles from './profile.module.css';

export default function ProfilePage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'CUSTOMER' | 'OWNER'>('CUSTOMER');
  const [shopId, setShopId] = useState<string | null>(null);
  const [shopName, setShopName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Add Product Modal State
  const [showAddProductModal, setShowAddProductModal] = useState(false);
  const [productName, setProductName] = useState('');
  const [productCategory, setProductCategory] = useState('Groceries');
  const [unitPrice, setUnitPrice] = useState('');
  const [currentStock, setCurrentStock] = useState('25');
  const [productDescription, setProductDescription] = useState('');
  const [productImageUrl, setProductImageUrl] = useState('');
  const [addingProduct, setAddingProduct] = useState(false);
  const [productError, setProductError] = useState('');

  // Toast feedback
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const custToken = localStorage.getItem('customerToken');
    const merchToken = localStorage.getItem('merchantToken');

    if (!custToken && !merchToken) {
      router.push('/auth');
      return;
    }

    const storedName = localStorage.getItem('customerName') || 'Valued User';
    const storedEmail = localStorage.getItem('customerEmail') || '';
    const storedRole = (localStorage.getItem('userRole') || 'CUSTOMER').toUpperCase() as 'CUSTOMER' | 'OWNER';
    const storedShopId = localStorage.getItem('shopId');
    const storedShopName = localStorage.getItem('shopName');

    setName(storedName);
    setEmail(storedEmail);
    setRole(storedRole);
    setShopId(storedShopId || null);
    setShopName(storedShopName || null);
    setLoading(false);
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('customerToken');
    localStorage.removeItem('merchantToken');
    localStorage.removeItem('customerName');
    localStorage.removeItem('customerEmail');
    localStorage.removeItem('userRole');
    localStorage.removeItem('shopId');
    localStorage.removeItem('shopName');
    router.push('/');
  };

  const handleShareStore = () => {
    if (!shopId) return;
    const url = `${window.location.origin}/shop/${shopId}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url);
      showToast('Store link copied to clipboard!');
    }
  };

  const handleAddProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem('merchantToken') || localStorage.getItem('customerToken');
    if (!token) {
      setProductError('Authentication token missing. Please sign in again.');
      return;
    }
    if (productName.trim().length < 2) {
      setProductError('Product name must be at least 2 characters.');
      return;
    }
    const priceNum = parseFloat(unitPrice);
    if (isNaN(priceNum) || priceNum < 0) {
      setProductError('Please enter a valid price in INR (₹).');
      return;
    }

    setAddingProduct(true);
    setProductError('');

    try {
      // Auto-generate safe unique SKU
      const randomPart = Math.floor(1000 + Math.random() * 9000);
      const cleanPrefix = productName.replace(/[^a-zA-Z0-9]/g, '').slice(0, 4).toUpperCase() || 'PROD';
      const sku = `${cleanPrefix}-${randomPart}`;

      const res = await fetch(`${API_BASE}/api/inventory/products`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          product_name: productName.trim(),
          sku,
          description: productDescription.trim() || undefined,
          current_stock: parseInt(currentStock, 10) || 0,
          min_stock: 5,
          max_stock: 500,
          reorder_level: 10,
          unit_price: priceNum,
          purchase_price: Math.round(priceNum * 0.75 * 100) / 100,
          category: productCategory,
          image_url: productImageUrl.trim() || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Failed to add product to catalog.');
      }

      // Celebrate with confetti
      confetti({
        particleCount: 80,
        spread: 60,
        origin: { y: 0.6 },
      });

      showToast(`Product "${productName}" is now live in your store!`);
      setShowAddProductModal(false);

      // Reset form fields
      setProductName('');
      setUnitPrice('');
      setProductDescription('');
      setProductImageUrl('');
    } catch (err: any) {
      setProductError(err.message || 'Error creating product.');
    } finally {
      setAddingProduct(false);
    }
  };

  if (loading) return null;

  const isSeller = role === 'OWNER' || Boolean(shopId);

  return (
    <main className={styles.profilePage}>
      {/* 3D Floating Orbs */}
      <div className={styles.orbA} />
      <div className={styles.orbB} />

      <div className={styles.container}>
        {/* ── 1. Profile Header Card ── */}
        <motion.div
          className={styles.profileHeaderCard}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
        >
          <div className={styles.headerGlowLine} />

          <div className={styles.userInfoArea}>
            <div className={styles.avatarAura}>
              <div className={styles.avatarInner}>
                {name.charAt(0).toUpperCase()}
              </div>
            </div>

            <div className={styles.userMeta}>
              <div className={styles.userNameRow}>
                <h1 className={styles.userName}>{name}</h1>
                <span className={`${styles.roleBadge} ${isSeller ? styles.roleSeller : styles.roleCustomer}`}>
                  {isSeller ? <Store size={13} /> : <ShoppingBag size={13} />}
                  {isSeller ? '👑 Store Owner' : '🛍️ Shopper'}
                </span>
              </div>
              {email && <p className={styles.userEmail}>{email}</p>}
            </div>
          </div>

          <div className={styles.headerActions}>
            <button type="button" onClick={handleLogout} className={styles.logoutBtn}>
              <LogOut size={16} />
              <span>Sign Out</span>
            </button>
          </div>
        </motion.div>

        {/* ── 2. Seller Hub (If Merchant / Store Owner) ── */}
        {isSeller && (
          <motion.div
            className={styles.sellerHubCard}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.1 }}
          >
            <div className={styles.hubTopRow}>
              <div className={styles.hubTitleGroup}>
                <div className={styles.hubIconBadge}>
                  <Store size={26} />
                </div>
                <div className={styles.hubTitleText}>
                  <h2>{shopName || `${name}'s Store`}</h2>
                  <p>Store ID: #{shopId || 'Live'} · Instant Online Selling Enabled</p>
                </div>
              </div>

              <div className={styles.hubQuickActions}>
                {shopId && (
                  <>
                    <Link href={`/shop/${shopId}`} className={styles.storeLinkBtn} target="_blank">
                      <ExternalLink size={15} />
                      <span>View Live Store</span>
                    </Link>
                    <button type="button" onClick={handleShareStore} className={styles.storeLinkBtn}>
                      <Share2 size={15} />
                      <span>Share Store Link</span>
                    </button>
                  </>
                )}
                <button
                  type="button"
                  onClick={() => setShowAddProductModal(true)}
                  className={styles.addProductTriggerBtn}
                >
                  <PlusCircle size={17} />
                  <span>Add Product</span>
                </button>
              </div>
            </div>

            {/* Seller Metrics */}
            <div className={styles.metricsGrid}>
              <div className={styles.metricTile}>
                <div className={styles.metricTileIcon}>
                  <Tag size={20} />
                </div>
                <div className={styles.metricInfo}>
                  <strong>0%</strong>
                  <span>Platform Fee</span>
                </div>
              </div>

              <div className={styles.metricTile}>
                <div className={styles.metricTileIcon}>
                  <TrendingUp size={20} />
                </div>
                <div className={styles.metricInfo}>
                  <strong>Instant</strong>
                  <span>Direct UPI Settlements</span>
                </div>
              </div>

              <div className={styles.metricTile}>
                <div className={styles.metricTileIcon}>
                  <Boxes size={20} />
                </div>
                <div className={styles.metricInfo}>
                  <strong>Online</strong>
                  <span>Digital Inventory Active</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── 3. Become a Seller Promo (If Regular Customer) ── */}
        {!isSeller && (
          <motion.div
            className={styles.becomeSellerCard}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.1 }}
          >
            <div className={styles.becomeSellerText}>
              <h3>Sell Products on RetailMind</h3>
              <p>
                Turn your store or catalog into an online business in 60 seconds. Get zero platform fees,
                instant UPI QR settlements, and reach local neighborhood shoppers today.
              </p>
              <div className={styles.perksRow}>
                <span className={styles.perkPill}>✓ 0% Setup Fees</span>
                <span className={styles.perkPill}>✓ Branded QR Code</span>
                <span className={styles.perkPill}>✓ Realtime Stock Sync</span>
              </div>
            </div>

            <Link href="/auth?role=seller" className={styles.launchStoreBtn}>
              <Store size={18} />
              <span>Open Your Store Now</span>
              <ArrowRight size={16} />
            </Link>
          </motion.div>
        )}

        {/* ── 4. Bento Navigation Grid ── */}
        <div className={styles.bentoNavGrid}>
          <Link href="/orders" className={styles.navCard}>
            <div className={styles.navCardIcon}>
              <Package size={22} />
            </div>
            <div>
              <h3 className={styles.navCardTitle}>
                My Orders <ArrowRight size={16} />
              </h3>
              <p className={styles.navCardDesc}>Track live package dispatch, view invoices, and order history.</p>
            </div>
          </Link>

          <Link href="/smart-shop" className={styles.navCard}>
            <div className={styles.navCardIcon}>
              <Trophy size={22} />
            </div>
            <div>
              <h3 className={styles.navCardTitle}>
                Smart Shopping Hub <ArrowRight size={16} />
              </h3>
              <p className={styles.navCardDesc}>AI-recommended baskets, price comparisons, and store deals.</p>
            </div>
          </Link>

          <Link href="/" className={styles.navCard}>
            <div className={styles.navCardIcon}>
              <Sparkles size={22} />
            </div>
            <div>
              <h3 className={styles.navCardTitle}>
                Explore Marketplace <ArrowRight size={16} />
              </h3>
              <p className={styles.navCardDesc}>Discover neighborhood shops and real-time inventory.</p>
            </div>
          </Link>
        </div>
      </div>

      {/* ── ADD PRODUCT MODAL ── */}
      <AnimatePresence>
        {showAddProductModal && (
          <div className={styles.modalBackdrop} onClick={() => setShowAddProductModal(false)}>
            <motion.div
              className={styles.modalContent}
              onClick={(e) => e.stopPropagation()}
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              transition={{ duration: 0.25 }}
            >
              <button
                type="button"
                className={styles.modalCloseBtn}
                onClick={() => setShowAddProductModal(false)}
                aria-label="Close modal"
              >
                <X size={18} />
              </button>

              <div className={styles.modalHeader}>
                <h3>Add Product to Store</h3>
                <p>List a new item for customers to discover and buy online immediately.</p>
              </div>

              {productError && (
                <div style={{ padding: '10px 14px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#fca5a5', marginBottom: '16px', fontSize: '13px' }}>
                  {productError}
                </div>
              )}

              <form onSubmit={handleAddProduct} className={styles.productForm}>
                <div className={styles.inputGroup}>
                  <label className={styles.inputLabel}>Product Name *</label>
                  <input
                    type="text"
                    value={productName}
                    onChange={(e) => setProductName(e.target.value)}
                    placeholder="e.g. Organic Almond Milk 1L"
                    className={styles.textInput}
                    required
                  />
                </div>

                <div className={styles.twoCols}>
                  <div className={styles.inputGroup}>
                    <label className={styles.inputLabel}>Unit Price (₹) *</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={unitPrice}
                      onChange={(e) => setUnitPrice(e.target.value)}
                      placeholder="e.g. 199.00"
                      className={styles.textInput}
                      required
                    />
                  </div>

                  <div className={styles.inputGroup}>
                    <label className={styles.inputLabel}>Available Stock *</label>
                    <input
                      type="number"
                      min="0"
                      value={currentStock}
                      onChange={(e) => setCurrentStock(e.target.value)}
                      placeholder="e.g. 50"
                      className={styles.textInput}
                      required
                    />
                  </div>
                </div>

                <div className={styles.twoCols}>
                  <div className={styles.inputGroup}>
                    <label className={styles.inputLabel}>Category</label>
                    <select
                      value={productCategory}
                      onChange={(e) => setProductCategory(e.target.value)}
                      className={styles.textInput}
                    >
                      <option value="Groceries">Groceries & Essentials</option>
                      <option value="Snacks & Beverages">Snacks & Beverages</option>
                      <option value="Dairy & Bakery">Dairy & Bakery</option>
                      <option value="Electronics">Electronics</option>
                      <option value="Fashion">Fashion & Clothing</option>
                      <option value="Health & Beauty">Health & Beauty</option>
                      <option value="General">General Store</option>
                    </select>
                  </div>

                  <div className={styles.inputGroup}>
                    <label className={styles.inputLabel}>Image URL (Optional)</label>
                    <input
                      type="url"
                      value={productImageUrl}
                      onChange={(e) => setProductImageUrl(e.target.value)}
                      placeholder="https://.../photo.jpg"
                      className={styles.textInput}
                    />
                  </div>
                </div>

                <div className={styles.inputGroup}>
                  <label className={styles.inputLabel}>Product Description</label>
                  <textarea
                    value={productDescription}
                    onChange={(e) => setProductDescription(e.target.value)}
                    placeholder="Short description, pack size, brand or ingredients..."
                    className={styles.textInput}
                  />
                </div>

                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  type="submit"
                  disabled={addingProduct}
                  className={styles.productSubmitBtn}
                >
                  {addingProduct ? (
                    'Publishing Product...'
                  ) : (
                    <>
                      <PlusCircle size={17} />
                      Publish to My Store
                    </>
                  )}
                </motion.button>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── TOAST NOTIFICATION ── */}
      <AnimatePresence>
        {toastMessage && (
          <motion.div
            className={styles.toastNotice}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 15 }}
          >
            <CheckCircle size={18} />
            <span>{toastMessage}</span>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
