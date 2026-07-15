'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, useMotionValue, useSpring, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Eye, EyeOff, Lock, Phone, Atom, ArrowRight, User } from 'lucide-react';
import styles from './auth.module.css';

export default function AuthPage() {
  const router = useRouter();
  const [view, setView] = useState<'login' | 'register' | 'reset'>('login');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Advanced Mouse Tracking Glow Effect
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springX = useSpring(mouseX, { stiffness: 50, damping: 20 });
  const springY = useSpring(mouseY, { stiffness: 50, damping: 20 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mouseX.set(e.clientX);
      mouseY.set(e.clientY);
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [mouseX, mouseY]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('/store/customer/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, password })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.message || 'Login failed. Please check your credentials.');
      
      localStorage.setItem('customerToken', data.access_token);
      localStorage.setItem('customerName', data.customer?.name || data.name || phone);
      router.push('/');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('/store/customer/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, phone, password, shop_id: 1, firebase_id_token: null })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.message || 'Registration failed. Please try again.');
      
      localStorage.setItem('customerToken', data.access_token);
      localStorage.setItem('customerName', data.name || name);
      router.push('/');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/store/customer/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.message || 'Reset failed.');
      alert('Password reset instructions sent!');
      setView('login');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className={styles.authMain}>
      
      {/* Background Layers */}
      <div className={styles.spaceBackground}>
        <div className={styles.spaceImage} />
        <div className={styles.spaceGradientTop} />
        <div className={styles.spaceGradientBottom} />
      </div>

      {/* Centered Form Column */}
      <div className={styles.authRightCol}>
        
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, type: "spring" }}
          className={styles.authFormContainer}
        >
          {/* Logo */}
          <motion.div 
            whileHover={{ scale: 1.05 }}
            className={styles.brandLogo}
            onClick={() => router.push("/")}
          >
            <span className={styles.brandText}>
              RetailShop
            </span>
          </motion.div>

          <AnimatePresence mode="wait">
            
            {/* LOGIN VIEW */}
            {view === 'login' && (
              <motion.div key="login" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} transition={{ duration: 0.3 }}>
                <h1 className={styles.authTitle}>Welcome Back</h1>
                <p className={styles.authSubtitle}>Sign in to continue your journey.</p>

                <form onSubmit={handleLogin}>
                  {error && (
                    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className={styles.authErrorMsg}>
                      {error}
                    </motion.div>
                  )}

                  <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }} className={styles.inputGroup}>
                    <label className={styles.inputLabel}>Mobile Number</label>
                    <div className={styles.inputWrapper}>
                      <div className={styles.inputIcon}><Phone size={20} /></div>
                      <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} className={styles.authInput} placeholder="Enter 10 digit number" required pattern="[0-9]{10}" />
                    </div>
                  </motion.div>

                  <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }} className={styles.inputGroup}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                      <label className={styles.inputLabel} style={{ marginBottom: 0 }}>Password</label>
                      <span onClick={() => setView('reset')} style={{ fontSize: '0.875rem', fontWeight: 500, color: '#4cc9f0', cursor: 'pointer' }}>Forgot password?</span>
                    </div>
                    <div className={styles.inputWrapper}>
                      <div className={styles.inputIcon}><Lock size={20} /></div>
                      <input type={showPassword ? "text" : "password"} value={password} onChange={e => setPassword(e.target.value)} className={styles.authInput} placeholder="••••••••" required />
                      <button type="button" onClick={() => setShowPassword(!showPassword)} className={styles.passwordToggle}>
                        {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                      </button>
                    </div>
                  </motion.div>

                  <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
                    <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} type="submit" disabled={loading} className={styles.submitBtn}>
                      {loading ? 'Logging in...' : <><Atom size={20} /> Sign In <ArrowRight size={20} /></>}
                    </motion.button>
                  </motion.div>
                </form>

                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} className={styles.bottomLink}>
                  New to RetailShop? <span onClick={() => setView('register')} style={{ cursor: 'pointer', color: '#4cc9f0', fontWeight: 'bold' }}>Create an account</span>
                </motion.div>
              </motion.div>
            )}

            {/* REGISTER VIEW */}
            {view === 'register' && (
              <motion.div key="register" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.3 }}>
                <h1 className={styles.authTitle}>Create Account</h1>
                <p className={styles.authSubtitle}>Join us to access orders and wishlist.</p>

                <form onSubmit={handleRegister}>
                  {error && <div className={styles.authErrorMsg}>{error}</div>}

                  <div className={styles.inputGroup}>
                    <label className={styles.inputLabel}>Full Name</label>
                    <div className={styles.inputWrapper}>
                      <div className={styles.inputIcon}><User size={20} /></div>
                      <input type="text" value={name} onChange={e => setName(e.target.value)} className={styles.authInput} placeholder="Enter your name" required />
                    </div>
                  </div>

                  <div className={styles.inputGroup}>
                    <label className={styles.inputLabel}>Mobile Number</label>
                    <div className={styles.inputWrapper}>
                      <div className={styles.inputIcon}><Phone size={20} /></div>
                      <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} className={styles.authInput} placeholder="Enter 10 digit number" required pattern="[0-9]{10}" />
                    </div>
                  </div>

                  <div className={styles.inputGroup}>
                    <label className={styles.inputLabel}>Password</label>
                    <div className={styles.inputWrapper}>
                      <div className={styles.inputIcon}><Lock size={20} /></div>
                      <input type="password" value={password} onChange={e => setPassword(e.target.value)} className={styles.authInput} placeholder="Create password" required />
                    </div>
                  </div>

                  <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} type="submit" disabled={loading} className={styles.submitBtn}>
                    {loading ? 'Creating...' : <><Atom size={20} /> Continue <ArrowRight size={20} /></>}
                  </motion.button>
                </form>

                <div className={styles.bottomLink}>
                  Existing User? <span onClick={() => setView('login')} style={{ cursor: 'pointer', color: '#4cc9f0', fontWeight: 'bold' }}>Log in</span>
                </div>
              </motion.div>
            )}

            {/* RESET VIEW */}
            {view === 'reset' && (
              <motion.div key="reset" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} transition={{ duration: 0.3 }}>
                <h1 className={styles.authTitle}>Reset Password</h1>
                <p className={styles.authSubtitle}>Enter your registered number to reset.</p>

                <form onSubmit={handleReset}>
                  {error && <div className={styles.authErrorMsg}>{error}</div>}

                  <div className={styles.inputGroup}>
                    <label className={styles.inputLabel}>Mobile Number</label>
                    <div className={styles.inputWrapper}>
                      <div className={styles.inputIcon}><Phone size={20} /></div>
                      <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} className={styles.authInput} placeholder="Enter registered number" required pattern="[0-9]{10}" />
                    </div>
                  </div>

                  <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} type="submit" disabled={loading} className={styles.submitBtn}>
                    {loading ? 'Processing...' : 'Reset Password'}
                  </motion.button>
                </form>

                <div className={styles.bottomLink}>
                  <span onClick={() => setView('login')} style={{ cursor: 'pointer', color: '#4cc9f0', fontWeight: 'bold' }}>Back to Login</span>
                </div>
              </motion.div>
            )}
            
          </AnimatePresence>
        </motion.div>
      </div>
    </main>
  );
}
