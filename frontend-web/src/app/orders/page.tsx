'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Package, MapPin, Clock, CheckCircle, Truck, ArrowLeft } from 'lucide-react';
import { API_BASE } from '../../lib/api';

interface OrderItem {
  product_id: number;
  quantity: number;
}

interface Order {
  order_id: number;
  shop_id: number;
  status: string;
  total_amount: number;
  delivery_address: string;
  items: OrderItem[];
  created_at: string;
}

export default function MyOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.push('/auth');
      return;
    }

    const fetchOrders = async () => {
      try {
        const response = await fetch(`${API_BASE}/store/my-orders`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            localStorage.removeItem('customerToken');
            router.push('/auth');
            return;
          }
          throw new Error('Failed to load orders');
        }

        const data = await response.json();
        setOrders(data.orders || []);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchOrders();
  }, [router]);

  const statusConfig: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
    PENDING:   { color: '#facc15', bg: 'rgba(250,204,21,0.12)', icon: <Clock size={14} /> },
    CONFIRMED: { color: '#22d3ee', bg: 'rgba(34,211,238,0.12)', icon: <CheckCircle size={14} /> },
    SHIPPED:   { color: '#818cf8', bg: 'rgba(129,140,248,0.12)', icon: <Truck size={14} /> },
    DELIVERED: { color: '#10b981', bg: 'rgba(16,185,129,0.12)', icon: <CheckCircle size={14} /> },
    CANCELLED: { color: '#f87171', bg: 'rgba(248,113,113,0.12)', icon: <Package size={14} /> },
  };

  return (
    <div className="container" style={{ padding: '40px 20px' }}>
      <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:32 }}>
        <button onClick={() => router.back()} style={{ background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.1)', borderRadius:10, padding:'8px 12px', color:'#fff', cursor:'pointer', display:'flex', alignItems:'center', gap:6 }}>
          <ArrowLeft size={16} /> Back
        </button>
        <h1 style={{ fontSize:'1.75rem', fontWeight:700 }}>My Orders</h1>
      </div>

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {[1, 2, 3].map(i => (
            <div key={i} style={{ height: '120px', background: 'rgba(255,255,255,0.05)', borderRadius: '16px', animation: 'pulse 1.5s infinite' }} />
          ))}
        </div>
      ) : error ? (
        <div style={{ padding: '20px', background: 'rgba(255,0,0,0.1)', color: '#ff4444', borderRadius: '12px' }}>
          {error}
        </div>
      ) : orders.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', background: 'rgba(255,255,255,0.02)', borderRadius: '24px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px', opacity: 0.5 }}>📦</div>
          <h2 style={{ marginBottom: '8px' }}>No orders yet</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>Looks like you haven't placed any orders.</p>
          <button className="btn-primary" onClick={() => router.push('/')}>Start Shopping</button>
        </div>
      ) : (
        <div style={{ display:'flex', flexDirection:'column', gap:20 }}>
          {orders.map(order => {
            const sc = statusConfig[order.status] || statusConfig['PENDING'];
            return (
              <div key={order.order_id} style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
                borderRadius: 20,
                padding: 24,
                boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
                transition: 'border-color 0.2s',
              }}>
                {/* Order header */}
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', borderBottom:'1px solid rgba(255,255,255,0.08)', paddingBottom:16, marginBottom:16 }}>
                  <div>
                    <div style={{ fontWeight:700, fontSize:16 }}>Order #{order.order_id}</div>
                    <div style={{ fontSize:13, color:'var(--text-secondary)', marginTop:4 }}>
                      <Clock size={12} style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
                      {new Date(order.created_at).toLocaleString()}
                    </div>
                  </div>
                  <span style={{ display:'flex', alignItems:'center', gap:6, background:sc.bg, color:sc.color, padding:'5px 12px', borderRadius:20, fontSize:12, fontWeight:700, letterSpacing:'0.5px' }}>
                    {sc.icon} {order.status}
                  </span>
                </div>

                {/* Items */}
                <div style={{ display:'flex', flexDirection:'column', gap:8, marginBottom:16 }}>
                  {order.items.map((item, idx) => (
                    <div key={idx} style={{ display:'flex', justifyContent:'space-between', fontSize:14, color:'var(--text-secondary)' }}>
                      <span><Package size={13} style={{ display:'inline', verticalAlign:'middle', marginRight:6 }} />Product #{item.product_id}</span>
                      <span style={{ color:'#fff', fontWeight:600 }}>× {item.quantity}</span>
                    </div>
                  ))}
                </div>

                {/* Footer */}
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-end', borderTop:'1px solid rgba(255,255,255,0.08)', paddingTop:16 }}>
                  <div style={{ flex:1, marginRight:16 }}>
                    <div style={{ fontSize:11, color:'var(--text-secondary)', marginBottom:4, textTransform:'uppercase', letterSpacing:'0.5px' }}>Delivery Address</div>
                    <div style={{ fontSize:13, display:'flex', alignItems:'flex-start', gap:6 }}>
                      <MapPin size={14} style={{ color:'var(--fk-blue)', flexShrink:0, marginTop:1 }} />
                      <span style={{ display:'-webkit-box', WebkitLineClamp:2, WebkitBoxOrient:'vertical' as const, overflow:'hidden' }}>{order.delivery_address}</span>
                    </div>
                  </div>
                  <div style={{ textAlign:'right' }}>
                    <div style={{ fontSize:11, color:'var(--text-secondary)', marginBottom:4, textTransform:'uppercase', letterSpacing:'0.5px' }}>Total</div>
                    <div style={{ fontSize:22, fontWeight:800, color:'var(--fk-blue)' }}>₹{order.total_amount.toFixed(2)}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
      <style>{`
        @keyframes pulse {
          0% { opacity: 1; }
          50% { opacity: 0.5; }
          100% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
