import { Briefcase, ChevronRight, UserRound, type LucideIcon } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { useErrorText } from "../components/shared";
import { Button, Card, Checkbox, cx, ErrorBox } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

type AppRole = "worker" | "employer";
const CONSENT_VERSION = "1.0";

/** "Siz kim sifatida davom etasiz?" — rol + roziliklar (TZ 3: shartlar, maxfiylik, shartnoma) */
export default function RoleSelect() {
  const { t } = useI18n();
  const { refreshMe, setRole } = useAuth();
  const errorText = useErrorText();
  const [choice, setChoice] = useState<AppRole | null>(null);
  const [agree, setAgree] = useState(false);

  const save = useMutation({
    mutationFn: async (role: AppRole) => {
      await api("/me/roles", { body: { role } });
      await api("/me/consents", {
        body: {
          items: ["terms", "privacy", `${role}_contract`].map((doc_type) => ({ doc_type, version: CONSENT_VERSION })),
        },
      });
      return role;
    },
    onSuccess: async (role) => {
      setRole(role);
      await refreshMe();
    },
  });

  const option = (role: AppRole, Icon: LucideIcon, title: string, hint: string) => (
    <Card
      onClick={() => setChoice(role)}
      className={cx("flex items-center gap-4 border-2 transition", choice === role ? "border-brand" : "border-transparent")}
    >
      <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
        <Icon size={28} strokeWidth={1.8} aria-hidden />
      </span>
      <span className="flex-1">
        <span className="block font-semibold">{title}</span>
        <span className="block text-sm text-muted">{hint}</span>
      </span>
      <ChevronRight size={22} className="text-brand" aria-hidden />
    </Card>
  );

  return (
    <div className="relative min-h-screen">
      <img src="/backgrounds/11_blue_sky_720.webp" alt="" className="absolute inset-x-0 top-0 h-72 w-full object-cover opacity-60" />
      <div className="relative mx-auto max-w-md px-4 pb-10 pt-16">
        <h1 className="text-center font-display text-3xl font-extrabold">{t("role.title")}</h1>
        <p className="mt-2 text-center text-muted">{t("role.subtitle")}</p>
        <div className="mt-8 space-y-3">
          {option("worker", UserRound, t("role.worker"), t("role.workerHint"))}
          {option("employer", Briefcase, t("role.employer"), t("role.employerHint"))}
        </div>
        <div className="mt-6">
          <Checkbox checked={agree} onChange={setAgree}>
            {t("role.agree")}
          </Checkbox>
        </div>
        <div className="mt-6 space-y-3">
          <ErrorBox message={errorText(save.error)} />
          <Button disabled={!choice || !agree} loading={save.isPending} onClick={() => choice && save.mutate(choice)}>
            {t("common.continue")}
          </Button>
        </div>
      </div>
    </div>
  );
}
