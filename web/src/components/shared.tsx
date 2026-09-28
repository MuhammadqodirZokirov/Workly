import { BadgeCheck, BriefcaseBusiness, Bus, ClipboardList, House, Moon, Plus, Soup, Timer, UserRound, Wrench, type LucideIcon } from "lucide-react";
import { NavLink, Outlet } from "react-router";

import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useCatalog } from "../lib/catalog";
import { CategoryIcon } from "./icons";
import { dateTime, isToday, minutesLeft, money } from "../lib/format";
import { errorKey, pickName, useI18n } from "../lib/i18n";
import type { JobCard } from "../lib/types";
import { Card, cx, Tag } from "./ui";

/** Backend xatosini foydalanuvchi tilida */
export function useErrorText() {
  const { t } = useI18n();
  return (err: unknown): string | null => {
    if (!err) return null;
    if (err instanceof ApiError) {
      const key = errorKey(err.code);
      if (key) return t(key);
      return err.message || t("common.error");
    }
    return t("common.error");
  };
}

export function AppLayout() {
  const { role } = useAuth();
  const { t } = useI18n();
  const item = (to: string, Icon: LucideIcon, label: string) => (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        cx("flex min-h-12 flex-1 flex-col items-center justify-center gap-0.5 text-[11px]", isActive ? "text-brand" : "text-muted")
      }
    >
      <Icon size={22} strokeWidth={1.9} aria-hidden />
      {label}
    </NavLink>
  );
  return (
    <>
      <Outlet />
      <nav className="safe-bottom fixed inset-x-0 bottom-0 z-20 border-t border-mist bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-md items-end px-2 pt-1.5">
          {item("/", House, t("nav.home"))}
          {role === "employer" ? item("/orders", ClipboardList, t("nav.orders")) : item("/jobs", BriefcaseBusiness, t("nav.jobs"))}
          {role === "employer" && (
            <NavLink
              to="/orders/new"
              aria-label={t("nav.new")}
              className="-mt-6 mx-2 flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand text-white shadow-lg shadow-brand/30"
            >
              <Plus size={28} aria-hidden />
            </NavLink>
          )}
          {item("/profile", UserRound, t("nav.profile"))}
        </div>
      </nav>
    </>
  );
}

/** Ish kartasi (taklif, lenta, tayinlov) — dizayndagi ro'yxat kartasi */
export function JobCardView({ job, footer, extra }: { job: JobCard; footer?: React.ReactNode; extra?: React.ReactNode }) {
  const { t, lang } = useI18n();
  const catalog = useCatalog();
  const cat = catalog.category(job.category_id);
  const spec = catalog.specialization(job.specialization_id);
  const district = catalog.district(job.district_id);
  const duration =
    job.duration === "multi_day" ? t("dur.days", { n: job.days }) : job.duration ? t(`dur.${job.duration}`) : "";
  return (
    <Card>
      <div className="flex gap-3">
        <CategoryIcon code={cat?.code} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="truncate font-semibold">{spec ? pickName(spec.name, lang) : "…"}</p>
            {isToday(job.starts_at) && <Tag>{t("job.today")}</Tag>}
          </div>
          <p className="truncate text-sm text-muted">
            {district ? pickName(district.name, lang) : ""}
            {job.distance_km != null && ` · ~${job.distance_km.toFixed(1)} ${t("common.km")}`}
          </p>
          <p className="text-sm text-muted">
            {dateTime(job.starts_at)} · {duration}
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {job.is_night && <Tag tone="brand"><Moon size={13} aria-hidden /> {t("job.night")}</Tag>}
        {job.lunch && <Tag tone="muted"><Soup size={13} aria-hidden /> {t("job.lunch")}</Tag>}
        {job.transport && <Tag tone="muted"><Bus size={13} aria-hidden /> {t("job.transport")}</Tag>}
        {job.tools_by === "worker" && <Tag tone="muted"><Wrench size={13} aria-hidden /> {t("job.ownTools")}</Tag>}
        {job.employer.verified && <Tag tone="success"><BadgeCheck size={13} aria-hidden /> {t("job.verifiedEmployer")}</Tag>}
        {extra}
      </div>
      {job.description && <p className="mt-2 line-clamp-2 text-sm text-midnight/80">{job.description}</p>}
      <div className="mt-3 flex items-end justify-between">
        <div>
          <p className="text-xs text-muted">{t("job.youGet")}</p>
          <p className="text-lg font-bold text-brand">
            {money(job.worker_net)} {t("common.som")}
          </p>
        </div>
        <p className="text-right text-xs text-muted">
          {job.employer.name}
          <br />
          {cat ? pickName(cat.name, lang) : ""}
        </p>
      </div>
      {footer && <div className="mt-3">{footer}</div>}
    </Card>
  );
}

export function Countdown({ until }: { until: string }) {
  const { t } = useI18n();
  return (
    <Tag tone="accent">
      <Timer size={13} aria-hidden /> {t("job.expiresIn", { min: minutesLeft(until) })}
    </Tag>
  );
}
