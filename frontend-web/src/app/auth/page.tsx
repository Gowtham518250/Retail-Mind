'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Eye, EyeOff, Lock, Phone, ShoppingBag, ArrowRight, User, Mail, CheckCircle } from 'lucide-react';
import { API_BASE } from '../../lib/api';
import styles from './auth.module.css';

type View = 'login' | 'register' | 'reset';

export default function AuthPage() {
  const router = useRouter();
  const [view, setView] = useState<View>('login');
  const [phone, setPhone]     = useState('');
  const [password, setPassword] = useState('');
  const [name, setName]       = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [success, setSuccess] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Redirect if already logged in
  useEffect(() => {
    if (typeof window !== 'undefined' && localStorage.getItem('customerToken')) {
      router.replace('/');
    }
  }, [router]);

  const switchView = (v: View) => {
    setError('');
    setSuccess('');
    setView(v);
  };

  // ── Login ────────────────────────────────────────────────────────────────
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/store/customer/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Login failed. Check your credentials.');

      localStorage.setItem('customerToken', data.access_token);
      localStorage.setItem('customerName', data.customer?.name || data.name || phone);
      router.replace('/');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Register ─────────────────────────────────────────────────────────────
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/store/customer/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, phone, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Registration failed. Please try again.');

      localStorage.setItem('customerToken', data.access_token);
      localStorage.setItem('customerName', data.name || name);
      router.replace('/');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Forgot Password ───────────────────────────────────────────────────────
  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const res = await fetch(`${API_BASE}/store/customer/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Reset failed. Please try again.');
      setSuccess('Password reset instructions sent to your registered contact.');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className={styles.authMain}>
      {/* Animated background orbs */}
      <div className={styles.orb1} />
      <div className={styles.orb2} />
      <div className={styles.orb3} />

      <div className={styles.authCenter}>
        <motion.div
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, type: 'spring', stiffness: 100 }}
          className={styles.authCard}
        >
          {/* Logo */}
          <motion.div
            whileHover={{ scale: 1.06 }}
            className={styles.logoArea}
            onClick={() => router.push('/')}
          >
            <div className={styles.logoIcon}>
              <ShoppingBag size={22} />
            </div>
            <span className={styles.logoText}>RetailShop</span>
          </motion.div>

          <AnimatePresence mode="wait">

            {/* ── LOGIN ── */}
            {view === 'login' && (
              <motion.div
                key="login"
                initial={{ opacity: 0, x: -24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 24 }}
                transition={{ duration: 0.28 }}
              >
                <h1 className={styles.authTitle}>Welcome back</h1>
                <p className={styles.authSubtitle}>Sign in to continue shopping</p>

                <form onSubmit={handleLogin} className={styles.form} noValidate>
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
                  </AnimatePresence>

                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Mobile Number</label>
                    <div className={styles.inputWrap}>
                      <Phone size={17} className={styles.inputIcon} />
                      <input
                        id="login-phone"
                        type="tel"
                        value={phone}
                        onChange={e => setPhone(e.target.value)}
                        className={styles.input}
                        placeholder="10-digit number"
                        required
                        pattern="[0-9]{10}"
                        maxLength={10}
                        autoComplete="tel"
                      />
                    </div>
                  </div>

                  <div className={styles.fieldGroup}>
                    <div className={styles.labelRow}>
                      <label className={styles.label}>Password</label>
                      <span className={styles.link} onClick={() => switchView('reset')}>Forgot password?</span>
                    </div>
                    <div className={styles.inputWrap}>
                      <Lock size={17} className={styles.inputIcon} />
                      <input
                        id="login-password"
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        className={styles.input}
                        placeholder="••••••••"
                        required
                        autoComplete="current-password"
                      />
                      <button type="button" className={styles.eyeBtn} onClick={() => setShowPassword(v => !v)} tabIndex={-1}>
                        {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                      </button>
                    </div>
                  </div>

                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.97 }}
                    type="submit"
                    disabled={loading}
                    className={styles.submitBtn}
                    id="login-submit"
                  >
                    {loading ? <span className={styles.spinner} /> : <>Sign In <ArrowRight size={17} /></>}
                  </motion.button>
                </form>

                <p className={styles.switchText}>
                  New here?{' '}
                  <span className={styles.link} onClick={() => switchView('register')}>Create an account</span>
                </p>
              </motion.div>
            )}

            {/* ── REGISTER ── */}
            {view === 'register' && (
              <motion.div
                key="register"
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -24 }}
                transition={{ duration: 0.28 }}
              >
                <h1 className={styles.authTitle}>Create account</h1>
                <p className={styles.authSubtitle}>Join thousands of happy shoppers</p>

                <form onSubmit={handleRegister} className={styles.form} noValidate>
                  <AnimatePresence>
                    {error && (
                      <motion.div key="err" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className={styles.errorBanner}>
                        {error}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Full Name</label>
                    <div className={styles.inputWrap}>
                      <User size={17} className={styles.inputIcon} />
                      <input
                        id="reg-name"
                        type="text"
                        value={name}
                        onChange={e => setName(e.target.value)}
                        className={styles.input}
                        placeholder="Your full name"
                        required
                        minLength={2}
                        autoComplete="name"
                      />
                    </div>
                  </div>

                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Mobile Number</label>
                    <div className={styles.inputWrap}>
                      <Phone size={17} className={styles.inputIcon} />
                      <input
                        id="reg-phone"
                        type="tel"
                        value={phone}
                        onChange={e => setPhone(e.target.value)}
                        className={styles.input}
                        placeholder="10-digit number"
                        required
                        pattern="[0-9]{10}"
                        maxLength={10}
                        autoComplete="tel"
                      />
                    </div>
                  </div>

                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Password</label>
                    <div className={styles.inputWrap}>
                      <Lock size={17} className={styles.inputIcon} />
                      <input
                        id="reg-password"
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        className={styles.input}
                        placeholder="Min. 6 characters"
                        required
                        minLength={6}
                        autoComplete="new-password"
                      />
                      <button type="button" className={styles.eyeBtn} onClick={() => setShowPassword(v => !v)} tabIndex={-1}>
                        {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                      </button>
                    </div>
                  </div>

                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.97 }}
                    type="submit"
                    disabled={loading}
                    className={styles.submitBtn}
                    id="reg-submit"
                  >
                    {loading ? <span className={styles.spinner} /> : <>Create Account <ArrowRight size={17} /></>}
                  </motion.button>
                </form>

                <p className={styles.switchText}>
                  Already a member?{' '}
                  <span className={styles.link} onClick={() => switchView('login')}>Sign in</span>
                </p>
              </motion.div>
            )}

            {/* ── RESET ── */}
            {view === 'reset' && (
              <motion.div
                key="reset"
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.28 }}
              >
                <h1 className={styles.authTitle}>Reset password</h1>
                <p className={styles.authSubtitle}>Enter your registered mobile number</p>

                <form onSubmit={handleReset} className={styles.form} noValidate>
                  <AnimatePresence>
                    {error && (
                      <motion.div key="err" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className={styles.errorBanner}>
                        {error}
                      </motion.div>
                    )}
                    {success && (
                      <motion.div key="ok" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className={styles.successBanner}>
                        <CheckCircle size={16} style={{ flexShrink: 0 }} /> {success}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className={styles.fieldGroup}>
                    <label className={styles.label}>Mobile Number</label>
                    <div className={styles.inputWrap}>
                      <Phone size={17} className={styles.inputIcon} />
                      <input
                        id="reset-phone"
                        type="tel"
                        value={phone}
                        onChange={e => setPhone(e.target.value)}
                        className={styles.input}
                        placeholder="Registered number"
                        required
                        pattern="[0-9]{10}"
                        maxLength={10}
                      />
                    </div>
                  </div>

                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.97 }}
                    type="submit"
                    disabled={loading || !!success}
                    className={styles.submitBtn}
                    id="reset-submit"
                  >
                    {loading ? <span className={styles.spinner} /> : 'Send Reset Link'}
                  </motion.button>
                </form>

                <p className={styles.switchText}>
                  <span className={styles.link} onClick={() => switchView('login')}>← Back to Sign In</span>
                </p>
              </motion.div>
            )}

          </AnimatePresence>
        </motion.div>
      </div>
    </main>
  );
}
