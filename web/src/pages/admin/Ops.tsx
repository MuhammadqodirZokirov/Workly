import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, CircleAlert, Phone, PhoneCall, RotateCcw, Search, UserPlus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router";

import { useErrorText } from "../../components/shared";
import { Button, Card, Checkbox, Chip, Empty, ErrorBox, Field, Input, Select, Spinner, Tag, Textarea } from "../../components/ui";
import { api } from "../../lib/api";
import { useCatalog } from "../../lib/catalog";
import { dateTime, money, phonePretty } from "../../lib/format";
import type { Order } from "../../lib/types";

// Admin panel o'zbek (lotin) tilida — TZ 16
const ORDER_STATUS: Record<string, string> = {
  pending_approval: "Tasdiq kutmoqda",
  matching: "Izlanmoqda",
  partially_assigned: "Qisman to'ldi",
  assigned: "Tayinlandi",
  in_progress: "Ishlanmoqda",
  completed: "Tugadi",
  cancelled: "Bekor qilindi",
  expired: "Muddati o'tdi",
};
const SLOT_STATUS: Record<string, string> = {
  open: "Izlanmoqda",
  assigned: "Tayinlangan",
  arrived: "Joyida",
  working: "Ishlamoqda",
  finished: "Tugatdi",
  confirmed: "Tasdiqlangan",
  disputed: "Nizo",
  no_show: "Kelmadi",
  replaced: "Almashtirildi",
  cancelled: "Bekor",
};

interface Board {
  date: string;
  orders: Record<string, number>;
  assignments: Record<string, number>;
  pending: Record<string, number>;
  call_queue: {
    assignment_id: number;
    order_id: number;
    starts_at: string;
    minutes_late: number;
    worker_name: string | null;
    worker_phone: string | null;
    employer_phone: string | null;
    address_text: string;
  }[];
  problems: { assignment_id: number; order_id: number; worker_name: string | null; problem: string | null; since: string | null }[];
  unfilled: number[];
}

interface AdminOrder {
  order: Order;
  employer_id: number;
  employer_phone: string | null;
  cancel_reason: string | null;
  timeline: { object_type: string; object_id: number; from_state: string | null; to_state: string; actor_id: number | null; reason: string | null; created_at: string }[];
}

interface AdminUser {
  id: number;
  phone: string | null;
  full_name: string | null;
  status: string;
  roles: string[];
  created_at: string;
  worker_status: string | null;
  worker_reliability: number | null;
  employer_reliability: number | null;
}

const admin = { admin: true } as const;

function Stat({ label, value, tone }: { label: string; value: number; tone?: "danger" | "accent" }) {
  return (
    <Card className="min-w-0">
      <p className="truncate text-xs text-muted">{label}</p>
      <p className={`text-2xl font-bold ${tone === "danger" && value ? "text-danger" : tone === "accent" && value ? "text-accent" : ""}`}>{value}</p>
    </Card>
  );
}

// ---------------- Operatsiya taxtasi ----------------
export function OpsBoard() {
  const qc = useQueryClient();
  const errorText = useErrorText();
  const board = useQuery({ queryKey: ["admin", "board"], queryFn: () => api<Board>("/admin/ops/board", admin), refetchInterval: 30_000 });
  const [notes, setNotes] = useState<Record<number, string>>({});
  const called = useMutation({
    mutationFn: (id: number) => api(`/admin/ops/calls/${id}`, { ...admin, body: { note: notes[id] || null } }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["admin", "board"] }),
  });
  const b = board.data;
  if (board.isLoading) return <Spinner />;
  if (!b) return <ErrorBox message={errorText(board.error)} />;
  const sum = (o: Record<string, number>, keys: string[]) => keys.reduce((s, k) => s + (o[k] ?? 0), 0);

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Operatsiya taxtasi</h1>
        <p className="text-sm text-muted">{b.date} · har 30 soniyada yangilanadi</p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Bugungi buyurtmalar" value={Object.values(b.orders).reduce((s, n) => s + n, 0)} />
        <Stat label="Ishchilar joyida / ishlamoqda" value={sum(b.assignments, ["arrived", "working"])} />
        <Stat label="Hali kelmagan" value={b.assignments.assigned ?? 0} tone="accent" />
        <Stat label="Kelmadi" value={b.assignments.no_show ?? 0} tone="danger" />
        <Stat label="Qo'ng'iroq navbati" value={b.call_queue.length} tone="danger" />
        <Stat label="Nizolar" value={b.pending.disputes ?? 0} tone="danger" />
        <Stat label="Verifikatsiya kutmoqda" value={b.pending.verifications ?? 0} tone="accent" />
        <Stat label="Tasdiq kutayotgan buyurtma" value={b.pending.orders_approval ?? 0} tone="accent" />
      </div>

      <section>
        <h2 className="mb-2 flex items-center gap-2 text-lg font-bold">
          <PhoneCall size={20} aria-hidden /> Qo'ng'iroq navbati (T+30)
        </h2>
        <p className="mb-3 text-sm text-muted">SLA: 10 daqiqa ichida ishchi va ish beruvchiga qo'ng'iroq.</p>
        <ErrorBox message={errorText(called.error)} />
        {b.call_queue.length === 0 && <Empty text="Navbat bo'sh" />}
        <div className="space-y-2">
          {b.call_queue.map((c) => (
            <Card key={c.assignment_id} className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <Link to={`/admin/orders/${c.order_id}`} className="font-semibold text-brand">
                    Buyurtma #{c.order_id}
                  </Link>
                  <p className="text-sm text-muted">{dateTime(c.starts_at)} · {c.address_text}</p>
                </div>
                <Tag tone="danger">{c.minutes_late} daqiqa kechikdi</Tag>
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                {c.worker_phone && (
                  <a href={`tel:${c.worker_phone}`} className="flex items-center gap-2 rounded-xl bg-snow p-3 text-sm">
                    <Phone size={16} aria-hidden /> Ishchi: {c.worker_name} · {phonePretty(c.worker_phone)}
                  </a>
                )}
                {c.employer_phone && (
                  <a href={`tel:${c.employer_phone}`} className="flex items-center gap-2 rounded-xl bg-snow p-3 text-sm">
                    <Phone size={16} aria-hidden /> Ish beruvchi: {phonePretty(c.employer_phone)}
                  </a>
                )}
              </div>
              <div className="grid grid-cols-[1fr_auto] gap-2">
                <Input
                  placeholder="Natija (masalan: yo'lda, 10 daqiqada yetadi)"
                  value={notes[c.assignment_id] ?? ""}
                  onChange={(e) => setNotes((n) => ({ ...n, [c.assignment_id]: e.target.value }))}
                />
                <Button className="px-5" loading={called.isPending && called.variables === c.assignment_id} onClick={() => called.mutate(c.assignment_id)}>
                  Qo'ng'iroq qilindi
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-2 flex items-center gap-2 text-lg font-bold">
          <CircleAlert size={20} aria-hidden /> Nizo va muammolar
        </h2>
        {b.problems.length === 0 && <Empty text="Ochiq nizo yo'q" />}
        <div className="space-y-2">
          {b.problems.map((p) => (
            <Link key={p.assignment_id} to={`/admin/orders/${p.order_id}`} className="block">
              <Card className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-semibold">Buyurtma #{p.order_id} · {p.worker_name ?? "—"}</p>
                  <p className="text-sm text-muted">{p.problem ?? "—"}</p>
                </div>
                {p.since && <span className="shrink-0 text-xs text-muted">{dateTime(p.since)}</span>}
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {b.unfilled.length > 0 && (
        <section>
          <h2 className="mb-2 text-lg font-bold">3 to'lqindan keyin to'lmagan</h2>
          <div className="flex flex-wrap gap-2">
            {b.unfilled.map((id) => (
              <Link key={id} to={`/admin/orders/${id}`}>
                <Tag tone="accent">#{id}</Tag>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ---------------- Buyurtmalar ----------------
export function AdminOrders() {
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const catalog = useCatalog();
  const params = new URLSearchParams();
  if (search) params.set("q", search);
  if (status) params.set("status", status);
  const orders = useQuery({ queryKey: ["admin", "orders", search, status], queryFn: () => api<Order[]>(`/admin/orders?${params}`, admin) });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setSearch(q.trim());
  };
  return (
    <div className="max-w-5xl space-y-4">
      <h1 className="text-2xl font-bold">Buyurtmalar</h1>
      <form onSubmit={submit} className="grid grid-cols-[1fr_auto] gap-2">
        <Input placeholder="#raqam yoki telefon" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" className="px-5" aria-label="Qidirish">
          <Search size={18} aria-hidden />
        </Button>
      </form>
      <div className="flex flex-wrap gap-2">
        <Chip active={!status} onClick={() => setStatus("")}>Hammasi</Chip>
        {Object.entries(ORDER_STATUS).map(([s, label]) => (
          <Chip key={s} active={status === s} onClick={() => setStatus(s)}>
            {label}
          </Chip>
        ))}
      </div>
      {orders.isLoading && <Spinner />}
      {orders.data?.length === 0 && <Empty text="Topilmadi" />}
      <div className="space-y-2">
        {orders.data?.map((o) => {
          const filled = o.assignments.filter((a) => a.worker_id && !["cancelled", "replaced", "no_show"].includes(a.status)).length;
          return (
            <Link key={o.id} to={`/admin/orders/${o.id}`} className="block">
              <Card className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold">
                    #{o.id} · {catalog.specialization(o.specialization_id)?.name.uz_latn ?? ""}
                  </p>
                  <p className="truncate text-sm text-muted">
                    {dateTime(o.starts_at)} · {filled}/{o.workers} ishchi · {money(o.price.employer_total)} so'm
                  </p>
                </div>
                <Tag tone="brand">{ORDER_STATUS[o.status] ?? o.status}</Tag>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export function AdminOrderDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const errorText = useErrorText();
  const catalog = useCatalog();
  const data = useQuery({ queryKey: ["admin", "order", id], queryFn: () => api<AdminOrder>(`/admin/orders/${id}`, admin) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin"] });
  const [cancelReason, setCancelReason] = useState("");
  const [workerId, setWorkerId] = useState("");
  const cancel = useMutation({ mutationFn: () => api(`/admin/orders/${id}/cancel`, { ...admin, body: { reason: cancelReason } }), onSuccess: refresh });
  const assign = useMutation({
    mutationFn: () => api(`/admin/orders/${id}/assign`, { ...admin, body: { worker_id: Number(workerId) } }),
    onSuccess: () => {
      setWorkerId("");
      refresh();
    },
  });
  if (data.isLoading) return <Spinner />;
  const d = data.data;
  if (!d) return <ErrorBox message={errorText(data.error)} />;
  const o = d.order;
  const active = ["pending_approval", "matching", "partially_assigned", "assigned", "in_progress"].includes(o.status);
  const hasOpen = o.assignments.some((a) => a.status === "open");

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Buyurtma #{o.id}</h1>
        <Tag tone="brand">{ORDER_STATUS[o.status] ?? o.status}</Tag>
      </div>
      <Card className="grid gap-2 text-sm md:grid-cols-2">
        <p><b>Ish:</b> {catalog.specialization(o.specialization_id)?.name.uz_latn} · {o.workers} ishchi</p>
        <p><b>Vaqt:</b> {dateTime(o.starts_at)}</p>
        <p><b>Manzil:</b> {o.address_text}</p>
        <p><b>Summa:</b> {money(o.price.employer_total)} so'm ({money(o.price.worker_price)} × {o.price.workers} × {o.price.days})</p>
        <p>
          <b>Ish beruvchi:</b> #{d.employer_id} {d.employer_phone && <a className="text-brand" href={`tel:${d.employer_phone}`}>{phonePretty(d.employer_phone)}</a>}
        </p>
        {d.cancel_reason && <p><b>Bekor sababi:</b> {d.cancel_reason}</p>}
      </Card>

      <section className="space-y-2">
        <h2 className="text-lg font-bold">Ishchilar</h2>
        {o.assignments.map((a) => (
          <Card key={a.id} className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium">
                #{a.slot_no} · {a.worker_name ?? "—"} {a.worker_phone && <a className="text-brand" href={`tel:${a.worker_phone}`}>{phonePretty(a.worker_phone)}</a>}
              </p>
              <Tag tone={a.status === "disputed" || a.status === "no_show" ? "danger" : "brand"}>{SLOT_STATUS[a.status] ?? a.status}</Tag>
            </div>
            {a.problem && <p className="rounded-xl bg-red-50 p-3 text-sm text-danger">{a.problem}</p>}
            {a.status === "disputed" && <ResolveForm assignmentId={a.id} onDone={refresh} />}
          </Card>
        ))}
      </section>

      {active && (
        <section className="grid gap-4 md:grid-cols-2">
          {hasOpen && (
            <Card className="space-y-3">
              <p className="flex items-center gap-2 font-semibold"><UserPlus size={18} aria-hidden /> Qo'lda tayinlash</p>
              <Input inputMode="numeric" placeholder="Ishchi ID" value={workerId} onChange={(e) => setWorkerId(e.target.value.replace(/\D/g, ""))} />
              <ErrorBox message={errorText(assign.error)} />
              <Button disabled={!workerId} loading={assign.isPending} onClick={() => assign.mutate()}>Tayinlash</Button>
            </Card>
          )}
          <Card className="space-y-3">
            <p className="font-semibold text-danger">Admin bekor qilishi (jarimasiz)</p>
            <Textarea placeholder="Sabab (kamida 10 belgi)" value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} />
            <ErrorBox message={errorText(cancel.error)} />
            <Button variant="danger" disabled={cancelReason.trim().length < 10} loading={cancel.isPending} onClick={() => cancel.mutate()}>
              Bekor qilish
            </Button>
          </Card>
        </section>
      )}

      <section>
        <h2 className="mb-2 text-lg font-bold">Vaqt chizig'i</h2>
        <Card className="space-y-1 text-sm">
          {d.timeline.map((t, i) => (
            <p key={i} className="flex flex-wrap gap-x-2">
              <span className="text-muted">{dateTime(t.created_at)}</span>
              <span>
                {t.object_type === "order" ? "Buyurtma" : `Slot ${t.object_id}`}: {t.from_state ?? "—"} → <b>{t.to_state}</b>
              </span>
              {t.actor_id && <span className="text-muted">#{t.actor_id}</span>}
              {t.reason && <span className="text-muted">({t.reason})</span>}
            </p>
          ))}
        </Card>
      </section>
    </div>
  );
}

function ResolveForm({ assignmentId, onDone }: { assignmentId: number; onDone: () => void }) {
  const errorText = useErrorText();
  const [confirm, setConfirm] = useState(true);
  const [reason, setReason] = useState("");
  const [unfounded, setUnfounded] = useState("");
  const resolve = useMutation({
    mutationFn: () => api(`/admin/assignments/${assignmentId}/resolve`, { ...admin, body: { confirm, reason, unfounded: unfounded || null } }),
    onSuccess: onDone,
  });
  return (
    <div className="space-y-3 rounded-xl border border-mist p-3">
      <p className="font-semibold">Nizo qarori</p>
      <div className="flex flex-wrap gap-2">
        <Chip active={confirm} onClick={() => setConfirm(true)}>Ish bajarilgan</Chip>
        <Chip active={!confirm} onClick={() => setConfirm(false)}>Ish hisoblanmaydi</Chip>
      </div>
      <Field label="Asossiz nizo ochgan tomon (−10 Ishonchlilik)">
        <Select value={unfounded} onChange={(e) => setUnfounded(e.target.value)}>
          <option value="">Yo'q</option>
          <option value="employer">Ish beruvchi</option>
          <option value="worker">Ishchi</option>
        </Select>
      </Field>
      <Textarea placeholder="Qaror sababi (kamida 10 belgi) — ikkala tomonga ko'rinadi" value={reason} onChange={(e) => setReason(e.target.value)} />
      <ErrorBox message={errorText(resolve.error)} />
      <Button disabled={reason.trim().length < 10} loading={resolve.isPending} onClick={() => resolve.mutate()}>
        Qarorni saqlash
      </Button>
    </div>
  );
}

// ---------------- Foydalanuvchilar ----------------
export function AdminUsers() {
  const qc = useQueryClient();
  const errorText = useErrorText();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const users = useQuery({
    queryKey: ["admin", "users", search],
    queryFn: () => api<AdminUser[]>(`/admin/users?q=${encodeURIComponent(search)}`, admin),
    enabled: search.length > 0,
  });
  const toggle = useMutation({
    mutationFn: (u: AdminUser) =>
      api(`/admin/users/${u.id}/${u.status === "blocked" ? "unblock" : "block"}`, { ...admin, body: { reason: reasons[u.id] ?? "" } }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
  return (
    <div className="max-w-4xl space-y-4">
      <h1 className="text-2xl font-bold">Foydalanuvchilar</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setSearch(q.trim());
        }}
        className="grid grid-cols-[1fr_auto] gap-2"
      >
        <Input placeholder="Telefon, ism yoki ID" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" className="px-5" aria-label="Qidirish">
          <Search size={18} aria-hidden />
        </Button>
      </form>
      <ErrorBox message={errorText(toggle.error ?? users.error)} />
      {users.data?.length === 0 && <Empty text="Topilmadi" />}
      <div className="space-y-2">
        {users.data?.map((u) => (
          <Card key={u.id} className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold">#{u.id} · {u.full_name ?? "—"}</p>
                <p className="text-sm text-muted">
                  {u.phone ? phonePretty(u.phone) : "—"} · {u.roles.join(", ") || "rol yo'q"}
                  {u.worker_reliability !== null && ` · ishchi ishonchliligi ${u.worker_reliability}`}
                  {u.employer_reliability !== null && ` · employer ishonchliligi ${u.employer_reliability}`}
                </p>
              </div>
              <Tag tone={u.status === "blocked" ? "danger" : "success"}>{u.status === "blocked" ? "Bloklangan" : "Faol"}</Tag>
            </div>
            <div className="grid grid-cols-[1fr_auto] gap-2">
              <Input
                placeholder="Sabab (kamida 10 belgi)"
                value={reasons[u.id] ?? ""}
                onChange={(e) => setReasons((r) => ({ ...r, [u.id]: e.target.value }))}
              />
              <Button
                variant={u.status === "blocked" ? "secondary" : "danger"}
                className="px-5"
                disabled={(reasons[u.id] ?? "").trim().length < 10}
                loading={toggle.isPending && toggle.variables?.id === u.id}
                onClick={() => toggle.mutate(u)}
              >
                {u.status === "blocked" ? <><RotateCcw size={16} aria-hidden /> Blokdan chiqarish</> : <><Ban size={16} aria-hidden /> Bloklash</>}
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ---------------- Narxlar ----------------
interface PriceRow {
  id: number;
  category_id: number;
  specialization_id: number | null;
  unit: string;
  base: number;
  min_price: number;
  max_price: number;
  min_order_amount: number;
  active_from: string;
}

const UNITS: Record<string, string> = { day: "kun", hour: "soat", m2: "m²", guest: "kishi" };

export function AdminPrices() {
  const qc = useQueryClient();
  const catalog = useCatalog();
  const errorText = useErrorText();
  const prices = useQuery({ queryKey: ["admin", "prices"], queryFn: () => api<PriceRow[]>("/admin/prices", admin) });
  const [edit, setEdit] = useState<PriceRow | null>(null);
  const [manual, setManual] = useState(false);
  const save = useMutation({
    mutationFn: (p: PriceRow) =>
      api("/admin/prices", {
        ...admin,
        body: {
          category_id: p.category_id,
          specialization_id: p.specialization_id,
          unit: p.unit,
          base: p.base,
          min_price: manual ? p.min_price : null,
          max_price: manual ? p.max_price : null,
          min_order_amount: p.min_order_amount,
        },
      }),
    onSuccess: () => {
      setEdit(null);
      qc.invalidateQueries({ queryKey: ["admin", "prices"] });
    },
  });
  const name = (p: PriceRow) =>
    (p.specialization_id ? catalog.specialization(p.specialization_id)?.name.uz_latn : catalog.category(p.category_id)?.name.uz_latn) ?? `Kategoriya #${p.category_id} (o'chirilgan)`;
  const num = (v: string) => Number(v.replace(/\D/g, "")) || 0;

  return (
    <div className="max-w-4xl space-y-4">
      <h1 className="text-2xl font-bold">Narxlar</h1>
      <p className="text-sm text-muted">Har o'zgarish yangi versiya bo'ladi va faqat yangi buyurtmalarga ta'sir qiladi (TZ 8). Min/max — avtomatik ×0.75 va ×2.</p>
      {prices.isLoading && <Spinner />}
      <div className="space-y-2">
        {prices.data?.map((p) => (
          <Card key={p.id} className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold">{name(p)}{!p.specialization_id && <span className="text-muted"> (kategoriya)</span>}</p>
                <p className="text-sm text-muted">
                  {money(p.base)} so'm / {UNITS[p.unit] ?? p.unit} · {money(p.min_price)}–{money(p.max_price)} · {dateTime(p.active_from)} dan
                </p>
              </div>
              <Button variant="secondary" className="w-auto" onClick={() => { setEdit(p); setManual(false); }}>
                O'zgartirish
              </Button>
            </div>
            {edit?.id === p.id && (
              <div className="space-y-3 rounded-xl border border-mist p-3">
                <div className="grid gap-3 md:grid-cols-2">
                  <Field label="Bazaviy narx (so'm)">
                    <Input inputMode="numeric" value={String(edit.base)} onChange={(e) => setEdit({ ...edit, base: num(e.target.value) })} />
                  </Field>
                  <Field label="Eng kam buyurtma summasi">
                    <Input inputMode="numeric" value={String(edit.min_order_amount)} onChange={(e) => setEdit({ ...edit, min_order_amount: num(e.target.value) })} />
                  </Field>
                </div>
                <Checkbox checked={manual} onChange={setManual}>Min/max ni qo'lda kiritish</Checkbox>
                {manual && (
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Min">
                      <Input inputMode="numeric" value={String(edit.min_price)} onChange={(e) => setEdit({ ...edit, min_price: num(e.target.value) })} />
                    </Field>
                    <Field label="Max">
                      <Input inputMode="numeric" value={String(edit.max_price)} onChange={(e) => setEdit({ ...edit, max_price: num(e.target.value) })} />
                    </Field>
                  </div>
                )}
                <p className="text-sm">
                  Saqlaysizmi? <b>{money(edit.base)} so'm</b>
                  {!manual && ` · min ${money(Math.round(edit.base * 0.75))} · max ${money(edit.base * 2)}`}
                </p>
                <ErrorBox message={errorText(save.error)} />
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" onClick={() => setEdit(null)}>Bekor</Button>
                  <Button disabled={!edit.base} loading={save.isPending} onClick={() => save.mutate(edit)}>Ha, saqlash</Button>
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
