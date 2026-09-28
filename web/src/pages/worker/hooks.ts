import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";
import { haptic } from "../../lib/telegram";
import type { JobCard, Offer, WorkerAssignment, WorkerProfile } from "../../lib/types";

export const useWorkerProfile = () =>
  useQuery({ queryKey: ["worker", "profile"], queryFn: () => api<WorkerProfile>("/worker/profile") });

export const useOffers = (enabled: boolean) =>
  useQuery({
    queryKey: ["worker", "offers"],
    queryFn: () => api<Offer[]>("/worker/offers"),
    enabled,
    refetchInterval: 20_000, // taklif 5–10 daqiqa yashaydi; WebSocket — keyingi bosqichda
  });

export const useOpenJobs = (enabled: boolean) =>
  useQuery({ queryKey: ["worker", "open"], queryFn: () => api<JobCard[]>("/jobs/open"), enabled, refetchInterval: 30_000 });

export const useAssignments = (enabled: boolean) =>
  useQuery({ queryKey: ["worker", "assignments"], queryFn: () => api<WorkerAssignment[]>("/worker/assignments"), enabled });

export function useJobActions() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["worker"] });
  const accept = useMutation({
    mutationFn: (offerId: number) => api<WorkerAssignment>(`/offers/${offerId}/accept`, { method: "POST" }),
    onSuccess: () => haptic("success"),
    onError: () => haptic("error"),
    onSettled: refresh,
  });
  const decline = useMutation({
    mutationFn: (offerId: number) => api(`/offers/${offerId}/decline`, { method: "POST" }),
    onSettled: refresh,
  });
  const take = useMutation({
    mutationFn: (orderId: number) => api<WorkerAssignment>(`/jobs/${orderId}/take`, { method: "POST" }),
    onSuccess: () => haptic("success"),
    onError: () => haptic("error"),
    onSettled: refresh,
  });
  return { accept, decline, take };
}
