import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [invoices, setInvoices] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch data from the FastAPI backend
    const fetchData = async () => {
      try {
        // In a real app, you would pass the authorization token here
        const [invoicesRes, analyticsRes] = await Promise.all([
          fetch('/api/invoices/'),
          fetch('/api/invoices/analytics/summary')
        ]);

        if (invoicesRes.ok) {
          const data = await invoicesRes.json();
          setInvoices(data.slice(0, 10)); // Show top 10 recent
        }
        
        if (analyticsRes.ok) {
          const data = await analyticsRes.json();
          setAnalytics(data);
        }
      } catch (error) {
        console.error("Error fetching data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return <div className="loading">Initializing Retail Mind...</div>;
  }

  return (
    <div className="dashboard-container">
      <header className="animate-fade-in delay-1">
        <div className="logo-area">
          <h1>Retail Mind AI</h1>
          <p>Advanced Dashboard Hub</p>
        </div>
      </header>

      <main>
        {analytics && (
          <div className="kpi-grid animate-fade-in delay-2">
            <div className="glass-card">
              <h3 className="kpi-title">Total Revenue</h3>
              <div className="kpi-value">
                ₹{analytics.total_amount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
              </div>
            </div>
            
            <div className="glass-card">
              <h3 className="kpi-title">Collected Amount</h3>
              <div className="kpi-value" style={{ color: 'var(--success)' }}>
                ₹{analytics.total_paid.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
              </div>
            </div>
            
            <div className="glass-card">
              <h3 className="kpi-title">Total Invoices</h3>
              <div className="kpi-value">{analytics.total_invoices}</div>
            </div>
            
            <div className="glass-card">
              <h3 className="kpi-title">Collection Rate</h3>
              <div className="kpi-value">{analytics.collection_rate}%</div>
            </div>
          </div>
        )}

        <div className="data-table-container animate-fade-in delay-3">
          <h2>Recent Sales & Invoices</h2>
          {invoices.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Invoice No.</th>
                  <th>Date</th>
                  <th>Customer</th>
                  <th>Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.invoice_number}</td>
                    <td>{inv.invoice_date}</td>
                    <td>
                      {inv.customer_name || inv.customer_phone || 'Walk-in Customer'}
                    </td>
                    <td>₹{inv.total_amount.toFixed(2)}</td>
                    <td>
                      <span className={`status-badge status-${inv.payment_status?.toLowerCase() || 'unpaid'}`}>
                        {inv.payment_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ color: 'var(--text-secondary)' }}>No recent invoices found.</p>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
