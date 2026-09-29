// Backend /api/v1 javoblari (backend/workly/interfaces/api/schemas*.py bilan mos)
export type Lang = "uz_latn" | "uz_cyrl" | "ru";
export type Role = "worker" | "employer" | "agent" | "moderator" | "admin" | "super_admin";
export type Names = Record<Lang, string>;

export interface Me {
  id: number;
  phone: string | null;
  phone_verified: boolean;
  telegram_id: number | null;
  full_name: string | null;
  lang: Lang;
  status: string;
  roles: Role[];
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: Me;
}

export interface Specialization {
  id: number;
  code: string;
  name: Names;
}
export interface Category {
  id: number;
  code: string;
  name: Names;
  specializations: Specialization[];
}
export interface District {
  id: number;
  region_id: number;
  code: string;
  name: Names;
}
export interface GeoPoint {
  lat: number;
  lon: number;
}

export type Duration = "half_day" | "day" | "multi_day";
export type Experience = "none" | "1_2" | "3_5" | "5_plus";

export interface Price {
  unit: "day" | "hour" | "m2" | "guest";
  worker_price: number;
  days: number;
  workers: number;
  subtotal: number;
  service_fee: number;
  employer_total: number;
  worker_net: number;
  commission_enabled: boolean;
}

export interface Quote {
  quote_id: string;
  expires_at: string;
  price: Price;
  night: boolean;
  needs_approval: boolean;
  cancellation_policy: string[];
}

export interface OrderInput {
  category_id: number;
  specialization_id: number;
  workers: number;
  date: string;
  start_time: string;
  duration: Duration | null;
  days: number;
  volume?: number | null;
  point: GeoPoint;
  district_id: number;
  address_text: string;
  landmark?: string | null;
  description?: string | null;
  tools_by: "employer" | "worker";
  lunch: boolean;
  transport: boolean;
  top_only: boolean;
}

export interface AssignmentSlot {
  id: number;
  slot_no: number;
  worker_id: number | null;
  status: string;
  worker_name: string | null;
  worker_phone: string | null;
  arrived_at: string | null;
  finished_at: string | null;
  confirmed_at: string | null;
  problem: string | null;
  favorite: boolean;
  blocked: boolean;
}

/** Bekor qilish oqibati (TZ 11); pilotda charged=false — summa olinmaydi */
export interface CancelTerms {
  tier: "free" | "h6_24" | "lt6" | "after_arrival";
  percent: number;
  amount: number;
  reliability: number;
  charged: boolean;
}

export interface Order {
  id: number;
  status: string;
  category_id: number;
  specialization_id: number;
  workers: number;
  starts_at: string;
  duration: Duration | null;
  days: number;
  is_night: boolean;
  district_id: number;
  point: GeoPoint;
  address_text: string;
  landmark: string | null;
  description: string | null;
  price: Price;
  assignments: AssignmentSlot[];
  created_at: string;
  partial_asked_at: string | null;
  partial_decision: "start" | "wait" | null;
}

export interface JobCard {
  order_id: number;
  category_id: number;
  specialization_id: number;
  district_id: number;
  distance_km: number | null;
  starts_at: string;
  duration: Duration | null;
  days: number;
  is_night: boolean;
  lunch: boolean;
  transport: boolean;
  tools_by: "employer" | "worker";
  worker_net: number;
  open_slots: number;
  employer: { name: string | null; verified: boolean };
  description: string | null;
}

export interface Offer extends JobCard {
  offer_id: number;
  expires_at: string;
}

export interface WorkerAssignment extends JobCard {
  assignment_id: number;
  status: string;
  address_text: string;
  landmark: string | null;
  point: GeoPoint;
  employer_phone: string | null;
  arrived_at: string | null;
  finished_at: string | null;
  confirmed_at: string | null;
  cash_received: number | null;
}

/** POST /assignments/{id}/... javobi */
export interface AssignmentState {
  id: number;
  order_id: number;
  status: string;
  arrived_at: string | null;
  arrival_confirmed_at: string | null;
  finished_at: string | null;
  confirmed_at: string | null;
  auto_confirmed: boolean;
  cash_received: number | null;
  problem: string | null;
}

export interface Reviews {
  reviewed_by_me: boolean;
  visible: { rating: number; tags: string[]; comment: string | null; is_auto: boolean; mine: boolean }[];
}

export type VerificationStatus = "not_submitted" | "pending" | "verified" | "rejected" | "expired";

export interface WorkerProfile {
  user_id: number;
  last_name: string | null;
  first_name: string | null;
  middle_name: string | null;
  birth_date: string | null;
  gender: "male" | "female" | null;
  district_ids: number[];
  skills: { category_id: number; experience: Experience; specialization_ids: number[] }[];
  badges: string[];
  available_now_until: string | null;
  verification: {
    status: VerificationStatus;
    rejection_reason: string | null;
    rejection_comment: string | null;
  };
  files: { id: number; kind: string; content_type: string; created_at: string }[];
}
