// services/runtimeKeys.ts
export type Supplier = "google" | "openai";

type Store = Record<Supplier, string | null>;
const store: Store = { google: null, openai: null };

export function getRuntimeKey(supplier: Supplier): string | null {
  return store[supplier];
}

export function clearRuntimeKey(supplier: Supplier): void {
  store[supplier] = null;
}

export async function refreshRuntimeKey(supplier: Supplier): Promise<void> {
  try {
    const res = await fetch(`/api/credentials/${supplier}`, { method: "GET" });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      store[supplier] = null;
      return;
    }
    const k = String(data?.apiKey || "").trim();
    store[supplier] = k.length ? k : null;
  } catch {
    store[supplier] = null;
  }
}

export async function warmRuntimeKeys(): Promise<void> {
  await Promise.all([refreshRuntimeKey("google"), refreshRuntimeKey("openai")]);
}

/**
 * One-time cleanup: remove old browser keys so nobody can keep using them.
 * After we stop reading localStorage, this is just for safety + clarity.
 */
export function purgeLegacyLocalStorageKeys(): void {
  try {
    localStorage.removeItem("vision_api_key_override");
    localStorage.removeItem("vision_google_api_key_override");
    localStorage.removeItem("vision_openai_api_key_override");
  } catch {}
}
