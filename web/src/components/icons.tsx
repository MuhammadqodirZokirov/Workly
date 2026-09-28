import {
  Baby,
  ChefHat,
  HardHat,
  type LucideIcon,
  Package,
  SprayCan,
  Sprout,
  Wrench,
} from "lucide-react";

import { cx } from "./ui";

// Ikonkalar: Lucide (https://lucide.dev, ISC litsenziya) — dizayndagi chiziqli, yumaloq uslub.
// Emoji ishlatilmaydi: platformaga qarab turlicha ko'rinadi va brend ranglariga bo'ysunmaydi.

const CATEGORY: Record<string, { icon: LucideIcon; tint: string }> = {
  construction: { icon: HardHat, tint: "bg-accent-soft text-accent" },
  cargo: { icon: Package, tint: "bg-brand-soft text-brand" },
  cleaning: { icon: SprayCan, tint: "bg-violet-50 text-violet-600" },
  other: { icon: Wrench, tint: "bg-rose-50 text-rose-500" },
  childcare: { icon: Baby, tint: "bg-pink-50 text-pink-500" },
  cooking: { icon: ChefHat, tint: "bg-amber-50 text-amber-600" },
  farming: { icon: Sprout, tint: "bg-green-50 text-success" },
};

export function CategoryIcon({ code, size = "md", className }: { code?: string; size?: "sm" | "md"; className?: string }) {
  const { icon: Icon, tint } = CATEGORY[code ?? "other"] ?? CATEGORY.other;
  return (
    <span
      className={cx(
        "flex shrink-0 items-center justify-center",
        size === "md" ? "h-14 w-14 rounded-2xl" : "h-12 w-12 rounded-2xl",
        tint,
        className,
      )}
    >
      <Icon size={size === "md" ? 26 : 22} strokeWidth={1.8} aria-hidden />
    </span>
  );
}
