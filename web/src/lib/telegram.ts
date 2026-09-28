// Telegram Mini App: https://core.telegram.org/bots/webapps
interface TgWebApp {
  initData: string;
  initDataUnsafe: { user?: { language_code?: string } };
  colorScheme: "light" | "dark";
  ready(): void;
  expand(): void;
  HapticFeedback?: { notificationOccurred(type: "success" | "error" | "warning"): void };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TgWebApp };
  }
}

export const tg = (): TgWebApp | undefined => window.Telegram?.WebApp;

/** Telegram ichida ochilganmi (brauzerda initData bo'sh bo'ladi) */
export const inTelegram = (): boolean => Boolean(tg()?.initData);

export function initTelegram(): void {
  const app = tg();
  if (!app?.initData) return;
  app.ready();
  app.expand();
}

export const haptic = (type: "success" | "error" | "warning") => tg()?.HapticFeedback?.notificationOccurred(type);

/** Bot manzili (VITE_BOT_URL, masalan https://t.me/<bot>) — telefon Telegram'da bot orqali tasdiqlanadi */
export const BOT_URL: string | null = import.meta.env.VITE_BOT_URL || null;
