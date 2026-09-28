import { ArrowLeft } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { useNavigate } from "react-router";

import { useI18n } from "../lib/i18n";

const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(" ");

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
};

/** Tugma balandligi ≥ 48px (TZ 19: katta tugmalar) */
export function Button({ variant = "primary", loading, className, children, disabled, ...rest }: ButtonProps) {
  const styles = {
    primary: "bg-brand text-white hover:bg-brand-dark disabled:bg-brand/50",
    secondary: "bg-white text-midnight border border-mist hover:bg-snow disabled:opacity-50",
    ghost: "bg-transparent text-brand hover:bg-brand-soft disabled:opacity-50",
    danger: "bg-white text-danger border border-danger/30 hover:bg-red-50 disabled:opacity-50",
  }[variant];
  return (
    <button
      className={cx(
        "flex min-h-12 w-full items-center justify-center gap-2 rounded-xl px-4 font-semibold transition",
        styles,
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Spinner light={variant === "primary"} /> : children}
    </button>
  );
}

export function Spinner({ light }: { light?: boolean }) {
  return (
    <span
      aria-label="loading"
      className={cx(
        "inline-block h-5 w-5 animate-spin rounded-full border-2 border-t-transparent",
        light ? "border-white" : "border-brand",
      )}
    />
  );
}

export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string | null; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-midnight">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-danger">{error}</span>}
    </label>
  );
}

const inputClass =
  "min-h-12 w-full rounded-xl border border-mist bg-white px-4 text-base outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20";

export const Input = (props: InputHTMLAttributes<HTMLInputElement>) => (
  <input {...props} className={cx(inputClass, props.className)} />
);

export const Select = ({ children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) => (
  <select {...props} className={cx(inputClass, "appearance-none", props.className)}>
    {children}
  </select>
);

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx(inputClass, "min-h-24 py-3", props.className)} />;
}

export function Card({ children, className, onClick }: { children: ReactNode; className?: string; onClick?: () => void }) {
  return (
    <div
      onClick={onClick}
      className={cx("rounded-[var(--radius-card)] bg-white p-4 shadow-[var(--shadow-card)]", onClick && "cursor-pointer", className)}
    >
      {children}
    </div>
  );
}

export function Chip({ active, children, onClick }: { active?: boolean; children: ReactNode; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx(
        "min-h-10 shrink-0 rounded-full border px-4 text-sm font-medium transition",
        active ? "border-brand bg-brand text-white" : "border-mist bg-white text-midnight hover:border-brand/40",
      )}
    >
      {children}
    </button>
  );
}

export function Tag({ tone = "accent", children }: { tone?: "accent" | "brand" | "success" | "muted" | "danger"; children: ReactNode }) {
  const styles = {
    accent: "bg-accent-soft text-accent",
    brand: "bg-brand-soft text-brand",
    success: "bg-green-50 text-success",
    muted: "bg-snow text-muted",
    danger: "bg-red-50 text-danger",
  }[tone];
  return <span className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold", styles)}>{children}</span>;
}

export function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange(v: boolean): void; label: string; hint?: string }) {
  return (
    <button type="button" onClick={() => onChange(!checked)} className="flex w-full items-center justify-between gap-3 text-left">
      <span>
        <span className="block font-medium">{label}</span>
        {hint && <span className="block text-xs text-muted">{hint}</span>}
      </span>
      <span className={cx("relative h-7 w-12 shrink-0 rounded-full transition", checked ? "bg-brand" : "bg-mist")}>
        <span className={cx("absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all", checked ? "left-6" : "left-1")} />
      </span>
    </button>
  );
}

export function Checkbox({ checked, onChange, children }: { checked: boolean; onChange(v: boolean): void; children: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 text-sm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 h-5 w-5 accent-brand" />
      <span>{children}</span>
    </label>
  );
}

export function TopBar({ title, back, right }: { title: string; back?: boolean; right?: ReactNode }) {
  const navigate = useNavigate();
  const { t } = useI18n();
  return (
    <header className="sticky top-0 z-10 flex items-center gap-2 bg-snow/90 px-4 py-3 backdrop-blur">
      {back && (
        <button aria-label={t("common.back")} onClick={() => navigate(-1)} className="-ml-2 flex h-10 w-10 items-center justify-center rounded-full text-xl hover:bg-white">
          <ArrowLeft size={22} aria-hidden />
        </button>
      )}
      <h1 className="flex-1 truncate text-lg font-bold">{title}</h1>
      {right}
    </header>
  );
}

export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <main className={cx("mx-auto w-full max-w-md px-4 pb-28", className)}>{children}</main>;
}

export function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="mt-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-bold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Empty({ text, image = "/backgrounds/05_soft_geometric_720.webp" }: { text: string; image?: string }) {
  return (
    <div className="relative overflow-hidden rounded-[var(--radius-card)] bg-white p-6 text-center shadow-[var(--shadow-card)]">
      <img src={image} alt="" className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-25" />
      <p className="relative text-sm text-muted">{text}</p>
    </div>
  );
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null;
  return <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-danger">{message}</p>;
}

export function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner />
    </div>
  );
}

export { cx };
