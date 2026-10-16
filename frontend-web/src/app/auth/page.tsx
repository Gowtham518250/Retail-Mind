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
  Sparkles,
  ShieldCheck,
  Zap,
  Truck,
  Smartphone,
  KeyRound,
} from 'lucide-react';
import { API_BASE } from '../../lib/api';
import HeroScene3D from '../../components/HeroScene3D';
import styles from './auth.module.css';

type View = 'login' | 'register' | 'reset';

export default function AuthPage() {
  const router = useRouter();
  const [view, setView] = useState<View>('login');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');

  // Password Reset states (OTP flow)
  const [resetStep, setResetStep] = useState<'request' | 'verify' | 'password'>('request');
  const [resetOtp, setResetOtp] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [resetPassword, setResetPassword] = useState('');
  const [resetPasswordConfirm, setResetPasswordConfirm] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);

  // Status
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [redirectPath, setRedirectPath] = useState('/');

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    const resetRequested = params.get('view') === 'reset';
    const emailParam = params.get('email') || '';
    const requestedNext = params.get('next') || '/';
    const safeNext = requestedNext.startsWith('/') && !requestedNext.startsWith('//')
      ? requestedNext
      : '/';

    setRedirectPath(safeNext);

    if (emailParam) {
      setEmail(emailParam);
    }

    if (resetRequested || emailParam) {
      setView('reset');
      setResetStep('request');
      return;
    }

    if (localStorage.getItem('customerToken')) {
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

  const isValidEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

  // ── Customer Login ──
  const handleLogin = async (e: React.FormEvent) => {
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
      router.replace(redirectPath);
    } catch (err: any) {
      setError(err.message || 'Sign in failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // ── Customer Registration ──
  const handleRegister = async (e: React.FormEvent) => {
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
        body: JSON.stringify({ name: name.trim(), email: email.trim(), phone: phone.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Registration failed. Please try again.');

      localStorage.setItem('customerToken', data.access_token);
      localStorage.setItem('customerName', data.name || name.trim());
      localStorage.setItem('customerEmail', email.trim());
      router.replace(redirectPath);
    } catch (err: any) {
      setError(err.message || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  // ── OTP Password Reset Flow ──
  const requestResetOtp = async () => {
    if (!isValidEmail(email)) {
      throw new Error('Please enter a valid email address.');
    }
    const res = await fetch(`${API_BASE}/store/customer/request-password-reset-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim() }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Unable to send OTP.');
    if (data.success === false || data.email_sent === false) {
      // Keep the response generic without telling strangers whether the address has an account.
      setSuccess(data.message || 'If this email is eligible for password reset, a code may be sent. Check your inbox or try again later.');
      return;
    }
    setResetStep('verify');
    setResendCooldown(30);
    setSuccess('A 6-digit OTP has been sent to your registered email address.');
  };

  const handleReset = async (e: React.FormEvent, forcedStep?: 'request' | 'verify' | 'password') => {
    const activeStep = forcedStep || resetStep;
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      if (activeStep !== resetStep) throw new Error('Complete the previous recovery step first.');
      if (activeStep === 'request') {
        await requestResetOtp();
        return;
      }
      if (activeStep === 'verify') {
        if (!/^\d{6}$/.test(resetOtp)) {
          throw new Error('Enter the 6-digit OTP from your email.');
        }
        const res = await fetch(`${API_BASE}/store/customer/verify-password-reset-otp`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.trim(), otp: resetOtp.trim() }),
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
      {/* 3D Ambient Orbs */}
      <div className={styles.orb1} />
      <div className={styles.orb2} />
      <div className={styles.orb3} />

      <div className={`${styles.authContainer} ${view === 'reset' ? styles.authContainerReset : ''}`}>
        {view !== 'reset' && (
          <>
                  {/* Left Hero Showcase */}
                  <motion.div
                    className={styles.heroShowcase}
                    initial={{ opacity: 0, x: -30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.65 }}
                  >
                    <div className={styles.brandPill}>
                      <Sparkles size={14} />
                      <span>RetailMind Customer Hub</span>
                    </div>
          
                    <h1 className={styles.heroTitle}>
                      Welcome to{' '}
                      <span className={styles.heroGradientText}>Retail Mind</span>
                    </h1>
          
                    <p className={styles.heroSubtitle}>
                      Shop from local stores, discover fresh products and find everyday essentials — delivered to your doorstep.
                    </p>
          
                    <div className={styles.featureList}>
                      <div className={styles.featureItem}>
                        <div className={styles.featureIconWrap}>
                          <ShoppingBag size={20} />
                        </div>
                        <div className={styles.featureContent}>
                          <strong>Wide Range of Local Stores</strong>
                          <span>Groceries, daily needs, fresh products and more</span>
                        </div>
                      </div>
          
                      <div className={styles.featureItem}>
                        <div className={styles.featureIconWrap}>
                          <Truck size={20} />
                        </div>
                        <div className={styles.featureContent}>
                          <strong>Fast &amp; Reliable Delivery</strong>
                          <span>Review local delivery options from nearby stores</span>
                        </div>
                      </div>
          
                      <div className={styles.featureItem}>
                        <div className={styles.featureIconWrap}>
                          <ShieldCheck size={20} />
                        </div>
                        <div className={styles.featureContent}>
                          <strong>Safe &amp; Secure Shopping</strong>
                          <span>Your customer account and order details stay protected</span>
                        </div>
                      </div>
                    </div>
                    <div className={styles.authScene} aria-label="Animated 3D shopping scene">
                      <HeroScene3D lite className={styles.authSceneCanvas} />
                    </div>
                  </motion.div>
          
          
          </>
        )}
        {/* Right Glass Card */}
        <motion.div
          className={`${styles.authCard} ${view === 'reset' ? styles.authCardReset : ''}`}
          initial={{ opacity: 0, y: 25 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.1 }}
        >
          <div className={styles.cardGlowBar} />

          <div className={styles.cardHeader}>
            <div className={styles.cardHeadingCopy}>
              <h2 className={styles.authTitle}>
                {view === 'login'
                  ? 'Sign In to Shop'
                  : view === 'register'
                    ? 'Create Customer Account'
                    : 'Forgot Password'}
              </h2>
              <p className={styles.authSubtitle}>
                {view === 'login'
                  ? 'Sign in to access your cart, tracked orders, and saved addresses'
                  : view === 'register'
                    ? 'Join RetailMind for instant local shopping and convenient checkout'
                    : 'Reset your password using your email and 6-digit verification code.'}
              </p>
            </div>
            {view === 'reset' && (
              <button type="button" className={styles.resetBackLink} onClick={() => switchView('login')}>
                <ArrowRight size={14} /> Back to Sign In
              </button>
            )}
          </div>

          {/* Mode Tabs */}
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
                Create Account
                {view === 'register' && <motion.div layoutId="modeUnderline" className={styles.modeIndicator} />}
              </button>
            </div>
          )}

          {/* Feedback */}
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

          {/* ── FORMS ── */}
          <AnimatePresence mode="wait">
            {/* ── Sign In ── */}
            {view === 'login' && (
              <motion.form
                key="login-form"
                onSubmit={handleLogin}
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

            {/* ── Register ── */}
            {view === 'register' && (
              <motion.form
                key="reg-form"
                onSubmit={handleRegister}
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
                  <div className={styles.passwordStrength} aria-live="polite">
                    <div className={styles.passwordStrengthTrack}>
                      <span
                        className={styles.passwordStrengthFill}
                        data-strength={password.length === 0 ? 'empty' : password.length < 6 ? 'weak' : password.length < 8 || !/[A-Z]/.test(password) || !/[0-9]/.test(password) ? 'medium' : 'strong'}
                      />
                    </div>
                    <small>
                      {password.length === 0
                        ? 'Use 8+ characters for a stronger password.'
                        : password.length < 6
                          ? 'Weak — add more characters.'
                          : password.length < 8 || !/[A-Z]/.test(password) || !/[0-9]/.test(password)
                            ? 'Fair — add a number and uppercase letter.'
                            : 'Strong password.'}
                    </small>
                  </div>
                </div>

                <motion.button
                  whileHover={{ scale: 1.015 }}
                  whileTap={{ scale: 0.985 }}
                  type="submit"
                  disabled={loading}
                  className={styles.submitBtn}
                >
                  {loading ? <span className={styles.spinner} /> : <>Create Customer Account <ArrowRight size={17} /></>}
                </motion.button>
              </motion.form>
            )}

            {/* ── Password Reset Flow ── */}
            {view === 'reset' && (
              <motion.div
                key="reset-board"
                className={styles.resetBoard}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.22 }}
              >
                <section className={styles.resetStageCard + ' ' + (resetStep === 'request' ? styles.resetStageActive : styles.resetStageComplete)}>
                  <div className={styles.resetStageIllustration}><Mail size={27} /><span>EMAIL</span></div>
                  <div className={styles.resetStageBadge}>01 · ACCOUNT RECOVERY</div>
                  <h3>Reset your password</h3>
                  <p>Enter your email address and we’ll send a 6 digit reset code.</p>
                  <form onSubmit={(event) => void handleReset(event, 'request')} className={styles.resetStageForm}>
                    <label className={styles.label}>Email Address</label>
                    <div className={styles.inputWrap}>
                      <Mail size={16} className={styles.inputIcon} />
                      <input
                        type="email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        placeholder="you@example.com"
                        className={styles.input}
                        required
                        autoComplete="email"
                      />
                    </div>
                    <button className={styles.submitBtn} type="submit" disabled={loading || resetStep !== 'request'}>
                      {loading && resetStep === 'request' ? <span className={styles.spinner} /> : 'Send OTP'} <ArrowRight size={15} />
                    </button>
                  </form>
                  {resetStep !== 'request' && <div className={styles.resetStageState}><CheckCircle size={13} /> OTP requested</div>}
                </section>

                <section className={styles.resetStageCard + ' ' + (resetStep === 'verify' ? styles.resetStageActive : resetStep === 'password' ? styles.resetStageComplete : '')}>
                  <div className={styles.resetStageIllustration}><Smartphone size={27} /><span>OTP</span></div>
                  <div className={styles.resetStageBadge}>02 · VERIFY IDENTITY</div>
                  <h3>Enter the 6 digit OTP</h3>
                  <p>Enter the verification code sent to <strong className={styles.resetEmail}>{email || 'your email address'}</strong>.</p>
                  <form onSubmit={(event) => void handleReset(event, 'verify')} className={styles.resetStageForm}>
                    <label className={styles.label}>Verification Code</label>
                    <div className={styles.inputWrap}>
                      <CheckCircle size={16} className={styles.inputIcon} />
                      <input
                        type="text"
                        inputMode="numeric"
                        value={resetOtp}
                        onChange={(event) => setResetOtp(event.target.value.replace(/\D/g, '').slice(0, 6))}
                        placeholder="000000"
                        maxLength={6}
                        className={styles.input}
                        required
                        autoComplete="one-time-code"
                      />
                    </div>
                    <button type="button" className={styles.resetResend} onClick={() => void requestResetOtp().catch((err) => setError(err instanceof Error ? err.message : 'Unable to resend OTP.'))} disabled={resendCooldown > 0 || loading || resetStep !== 'verify'}>
                      {resendCooldown > 0 ? 'Resend in ' + resendCooldown + 's' : 'Resend OTP'}
                    </button>
                    <button className={styles.submitBtn} type="submit" disabled={loading || resetStep !== 'verify'}>
                      {loading && resetStep === 'verify' ? <span className={styles.spinner} /> : 'Verify OTP'} <ArrowRight size={15} />
                    </button>
                  </form>
                  {resetStep === 'password' && <div className={styles.resetStageState}><CheckCircle size={13} /> Email verified</div>}
                </section>

                <section className={styles.resetStageCard + ' ' + (resetStep === 'password' ? styles.resetStageActive : '')}>
                  <div className={styles.resetStageIllustration}><KeyRound size={27} /><span>SECURE</span></div>
                  <div className={styles.resetStageBadge}>03 · NEW PASSWORD</div>
                  <h3>Create new password</h3>
                  <p>Set a new password for your customer account.</p>
                  <form onSubmit={(event) => void handleReset(event, 'password')} className={styles.resetStageForm}>
                    <label className={styles.label}>New Password</label>
                    <div className={styles.inputWrap}>
                      <Lock size={16} className={styles.inputIcon} />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={resetPassword}
                        onChange={(event) => setResetPassword(event.target.value)}
                        placeholder="Enter new password"
                        className={styles.input}
                        required
                        minLength={8}
                        autoComplete="new-password"
                      />
                      <button type="button" className={styles.eyeBtn} onClick={() => setShowPassword((value) => !value)} aria-label="Toggle password visibility">
                        {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                    <label className={styles.label}>Confirm New Password</label>
                    <div className={styles.inputWrap}>
                      <Lock size={16} className={styles.inputIcon} />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={resetPasswordConfirm}
                        onChange={(event) => setResetPasswordConfirm(event.target.value)}
                        placeholder="Confirm new password"
                        className={styles.input}
                        required
                        minLength={8}
                        autoComplete="new-password"
                      />
                    </div>
                    <div className={styles.resetMiniStrength}><span style={{ width: Math.min(100, Math.round(resetPassword.length / 12 * 100)) + '%' }} /></div>
                    <button className={styles.submitBtn} type="submit" disabled={loading || resetStep !== 'password'}>
                      {loading && resetStep === 'password' ? <span className={styles.spinner} /> : 'Reset Password'} <ArrowRight size={15} />
                    </button>
                  </form>
                </section>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Footer switch */}
          <div className={styles.switchRow}>
            {view === 'reset' ? (
              <span>Remember your password? <button type="button" className={styles.switchAction} onClick={() => switchView('login')}>Back to Sign In</button></span>
            ) : view === 'login' ? (
              <span>
                New customer?{' '}
                <button type="button" className={styles.switchAction} onClick={() => switchView('register')}>
                  Create an Account
                </button>
              </span>
            ) : (
              <span>
                Already have an account?{' '}
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