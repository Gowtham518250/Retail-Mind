// Central API configuration for the customer web application.
// Set NEXT_PUBLIC_API_URL explicitly for each deployment environment.
// Never silently route a staging build to the production backend.
const rawApiBase = process.env.NEXT_PUBLIC_API_URL?.trim();

if (!rawApiBase) {
  throw new Error(
    'NEXT_PUBLIC_API_URL is required. Configure the staging or production API URL before building the customer web application.',
  );
}

let parsedApiBase: URL;
try {
  parsedApiBase = new URL(rawApiBase);
} catch {
  throw new Error('NEXT_PUBLIC_API_URL must be an absolute HTTP(S) URL.');
}

const isLocalHost =
  parsedApiBase.hostname === 'localhost' ||
  parsedApiBase.hostname === '127.0.0.1' ||
  parsedApiBase.hostname === '::1';

if (
  !['https:', 'http:'].includes(parsedApiBase.protocol) ||
  parsedApiBase.username ||
  parsedApiBase.password ||
  parsedApiBase.search ||
  parsedApiBase.hash ||
  !['', '/'].includes(parsedApiBase.pathname) ||
  (parsedApiBase.protocol === 'http:' && !isLocalHost)
) {
  throw new Error(
    'NEXT_PUBLIC_API_URL must be a root HTTPS URL (HTTP is permitted only for local development).',
  );
}

export const API_BASE = parsedApiBase.origin;
