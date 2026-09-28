import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { useErrorText } from "../../components/shared";
import { Button, Card, Checkbox, Chip, ErrorBox, Field, Input, Page, Section, Select, Tag, Textarea, Toggle, TopBar } from "../../components/ui";
import { api, newIdempotencyKey } from "../../lib/api";
import { DISTRICT_CENTERS, useCatalog } from "../../lib/catalog";
import { dateTashkent, money } from "../../lib/format";
import { pickName, useI18n } from "../../lib/i18n";
import type { Duration, GeoPoint, Order, OrderInput, Quote } from "../../lib/types";

/**
 * Yangi buyurtma (dizayndagi "Yangi ish joyi"). Dizayndan farqi: "Maosh" maydoni yo'q —
 * narx backend'da hisoblanadi (TZ 8), bekor qilish qoidalari ko'rsatiladi (TZ 5).
 */
export default function NewOrder() {
  const { t, lang } = useI18n();
  const catalog = useCatalog();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const errorText = useErrorText();
  const [params] = useSearchParams();
  const repeatId = params.get("repeat");

  const [form, setForm] = useState({
    category_id: Number(params.get("category")) || 0,
    specialization_id: 0,
    workers: 1,
    date: dateTashkent(1),
    start_time: "08:00",
    duration: "day" as Duration,
    days: 2,
    district_id: 0,
    address_text: "",
    landmark: "",
    description: "",
    tools_by: "employer" as "employer" | "worker",
    lunch: false,
    transport: false,
    top_only: false,
  });
  const [point, setPoint] = useState<GeoPoint | null>(null);
  const [pointExact, setPointExact] = useState(false);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [agree, setAgree] = useState(false);
  const idempotencyKey = useMemo(newIdempotencyKey, [quote?.quote_id]);

  // "Qayta buyurtma" — oldingi parametrlar
  const previous = useQuery({ queryKey: ["orders", repeatId], queryFn: () => api<Order>(`/orders/${repeatId}`), enabled: !!repeatId });
  useEffect(() => {
    const o = previous.data;
    if (!o) return;
    setForm((f) => ({
      ...f,
      category_id: o.category_id,
      specialization_id: o.specialization_id,
      workers: o.workers,
      duration: o.duration ?? "day",
      days: o.days > 1 ? o.days : 2,
      district_id: o.district_id,
      address_text: o.address_text,
      landmark: o.landmark ?? "",
      description: o.description ?? "",
    }));
  }, [previous.data]);

  const category = catalog.category(form.category_id);
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setQuote(null);
  };

  const locate = () =>
    navigator.geolocation?.getCurrentPosition(
      (pos) => {
        setPoint({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setPointExact(true);
        setQuote(null);
      },
      () => setPointExact(false),
      { enableHighAccuracy: true, timeout: 10_000 },
    );

  const body = (): OrderInput => {
    const district = catalog.district(form.district_id);
    const center = district ? DISTRICT_CENTERS[district.code] : undefined;
    return {
      category_id: form.category_id,
      specialization_id: form.specialization_id,
      workers: form.workers,
      date: form.date,
      start_time: form.start_time,
      duration: form.duration,
      days: form.duration === "multi_day" ? form.days : 1,
      point: point ?? (center ? { lat: center[0], lon: center[1] } : { lat: 41.3111, lon: 69.2797 }),
      district_id: form.district_id,
      address_text: form.address_text,
      landmark: form.landmark || null,
      description: form.description || null,
      tools_by: form.tools_by,
      lunch: form.lunch,
      transport: form.transport,
      top_only: form.top_only,
    };
  };

  const getQuote = useMutation({ mutationFn: () => api<Quote>("/orders/quote", { body: body() }), onSuccess: setQuote });
  const create = useMutation({
    mutationFn: () =>
      api<Order>("/orders", {
        body: { quote_id: quote!.quote_id, accept_rules: agree },
        headers: { "Idempotency-Key": idempotencyKey },
      }),
    onSuccess: (order) => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      navigate(`/orders/${order.id}`, { replace: true });
    },
  });

  const ready = form.specialization_id && form.district_id && form.address_text.trim().length >= 3;

  return (
    <>
      <TopBar title={t("order.new")} back />
      <Page>
        <Section title={t("order.category")}>
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
            {catalog.categories.map((c) => (
              <Chip key={c.id} active={form.category_id === c.id} onClick={() => setForm((f) => ({ ...f, category_id: c.id, specialization_id: 0 }))}>
                {pickName(c.name, lang)}
              </Chip>
            ))}
          </div>
          {category && (
            <div className="mt-3 flex flex-wrap gap-2">
              {category.specializations.map((s) => (
                <Chip key={s.id} active={form.specialization_id === s.id} onClick={() => set("specialization_id", s.id)}>
                  {pickName(s.name, lang)}
                </Chip>
              ))}
            </div>
          )}
        </Section>

        <Section title={t("order.workers")}>
          <div className="flex items-center gap-4">
            <Button variant="secondary" className="w-12" onClick={() => set("workers", Math.max(1, form.workers - 1))}>
              −
            </Button>
            <span className="w-10 text-center text-2xl font-bold">{form.workers}</span>
            <Button variant="secondary" className="w-12" onClick={() => set("workers", Math.min(50, form.workers + 1))}>
              +
            </Button>
          </div>
        </Section>

        <div className="mt-6 grid grid-cols-2 gap-3">
          <Field label={t("order.date")}>
            <Input type="date" min={dateTashkent()} max={dateTashkent(30)} value={form.date} onChange={(e) => set("date", e.target.value)} />
          </Field>
          <Field label={t("order.time")}>
            <Input type="time" value={form.start_time} onChange={(e) => set("start_time", e.target.value)} />
          </Field>
        </div>

        <Section title={t("order.duration")}>
          <div className="flex flex-wrap gap-2">
            {(["half_day", "day", "multi_day"] as Duration[]).map((d) => (
              <Chip key={d} active={form.duration === d} onClick={() => set("duration", d)}>
                {t(`dur.${d}`)}
              </Chip>
            ))}
          </div>
          {form.duration === "multi_day" && (
            <div className="mt-3">
              <Field label={t("order.days")}>
                <Input type="number" min={2} max={30} value={form.days} onChange={(e) => set("days", Number(e.target.value))} />
              </Field>
            </div>
          )}
        </Section>

        <Section title={t("order.address")}>
          <div className="space-y-3">
            <Field label={t("order.district")}>
              <Select value={form.district_id} onChange={(e) => set("district_id", Number(e.target.value))}>
                <option value={0}>—</option>
                {catalog.districts.map((d) => (
                  <option key={d.id} value={d.id}>
                    {pickName(d.name, lang)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("order.address")}>
              <Input placeholder={t("order.addressHint")} value={form.address_text} onChange={(e) => set("address_text", e.target.value)} />
            </Field>
            <Field label={t("order.landmark")}>
              <Input value={form.landmark} onChange={(e) => set("landmark", e.target.value)} />
            </Field>
            <Button variant="secondary" onClick={locate}>
              📍 {pointExact ? t("order.pointSet") : t("order.point")}
            </Button>
            <Field label={t("order.description")}>
              <Textarea maxLength={500} placeholder={t("order.descriptionHint")} value={form.description} onChange={(e) => set("description", e.target.value)} />
            </Field>
          </div>
        </Section>

        <Card className="mt-6 space-y-4">
          <Toggle checked={form.tools_by === "worker"} onChange={(v) => set("tools_by", v ? "worker" : "employer")} label={t("order.tools")} />
          <Toggle checked={form.lunch} onChange={(v) => set("lunch", v)} label={t("order.lunch")} />
          <Toggle checked={form.transport} onChange={(v) => set("transport", v)} label={t("order.transport")} />
          <Toggle checked={form.top_only} onChange={(v) => set("top_only", v)} label={t("order.topOnly")} />
        </Card>

        <div className="mt-6 space-y-3">
          <ErrorBox message={errorText(getQuote.error)} />
          {!quote && (
            <Button disabled={!ready} loading={getQuote.isPending} onClick={() => getQuote.mutate()}>
              {t("order.getPrice")}
            </Button>
          )}
        </div>

        {quote && (
          <Card className="mt-2 border-2 border-brand">
            <p className="font-bold">{t("order.price")}</p>
            <div className="mt-3 space-y-1.5 text-sm">
              <Row label={`${t("order.perWorker")} (${quote.price.days > 1 ? t("dur.days", { n: quote.price.days }) : "1"})`} value={quote.price.worker_price} />
              <Row label={`× ${quote.price.workers}`} value={quote.price.subtotal} />
              <Row label={t("order.serviceFee")} value={quote.price.service_fee} />
              <div className="flex justify-between border-t border-mist pt-2 text-base font-bold">
                <span>{t("order.total")}</span>
                <span className="text-brand">
                  {money(quote.price.employer_total)} {t("common.som")}
                </span>
              </div>
            </div>
            {!quote.price.commission_enabled && <p className="mt-2 text-xs text-success">{t("order.pilotFree")}</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              {quote.night && <Tag tone="brand">🌙 {t("job.night")}</Tag>}
              {quote.needs_approval && <Tag>{t("order.approval")}</Tag>}
            </div>
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer font-medium">{t("order.policy")}</summary>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
                {quote.cancellation_policy.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </details>
            <p className="mt-2 text-xs text-muted">{t("order.quoteExpires")}</p>
            <div className="mt-4 space-y-3">
              <Checkbox checked={agree} onChange={setAgree}>
                {t("order.rules")}
              </Checkbox>
              <ErrorBox message={errorText(create.error)} />
              <Button disabled={!agree} loading={create.isPending} onClick={() => create.mutate()}>
                {t("order.confirm")}
              </Button>
            </div>
          </Card>
        )}
      </Page>
    </>
  );
}

function Row({ label, value }: { label: string; value: number }) {
  const { t } = useI18n();
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span>
        {money(value)} {t("common.som")}
      </span>
    </div>
  );
}
