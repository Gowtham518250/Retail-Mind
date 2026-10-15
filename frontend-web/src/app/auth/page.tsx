'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Eye,
  EyeOff,
  Lock,
  Phone,
  ShoppingBag,
  ArrowRight,
  User,
  Mail,
  CheckCircle,
  Store,
  Sparkles,
  QrCode,
  TrendingUp,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { API_BASE } from '../../lib/api';
import styles from './auth.module.css';

type Role = 'customer' | 'seller';
type View = 'login' | 'register' | 'reset';

export default function AuthPage() {
  const router = useRouter();
  const [role, setRole] = useState<Role>('customer');
  const [view, setView] = useState<View>('login');

  // Common fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');

  // Seller specific fields
  const [shopName, setShopName] = useState('');
  const [shopCategory, setShopCategory] = useState('General Retail');

  // Reset password states (Customer)
  const [resetStep, setResetStep] = useState<'request' | 'verify' | 'password'>('request');
  const [resetOtp, setResetOtp] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [resetPassword, setResetPassword] = useState('');
  const [resetPasswordConfirm, setResetPasswordConfirm] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);

  // Status indicators
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [redirectPath, setRedirectPath] = useState('/profile');

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    const roleParam = params.get('role') || params.get('mode');
    if (roleParam === 'seller' || roleParam === 'merchant') {
      setRole('seller');
    }

    const resetRequested = params.get('view') === 'reset';
    const emailParam = params.get('email') || '';
    const requestedNext = params.get('next') || '/profile';
    const safeNext = requestedNext.startsWith('/') && !requestedNext.startsWith('//')
      ? requestedNext
      : '/profile';

    setRedirectPath(safeNext);

    if (emailParam) {
      setEmail(emailParam);
    }

    if (resetRequested || emailParam) {
      setView('reset');
      setResetStep('request');
      return;
    }

    // Check existing customer or merchant session
    if (localStorage.getItem('customerToken') || localStorage.getItem('merchantToken')) {
      router.replace(safeNext);
    }
  }, [router]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = window.setInterval(() => {
      setResendCooldown((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendCooldown]);

  const switchView = (v: View) => {
    setError('');
    setSuccess('');
    if (v === 'reset') {
      setResetStep('request');
      setResetOtp('');
      setResetToken('');
      setResetPassword('');
      setResetPasswordConfirm('');
      setResendCooldown(0);
    }
    setView(v);
  };

  const switchRole = (r: Role) => {
    setError('');
    setSuccess('');
    setRole(r);
    if (view === 'reset') setView('login');
  };

  const isValidEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

  // ── CUSTOMER LOGIN ────────────────────────────────────────────────────────
  const handleCustomerLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidEmail(email)) {
      setError('Please enter a valid email address.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/store/customer/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Login failed. Check your credentials.');

      localStorage.setItem('customerToken', data.access_token);
      localStorage.setItem('customerName', data.customer?.name || data.name || email);
      localStorage.setItem('customerEmail', data.customer?.email || data.email || email);
      localStorage.setItem('userRole', 'CUSTOMER');
      router.replace(redirectPath);
    } catch (err: any) {
      setError(err.message || 'Customer login failed.');
    } finally {
      setLoading(false);
    }
  };

  // ── CUSTOMER REGISTER ─────────────────────────────────────────────────────
  const handleCustomerRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim().length < 2) {
      setError('Name must be at least 2 characters long.');
      return;
    }
    if (!isValidEmail(email)) {
      setError('Please enter a valid email address.');
      return;
    }
    if (!/^\d{10}$/.test(phone)) {
      setError('Please enter a valid 10-digit mobile number.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/store/customer/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, phone, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Registration failed. Please try again.');

      localStorage.setItem('customerToken', data.access_token);
      localStorage.setItem('customerName', data.name || name);
      localStorage.setItem('customerEmail', email);
      localStorage.setItem('userRole', 'CUSTOMER');
      router.replace(redirectPath);
    } catch (err: any) {
      setError(err.message || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  // ── SELLER / OWNER LOGIN ──────────────────────────────────────────────────
  const handleSellerLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidEmail(email)) {
      setError('Please enter your registered email address.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Seller sign-in failed. Check credentials.');

      const token = data.access_token;
      const resolvedShopId = data.shop_profile?.shop_id || data.user_id;
      const resolvedShopName = data.shop_profile?.shop_name || `${data.username}'s Store`;

      localStorage.setItem('merchantToken', token);
      localStorage.setItem('customerToken', token); // Allow unified browsing
      localStorage.setItem('userRole', 'OWNER');
      localStorage.setItem('customerName', data.username || email);
      localStorage.setItem('customerEmail', email);
      localStorage.setItem('shopId', String(resolvedShopId));
      localStorage.setItem('shopName', resolvedShopName);

      setSuccess('Store owner verified! Redirecting to your merchant dashboard...');
      setTimeout(() => {
        router.replace('/profile');
      }, 600);
    } catch (err: any) {
      setError(err.message || 'Seller login failed.');
    } finally {
      setLoading(false);
    }
  };

  // ── SELLER / OWNER REGISTER (OPEN STORE) ──────────────────────────────────
  const handleSellerRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim().length < 2) {
      setError('Please enter the business owner name.');
      return;
    }
    if (shopName.trim().length < 2) {
      setError('Please enter your store or shop name.');
      return;
    }
    if (!isValidEmail(email)) {
      setError('Please enter a valid business email address.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: name.trim(),
          email: email.trim().toLowerCase(),
          password,
          user_type: 'OWNER',
          shop_name: shopName.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Could not register store. Please try again.');

      const token = data.access_token;
      const registeredShopId = data.shop_profile?.shop_id || data.user_id;
      const registeredShopName = data.shop_profile?.shop_name || shopName.trim();

      localStorage.setItem('merchantToken', token);
      localStorage.setItem('customerToken', token);
      localStorage.setItem('userRole', 'OWNER');
      localStorage.setItem('customerName', name.trim());
      localStorage.setItem('customerEmail', email.trim().toLowerCase());
      localStorage.setItem('shopId', String(registeredShopId));
      localStorage.setItem('shopName', registeredShopName);

      setSuccess(`Congratulations! "${registeredShopName}" is now registered and live online!`);
      setTimeout(() => {
        router.replace('/profile');
      }, 800);
    } catch (err: any) {
      setError(err.message || 'Seller registration failed.');
    } finally {
      setLoading(false);
    }
  };

  // ── CUSTOMER PASSWORD RESET ───────────────────────────────────────────────
  const requestResetOtp = async () => {
    if (!isValidEmail(email)) {
      throw new Error('Please enter a valid email address.');
    }
    const res = await fetch(`${API_BASE}/store/customer/request-password-reset-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Unable to send OTP.');
    setResetStep('verify');
    setResendCooldown(30);
    setSuccess('A 6-digit OTP has been sent to your registered email address.');
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      if (resetStep === 'request') {
        await requestResetOtp();
        return;
      }
      if (resetStep === 'verify') {
        if (!/^\d{6}$/.test(resetOtp)) {
          throw new Error('Enter the 6-digit OTP from your email.');
        }
        const res = await fetch(`${API_BASE}/store/customer/verify-password-reset-otp`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, otp: resetOtp }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || data.message || 'OTP verification failed.');
        setResetToken(data.reset_token || '');
        setResetStep('password');
        setSuccess('OTP verified. Create your new password.');
        return;
      }
      if (!resetToken) {
        throw new Error('Reset authorization expired. Request a new OTP.');
      }
      if (resetPassword.length < 8) {
        throw new Error('New password must be at least 8 characters long.');
      }
      if (resetPassword !== resetPasswordConfirm) {
        throw new Error('Passwords do not match.');
      }
      const res = await fetch(`${API_BASE}/store/customer/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reset_token: resetToken, new_password: resetPassword }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Password reset failed.');
      setSuccess('Password reset successfully. You can now sign in.');
      setView('login');
    } catch (err: any) {
      setError(err.message || 'Password reset failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className={styles.authMain}>
      {/* 3D Floating Glow Orbs */}
      <div className={styles.orb1} />
      <div className={styles.orb2} />
      <div className={styles.orb3} />
      <div className={styles.orb4} />

      <div className={styles.authContainer}>
        {/* Left Side: 3D Feature Showcase */}
        <motion.div
          className={styles.heroShowcase}
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className={styles.brandPill}>
            <Sparkles size={14} />
            <span>RetailMind Next-Gen Platform</span>
          </div>

          <h1 className={styles.heroTitle}>
            {role === 'seller' ? (
              <>
                Sell to Thousands.{' '}
                <span className={styles.heroGradientText}>Zero Platform Commission.</span>
              </>
            ) : (
              <>
                The Smartest Way to{' '}
                <span className={styles.heroGradientText}>Shop Your Local Stores.</span>
              </>
            )}
          </h1>

          <p className={styles.heroSubtitle}>
            {role === 'seller'
              ? 'Launch your digital storefront in 60 seconds. Receive instant UPI payments, manage inventory with AI, and serve neighborhood customers effortlessly.'
              : 'Discover neighborhood verified stores, order in real-time, get instant local dispatch, and enjoy AI-guided voice and text shopping.'}
          </p>

          <div className={styles.featureList}>
            {role === 'seller' ? (
              <>
                <div className={styles.featureItem}>
                  <div className={styles.featureIconWrap}>
                    <Store size={20} />
                  </div>
                  <div className={styles.featureContent}>
                    <strong>Instant Digital Storefront</strong>
                    <span>Get a branded URL & QR code for your shop right away</span>
                  </div>
                </div>
                <div className={styles.featureItem}>
                  <div className={styles.featureIconWrap}>
                    <QrCode size={20} />
                  </div>
                  <div className={styles.featureContent}>
                    <strong>Direct UPI Settlements</strong>
                    <span>Customers pay your UPI QR directly with instant voice alerts</span>
                  </div>
                </div>
                <div className={styles.featureItem}>
                  <div className={styles.featureIconWrap}>
                    <TrendingUp size={20} />
                  </div>
                  <div className={styles.featureContent}>
                    <strong>Realtime Stock & AI Insights</strong>
                    <span>Live stock movement, low stock radar, and automated sales sync</span>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className={styles.featureItem}>
                  <div className={styles.featureIconWrap}>
                    <ShoppingBag size={20} />
                  </div>
                  <div className={styles.featureContent}>
                    <strong>Curated Local Catalogs</strong>
                    <span>Browse actual live inventory from verified retail merchants</span>
                  </div>
                </div>
                <div className={styles.featureItem}>
                  <div className={styles.featureIconWrap}>
                    <Zap size={20} />
                  </div>
                  <div className={styles.featureContent}>
                    <strong>Instant Local Delivery</strong>
                    <span>Direct dispatch from nearby stores right to your doorstep</span>
                  </div>
                </div>
                <div className={styles.featureItem}>
                  <div className={styles.featureIconWrap}>
                    <ShieldCheck size={20} />
                  </div>
                  <div className={styles.featureContent}>
                    <strong>Verified & Secure Payments</strong>
                    <span>Pay seamlessly with UPI, Cards, NetBanking or Cash on Delivery</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </motion.div>

        {/* Right Side: Auth Glass Card */}
        <motion.div
          className={styles.authCard}
          initial={{ opacity: 0, y: 25 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className={styles.cardGlowBar} />

          {/* Role Selector: Customer vs Seller */}
          <div className={styles.roleSelector} role="tablist" aria-label="Account Type">
            <button
              type="button"
              className={`${styles.roleBtn} ${role === 'customer' ? styles.roleBtnActive : ''}`}
              onClick={() => switchRole('customer')}
              role="tab"
              aria-selected={role === 'customer'}
            >
              <ShoppingBag size={15} />
              <span>Customer</span>
            </button>
            <button
              type="button"
              className={`${styles.roleBtn} ${role === 'seller' ? styles.roleBtnActive : ''}`}
              onClick={() => switchRole('seller')}
              role="tab"
              aria-selected={role === 'seller'}
            >
              <Store size={15} />
              <span>Sell Products</span>
              <span className={styles.roleBadge}>NEW</span>
            </button>
          </div>

          {/* Card Header */}
          <div className={styles.cardHeader}>
            <h2 className={styles.authTitle}>
              {role === 'seller'
                ? view === 'login'
                  ? 'Merchant Sign In'
                  : 'Open Your Online Store'
                : view === 'login'
                  ? 'Welcome Back'
                  : view === 'register'
                    ? 'Create Your Account'
                    : 'Account Recovery'}
            </h2>
            <p className={styles.authSubtitle}>
              {role === 'seller'
                ? view === 'login'
                  ? 'Log in to manage your storefront, products and orders'
                  : 'Register online and start selling your products in minutes'
                : view === 'login'
                  ? 'Sign in to access your orders and smart shopping hub'
                  : view === 'register'
                    ? 'Join RetailMind for instant local shopping and fast delivery'
                    : 'We will send a verification OTP to reset your password'}
            </p>
          </div>

          {/* Mode Tabs (Sign In / Register) */}
          {view !== 'reset' && (
            <div className={styles.modeTabs}>
              <button
                type="button"
                className={`${styles.modeTabBtn} ${view === 'login' ? styles.modeTabActive : ''}`}
                onClick={() => switchView('login')}
              >
                Sign In
                {view === 'login' && <motion.div layoutId="modeUnderline" className={styles.modeIndicator} />}
              </button>
              <button
                type="button"
                className={`${styles.modeTabBtn} ${view === 'register' ? styles.modeTabActive : ''}`}
                onClick={() => switchView('register')}
              >
                {role === 'seller' ? 'Register Store' : 'Create Account'}
                {view === 'register' && <motion.div layoutId="modeUnderline" className={styles.modeIndicator} />}
              </button>
            </div>
          )}

          {/* Feedback Messages */}
          <AnimatePresence>
            {error && (
              <motion.div
                key="err"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className={styles.errorBanner}
              >
                {error}
              </motion.div>
            )}
            {success && (
              <motion.div
                key="ok"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className={styles.successBanner}
              >
                <CheckCircle size={17} style={{ flexShrink: 0 }} />
                <span>{success}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ═══════════════════ FORMS ═══════════════════ */}
          <AnimatePresence mode="wait">
            {/* ── 1. CUSTOMER LOGIN ── */}
            {role === 'customer' && view === 'login' && (
              <motion.form
                key="cust-login"
                onSubmit={handleCustomerLogin}
                className={styles.form}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.25 }}
              >
                <div className={styles.fieldGroup}>
                  <label className={styles.label}>Email Address</label>
                  <div className={styles.inputWrap}>
                    <Mail size={17} className={styles.inputIcon} />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      className={styles.input}
                      required
                      autoComplete="email"
                    />
                  </div>
                </div>

                <div className={styles.fieldGroup}>
                  <div className={styles.labelRow}>
                    <label className={styles.label}>Password</label>
                    <span className={styles.forgotLink} onClick={() => switchView('reset')}>
                      Forgot Password?
                    </span>
                  </div>
                  <div className={styles.inputWrap}>
                    <Lock size={17} className={styles.inputIcon} />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className={styles.input}
                      required
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      className={styles.eyeBtn}
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                      aria-label="Toggle password visibility"
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <motion.button
                  whileHover={{ scale: 1.015 }}
                  whileTap={{ scale: 0.985 }}
                  type="submit"
                  disabled={loading}
                  className={styles.submitBtn}
                >
                  {loading ? <span className={styles.spinner} /> : <>Sign In to Shop <ArrowRight size={17} /></>}
                </motion.button>
              </motion.form>
            )}

            {/* ── 2. CUSTOMER REGISTER ── */}
            {role === 'customer' && view === 'register' && (
              <motion.form
                key="cust-reg"
                onSubmit={handleCustomerRegister}
                className={styles.form}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.25 }}
              >
                <div className={styles.fieldGroup}>
                  <label className={styles.label}>Full Name</label>
                  <div className={styles.inputWrap}>
                    <User size={17} className={styles.inputIcon} />
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Your full name"
                      className={styles.input}
                      required
                      minLength={2}
                      autoComplete="name"
                    />
                  </div>
                </div>

                <div className={styles.twoCols}>
                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Email Address</label>
                    <div className={styles.inputWrap}>
                      <Mail size={17} className={styles.inputIcon} />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@email.com"
                        className={styles.input}
                        required
                        autoComplete="email"
                      />
                    </div>
                  </div>

                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Mobile Number</label>
                    <div className={styles.inputWrap}>
                      <Phone size={17} className={styles.inputIcon} />
                      <input
                        type="tel"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="10-digit number"
                        className={styles.input}
                        required
                        maxLength={10}
                        pattern="[0-9]{10}"
                      />
                    </div>
                  </div>
                </div>

                <div className={styles.fieldGroup}>
                  <label className={styles.label}>Password</label>
                  <div className={styles.inputWrap}>
                    <Lock size={17} className={styles.inputIcon} />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Min. 6 characters"
                      className={styles.input}
                      required
                      minLength={6}
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      className={styles.eyeBtn}
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                      aria-label="Toggle password visibility"
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <motion.button
                  whileHover={{ scale: 1.015 }}
                  whileTap={{ scale: 0.985 }}
                  type="submit"
                  disabled={loading}
                  className={styles.submitBtn}
                >
                  {loading ? <span className={styles.spinner} /> : <>Create Account <ArrowRight size={17} /></>}
                </motion.button>
              </motion.form>
            )}

            {/* ── 3. SELLER LOGIN ── */}
            {role === 'seller' && view === 'login' && (
              <motion.form
                key="seller-login"
                onSubmit={handleSellerLogin}
                className={styles.form}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.25 }}
              >
                <div className={styles.fieldGroup}>
                  <label className={styles.label}>Merchant / Business Email</label>
                  <div className={styles.inputWrap}>
                    <Mail size={17} className={styles.inputIcon} />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="merchant@store.com"
                      className={styles.input}
                      required
                      autoComplete="email"
                    />
                  </div>
                </div>

                <div className={styles.fieldGroup}>
                  <div className={styles.labelRow}>
                    <label className={styles.label}>Store Owner Password</label>
                  </div>
                  <div className={styles.inputWrap}>
                    <Lock size={17} className={styles.inputIcon} />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className={styles.input}
                      required
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      className={styles.eyeBtn}
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                      aria-label="Toggle password visibility"
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <div className={styles.sellerPerks}>
                  <div className={styles.sellerPerkItem}>
                    <CheckCircle size={14} /> <span>0% Platform Commission</span>
                  </div>
                  <div className={styles.sellerPerkItem}>
                    <CheckCircle size={14} /> <span>Live Storefront URL & QR</span>
                  </div>
                </div>

                <motion.button
                  whileHover={{ scale: 1.015 }}
                  whileTap={{ scale: 0.985 }}
                  type="submit"
                  disabled={loading}
                  className={styles.submitBtn}
                >
                  {loading ? <span className={styles.spinner} /> : <>Sign In as Merchant <ArrowRight size={17} /></>}
                </motion.button>
              </motion.form>
            )}

            {/* ── 4. SELLER REGISTER (OPEN STORE) ── */}
            {role === 'seller' && view === 'register' && (
              <motion.form
                key="seller-reg"
                onSubmit={handleSellerRegister}
                className={styles.form}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.25 }}
              >
                <div className={styles.twoCols}>
                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Business Owner Name</label>
                    <div className={styles.inputWrap}>
                      <User size={17} className={styles.inputIcon} />
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Owner name"
                        className={styles.input}
                        required
                        minLength={2}
                      />
                    </div>
                  </div>

                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Shop / Store Name</label>
                    <div className={styles.inputWrap}>
                      <Store size={17} className={styles.inputIcon} />
                      <input
                        type="text"
                        value={shopName}
                        onChange={(e) => setShopName(e.target.value)}
                        placeholder="e.g. Royal Mart"
                        className={styles.input}
                        required
                        minLength={2}
                      />
                    </div>
                  </div>
                </div>

                <div className={styles.twoCols}>
                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Business Email</label>
                    <div className={styles.inputWrap}>
                      <Mail size={17} className={styles.inputIcon} />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="store@email.com"
                        className={styles.input}
                        required
                      />
                    </div>
                  </div>

                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Store Category</label>
                    <div className={styles.inputWrap}>
                      <select
                        value={shopCategory}
                        onChange={(e) => setShopCategory(e.target.value)}
                        className={styles.input}
                      >
                        <option value="General Retail">General Store / Supermarket</option>
                        <option value="Grocery">Grocery & Daily Essentials</option>
                        <option value="Electronics">Electronics & Mobiles</option>
                        <option value="Fashion">Fashion & Apparel</option>
                        <option value="Pharmacy">Pharmacy & Healthcare</option>
                        <option value="Bakery">Bakery & Cafe</option>
                      </select>
                    </div>
                  </div>
                </div>

                <div className={styles.fieldGroup}>
                  <label className={styles.label}>Set Password</label>
                  <div className={styles.inputWrap}>
                    <Lock size={17} className={styles.inputIcon} />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Min. 6 characters"
                      className={styles.input}
                      required
                      minLength={6}
                    />
                    <button
                      type="button"
                      className={styles.eyeBtn}
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                      aria-label="Toggle password visibility"
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <div className={styles.sellerPerks}>
                  <div className={styles.sellerPerkItem}>
                    <CheckCircle size={14} /> <span>Instant Store ID & QR</span>
                  </div>
                  <div className={styles.sellerPerkItem}>
                    <CheckCircle size={14} /> <span>Add Products Online Anytime</span>
                  </div>
                </div>

                <motion.button
                  whileHover={{ scale: 1.015 }}
                  whileTap={{ scale: 0.985 }}
                  type="submit"
                  disabled={loading}
                  className={styles.submitBtn}
                >
                  {loading ? <span className={styles.spinner} /> : <>Launch My Store Online <ArrowRight size={17} /></>}
                </motion.button>
              </motion.form>
            )}

            {/* ── 5. RESET PASSWORD FLOW (CUSTOMER) ── */}
            {view === 'reset' && (
              <motion.form
                key="reset-flow"
                onSubmit={handleReset}
                className={styles.form}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.25 }}
              >
                {resetStep === 'request' && (
                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Registered Email Address</label>
                    <div className={styles.inputWrap}>
                      <Mail size={17} className={styles.inputIcon} />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@example.com"
                        className={styles.input}
                        required
                        autoComplete="email"
                      />
                    </div>
                  </div>
                )}

                {resetStep === 'verify' && (
                  <>
                    <div className={styles.fieldGroup}>
                      <label className={styles.label}>6-Digit OTP Code</label>
                      <div className={styles.inputWrap}>
                        <CheckCircle size={17} className={styles.inputIcon} />
                        <input
                          type="text"
                          inputMode="numeric"
                          value={resetOtp}
                          onChange={(e) => setResetOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                          placeholder="000000"
                          maxLength={6}
                          className={styles.input}
                          required
                          autoComplete="one-time-code"
                        />
                      </div>
                    </div>
                    <button
                      type="button"
                      className={styles.forgotLink}
                      onClick={() => void requestResetOtp()}
                      disabled={resendCooldown > 0 || loading}
                      style={{ background: 'none', border: 'none', alignSelf: 'flex-start', padding: 0 }}
                    >
                      {resendCooldown > 0 ? `Resend OTP in ${resendCooldown}s` : 'Resend OTP'}
                    </button>
                  </>
                )}

                {resetStep === 'password' && (
                  <>
                    <div className={styles.fieldGroup}>
                      <label className={styles.label}>New Password</label>
                      <div className={styles.inputWrap}>
                        <Lock size={17} className={styles.inputIcon} />
                        <input
                          type={showPassword ? 'text' : 'password'}
                          value={resetPassword}
                          onChange={(e) => setResetPassword(e.target.value)}
                          placeholder="Min. 8 characters"
                          className={styles.input}
                          required
                          minLength={8}
                        />
                        <button
                          type="button"
                          className={styles.eyeBtn}
                          onClick={() => setShowPassword(!showPassword)}
                          tabIndex={-1}
                          aria-label="Toggle password visibility"
                        >
                          {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>

                    <div className={styles.fieldGroup}>
                      <label className={styles.label}>Confirm New Password</label>
                      <div className={styles.inputWrap}>
                        <Lock size={17} className={styles.inputIcon} />
                        <input
                          type={showPassword ? 'text' : 'password'}
                          value={resetPasswordConfirm}
                          onChange={(e) => setResetPasswordConfirm(e.target.value)}
                          placeholder="Re-enter new password"
                          className={styles.input}
                          required
                          minLength={8}
                        />
                      </div>
                    </div>
                  </>
                )}

                <motion.button
                  whileHover={{ scale: 1.015 }}
                  whileTap={{ scale: 0.985 }}
                  type="submit"
                  disabled={loading}
                  className={styles.submitBtn}
                >
                  {loading ? (
                    <span className={styles.spinner} />
                  ) : resetStep === 'request' ? (
                    'Send Verification OTP'
                  ) : resetStep === 'verify' ? (
                    'Verify OTP'
                  ) : (
                    'Save New Password'
                  )}
                </motion.button>
              </motion.form>
            )}
          </AnimatePresence>

          {/* Footer Navigation */}
          <div className={styles.switchRow}>
            {view === 'reset' ? (
              <button type="button" className={styles.switchAction} onClick={() => switchView('login')}>
                ← Back to Sign In
              </button>
            ) : view === 'login' ? (
              <span>
                Don&apos;t have an account?{' '}
                <button type="button" className={styles.switchAction} onClick={() => switchView('register')}>
                  {role === 'seller' ? 'Open Your Store' : 'Register Now'}
                </button>
              </span>
            ) : (
              <span>
                Already registered?{' '}
                <button type="button" className={styles.switchAction} onClick={() => switchView('login')}>
                  Sign In
                </button>
              </span>
            )}
          </div>
        </motion.div>
      </div>
    </main>
  );
}