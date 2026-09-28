import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, CheckCircle2, CircleAlert, Clock, MapPin, Star, UserCheck, UserX } from "lucide-react";
import { useState } from "react";

import { api } from "../lib/api";
import { money } from "../lib/format";
import { useI18n, type MsgKey } from "../lib/i18n";
import { haptic } from "../lib/telegram";
import type { AssignmentSlot, AssignmentState, Reviews, WorkerAssignment } from "../lib/types";
import { useErrorText } from "./shared";
import { Button, Chip, cx, ErrorBox, Input, Tag, Textarea } from "./ui";

const MIN = 60_000;
const CHECKIN_OPENS_MIN = 30; // backend domain/workday.py bilan bir xil
const LATE_ESCALATE_MIN = 30;
const REASON_MIN = 20;

const WORKER_TAGS = ["on_time", "quality", "polite"] as const; // employer ishchiga
const EMPLOYER_TAGS = ["paid_on_time", "polite", "clear_task"] as const; // ishchi employerga

const TONE: Record<string, "accent" | "brand" | "success" | "muted" | "danger"> = {
  assigned: "brand",
  arrived: "accent",
  working: "success",
  finished: "accent",
  confirmed: "success",
  disputed: "danger",
  no_show: "danger",
  replaced: "muted",
  open: "brand",
};

export function WorkdayTag({ status }: { status: string }) {
  const { t } = useI18n();
  return <Tag tone={TONE[status] ?? "muted"}>{t(`wd.status.${status}` as MsgKey)}</Tag>;
}

function Hint({ icon: Icon = Clock, children, tone = "muted" }: { icon?: typeof Clock; children: React.ReactNode; tone?: "muted" | "danger" }) {
  return (
    <p className={cx("flex items-start gap-2 text-sm", tone === "danger" ? "text-danger" : "text-muted")}>
      <Icon size={16} className="mt-0.5 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}

function useAction(assignmentId: number, path: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body?: unknown) => api<AssignmentState>(`/assignments/${assignmentId}/${path}`, { body: body ?? {} }),
    onSuccess: () => haptic("success"),
    onError: () => haptic("error"),
    onSettled: () => qc.invalidateQueries(),
  });
}

function getPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("no-geo"));
    navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 20_000, maximumAge: 0 });
  });
}

/** Check-in: 1) GPS (≤ 200 m, aniqlik ≤ 100 m) 2) old kamera orqali jonli selfie (TZ 10) */
function CheckIn({ a }: { a: WorkerAssignment }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const errorText = useErrorText();
  const [pos, setPos] = useState<GeolocationCoordinates | null>(null);
  const [locating, setLocating] = useState(false);
  const [geoError, setGeoError] = useState(false);
  const send = useMutation({
    mutationFn: (selfie: File) => {
      const form = new FormData();
      form.set("lat", String(pos!.latitude));
      form.set("lon", String(pos!.longitude));
      form.set("accuracy", String(pos!.accuracy));
      form.set("selfie", selfie);
      return api<AssignmentState>(`/assignments/${a.assignment_id}/checkin`, { form });
    },
    onSuccess: () => haptic("success"),
    onError: () => {
      haptic("error");
      setPos(null); // joylashuvni qayta aniqlash kerak
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["worker"] }),
  });

  const opensAt = new Date(a.starts_at).getTime() - CHECKIN_OPENS_MIN * MIN;
  if (Date.now() < opensAt) return <Hint>{t("wd.checkinOpens")}</Hint>;

  const locate = async () => {
    setLocating(true);
    setGeoError(false);
    send.reset();
    try {
      setPos((await getPosition()).coords);
    } catch {
      setGeoError(true);
    } finally {
      setLocating(false);
    }
  };

  return (
    <div className="space-y-2">
      <ErrorBox message={errorText(send.error)} />
      {geoError && <Hint icon={CircleAlert} tone="danger">{t("wd.gpsDenied")}</Hint>}
      {!pos ? (
        <>
          <Button onClick={locate} loading={locating}>
            <MapPin size={18} aria-hidden /> {t("wd.checkin")}
          </Button>
          <p className="text-xs text-muted">{locating ? t("wd.locating") : t("wd.checkinHint")}</p>
        </>
      ) : (
        // Selfie tugmasi — foydalanuvchining to'g'ridan-to'g'ri bosishi (brauzer kamerani faqat shunda ochadi)
        <label className={cx("flex min-h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-brand px-4 font-semibold text-white", send.isPending && "opacity-60")}>
          <Camera size={18} aria-hidden /> {t("wd.takeSelfie")} · ±{Math.round(pos.accuracy)} m
          <input
            type="file"
            accept="image/*"
            capture="user"
            className="hidden"
            disabled={send.isPending}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) send.mutate(file);
              e.target.value = "";
            }}
          />
        </label>
      )}
    </div>
  );
}

function CashForm({ a }: { a: WorkerAssignment }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const cash = useAction(a.assignment_id, "cash-received");
  const [sum, setSum] = useState(String(a.worker_net));
  if (a.cash_received !== null) {
    return <Hint icon={CheckCircle2}>{t("wd.cashSaved", { sum: money(a.cash_received) })}</Hint>;
  }
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{t("wd.cash")}</p>
      <ErrorBox message={errorText(cash.error)} />
      <div className="grid grid-cols-[1fr_auto] gap-2">
        <Input className="min-w-0" inputMode="numeric" value={sum} onChange={(e) => setSum(e.target.value.replace(/\D/g, ""))} aria-label={t("wd.cash")} />
        <Button variant="secondary" loading={cash.isPending} disabled={!sum} onClick={() => cash.mutate({ amount: Number(sum) })}>
          {t("wd.cashSave")}
        </Button>
      </div>
    </div>
  );
}

/** Ishchi: tayinlangan ish kartasidagi ish kuni harakatlari */
export function WorkerDayActions({ a }: { a: WorkerAssignment }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const finish = useAction(a.assignment_id, "finish");

  switch (a.status) {
    case "assigned":
      return <CheckIn a={a} />;
    case "arrived":
    case "working":
      return (
        <div className="space-y-2">
          {a.status === "arrived" && <Hint>{t("wd.waitEmployer")}</Hint>}
          <ErrorBox message={errorText(finish.error)} />
          <Button onClick={() => finish.mutate(undefined)} loading={finish.isPending}>
            <CheckCircle2 size={18} aria-hidden /> {t("wd.finish")}
          </Button>
        </div>
      );
    case "finished":
      return (
        <div className="space-y-3">
          <Hint>{t("wd.waitConfirm")}</Hint>
          <CashForm a={a} />
        </div>
      );
    case "confirmed":
      return (
        <div className="space-y-3">
          <CashForm a={a} />
          <ReviewBox assignmentId={a.assignment_id} target="employer" />
        </div>
      );
    case "disputed":
      return <Hint icon={CircleAlert} tone="danger">{t("wd.disputed")}</Hint>;
    default:
      return null;
  }
}

/** Ish beruvchi: buyurtmadagi har bir ishchi uchun harakatlar */
export function EmployerSlotActions({ slot, startsAt }: { slot: AssignmentSlot; startsAt: string }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const arrival = useAction(slot.id, "confirm-arrival");
  const confirm = useAction(slot.id, "confirm");
  const replace = useAction(slot.id, "replace");
  const [problem, setProblem] = useState<string | null>(null);
  const error = errorText(arrival.error ?? confirm.error ?? replace.error);

  if (slot.status === "assigned") {
    const late = Date.now() > new Date(startsAt).getTime() + LATE_ESCALATE_MIN * MIN;
    if (!late) return null;
    return (
      <div className="space-y-2">
        <Hint icon={CircleAlert} tone="danger">{t("wd.late")}</Hint>
        <ErrorBox message={error} />
        <Button variant="secondary" loading={replace.isPending} onClick={() => replace.mutate(undefined)}>
          {t("wd.replace")}
        </Button>
      </div>
    );
  }
  if (slot.status === "arrived") {
    return (
      <div className="space-y-2">
        <p className="text-sm font-medium">{t("wd.arrivedQ")}</p>
        <ErrorBox message={error} />
        <div className="grid grid-cols-2 gap-2">
          <Button loading={arrival.isPending} onClick={() => arrival.mutate({ same_person: true })}>
            <UserCheck size={18} aria-hidden /> {t("wd.yes")}
          </Button>
          <Button variant="danger" disabled={arrival.isPending} onClick={() => arrival.mutate({ same_person: false })}>
            <UserX size={18} aria-hidden /> {t("wd.no")}
          </Button>
        </div>
      </div>
    );
  }
  if (slot.status === "working" || slot.status === "finished") {
    return (
      <div className="space-y-2">
        {slot.status === "finished" && <p className="text-sm font-medium">{t("wd.workDone")}</p>}
        <ErrorBox message={error} />
        {problem === null ? (
          <div className="grid grid-cols-2 gap-2">
            <Button loading={confirm.isPending} onClick={() => confirm.mutate({ ok: true })}>
              <CheckCircle2 size={18} aria-hidden /> {t("wd.done")}
            </Button>
            <Button variant="danger" onClick={() => setProblem("")}>
              {t("wd.problem")}
            </Button>
          </div>
        ) : (
          <>
            <Textarea value={problem} maxLength={300} placeholder={t("wd.problemHint")} onChange={(e) => setProblem(e.target.value)} />
            <Button
              variant="danger"
              disabled={problem.trim().length < REASON_MIN}
              loading={confirm.isPending}
              onClick={() => confirm.mutate({ ok: false, reason: problem.trim() })}
            >
              {t("wd.send")}
            </Button>
          </>
        )}
      </div>
    );
  }
  if (slot.status === "confirmed") return <ReviewBox assignmentId={slot.id} target="worker" />;
  if (slot.status === "disputed") return <Hint icon={CircleAlert} tone="danger">{t("wd.disputed")}</Hint>;
  return null;
}

function Stars({ value, onChange, size = 32 }: { value: number; onChange?: (v: number) => void; size?: number }) {
  return (
    <div className="flex gap-1" role={onChange ? "radiogroup" : undefined}>
      {[1, 2, 3, 4, 5].map((n) => {
        const icon = <Star size={size} aria-hidden className={n <= Math.round(value) ? "fill-accent text-accent" : "text-mist"} />;
        return onChange ? (
          <button key={n} type="button" role="radio" aria-checked={n === value} aria-label={String(n)} onClick={() => onChange(n)} className="p-0.5">
            {icon}
          </button>
        ) : (
          <span key={n}>{icon}</span>
        );
      })}
    </div>
  );
}

/** Ikki tomonlama yashirin baho: qarshi tomon ham baholagach yoki 48 soatdan keyin ochiladi (TZ 13) */
export function ReviewBox({ assignmentId, target }: { assignmentId: number; target: "worker" | "employer" }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const errorText = useErrorText();
  const key = ["reviews", assignmentId];
  const reviews = useQuery({ queryKey: key, queryFn: () => api<Reviews>(`/assignments/${assignmentId}/reviews`) });
  const [rating, setRating] = useState(0);
  const [tags, setTags] = useState<string[]>([]);
  const [comment, setComment] = useState("");
  const send = useMutation({
    mutationFn: () => api<Reviews>(`/assignments/${assignmentId}/review`, { body: { rating, tags, comment: comment.trim() || null } }),
    onSuccess: (data) => {
      haptic("success");
      qc.setQueryData(key, data);
    },
  });

  if (!reviews.data) return null;
  const theirs = reviews.data.visible.find((r) => !r.mine && !r.is_auto);
  if (reviews.data.reviewed_by_me) {
    return (
      <div className="space-y-2">
        <Hint icon={CheckCircle2}>{t("rv.thanks")}</Hint>
        {theirs && (
          <div className="rounded-xl bg-white p-3">
            <p className="mb-1 text-xs text-muted">{t("rv.their")}</p>
            <Stars value={theirs.rating} size={18} />
            {theirs.comment && <p className="mt-1 text-sm">{theirs.comment}</p>}
          </div>
        )}
      </div>
    );
  }
  const options = target === "worker" ? WORKER_TAGS : EMPLOYER_TAGS;
  const toggle = (tag: string) => setTags((cur) => (cur.includes(tag) ? cur.filter((x) => x !== tag) : [...cur, tag]));
  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold">{t(target === "worker" ? "rv.worker" : "rv.employer")}</p>
      <Stars value={rating} onChange={setRating} />
      <div className="flex flex-wrap gap-2">
        {options.map((tag) => (
          <Chip key={tag} active={tags.includes(tag)} onClick={() => toggle(tag)}>
            {t(`tag.${tag}` as MsgKey)}
          </Chip>
        ))}
      </div>
      <Textarea value={comment} maxLength={300} placeholder={t("rv.comment")} onChange={(e) => setComment(e.target.value)} />
      <ErrorBox message={errorText(send.error)} />
      <Button disabled={!rating} loading={send.isPending} onClick={() => send.mutate()}>
        {t("rv.send")}
      </Button>
    </div>
  );
}
