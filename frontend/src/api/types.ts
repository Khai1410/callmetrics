export interface ScoreOption {
  value: number;
  label: string;
}

export interface Threshold {
  min: number;
  label: string;
}

export interface CriteriaSet {
  id: string;
  code: string;
  name: string;
  max_score: number;
  thresholds: Threshold[];
  call_content_types: string[];
  failed_point_tags: string[];
}

export interface Criterion {
  id: string;
  criteria_set_id: string;
  stt: number;
  name: string;
  description: string | null;
  weight: number | null;
  include_in_total: boolean;
  selection_type: "single" | "multiple";
  score_options: ScoreOption[];
  check_type: "manual" | "keyword";
  check_config: Record<string, unknown> | null;
  is_active: boolean;
}

export interface CriteriaSetWithCriteria extends CriteriaSet {
  criteria: Criterion[];
}

export type RecordStatus = "uploaded" | "transcribing" | "transcribed" | "failed";

export interface RecordItem {
  id: string;
  original_filename: string;
  duration_seconds: number | null;
  criteria_set_id: string;
  uploaded_by: string | null;
  status: RecordStatus;
  error_message: string | null;
  created_at: string;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  id: string;
  text: string | null;
  segments: TranscriptSegment[] | null;
  language: string | null;
}

export interface RecordDetail extends RecordItem {
  transcript: Transcript | null;
  criteria_set: CriteriaSet;
}

export interface ScoreItem {
  id: string;
  criterion_id: string;
  auto_score: number | null;
  auto_evidence: string | null;
  final_score: number | null;
  note: string | null;
}

export type SessionStatus = "draft" | "completed";

export interface ScoringSession {
  id: string;
  record_id: string;
  criteria_set_id: string;
  scorer_name: string | null;
  call_content_type: string | null;
  failed_point_tags: string[];
  overall_comment: string | null;
  status: SessionStatus;
  total_score: number | null;
  classification: string | null;
  created_at: string;
  items: ScoreItem[];
}
