import { API_BASE } from './api';

/** Turns whatever the shopkeeper's upload returned (absolute or backend-relative) into a usable URL. */
export function resolveImageUrl(url?: string | null): string {
  const value = (url || '').trim();
  if (!value) return '';
  if (/^(https?:)?\/\//.test(value) || value.startsWith('data:') || value.startsWith('blob:')) return value;
  return API_BASE + (value.startsWith('/') ? value : '/' + value);
}

const DAY = 86400000;
const memory = new Map<string, Promise<string | null>>();
let running = 0;
const waiting: Array<() => void> = [];

async function slot<T>(job: () => Promise<T>): Promise<T> {
  if (running >= 4) await new Promise<void>((resolve) => waiting.push(resolve));
  running += 1;
  try { return await job(); } finally { running -= 1; waiting.shift()?.(); }
}

const keyFor = (name: string, category?: string) => (name.trim().toLowerCase() + '|' + (category || '').trim().toLowerCase());

/** Looks up a real photo online (via /api/product-image). Cached in memory and in localStorage. */
export function lookupProductImage(name: string, category?: string): Promise<string | null> {
  const key = keyFor(name, category);
  const existing = memory.get(key);
  if (existing) return existing;

  const storageKey = 'rm-img:' + key;
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (raw) {
      const saved = JSON.parse(raw) as { url: string | null; t: number };
      if (Date.now() - saved.t < (saved.url ? 14 * DAY : DAY)) {
        const done = Promise.resolve(saved.url);
        memory.set(key, done);
        return done;
      }
    }
  } catch { /* storage unavailable */ }

  const task = slot(async () => {
    try {
      const params = new URLSearchParams({ q: name });
      if (category) params.set('category', category);
      const response = await fetch('/api/product-image?' + params, { cache: 'force-cache' });
      if (!response.ok) return null;
      const data = await response.json() as { url?: string | null };
      const url = data.url || null;
      try { window.localStorage.setItem(storageKey, JSON.stringify({ url, t: Date.now() })); } catch { /* ignore */ }
      return url;
    } catch {
      return null;
    }
  });
  memory.set(key, task);
  return task;
}
