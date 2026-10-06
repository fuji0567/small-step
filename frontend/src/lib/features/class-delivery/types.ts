export interface Classroom {
  id: string;
  school_id: string;
  name: string;
  is_active: boolean;
  delivery_enabled: boolean;
  daily_growth_limit: number;
  created_at: string;
}

export interface ClassChild {
  id: string;
  school_id: string;
  classroom_id: string | null;
  display_name: string;
  guardian_line_user_id: string | null;
  is_active: boolean;
}

export interface ClassNewsletter {
  id: string;
  classroom_id: string;
  delivery_date: string;
  body: string;
  status: string;
  scheduled_for: string;
  is_trial: boolean;
  recipient_count: number;
  sent_count: number;
  failed_count: number;
}

export interface GrowthDeliveryEntry {
  record_id: string;
  child_id: string;
  child_name: string;
  summary: string;
  selected: boolean;
  last_sent_at: string | null;
  accepted_delivery_count: number;
}

export interface GrowthDeliveryBatch {
  id: string;
  classroom_id: string;
  delivery_date: string;
  daily_limit: number;
  status: string;
  scheduled_for: string;
  is_trial: boolean;
  requires_admin_review: boolean;
  candidates_without_guardian_link: number;
  entries: GrowthDeliveryEntry[];
}
