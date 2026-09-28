import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useNavigate, useParams } from "react-router";

import { useErrorText } from "../../components/shared";
import { Button, Card, Checkbox, Chip, cx, Empty, ErrorBox, Field, Input, Select, Spinner, Tag, Textarea } from "../../components/ui";
import { adminToken, api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useCatalog } from "../../lib/catalog";
import { dateTime, phonePretty } from "../../lib/format";
import type { Me } from "../../lib/types";
import {
  BUSINESS_REJECT_REASONS,
  type BusinessQueueItem,
  type CaseOut,
  FILE_LABELS,
  type QueueItem,
  REJECT_REASONS,
} from "./types";

// Admin panel faqat o'zbek (lotin) tilida — foydalanuvchilar: asoschi va moderatorlar
const STAFF = ["moderator", "admin", "super_admin"];
const STATUS_LABEL: Record<string, string> = {
  not_submitted: "To'ldirilmagan",
  pending: "Tekshiruvda",
  verified: "Tasdiqlangan",
  rejected: "Rad etilgan",
  expired: "Muddati o'tgan",
};
const EXPERIENCE: Record<string, string> = { none: "tajribasiz", "1_2": "1–2 yil", "3_5": "3–5 yil", "5_plus": "5+ yil" };

/** Kirish: SMS/Telegram (oddiy) → xodim roli → TOTP kodi (TZ 3) */
export function AdminGate() {
  const { me, loading } = useAuth();
  const [, force] = useState(0);
  if (loading) return <Spinner />;
  if (!me) return <Navigate to="/login?next=/admin" replace />;
  if (!me.roles.some((r) => STAFF.includes(r))) return <Navigate to="/" replace />;
  if (!adminToken.get()) return <TotpScreen onDone={() => force((n) => n + 1)} />;
  return <AdminLayout />;
}

function TotpScreen({ onDone }: { onDone: () => void }) {
  const [code, setCode] = useState("");
  const errorText = useErrorText();
  const verify = useMutation({
    mutationFn: () => api<{ access_token: string }>("/admin/auth/totp", { body: { code } }),
    onSuccess: (r) => {
      adminToken.set(r.access_token);
      onDone();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    verify.mutate();
  };
  return (
    <div className="flex min-h-screen items-center justify-center bg-midnight p-4">
      <img src="/backgrounds/12_dark_future_1080.webp" alt="" className="absolute inset-0 h-full w-full object-cover opacity-50" />
      <form onSubmit={submit} className="relative w-full max-w-sm space-y-4 rounded-2xl bg-white p-6">
        <img src="/brand/logo_320.webp" alt="Workly" className="mx-auto h-9" />
        <p className="text-center font-semibold">Admin panel</p>
        <p className="text-center text-sm text-muted">Authenticator ilovasidagi 6 xonali kodni kiriting</p>
        <Input
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          className="text-center text-2xl tracking-[0.5em]"
          aria-label="TOTP kod"
          autoFocus
        />
        <ErrorBox message={errorText(verify.error)} />
        <Button type="submit" disabled={code.length !== 6} loading={verify.isPending}>
          Kirish
        </Button>
      </form>
    </div>
  );
}

function AdminLayout() {
  const me = useQuery({ queryKey: ["admin", "me"], queryFn: () => api<Me>("/admin/me", { admin: true }) });
  const navigate = useNavigate();
  const link = (to: string, label: string) => (
    <NavLink
      to={to}
      className={({ isActive }) => cx("block rounded-xl px-4 py-3 font-medium", isActive ? "bg-brand text-white" : "hover:bg-snow")}
    >
      {label}
    </NavLink>
  );
  if (me.error) {
    adminToken.clear();
    return <Navigate to="/admin" replace />;
  }
  return (
    <div className="min-h-screen bg-snow md:flex">
      <aside className="border-b border-mist bg-white p-4 md:min-h-screen md:w-64 md:border-b-0 md:border-r">
        <img src="/brand/logo_320.webp" alt="Workly" className="h-8" />
        <p className="mt-1 text-xs text-muted">Admin panel</p>
        <nav className="mt-6 flex gap-2 md:block md:space-y-1">
          {link("/admin/verifications", "Verifikatsiya")}
          {link("/admin/businesses", "Bizneslar")}
        </nav>
        <div className="mt-6 hidden text-sm md:block">
          <p className="font-medium">{me.data?.full_name ?? (me.data?.phone && phonePretty(me.data.phone))}</p>
          <p className="text-muted">{me.data?.roles.filter((r) => STAFF.includes(r)).join(", ")}</p>
          <button
            className="mt-3 text-danger"
            onClick={() => {
              adminToken.clear();
              navigate("/");
            }}
          >
            Paneldan chiqish
          </button>
        </div>
      </aside>
      <main className="flex-1 p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}

// ---------------- Verifikatsiya ----------------
export function VerificationQueue() {
  const [status, setStatus] = useState("pending");
  const queue = useQuery({
    queryKey: ["admin", "verifications", status],
    queryFn: () => api<QueueItem[]>(`/admin/verifications?status=${status}`, { admin: true }),
    refetchInterval: 30_000,
  });
  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold">Verifikatsiya navbati</h1>
      <p className="text-sm text-muted">SLA: 24 soat (TZ 16). Eng eskisi birinchi.</p>
      <div className="mt-4 flex gap-2">
        {[
          ["pending", "Kutilmoqda"],
          ["rejected", "Rad etilgan"],
          ["verified", "Tasdiqlangan"],
        ].map(([s, label]) => (
          <Chip key={s} active={status === s} onClick={() => setStatus(s)}>
            {label}
          </Chip>
        ))}
      </div>
      <div className="mt-4 space-y-2">
        {queue.isLoading && <Spinner />}
        {queue.data?.length === 0 && <Empty text="Navbat bo'sh" />}
        {queue.data?.map((q) => (
          <Link key={q.user_id} to={`/admin/verifications/${q.user_id}`} className="block">
            <Card className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold">{q.full_name ?? `#${q.user_id}`}</p>
                <p className="text-sm text-muted">
                  #{q.user_id} · {q.age ?? "?"} yosh · {q.submitted_at ? dateTime(q.submitted_at) : "—"}
                </p>
              </div>
              {q.duplicate_of_user_id && <Tag tone="danger">⚠ Takroriy hujjat: #{q.duplicate_of_user_id}</Tag>}
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function VerificationCase() {
  const { id } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const catalog = useCatalog();
  const errorText = useErrorText();
  const [badges, setBadges] = useState<string[]>([]);
  const [reason, setReason] = useState("blurry");
  const [comment, setComment] = useState("");
  // Har ochilish audit jurnaliga yoziladi — keraksiz qayta so'ramaymiz
  const data = useQuery({
    queryKey: ["admin", "case", id],
    queryFn: () => api<CaseOut>(`/admin/verifications/${id}`, { admin: true }),
    staleTime: 4 * 60_000,
    refetchOnWindowFocus: false,
  });
  const done = () => {
    qc.invalidateQueries({ queryKey: ["admin", "verifications"] });
    navigate("/admin/verifications");
  };
  const approve = useMutation({
    mutationFn: () => api(`/admin/verifications/${id}/approve`, { admin: true, body: { badges } }),
    onSuccess: done,
  });
  const reject = useMutation({
    mutationFn: () => api(`/admin/verifications/${id}/reject`, { admin: true, body: { reason, comment: comment || null } }),
    onSuccess: done,
  });

  if (data.isLoading) return <Spinner />;
  const c = data.data;
  if (!c) return <ErrorBox message={errorText(data.error)} />;
  const p = c.profile;
  const kinds = new Set(c.files.map((f) => f.kind));
  const pending = p.verification.status === "pending";

  return (
    <div className="max-w-5xl">
      <Link to="/admin/verifications" className="text-sm text-brand">
        ← Navbat
      </Link>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">{p.full_name ?? `#${p.user_id}`}</h1>
        <Tag tone={pending ? "brand" : "muted"}>{STATUS_LABEL[p.verification.status] ?? p.verification.status}</Tag>
        {c.duplicate_of_user_id && <Tag tone="danger">⚠ Shu hujjat bilan akkaunt bor: #{c.duplicate_of_user_id}</Tag>}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Card className="space-y-2 text-sm">
          <Row label="Familiya / Ism / Otasining ismi" value={[p.last_name, p.first_name, p.middle_name].filter(Boolean).join(" ")} />
          <Row label="Tug'ilgan sana" value={p.birth_date} />
          <Row label="Jins" value={p.gender === "male" ? "Erkak" : p.gender === "female" ? "Ayol" : null} />
          <Row label="Telefon" value={c.phone && phonePretty(c.phone)} />
          <Row label="Hujjat raqami" value={c.doc_number} strong />
          <Row label="Tumanlar" value={p.district_ids.map((d) => catalog.district(d)?.name.uz_latn).join(", ")} />
          <div>
            <p className="text-muted">Ko'nikmalar</p>
            {p.skills.map((s) => (
              <p key={s.category_id}>
                <b>{catalog.category(s.category_id)?.name.uz_latn}</b> ({EXPERIENCE[s.experience]}):{" "}
                {s.specialization_ids.map((x) => catalog.specialization(x)?.name.uz_latn).join(", ")}
              </p>
            ))}
          </div>
          <p className="pt-2 text-xs text-muted">
            Tekshiring: selfie va hujjatdagi yuz bir odammi, yosh (18+), hujjat muddati, ism mosligi.
          </p>
        </Card>

        <div className="grid grid-cols-2 gap-3">
          {c.files.map((f) => (
            <a key={f.id} href={f.url} target="_blank" rel="noreferrer" className="block">
              <Card className="p-2">
                {f.content_type === "application/pdf" ? (
                  <div className="flex h-40 items-center justify-center text-4xl">📄</div>
                ) : (
                  <img src={f.url} alt={FILE_LABELS[f.kind] ?? f.kind} className="h-40 w-full rounded-lg object-cover" />
                )}
                <p className="mt-2 text-center text-xs font-medium">{FILE_LABELS[f.kind] ?? f.kind}</p>
              </Card>
            </a>
          ))}
          <p className="col-span-2 text-xs text-muted">Havolalar 5 daqiqa amal qiladi; har ko'rish audit jurnaliga yozilgan.</p>
        </div>
      </div>

      {pending && (
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <Card className="space-y-3">
            <p className="font-semibold">Tasdiqlash</p>
            <Checkbox
              checked={badges.includes("qualified")}
              onChange={(v) => setBadges((b) => (v ? [...b, "qualified"] : b.filter((x) => x !== "qualified")))}
            >
              "Tasdiqlangan malaka" {!kinds.has("qualification") && <span className="text-muted">(guvohnoma yuklanmagan)</span>}
            </Checkbox>
            <Checkbox
              checked={badges.includes("background_checked")}
              onChange={(v) =>
                setBadges((b) => (v ? [...b, "background_checked"] : b.filter((x) => x !== "background_checked")))
              }
            >
              "Tekshirilgan" {!kinds.has("criminal_record") && <span className="text-muted">(ma'lumotnoma yo'q)</span>}
            </Checkbox>
            <ErrorBox message={errorText(approve.error)} />
            <Button onClick={() => approve.mutate()} loading={approve.isPending}>
              ✓ Tasdiqlash
            </Button>
          </Card>
          <Card className="space-y-3">
            <p className="font-semibold">Rad etish</p>
            <Field label="Sabab">
              <Select value={reason} onChange={(e) => setReason(e.target.value)}>
                {REJECT_REASONS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Izoh (ishchiga ko'rinadi)">
              <Textarea maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} />
            </Field>
            <ErrorBox message={errorText(reject.error)} />
            <Button variant="danger" onClick={() => reject.mutate()} loading={reject.isPending}>
              Rad etish
            </Button>
          </Card>
        </div>
      )}
    </div>
  );
}

// ---------------- Bizneslar ----------------
export function BusinessQueue() {
  const qc = useQueryClient();
  const errorText = useErrorText();
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [reason, setReason] = useState("stir_invalid");
  const [comment, setComment] = useState("");
  const queue = useQuery({
    queryKey: ["admin", "businesses"],
    queryFn: () => api<BusinessQueueItem[]>("/admin/employers", { admin: true }),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin", "businesses"] });
  const approve = useMutation({
    mutationFn: (id: number) => api(`/admin/employers/${id}/approve`, { admin: true, method: "POST" }),
    onSuccess: refresh,
  });
  const reject = useMutation({
    mutationFn: (id: number) => api(`/admin/employers/${id}/reject`, { admin: true, body: { reason, comment: comment || null } }),
    onSuccess: () => {
      setRejecting(null);
      setComment("");
      refresh();
    },
  });
  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold">Biznes (STIR) tekshiruvi</h1>
      <p className="text-sm text-muted">STIR'ni soliq.uz orqali tekshiring; nom va faoliyat mosligini solishtiring.</p>
      <ErrorBox message={errorText(approve.error ?? reject.error)} />
      <div className="mt-4 space-y-3">
        {queue.isLoading && <Spinner />}
        {queue.data?.length === 0 && <Empty text="Navbat bo'sh" />}
        {queue.data?.map((b) => (
          <Card key={b.user_id} className="space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-semibold">{b.company_name}</p>
                <p className="text-sm">
                  STIR: <b>{b.stir}</b> · {b.responsible} · {b.phone && phonePretty(b.phone)}
                </p>
                <p className="text-xs text-muted">{b.submitted_at && dateTime(b.submitted_at)}</p>
              </div>
              {b.same_stir_user_ids.length > 0 && <Tag tone="accent">Shu STIR: #{b.same_stir_user_ids.join(", #")}</Tag>}
            </div>
            {rejecting === b.user_id ? (
              <div className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                <Select value={reason} onChange={(e) => setReason(e.target.value)}>
                  {BUSINESS_REJECT_REASONS.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </Select>
                <Input placeholder="Izoh" value={comment} onChange={(e) => setComment(e.target.value)} />
                <Button variant="danger" className="md:w-40" onClick={() => reject.mutate(b.user_id)} loading={reject.isPending}>
                  Rad etish
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2 md:w-96">
                <Button variant="secondary" onClick={() => setRejecting(b.user_id)}>
                  Rad etish…
                </Button>
                <Button onClick={() => approve.mutate(b.user_id)} loading={approve.isPending && approve.variables === b.user_id}>
                  ✓ Tasdiqlash
                </Button>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}

function Row({ label, value, strong }: { label: string; value: string | null | undefined; strong?: boolean }) {
  return (
    <div>
      <p className="text-muted">{label}</p>
      <p className={strong ? "text-base font-bold" : ""}>{value || "—"}</p>
    </div>
  );
}
