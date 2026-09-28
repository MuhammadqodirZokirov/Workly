import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Ban, CircleAlert, Heart, Hourglass, Play } from "lucide-react";
import { useState } from "react";

import { api } from "../lib/api";
import { money } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { haptic } from "../lib/telegram";
import type { AssignmentSlot, CancelTerms, Order } from "../lib/types";
import { useErrorText } from "./shared";
import { Button, Card, cx, ErrorBox, Textarea } from "./ui";

/**
 * Bekor qilish: avval oqibati ko'rsatiladi (TZ 5: "bekor qilishdan oldin to'lanadigan summa"),
 * keyin tasdiqlanadi. Pilotda summa olinmaydi — faqat Ishonchlilik.
 */
export function CancelFlow({
  previewPath,
  cancelPath,
  label,
  hint,
}: {
  previewPath: string;
  cancelPath: string;
  label: string;
  hint?: string;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const errorText = useErrorText();
  const [reason, setReason] = useState("");
  const preview = useMutation({ mutationFn: () => api<CancelTerms>(previewPath) });
  const cancel = useMutation({
    mutationFn: () => api(cancelPath, { body: { reason: reason.trim() || null } }),
    onSuccess: () => haptic("warning"),
    onSettled: () => qc.invalidateQueries(),
  });
  const terms = preview.data;

  if (!terms) {
    return (
      <div className="space-y-2">
        <ErrorBox message={errorText(preview.error)} />
        <Button variant="danger" loading={preview.isPending} onClick={() => preview.mutate()}>
          {label}
        </Button>
      </div>
    );
  }
  const free = terms.amount === 0 && terms.reliability === 0;
  return (
    <Card className="space-y-3 border border-danger/30">
      <p className="flex items-center gap-2 font-semibold">
        <CircleAlert size={18} className="text-danger" aria-hidden /> {t("cx.title")}
      </p>
      {free ? (
        <p className="text-sm">{t("cx.free")}</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {terms.amount > 0 && (
            <li>
              {t("cx.amount", { sum: money(terms.amount), pct: terms.percent })}
              {!terms.charged && <span className="block text-xs text-muted">{t("cx.pilot")}</span>}
            </li>
          )}
          {terms.reliability !== 0 && <li className="text-danger">{t("cx.reliability", { delta: terms.reliability })}</li>}
        </ul>
      )}
      {hint && <p className="text-xs text-muted">{hint}</p>}
      <Textarea value={reason} maxLength={200} placeholder={t("cx.reason")} onChange={(e) => setReason(e.target.value)} />
      <ErrorBox message={errorText(cancel.error)} />
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" onClick={() => preview.reset()}>
          {t("cx.keep")}
        </Button>
        <Button variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate()}>
          {t("cx.confirm")}
        </Button>
      </div>
    </Card>
  );
}

/** T−60: qisman to'lgan buyurtma — topilganlar bilan boshlash yoki kutish (TZ 6, OS-10) */
export function PartialDecision({ order }: { order: Order }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const errorText = useErrorText();
  const decide = useMutation({
    mutationFn: (start: boolean) => api<Order>(`/orders/${order.id}/partial`, { body: { start } }),
    onSuccess: (o) => qc.setQueryData(["orders", String(order.id)], o),
    onSettled: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });
  if (order.status !== "partially_assigned" || !order.partial_asked_at) return null;
  if (order.partial_decision === "wait") {
    return <p className="mt-4 rounded-xl bg-accent-soft p-3 text-sm text-accent">{t("partial.waiting")}</p>;
  }
  const found = order.assignments.filter((a) => a.status === "assigned").length;
  return (
    <Card className="mt-4 space-y-3 border border-accent/40">
      <p className="font-semibold">{t("partial.title")}</p>
      <p className="text-sm">{t("partial.text", { n: order.workers, found })}</p>
      <ErrorBox message={errorText(decide.error)} />
      <Button loading={decide.isPending && decide.variables} onClick={() => decide.mutate(true)}>
        <Play size={18} aria-hidden /> {t("partial.start")}
      </Button>
      <p className="-mt-1 text-xs text-muted">{t("partial.startHint")}</p>
      <Button variant="secondary" loading={decide.isPending && !decide.variables} onClick={() => decide.mutate(false)}>
        <Hourglass size={18} aria-hidden /> {t("partial.wait")}
      </Button>
      <p className="-mt-1 text-xs text-muted">{t("partial.waitHint")}</p>
    </Card>
  );
}

/** Sevimli / bloklash — faqat shu employer bilan ishlagan ishchi uchun (TZ 5) */
export function RelationButtons({ slot, orderId }: { slot: AssignmentSlot; orderId: number }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const errorText = useErrorText();
  const toggle = useMutation({
    mutationFn: ({ kind, on }: { kind: "favorites" | "blocks"; on: boolean }) =>
      api(`/employer/${kind}/${slot.worker_id}`, { method: on ? "PUT" : "DELETE" }),
    onSuccess: () => haptic("success"),
    onSettled: () => qc.invalidateQueries({ queryKey: ["orders", String(orderId)] }),
  });
  if (!slot.worker_id) return null;
  const busy = toggle.isPending;
  return (
    <div className="space-y-2">
      <ErrorBox message={errorText(toggle.error)} />
      {slot.blocked && <p className="text-xs text-danger">{t("rel.blocked")}</p>}
      <div className="flex flex-wrap gap-2">
        {!slot.blocked && (
          <button
            type="button"
            disabled={busy}
            onClick={() => toggle.mutate({ kind: "favorites", on: !slot.favorite })}
            className={cx(
              "inline-flex min-h-10 items-center gap-1.5 rounded-full border px-3 text-sm font-medium",
              slot.favorite ? "border-accent bg-accent-soft text-accent" : "border-mist bg-white text-midnight",
            )}
          >
            <Heart size={16} aria-hidden className={slot.favorite ? "fill-accent" : ""} />
            {t(slot.favorite ? "rel.unfavorite" : "rel.favorite")}
          </button>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={() => toggle.mutate({ kind: "blocks", on: !slot.blocked })}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-full border border-mist bg-white px-3 text-sm font-medium text-muted"
        >
          <Ban size={16} aria-hidden /> {t(slot.blocked ? "rel.unblock" : "rel.block")}
        </button>
      </div>
    </div>
  );
}
