// Static export needs a known set of params to pre-render at build time.
// Rather than depend on the current list of real shop IDs (which would mean
// every new shop requires a full rebuild+redeploy), we pre-render a single
// placeholder shell. The page itself is a pure client component that reads
// the *actual* shopId from the live URL via useParams() at runtime — so any
// shop ID works against this one shell without ever rebuilding.
export async function generateStaticParams() {
  return [{ shopId: 'placeholder' }];
}
