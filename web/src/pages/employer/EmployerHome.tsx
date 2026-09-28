import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";

import { Card, Empty, Page, Section, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { CATEGORY_ICONS, useCatalog } from "../../lib/catalog";
import { pickName, useI18n } from "../../lib/i18n";
import type { Order } from "../../lib/types";
import { OrderRow } from "./Orders";

export const useMyOrders = () => useQuery({ queryKey: ["orders"], queryFn: () => api<Order[]>("/orders") });

export default function EmployerHome() {
  const { t, lang } = useI18n();
  const { me } = useAuth();
  const catalog = useCatalog();
  const orders = useMyOrders();
  const navigate = useNavigate();
  const name = me?.full_name?.split(" ")[0];

  return (
    <Page>
      <header className="flex items-center justify-between py-4">
        <img src="/brand/logo_320.webp" alt="Workly" className="h-8" />
        <span className="rounded-full bg-white px-3 py-1.5 text-sm shadow-[var(--shadow-card)]">📍 Toshkent</span>
      </header>
      <h1 className="text-2xl font-bold">{name ? t("home.hello", { name }) : t("home.helloAnon")}</h1>

      <div className="mt-4 grid grid-cols-4 gap-2">
        {catalog.categories.map((c) => (
          <button key={c.id} onClick={() => navigate(`/orders/new?category=${c.id}`)} className="flex min-w-0 flex-col items-center gap-1.5">
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-soft text-2xl">
              {CATEGORY_ICONS[c.code] ?? "🧰"}
            </span>
            <span className="w-full break-words text-center text-[11px] leading-tight hyphens-auto">{pickName(c.name, lang)}</span>
          </button>
        ))}
      </div>

      <Link to="/orders/new" className="relative mt-5 block overflow-hidden rounded-[var(--radius-card)] bg-brand p-5 text-white">
        <img src="/backgrounds/09_cobalt_waves_720.webp" alt="" className="absolute inset-0 h-full w-full object-cover opacity-60" />
        <span className="relative block text-xl font-bold">{t("home.newOrder")}</span>
        <span className="relative mt-1 block max-w-[75%] text-sm text-white/85">{t("home.newOrderHint")}</span>
        <span className="absolute right-5 top-1/2 -translate-y-1/2 text-4xl">👷</span>
      </Link>

      <Section title={t("home.myOrders")} action={<Link to="/orders" className="text-sm text-brand">→</Link>}>
        {orders.isLoading ? (
          <Spinner />
        ) : orders.data?.length ? (
          <div className="space-y-3">
            {orders.data.slice(0, 5).map((o) => (
              <OrderRow key={o.id} order={o} />
            ))}
          </div>
        ) : (
          <Empty text={t("home.noOrders")} />
        )}
      </Section>
      <Card className="mt-6 text-xs text-muted">{t("app.tagline")}</Card>
    </Page>
  );
}
