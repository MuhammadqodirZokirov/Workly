import type { TokenPair } from "./types";

const BASE = "/api/v1";
const ACCESS = "workly.access";
const REFRESH = "workly.refresh";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

// localStorage ayrim WebView va maxfiy rejimlarda ishlamaydi — xotiraga qaytamiz
const memory = new Map<string, string>();
const store = {
  get(key: string): string | null {
    try {
      return localStorage.getItem(key) ?? memory.get(key) ?? null;
    } catch {
      return memory.get(key) ?? null;
    }
  },
  set(key: string, value: string) {
    memory.set(key, value);
    try {
      localStorage.setItem(key, value);
    } catch {
      /* xotirada qoladi */
    }
  },
  del(key: string) {
    memory.delete(key);
    try {
      localStorage.removeItem(key);
    } catch {
      /* */
    }
  },
};

export const tokens = {
  get access() {
    return store.get(ACCESS);
  },
  get refresh() {
    return store.get(REFRESH);
  },
  save(pair: Pick<TokenPair, "access_token" | "refresh_token">) {
    store.set(ACCESS, pair.access_token);
    store.set(REFRESH, pair.refresh_token);
  },
  clear() {
    store.del(ACCESS);
    store.del(REFRESH);
  },
};

export const prefs = { get: store.get, set: store.set };

// Bir vaqtda bir nechta 401 kelsa — refresh faqat bir marta: backend rotatsiyada
// eski tokenni qayta ishlatishni o'g'irlik deb biladi va barcha sessiyalarni yopadi.
let refreshing: Promise<boolean> | null = null;

export function refreshTokens(): Promise<boolean> {
  const refresh = tokens.refresh;
  if (!refresh) return Promise.resolve(false);
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) {
        tokens.clear();
        return false;
      }
      tokens.save(await res.json());
      return true;
    } catch {
      return false;
    }
  })().finally(() => {
    // Hal bo'lgach darhol tozalaymiz — eski natija keyingi 401 larda qayta ishlatilmasin
    refreshing = null;
  });
  return refreshing;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: FormData;
  headers?: Record<string, string>;
  auth?: boolean;
}

export async function api<T>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = { ...opts.headers };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.auth !== false && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;

  const res = await fetch(`${BASE}${path}`, {
    method: opts.method ?? (opts.body !== undefined || opts.form ? "POST" : "GET"),
    headers,
    body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
  });

  if (res.status === 401 && opts.auth !== false && !retried && tokens.refresh) {
    if (await refreshTokens()) return api<T>(path, opts, true);
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(res.status, data?.code ?? `HTTP_${res.status}`, data?.message ?? res.statusText, data?.details);
  }
  return data as T;
}

export const newIdempotencyKey = () =>
  (globalThis.crypto?.randomUUID?.() ?? `${Date.now()}${Math.random().toString(36).slice(2)}`)
    .replace(/-/g, "")
    .slice(0, 32);
