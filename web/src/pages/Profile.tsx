import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router";

import { useErrorText } from "../components/shared";
import { Button, Card, Chip, ErrorBox, Page, Section, TopBar } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { phonePretty } from "../lib/format";
import { useI18n } from "../lib/i18n";
import type { Lang } from "../lib/types";

const LANGS: [Lang, string][] = [
  ["uz_latn", "O'zbekcha"],
  ["uz_cyrl", "Ўзбекча"],
  ["ru", "Русский"],
];

export default function Profile() {
  const { t, lang, setLang } = useI18n();
  const { me, role, setRole, signOut, refreshMe } = useAuth();
  const errorText = useErrorText();
  const other = role === "worker" ? "employer" : "worker";
  const hasOther = me?.roles.includes(other);

  // Ikkinchi rolni qo'shish (TZ 3: bitta akkauntda ishchi va employer)
  const addRole = useMutation({
    mutationFn: async () => {
      await api("/me/roles", { body: { role: other } });
      await api("/me/consents", { body: { items: [{ doc_type: `${other}_contract`, version: "1.0" }] } });
    },
    onSuccess: async () => {
      await refreshMe();
      setRole(other);
    },
  });

  return (
    <>
      <TopBar title={t("profile.title")} />
      <Page>
        <Card className="flex items-center gap-4">
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-soft text-3xl">
            {role === "worker" ? "👷" : "💼"}
          </span>
          <div>
            <p className="text-lg font-bold">{me?.full_name ?? phonePretty(me?.phone ?? "")}</p>
            <p className="text-sm text-muted">
              {me?.phone && phonePretty(me.phone)} · {t(role === "worker" ? "profile.worker" : "profile.employer")}
            </p>
          </div>
        </Card>

        <Section title={t("profile.myProfile")}>
          <div className="space-y-2">
            {role === "worker" && (
              <Link to="/worker/profile">
                <Card className="flex justify-between">
                  <span>📄 {t("wp.title")}</span>
                  <span className="text-muted">→</span>
                </Card>
              </Link>
            )}
            <Card className="flex justify-between" onClick={() => (hasOther ? setRole(other) : addRole.mutate())}>
              <span>🔄 {t("role.switch")}: {t(other === "worker" ? "profile.worker" : "profile.employer")}</span>
              <span className="text-muted">→</span>
            </Card>
            <ErrorBox message={errorText(addRole.error)} />
          </div>
        </Section>

        <Section title={t("profile.language")}>
          <div className="flex flex-wrap gap-2">
            {LANGS.map(([code, label]) => (
              <Chip key={code} active={lang === code} onClick={() => setLang(code)}>
                {label}
              </Chip>
            ))}
          </div>
        </Section>

        <div className="mt-8">
          <Button variant="danger" onClick={() => void signOut()}>
            {t("profile.logout")}
          </Button>
        </div>
      </Page>
    </>
  );
}
