import { useQuery } from "@tanstack/react-query";

import { api } from "./api";
import type { Category, District } from "./types";

export function useCatalog() {
  const categories = useQuery({
    queryKey: ["catalog", "categories"],
    queryFn: () => api<Category[]>("/catalog/categories", { auth: false }),
    staleTime: Infinity,
  });
  const districts = useQuery({
    queryKey: ["catalog", "districts"],
    queryFn: () => api<District[]>("/catalog/districts", { auth: false }),
    staleTime: Infinity,
  });
  const cats = categories.data ?? [];
  const dists = districts.data ?? [];
  return {
    categories: cats,
    districts: dists,
    loading: categories.isLoading || districts.isLoading,
    category: (id: number) => cats.find((c) => c.id === id),
    specialization: (id: number) => cats.flatMap((c) => c.specializations).find((s) => s.id === id),
    district: (id: number) => dists.find((d) => d.id === id),
  };
}

// Toshkent tumanlari markazlari (taxminiy). Geolokatsiyaga ruxsat berilmasa ishlatiladi;
// Yandex Maps (TZ OS-22) ulanganda xaritadan aniq nuqta tanlanadi.
export const DISTRICT_CENTERS: Record<string, [number, number]> = {
  bektemir: [41.209, 69.334],
  chilonzor: [41.275, 69.204],
  mirobod: [41.287, 69.27],
  mirzo_ulugbek: [41.338, 69.335],
  olmazor: [41.35, 69.222],
  sergeli: [41.227, 69.219],
  shayxontohur: [41.323, 69.231],
  uchtepa: [41.296, 69.17],
  yakkasaroy: [41.286, 69.25],
  yangihayot: [41.195, 69.165],
  yashnobod: [41.304, 69.336],
  yunusobod: [41.365, 69.285],
};
