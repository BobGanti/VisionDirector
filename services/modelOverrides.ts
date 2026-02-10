// services/modelOverrides.ts
// NOTE: No localStorage persistence. Overrides are loaded/saved via backend SQLite endpoints.

export type Supplier = "google" | "openai";
export type ModelOverrides = Record<string, string>;

export type OverridesResponse = {
  supplier: Supplier;
  keys: string[];
  defaults: Record<string, string>;
  overrides: ModelOverrides; // backend may return only non-empty overrides
};

// In-memory cache only (non-persistent)
const cache: Record<Supplier, ModelOverrides> = {
  google: {},
  openai: {},
};

const defaultsCache: Record<Supplier, Record<string, string>> = {
  google: {},
  openai: {},
};

const keysCache: Record<Supplier, string[]> = {
  google: [],
  openai: [],
};

const loaded: Record<Supplier, boolean> = {
  google: false,
  openai: false,
};


function asText(e: any): string {
  return e?.message || String(e || "UNKNOWN_ERROR");
}

async function httpJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const contentType = res.headers.get("content-type") || "";
  const bodyText = await res.text();

  if (!res.ok) {
    // Try to surface server error messages without leaking secrets
    let msg = bodyText || `${res.status} ${res.statusText}`;
    try {
      const j = JSON.parse(bodyText);
      msg = j?.error || j?.message || msg;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }

  if (!bodyText) return {} as T;

  if (contentType.includes("application/json")) {
    return JSON.parse(bodyText) as T;
  }

  // If server returns non-json unexpectedly
  throw new Error("EXPECTED_JSON_RESPONSE");
}

export async function fetchModelOverrides(supplier: Supplier): Promise<OverridesResponse> {
  const resp = await httpJson<OverridesResponse>(`/api/model-overrides/${supplier}`, {
    method: "GET",
  });

  cache[supplier] = resp?.overrides || {};

  defaultsCache[supplier] = resp.defaults || {};
  keysCache[supplier] = resp.keys || [];
  loaded[supplier] = true;

  return resp;
}

/**
 * Save overrides to backend. Pass empty string to clear an override for a key.
 * Example: { VIDEO_GEN: "sora-2", IMAGE_GEN: "" }
 */
export async function saveModelOverrides(
  supplier: Supplier,
  overrides: Record<string, string>
): Promise<OverridesResponse> {
  const resp = await httpJson<OverridesResponse>(`/api/model-overrides/${supplier}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ overrides: overrides || {} }),
  });

  cache[supplier] = resp?.overrides || {};
  return resp;
}

export async function resetModelOverrides(supplier: Supplier): Promise<OverridesResponse> {
  const resp = await httpJson<OverridesResponse>(`/api/model-overrides/${supplier}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });

  cache[supplier] = resp?.overrides || {};
  return resp;
}

/**
 * Synchronous getter used by services (Gemini/OpenAI).
 * If overrides have not been fetched yet, this returns null and services fall back to defaults.
 */
export function getModelOverride(supplier: Supplier, key: string): string | null {
  const v = cache?.[supplier]?.[key];
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

// Optional helper to pre-load both suppliers early in app start-up.
export async function initModelOverrides(): Promise<void> {
  try {
    await Promise.all([fetchModelOverrides("google"), fetchModelOverrides("openai")]);
  } catch (e) {
    // Do not hard-fail boot if backend is not ready; UI can show errors later.
    console.warn("initModelOverrides failed:", asText(e));
  }
}

// Backwards-compatible helpers (non-persistent)
export function readModelOverrides(supplier: Supplier): ModelOverrides {
  return { ...(cache[supplier] || {}) };
}

export function writeModelOverrides(supplier: Supplier, overrides: ModelOverrides) {
  cache[supplier] = { ...(overrides || {}) };
}

export function clearModelOverrides(supplier: Supplier) {
  cache[supplier] = {};
}


export async function ensureModelRegistryLoaded(supplier: Supplier): Promise<void> {
  if (loaded[supplier]) return;
  await fetchModelOverrides(supplier);
}

export function getDefaultModel(supplier: Supplier, key: string): string | null {
  const v = defaultsCache?.[supplier]?.[key];
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

export function getEffectiveModel(supplier: Supplier, key: string): string | null {
  return getModelOverride(supplier, key) || getDefaultModel(supplier, key);
}
