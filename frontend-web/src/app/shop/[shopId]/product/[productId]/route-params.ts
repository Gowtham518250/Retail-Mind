// See generateStaticParams.ts files for rationale: one placeholder shell,
// real ids are read client-side from the live URL at runtime.
export async function getProductRouteParams() {
  return [{ shopId: 'placeholder', productId: 'placeholder' }];
}
