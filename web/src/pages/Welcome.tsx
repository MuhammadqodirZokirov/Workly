import { useNavigate } from "react-router";

import { Button, Spinner } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

/** Splash / xush kelibsiz — dizayndagi "01 Splash" (fon: 01_minimal_light) */
export default function Welcome() {
  const { t } = useI18n();
  const { telegramLogin } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden">
      <picture>
        <source media="(min-width: 600px)" srcSet="/backgrounds/01_minimal_light_1080.webp" />
        <img src="/backgrounds/01_minimal_light_720.webp" alt="" className="absolute inset-0 h-full w-full object-cover" />
      </picture>
      <div className="relative mx-auto flex w-full max-w-md flex-1 flex-col px-6 pb-10 pt-[18vh]">
        <img src="/brand/logo_640.webp" alt="Workly" className="mx-auto w-64" />
        <p className="mt-4 text-center text-base font-medium text-midnight/80">{t("app.tagline")}</p>
        <div className="mt-auto">
          {telegramLogin ? (
            <div className="flex items-center justify-center gap-3 text-sm text-midnight/70">
              <Spinner /> {t("auth.telegram")}
            </div>
          ) : (
            <Button onClick={() => navigate("/login")}>{t("common.continue")}</Button>
          )}
        </div>
      </div>
    </div>
  );
}
