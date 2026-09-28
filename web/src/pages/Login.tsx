import { Phone } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";

import { useErrorText } from "../components/shared";
import { Button, ErrorBox, Field, Input, Page, TopBar } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { phonePretty } from "../lib/format";
import { useI18n } from "../lib/i18n";
import type { TokenPair } from "../lib/types";

/** Brauzer / PWA: telefon + SMS kod (TZ 3). Parol yo'q — dizayndan farqli (docs/design/DESIGN.md). */
export default function Login() {
  const { t } = useI18n();
  const { signIn } = useAuth();
  const errorText = useErrorText();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  const fullPhone = `+998${phone.replace(/\D/g, "").slice(-9)}`;

  const send = useMutation({
    mutationFn: () => api<{ expires_in: number }>("/auth/otp/send", { body: { phone: fullPhone }, auth: false }),
    onSuccess: () => {
      setSentTo(fullPhone);
      setCooldown(60);
      setCode("");
    },
  });
  const verify = useMutation({
    mutationFn: () => api<TokenPair>("/auth/otp/verify", { body: { phone: sentTo, code }, auth: false }),
    onSuccess: signIn,
  });

  const submitPhone = (e: FormEvent) => {
    e.preventDefault();
    send.mutate();
  };
  const submitCode = (e: FormEvent) => {
    e.preventDefault();
    verify.mutate();
  };

  return (
    <>
      <TopBar title={t("auth.title")} back />
      <Page>
        <img src="/brand/logo_320.webp" alt="Workly" className="mx-auto mt-4 w-40" />
        {!sentTo ? (
          <form onSubmit={submitPhone} className="mt-8 space-y-4">
            <p className="text-center text-muted">{t("auth.subtitle")}</p>
            <Field label={t("auth.phone")}>
              <div className="flex items-center gap-2 rounded-xl border border-mist bg-white px-4 focus-within:border-brand">
                <span className="flex items-center gap-1.5 text-base font-medium">
                  <Phone size={18} className="text-muted" aria-hidden /> +998
                </span>
                <input
                  inputMode="tel"
                  autoComplete="tel-national"
                  placeholder="90 123 45 67"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="min-h-12 flex-1 bg-transparent text-base outline-none"
                  aria-label={t("auth.phone")}
                />
              </div>
            </Field>
            <ErrorBox message={errorText(send.error)} />
            <Button type="submit" loading={send.isPending} disabled={phone.replace(/\D/g, "").length < 9}>
              {t("auth.getCode")}
            </Button>
            <p className="text-center text-xs text-muted">{t("auth.terms")}</p>
          </form>
        ) : (
          <form onSubmit={submitCode} className="mt-8 space-y-4">
            <p className="text-center text-muted">{t("auth.codeSent", { phone: phonePretty(sentTo) })}</p>
            <Field label={t("auth.code")}>
              <Input
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                className="text-center text-2xl tracking-[0.5em]"
                autoFocus
              />
            </Field>
            <ErrorBox message={errorText(verify.error)} />
            <Button type="submit" loading={verify.isPending} disabled={code.length !== 6}>
              {t("auth.verify")}
            </Button>
            <Button type="button" variant="ghost" disabled={cooldown > 0 || send.isPending} onClick={() => send.mutate()}>
              {cooldown > 0 ? t("auth.resendIn", { sec: cooldown }) : t("auth.resend")}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setSentTo(null)}>
              {t("auth.changePhone")}
            </Button>
          </form>
        )}
      </Page>
    </>
  );
}
