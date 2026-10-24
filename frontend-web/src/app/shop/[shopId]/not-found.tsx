import type { Metadata } from 'next';
import NotFoundContent from '../../../components/NotFoundContent';

export const metadata: Metadata = {
  title: 'Page not found',
};

export default function ShopNotFound() {
  return <NotFoundContent />;
}