export default function Loading() {
  return (
    <div className="route-loading" role="status" aria-live="polite">
      <span className="route-loading-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <strong>Getting things ready</strong>
      <span className="route-loading-copy">Your local shopping experience is on its way.</span>
      <span className="route-loading-track" aria-hidden="true"><i /></span>
    </div>
  );
}
