const TZ = "Asia/Tashkent";

export const money = (value: number) => value.toLocaleString("ru-RU").replace(/ | /g, " ");

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    timeZone: TZ,
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Toshkent bo'yicha sana, YYYY-MM-DD */
export function dateTashkent(offsetDays = 0, from = Date.now()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date(from + offsetDays * 86_400_000));
}

export const isToday = (iso: string) => dateTashkent(0, new Date(iso).getTime()) === dateTashkent();

/** +998 90 123 45 67 */
export function phonePretty(phone: string): string {
  const d = phone.replace(/\D/g, "");
  if (d.length !== 12) return phone;
  return `+${d.slice(0, 3)} ${d.slice(3, 5)} ${d.slice(5, 8)} ${d.slice(8, 10)} ${d.slice(10)}`;
}

export const minutesLeft = (iso: string, now = Date.now()) => Math.max(0, Math.ceil((new Date(iso).getTime() - now) / 60_000));
