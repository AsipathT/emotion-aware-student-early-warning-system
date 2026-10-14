/**
 * src/api/staffStudents.ts
 *
 * API client and TypeScript interfaces for Feature 31:
 * Unified Student Context Summary (C1 + C2 + C3 Multi-Modal Profile - Component 4).
 */

import { apiClient } from './client';

export interface StaffStudentOverviewItem {
  pid: string;
  course_id: string;
  week_index: number;
  risk_score: number | null;
  risk_tier: string;
  trajectory_label: string;
  dominant_distress_class: string;
}

export interface StaffStudentOverviewResponse {
  items: StaffStudentOverviewItem[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface StudentContextIdentity {
  pid: string;
}

export interface StudentContextC1 {
  latest: {
    week_index: number;
    emotion_scores: Record<string, number>;
    stress_label: string;
    confidence: number;
    dominant_class: string;
    dominant_score: number;
  } | null;
  change_vs_previous: Record<string, number>;
  history: Array<{
    week_index: number;
    dominant_class: string;
    dominant_score: number;
    emotion_scores?: Record<string, number>;
  }>;
}

export interface StudentContextC2 {
  latest: {
    week_index: number;
    trajectory_label: string;
    confidence: number;
    contributing_indicators: string[];
  } | null;
  history: Array<{
    week_index: number;
    trajectory_label: string;
    confidence: number;
  }>;
}

export interface ModalityContributions {
  affective: number;
  behavioral: number;
  academic: number;
}

export interface StudentContextC3 {
  latest: {
    week_index: number;
    risk_score: number;
    risk_tier: string;
    confidence?: number;
    modality_contributions: ModalityContributions;
    dominant_modality: string;
    dominant_modality_value: number;
    top_drivers: string[];
  } | null;
  history: Array<{
    week_index: number;
    risk_score: number;
    risk_tier: string;
  }>;
}

export interface BehaviorWeeklyItem {
  week_index: number;
  login_count: number;
  session_minutes: number;
  clicks: number;
  video_play_count: number;
  video_pause_count: number;
  video_completion_pct: number;
  submissions_count: number;
  avg_submission_delay_hours: number;
}

export interface StudentContextBehaviour {
  history: BehaviorWeeklyItem[];
}

export interface InterventionOutcomeDetail {
  decision: string;
  completed: boolean;
  observed_change?: number | null;
  notes_present: boolean;
}

export interface InterventionHistoryItem {
  intervention_id: string;
  recommendation_id?: string | null;
  course_id?: string;
  intervention_type: string;
  status: string;
  created_at?: string | null;
  outcome?: InterventionOutcomeDetail | null;
}

export interface StudentContextInterventions {
  history: InterventionHistoryItem[];
}

export interface LaggingSourceItem {
  source: string;
  status?: string;
  lag_weeks: number | null;
}

export interface StudentContextFreshness {
  c1_week: number | null;
  c2_week: number | null;
  c3_week: number | null;
  behaviour_week: number | null;
  max_observed_week: number;
  lagging_sources: LaggingSourceItem[];
}

export interface StudentContextResponse {
  identity: StudentContextIdentity;
  c1: StudentContextC1;
  c2: StudentContextC2;
  c3: StudentContextC3;
  behaviour: StudentContextBehaviour;
  interventions: StudentContextInterventions;
  latest_common_week: number;
  data_freshness: StudentContextFreshness;
  summary_lines: string[];
}

export const staffStudentsApi = {
  getStudents: async (params?: {
    course_id?: string;
    tier?: string;
    page?: number;
    page_size?: number;
  }): Promise<StaffStudentOverviewResponse> => {
    const response = await apiClient.get<StaffStudentOverviewResponse>(
      '/staff/students',
      { params }
    );
    return response.data;
  },

  getStudentContext: async (
    pid: string,
    course_id: string
  ): Promise<StudentContextResponse> => {
    const response = await apiClient.get<StudentContextResponse>(
      `/staff/students/${pid}/context`,
      { params: { course_id } }
    );
    return response.data;
  },
};
