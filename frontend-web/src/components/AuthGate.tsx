'use client';

import { useState } from 'react';

export default function AuthGate() {
  const [isLogin, setIsLogin] = useState(true);
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const endpoint = isLogin ? '/store/customer/login' : '/store/customer/register';
    
    // In a real app, this would hit the actual endpoint
    console.log(`Submitting to ${endpoint}`, { phone, password });
    alert(`Simulating ${isLogin ? 'login' : 'register'} for ${phone}`);
  };

  return (
    <div className="auth-gate-overlay">
      <div className="auth-card pop-in">
        <h2>{isLogin ? 'Login' : 'Register'}</h2>
        <p>Get access to your Orders, Wishlist and Recommendations</p>
        
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '24px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Phone Number</label>
            <input 
              type="tel" 
              className="input-field" 
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="Enter mobile number"
              required 
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Password</label>
            <input 
              type="password" 
              className="input-field" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              required 
            />
          </div>
          
          <button type="submit" className="btn-primary" style={{ marginTop: '8px' }}>
            {isLogin ? 'Login' : 'Continue'}
          </button>
        </form>
        
        <div style={{ marginTop: '24px', textAlign: 'center', fontSize: '14px' }}>
          <span style={{ color: 'var(--text-secondary)' }}>
            {isLogin ? 'New to RetailShop? ' : 'Existing User? '}
          </span>
          <button 
            className="link-btn" 
            onClick={() => setIsLogin(!isLogin)}
            style={{ color: 'var(--fk-blue)', fontWeight: 600 }}
          >
            {isLogin ? 'Create an account' : 'Log in'}
          </button>
        </div>
      </div>
    </div>
  );
}
