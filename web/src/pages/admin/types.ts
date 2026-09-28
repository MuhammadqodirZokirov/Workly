import type { WorkerProfile } from "../../lib/types";

export interface QueueItem {
  user_id: number;
  full_name: string | null;
  age: number | null;
  submitted_at: string | null;
  duplicate_of_user_id: number | null;
}

export interface CaseFile {
  id: number;
  kind: string;
  content_type: string;
  size: number;
  created_at: string;
  url: string;
  expires_at: number;
}

export interface CaseOut {
  profile: WorkerProfile & { full_name: string | null };
  phone: string | null;
  doc_number: string | null;
  duplicate_of_user_id: number | null;
  files: CaseFile[];
}

export interface BusinessQueueItem {
  user_id: number;
  company_name: string | null;
  stir: string | null;
  responsible: string | null;
  phone: string | null;
  submitted_at: string | null;
  same_stir_user_ids: number[];
}

export const REJECT_REASONS: [string, string][] = [
  ["blurry", "Rasm noaniq"],
  ["mismatch", "Ma'lumot hujjatga mos emas"],
  ["underage", "Yosh yetmaydi (18+)"],
  ["doc_expired", "Hujjat muddati o'tgan"],
  ["duplicate", "Takroriy akkaunt"],
  ["other", "Boshqa (izoh majburiy)"],
];

export const BUSINESS_REJECT_REASONS: [string, string][] = [
  ["stir_invalid", "STIR topilmadi yoki faol emas"],
  ["company_mismatch", "Nomi STIR ga mos emas"],
  ["other", "Boshqa (izoh majburiy)"],
];

export const FILE_LABELS: Record<string, string> = {
  id_card_front: "ID karta — old",
  id_card_back: "ID karta — orqa",
  passport_main: "Pasport — asosiy sahifa",
  selfie: "Selfie",
  qualification: "Malaka guvohnomasi",
  criminal_record: "Sudlanmaganlik ma'lumotnomasi",
  avatar: "Profil rasmi",
};
