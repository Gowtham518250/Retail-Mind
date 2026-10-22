export function flyProductToCart(source: HTMLElement, imageUrl?: string): Promise<void> {
  const cartTarget = document.getElementById('navbar-cart-btn');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!cartTarget || reducedMotion) return Promise.resolve();

  const sourceRect = source.getBoundingClientRect();
  const targetRect = cartTarget.getBoundingClientRect();
  const startX = sourceRect.left + sourceRect.width / 2 - 27;
  const startY = sourceRect.top + sourceRect.height / 2 - 27;
  const deltaX = targetRect.left + targetRect.width / 2 - (startX + 34);
  const deltaY = targetRect.top + targetRect.height / 2 - (startY + 34);

  const flyer = document.createElement('div');
  flyer.setAttribute('aria-hidden', 'true');
  Object.assign(flyer.style, {
    position: 'fixed',
    zIndex: '10000',
    top: `${startY}px`,
    left: `${startX}px`,
    width: '54px',
    height: '54px',
    overflow: 'hidden',
    border: '1px solid rgba(255, 253, 247, .96)',
    borderRadius: '14px',
    background: '#d8ed91',
    boxShadow: '0 7px 18px rgba(16, 45, 33, .18)',
    pointerEvents: 'none',
    willChange: 'transform, opacity',
  });

  if (imageUrl) {
    const image = document.createElement('img');
    image.src = imageUrl;
    image.alt = '';
    Object.assign(image.style, {
      width: '100%',
      height: '100%',
      objectFit: 'cover',
    });
    flyer.appendChild(image);
  } else {
    flyer.textContent = 'RM';
    Object.assign(flyer.style, {
      display: 'grid',
      placeItems: 'center',
      color: '#173e2d',
      font: '900 1.1rem/1 sans-serif',
    });
  }

  document.body.appendChild(flyer);
  if (typeof flyer.animate !== 'function') {
    flyer.remove();
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    const animation = flyer.animate(
      [
        { transform: 'translate3d(0, 0, 0) scale(1)', opacity: 1, offset: 0 },
        {
          transform: `translate3d(${deltaX * 0.7}px, ${deltaY * 0.7}px, 0) scale(.62)`,
          opacity: .92,
          offset: 0.7,
        },
        {
          transform: `translate3d(${deltaX}px, ${deltaY}px, 0) scale(.22)`,
          opacity: 0,
          offset: 1,
        },
      ],
      { duration: 340, easing: 'cubic-bezier(.22,.72,.24,1)', fill: 'forwards' },
    );
    animation.onfinish = () => {
      flyer.remove();
      resolve();
    };
    animation.oncancel = () => {
      flyer.remove();
      resolve();
    };
  });
}
