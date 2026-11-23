// Central API configuration.
// Set NEXT_PUBLIC_API_URL in the deployment environment to override the fallback.
//
// Render's Environment UI expects a raw URL. Strip accidental wrapping quotes
// so values pasted as "https://..." do not produce a malformed fetch URL.
const configuredApiBase = (process.env.NEXT_PUBLIC_API_URL || '')
  .trim()
  .replace(/^["']|["']$/g, '');

export const API_BASE = (
  configuredApiBase || 'https://retail-mind-vkbp.onrender.com'
).replace(/\/+$/, '');

export interface ApiResponse {
  detail?: string;
  message?: string;
  access_token?: string;
  customer?: {
    name?: string;
    email?: string;
  };
  name?: string;
  email?: string;
  reset_token?: string;
}

/**
 * Read an API response safely.
 *
 * FastAPI errors are JSON, but a wrong Render URL or a missing route can return
 * an HTML page. Calling response.json() directly in that case throws the
 * confusing "Unexpected token '<'" error. This helper turns it into an
 * actionable message instead.
 */
export async function readApiResponse(response: Response): Promise<ApiResponse> {
  const body = await response.text();

  if (!body.trim()) {
    return {};
  }

  try {
    const parsed: unknown = JSON.parse(body);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as ApiResponse;
    }
    return {};
  } catch {
    const contentType = response.headers.get('content-type') || '';
    const looksLikeHtml =
      contentType.toLowerCase().includes('text/html') ||
      /^\s*<!doctype\s+html|^\s*<html\b/i.test(body);

    if (looksLikeHtml) {
      throw new Error(
        `The customer website received an HTML page instead of a JSON response (HTTP ${response.status}). Check NEXT_PUBLIC_API_URL in Render: it must be the URL of the FastAPI backend, not the customer website.`,
      );
    }

    throw new Error(
      `The backend returned an invalid response (HTTP ${response.status}). Please try again.`,
    );
  }
}
