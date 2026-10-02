'use client';

import { useEffect, useState } from 'react';
import { ArrowRight, Gift, Heart, Package, RotateCcw, Sparkles, Star, Store, Trophy } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { API_BASE } from '../../lib/api';

type BuyAgain = { product_id:number; shop_id:number; product_name?:string; last_price:number; last_quantity:number; order_id:number };
type Recommendation = { product_id:number; product_name:string; price:number; stock_available:number; category?:string; shop_id:number; shop_name:string; rating:number; rating_count:number };
type Loyalty = { shop_id:number; points_balance:number; lifetime_earned:number; lifetime_redeemed:number; tier:string; rupee_value:number };
type ReturnRow = { id:number; order_id:number; reason:string; status:string; refund_amount:number };

export default function SmartShopPage() {
  const router = useRouter();
  const [buyAgain,setBuyAgain]=useState<BuyAgain[]>([]);
  const [recommendations,setRecommendations]=useState<Recommendation[]>([]);
  const [loyalty,setLoyalty]=useState<Loyalty|null>(null);
  const [returns,setReturns]=useState<ReturnRow[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');

  async function load(){
    const token=localStorage.getItem('customerToken');
    if(!token){ router.replace('/auth'); return; }
    try{
      setLoading(true); setError('');
      const headers={Authorization:'Bearer '+token};
      const [buyRes,recRes,returnRes]=await Promise.all([
        fetch(API_BASE+'/store/buy-again',{headers,cache:'no-store'}),
        fetch(API_BASE+'/store/recommendations',{headers,cache:'no-store'}),
        fetch(API_BASE+'/store/returns',{headers,cache:'no-store'}),
      ]);
      if([buyRes,recRes,returnRes].some((res)=>res.status===401||res.status===403)){
        localStorage.removeItem('customerToken'); router.replace('/auth'); return;
      }
      const [buy,rec,ret]=await Promise.all([buyRes.json(),recRes.json(),returnRes.json()]);
      setBuyAgain(Array.isArray(buy.items)?buy.items:[]);
      setRecommendations(Array.isArray(rec.recommendations)?rec.recommendations:[]);
      setReturns(Array.isArray(ret.returns)?ret.returns:[]);
      const shopId=Number((buy.items&&buy.items[0]?.shop_id)||(rec.recommendations&&rec.recommendations[0]?.shop_id)||0);
      if(shopId>0){
        const lr=await fetch(API_BASE+'/store/loyalty?shop_id='+shopId,{headers,cache:'no-store'});
        if(lr.ok) setLoyalty(await lr.json());
      }
    }catch(err){ setError(err instanceof Error?err.message:'Unable to load your smart shopping hub.'); }
    finally{ setLoading(false); }
  }

  useEffect(()=>{ void load(); },[]);

  return (
    <main className='smart-shop-page'>
      <div className='container smart-shop-shell'>
        <section className='smart-shop-hero'>
          <div><span className='smart-shop-eyebrow'><Sparkles size={14}/> RETAILSHOP SMART HUB</span>
          <h1>Shop faster. Get rewarded. Buy again.</h1>
          <p>Your purchases, recommendations, rewards and returns in one place.</p></div>
          <button onClick={()=>router.push('/ai-shopping')} className='smart-shop-ai'><Sparkles size={16}/> Ask AI</button>
        </section>
        {error&&<div className='smart-shop-error'>{error}</div>}
        <section className='smart-shop-grid'>
          <article className='smart-panel loyalty'><div className='smart-panel-icon'><Trophy size={20}/></div><div className='smart-panel-content'><span>LOYALTY WALLET</span><h2>{loyalty?loyalty.points_balance:0} points</h2><p>{loyalty?loyalty.tier+' tier · ₹'+loyalty.rupee_value.toFixed(2)+' value':'Earn points automatically from eligible delivered orders.'}</p></div><Gift size={22}/></article>
          <article className='smart-panel'><div className='smart-panel-icon green'><Heart size={20}/></div><div className='smart-panel-content'><span>PERSONALIZED PICKS</span><h2>{recommendations.length} suggestions</h2><p>Based on products you have already purchased.</p></div></article>
        </section>
        <section className='smart-section'>
          <div className='smart-section-heading'><div><span>BUY AGAIN</span><h2>Your recent essentials</h2></div><Package size={21}/></div>
          {loading?<div className='smart-loading'>Loading your shopping history…</div>:buyAgain.length===0?<div className='smart-empty'>Your completed purchases will appear here for one-tap reordering.</div>:<div className='smart-cards'>{buyAgain.slice(0,6).map(item=><button key={item.product_id+'-'+item.shop_id} className='smart-product-card' onClick={()=>router.push('/shop/'+item.shop_id+'/product/'+item.product_id)}><div className='smart-product-icon'><Package size={19}/></div><strong>{item.product_name||('Product #'+item.product_id)}</strong><span>Last ₹{Number(item.last_price).toFixed(2)} · Qty {item.last_quantity}</span><b>Buy again <ArrowRight size={14}/></b></button>)}</div>}
        </section>
        <section className='smart-section'>
          <div className='smart-section-heading'><div><span>RECOMMENDED FOR YOU</span><h2>Products from live shops</h2></div><Star size={21}/></div>
          {recommendations.length===0?<div className='smart-empty'>Recommendations will appear after you have a few purchases.</div>:<div className='smart-cards'>{recommendations.slice(0,6).map(item=><button key={item.product_id+'-'+item.shop_id} className='smart-product-card' onClick={()=>router.push('/shop/'+item.shop_id+'/product/'+item.product_id)}><div className='smart-product-icon'><Store size={19}/></div><strong>{item.product_name}</strong><span>{item.shop_name} · ₹{item.price.toFixed(2)}</span><b><Star size={12} fill='currentColor'/> {item.rating>0?item.rating.toFixed(1):'New'}</b></button>)}</div>}
        </section>
        <section className='smart-section'>
          <div className='smart-section-heading'><div><span>RETURNS & REFUNDS</span><h2>Your return requests</h2></div><RotateCcw size={21}/></div>
          {returns.length===0?<div className='smart-empty'>No return requests yet. Returns are available from delivered orders.</div>:<div className='smart-returns'>{returns.map(row=><div key={row.id} className='smart-return-row'><div><strong>Order #{row.order_id}</strong><span>{row.reason}</span></div><div className='smart-return-status'><b>{row.status.replaceAll('_',' ')}</b><span>₹{Number(row.refund_amount).toFixed(2)}</span></div></div>)}</div>}
        </section>
      </div>
    </main>
  );
}