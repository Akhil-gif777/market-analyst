// api.js — Centralized fetch layer for all backend calls

const API_BASE = '';

let _toastFn = null;

/**
 * Register a toast handler so API errors show visual feedback.
 * Called once from app.js after toast system is initialized.
 */
export function setToastHandler(fn) {
  _toastFn = fn;
}

/**
 * Make an API call. Returns parsed JSON on success.
 * Shows toast on error and re-throws.
 */
export async function api(method, path, body) {
  try {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);

    const resp = await fetch(API_BASE + path, opts);

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    return await resp.json();
  } catch (e) {
    if (_toastFn) _toastFn(e.message, 'error');
    throw e;
  }
}
