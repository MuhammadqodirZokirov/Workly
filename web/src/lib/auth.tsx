import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, prefs, tokens } from "./api";
import { I18nContext, translate } from "./i18n";
import { inTelegram, tg } from "./telegram";
import type { Lang, Me, Role, TokenPair } from "./types";

type AppRole = Extract<Role, "worker" | "employer">;

interface AuthState {
  me: Me | null;
  loading: boolean;
  telegramLogin: boolean;
  role: AppRole | null;
  setRole(role: AppRole): void;
  signIn(pair: TokenPair): void;
  signOut(): Promise<void>;
  refreshMe(): Promise<unknown>;
}

const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("AuthProvider yo'q");
  return ctx;
}

function initialLang(): Lang {
  const saved = prefs.get("workly.lang") as Lang | null;
  if (saved) return saved;
  const code = tg()?.initDataUnsafe.user?.language_code ?? navigator.language;
  return code?.startsWith("ru") ? "ru" : "uz_latn";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [hasToken, setHasToken] = useState(Boolean(tokens.access));
  const [telegramLogin, setTelegramLogin] = useState(!tokens.access && inTelegram());
  const [lang, setLangState] = useState<Lang>(initialLang);
  const [roleState, setRoleState] = useState<AppRole | null>(() => prefs.get("workly.role") as AppRole | null);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: () => api<Me>("/me"),
    enabled: hasToken,
    retry: false,
    staleTime: 60_000,
  });

  // Telegram Mini App ichida — initData bilan avtomatik kirish (TZ 3)
  useEffect(() => {
    if (!telegramLogin) return;
    api<TokenPair>("/auth/telegram", { body: { init_data: tg()!.initData }, auth: false })
      .then((pair) => {
        tokens.save(pair);
        qc.setQueryData(["me"], pair.user);
        setHasToken(true);
      })
      .catch(() => undefined)
      .finally(() => setTelegramLogin(false));
  }, [telegramLogin, qc]);

  // Token yaroqsiz bo'lib qolsa — chiqamiz
  useEffect(() => {
    if (meQuery.isError) {
      tokens.clear();
      setHasToken(false);
    }
  }, [meQuery.isError]);

  const me = hasToken ? (meQuery.data ?? null) : null;

  useEffect(() => {
    if (me?.lang && !prefs.get("workly.lang")) setLangState(me.lang);
  }, [me?.lang]);

  // <html lang> — to'g'ri bo'g'in ko'chirish (hyphens) va ekran o'quvchilar uchun
  useEffect(() => {
    document.documentElement.lang = { uz_latn: "uz", uz_cyrl: "uz-Cyrl", ru: "ru" }[lang];
  }, [lang]);

  const appRoles = (me?.roles ?? []).filter((r): r is AppRole => r === "worker" || r === "employer");
  const role: AppRole | null = roleState && appRoles.includes(roleState) ? roleState : (appRoles[0] ?? null);

  const setRole = useCallback((r: AppRole) => {
    prefs.set("workly.role", r);
    setRoleState(r);
  }, []);

  const signIn = useCallback(
    (pair: TokenPair) => {
      tokens.save(pair);
      qc.setQueryData(["me"], pair.user);
      setHasToken(true);
    },
    [qc],
  );

  const signOut = useCallback(async () => {
    const refresh = tokens.refresh;
    if (refresh) await api("/auth/logout", { body: { refresh_token: refresh }, auth: false }).catch(() => undefined);
    tokens.clear();
    qc.clear();
    setHasToken(false);
  }, [qc]);

  const setLang = useCallback(
    (l: Lang) => {
      prefs.set("workly.lang", l);
      setLangState(l);
      if (tokens.access) {
        api<Me>("/me", { method: "PATCH", body: { lang: l } })
          .then((user) => qc.setQueryData(["me"], user))
          .catch(() => undefined);
      }
    },
    [qc],
  );

  const i18n = useMemo(() => ({ lang, setLang, t: translate.bind(null, lang) }), [lang, setLang]);
  const state: AuthState = {
    me,
    loading: telegramLogin || (hasToken && meQuery.isLoading),
    telegramLogin,
    role,
    setRole,
    signIn,
    signOut,
    refreshMe: () => meQuery.refetch(),
  };

  return (
    <I18nContext.Provider value={i18n}>
      <AuthContext.Provider value={state}>{children}</AuthContext.Provider>
    </I18nContext.Provider>
  );
}
