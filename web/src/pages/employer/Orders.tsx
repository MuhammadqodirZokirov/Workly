import { Phone, Repeat, UserRound, Users } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";

import { useErrorText } from "../../components/shared";
import { Button, Card, Empty, ErrorBox, Page, Section, Spinner, Tag, TopBar } from "../../components/ui";
import { api } from "../../lib/api";
import { CategoryIcon } from "../../components/icons";
import { useCatalog } from "../../lib/catalog";
import { dateTime, money, phonePretty } from "../../lib/format";
import { pickName, useI18n } from "../../lib/i18n";
import type { Order } from "../../lib/types";
import { useMyOrders } from "./EmployerHome";

const STATUS_TONE: Record<string, "accent" | "brand" | "success" | "muted" | "danger"> = {
  pending_approval: "accent",
  matching: "brand",
  partially_assigned: "accent",
  assigned: "success",
  in_progress: "success",
  completed: "muted",
  cancelled: "muted",
  expired: "danger",
};

export function StatusTag({ status }: { status: string }) {
  const { t } = useI18n();
  const key = `status.${status}` as Parameters<typeof t>[0];
  return <Tag tone={STATUS_TONE[status] ?? "muted"}>{t(key)}</Tag>;
}

export function OrderRow({ order }: { order: Order }) {
  const { lang } = useI18n();
  const catalog = useCatalog();
  const spec = catalog.specialization(order.specialization_id);
  const cat = catalog.category(order.category_id);
  const filled = order.assignments.filter((a) => a.worker_id).length;
  return (
    <Link to={`/orders/${order.id}`} className="block">
      <Card className="flex items-center gap-3">
        <CategoryIcon code={cat?.code} size="sm" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{spec ? pickName(spec.name, lang) : `#${order.id}`}</p>
          <p className="text-sm text-muted">
            <span className="inline-flex items-center gap-1">
              {dateTime(order.starts_at)} · <Users size={14} aria-hidden /> {filled}/{order.workers}
            </span>
          </p>
        </div>
        <StatusTag status={order.status} />
      </Card>
    </Link>
  );
}

export default function Orders() {
  const { t } = useI18n();
  const orders = useMyOrders();
  return (
    <>
      <TopBar title={t("home.myOrders")} />
      <Page>
        {orders.isLoading ? (
          <Spinner />
        ) : orders.data?.length ? (
          <div className="space-y-3">
            {orders.data.map((o) => (
              <OrderRow key={o.id} order={o} />
            ))}
          </div>
        ) : (
          <Empty text={t("home.noOrders")} />
        )}
      </Page>
    </>
  );
}

export function OrderDetail() {
  const { id } = useParams();
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const catalog = useCatalog();
  const errorText = useErrorText();
  const order = useQuery({
    queryKey: ["orders", id],
    queryFn: () => api<Order>(`/orders/${id}`),
    refetchInterval: (q) => (["matching", "partially_assigned"].includes(q.state.data?.status ?? "") ? 15_000 : false),
  });
  const cancel = useMutation({
    mutationFn: () => api<Order>(`/orders/${id}/cancel`, { body: {} }),
    onSuccess: (o) => {
      qc.setQueryData(["orders", id], o);
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });

  if (order.isLoading) return <Spinner />;
  const o = order.data;
  if (!o) return <ErrorBox message={errorText(order.error)} />;
  const spec = catalog.specialization(o.specialization_id);
  const district = catalog.district(o.district_id);
  const cancellable = ["pending_approval", "matching"].includes(o.status) && o.assignments.every((a) => !a.worker_id);

  return (
    <>
      <TopBar title={`#${o.id}`} back right={<StatusTag status={o.status} />} />
      <Page>
        <Card>
          <p className="text-lg font-bold">{spec ? pickName(spec.name, lang) : ""}</p>
          <p className="text-sm text-muted">
            {dateTime(o.starts_at)} · {district ? pickName(district.name, lang) : ""}
          </p>
          <p className="mt-2 text-sm">{o.address_text}</p>
          {o.landmark && <p className="text-sm text-muted">{o.landmark}</p>}
          {o.description && <p className="mt-2 text-sm">{o.description}</p>}
          <div className="mt-3 flex items-end justify-between border-t border-mist pt-3">
            <span className="text-sm text-muted">{t("order.total")}</span>
            <span className="text-lg font-bold text-brand">
              {money(o.price.employer_total)} {t("common.som")}
            </span>
          </div>
        </Card>

        <Section title={t("order.assigned")}>
          <div className="space-y-2">
            {o.assignments.map((a) => (
              <Card key={a.id} className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-snow text-brand">
                    <UserRound size={20} aria-hidden />
                  </span>
                  <span>
                    <span className="block font-medium">{a.worker_name ?? t("order.searching")}</span>
                    {a.worker_phone && <span className="block text-sm text-muted">{phonePretty(a.worker_phone)}</span>}
                  </span>
                </span>
                {a.worker_phone ? (
                  <a href={`tel:${a.worker_phone}`} aria-label={phonePretty(a.worker_phone)} className="rounded-full bg-brand-soft p-2.5 text-brand">
                    <Phone size={20} aria-hidden />
                  </a>
                ) : (
                  <Spinner />
                )}
              </Card>
            ))}
          </div>
        </Section>

        <div className="mt-6 space-y-2">
          <ErrorBox message={errorText(cancel.error)} />
          <Button variant="secondary" onClick={() => navigate(`/orders/new?repeat=${o.id}`)}>
            <Repeat size={18} aria-hidden /> {t("order.repeat")}
          </Button>
          {cancellable && (
            <Button variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate()}>
              {t("order.cancel")}
            </Button>
          )}
        </div>
      </Page>
    </>
  );
}
