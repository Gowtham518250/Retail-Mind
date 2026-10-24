import { Suspense } from 'react';
import OrderSuccessClientPage from './OrderSuccessClientPage';

export { generateStaticParams } from './generateStaticParams';

export default function OrderSuccessPage() {
  return (
    <Suspense fallback={<div className="page-loading" role="status" aria-live="polite">Loading your order confirmation…</div>}>
      <OrderSuccessClientPage />
    </Suspense>
  );
}
