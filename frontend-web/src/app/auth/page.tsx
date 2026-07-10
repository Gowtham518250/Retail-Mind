'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function AuthPage() {
  const [view, setView] = useState<'login' | 'register' | 'reset'>('login');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('/store/customer/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // send phone field — backend now supports phone OR email login
        body: JSON.stringify({ phone, password })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Login failed. Please check your credentials.');
      }
      
      localStorage.setItem('customerToken', data.access_token);
      const customerName = data.customer?.name || data.name || phone;
      localStorage.setItem('customerName', customerName);
      
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
    
    const shop_id = 1;

    try {
      const response = await fetch('/store/customer/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // email is omitted — backend now handles phone-only registration
        body: JSON.stringify({ 
          name, 
          phone, 
          password, 
          shop_id,
          firebase_id_token: null 
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Registration failed. Please try again.');
      }
      
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
        // send phone for reset — backend now supports phone OR email
        body: JSON.stringify({ phone })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Reset failed. Please try again.');
      }
      
      alert('Password reset instructions sent!');
      setView('login');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1>Retail<span className="brand-accent">Shop</span></h1>
          <p>
            {view === 'login' && 'Login to access your orders and wishlist'}
            {view === 'register' && 'Looks like you are new here! Sign up.'}
            {view === 'reset' && 'Reset your account password'}
          </p>
        </div>

        <div className="auth-body">
          {error && <div className="auth-error">{error}</div>}

          {/* LOGIN VIEW */}
          {view === 'login' && (
            <div className="slide-panel">
              <form onSubmit={handleLogin}>
                <div className="auth-form-group">
                  <label>Mobile Number</label>
                  <input 
                    type="tel" 
                    className="input-field" 
                    placeholder="Enter Mobile Number" 
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    required
                    pattern="[0-9]{10}"
                    title="Please enter a valid 10 digit mobile number"
                  />
                </div>
                <div className="auth-form-group">
                  <label>Password</label>
                  <input 
                    type="password" 
                    className="input-field" 
                    placeholder="Enter Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required 
                  />
                </div>
                <div style={{ textAlign: 'right', marginBottom: '24px' }}>
                  <span className="auth-link" onClick={() => setView('reset')}>Forgot Password?</span>
                </div>
                <button type="submit" className="btn-primary" style={{ width: '100%' }} disabled={loading}>
                  {loading ? 'Logging in...' : 'Login'}
                </button>
              </form>
              <div className="auth-link-container" style={{ textAlign: 'center', marginTop: '24px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>New to RetailShop? </span>
                <span className="auth-link" onClick={() => setView('register')}>Create an account</span>
              </div>
            </div>
          )}

          {/* REGISTER VIEW */}
          {view === 'register' && (
            <div className="slide-panel">
              <form onSubmit={handleRegister}>
                <div className="auth-form-group">
                  <label>Full Name</label>
                  <input 
                    type="text" 
                    className="input-field" 
                    placeholder="Enter Your Name" 
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />
                </div>
                <div className="auth-form-group">
                  <label>Mobile Number</label>
                  <input 
                    type="tel" 
                    className="input-field" 
                    placeholder="Enter Mobile Number" 
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    required
                    pattern="[0-9]{10}"
                  />
                </div>
                <div className="auth-form-group">
                  <label>Password</label>
                  <input 
                    type="password" 
                    className="input-field" 
                    placeholder="Create Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required 
                  />
                </div>
                <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '8px' }} disabled={loading}>
                  {loading ? 'Creating...' : 'Continue'}
                </button>
              </form>
              <div className="auth-link-container" style={{ textAlign: 'center', marginTop: '24px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Existing User? </span>
                <span className="auth-link" onClick={() => setView('login')}>Log in</span>
              </div>
            </div>
          )}

          {/* RESET PASSWORD VIEW */}
          {view === 'reset' && (
            <div className="slide-panel">
              <form onSubmit={handleReset}>
                <div className="auth-form-group">
                  <label>Mobile Number</label>
                  <input 
                    type="tel" 
                    className="input-field" 
                    placeholder="Enter Registered Mobile Number" 
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    required
                    pattern="[0-9]{10}"
                  />
                </div>
                <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '16px' }} disabled={loading}>
                  {loading ? 'Processing...' : 'Reset Password'}
                </button>
              </form>
              <div className="auth-link-container" style={{ textAlign: 'center', marginTop: '24px' }}>
                <span className="auth-link" onClick={() => setView('login')}>Back to Login</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
