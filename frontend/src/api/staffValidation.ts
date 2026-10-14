/**
 * src/api/staffValidation.ts
 *
 * Feature 36: Staff Validation API Client (Component 1 & Component 4 Ground-Truth).
 */

import { apiClient } from './client';

export type C1DistressLabel =
  | 'exam_anxiety'
  | 'conceptual_confusion'
  | 'academic_helplessness'
  | 'course_frustration'
  | 'motivation_erosion'
  | 'none';

export interface C1QueueMessageItem {
  message_id: string;
  source_type: string;
  timestamp: string;
  clean_text: string;
}

export interface C1QueueItemResponse {
  item_id: string;
  pid: string;
  course_id: string;
  week_index: number;
  message_count: number;
  messages: C1QueueMessageItem[];
  blind: boolean;
  model_top_class?: string | null;
  model_top_score?: number | null;
}

export interface C1LabelCreateRequest {
  pid: string;
  course_id: string;
  week_index: number;
  counsellor_label: C1DistressLabel;
  confidence: number;
}

export interface C1LabelCreateResponse {
  label_id: string;
  pid: string;
  course_id: string;
  week_index: number;
  counsellor_label: string;
  confidence: number;
  model_top_class: string;
  model_top_score: number;
  agreement: boolean;
  message: string;
}

export interface C1ClassMetricsItem {
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

export interface C1SummaryResponse {
  n_items: number;
  agreement_pct: number;
  cohen_kappa: number;
  cohen_kappa_band: string;
  confusion_matrix: Record<string, Record<string, number>>;
  per_class_metrics: Record<string, C1ClassMetricsItem>;
  macro_f1: number;
  inter_rater_kappa?: number | null;
  inter_rater_band?: string | null;
}

export interface C4CandidateItem {
  rank: number;
  intervention_type: string;
  label: string;
  student_label: string;
  delivery_module: string;
  suitability_score: number;
  rationale: string;
}

export interface C4QueueItemResponse {
  recommendation_id: string;
  pid: string;
  course_id?: string | null;
  week_index: number;
  risk_tier?: string | null;
  candidates: C4CandidateItem[];
  created_at: string;
}

export interface C4RatingCreateRequest {
  recommendation_id: string;
  appropriateness: number;
  suitable_ranks: number[];
  top1_acceptable: boolean;
  comment?: string | null;
}

export interface C4RatingCreateResponse {
  rating_id: string;
  recommendation_id: string;
  appropriateness: number;
  suitable_ranks: number[];
  top1_acceptable: boolean;
  message: string;
}

export interface C4SummaryResponse {
  n: number;
  mean_appropriateness: number;
  precision_at_1: number;
  precision_at_3: number;
  ndcg_at_3: number;
  top1_acceptable_rate: number;
  acceptance_mix: Record<string, any>;
}

export interface ValidationExportResponse {
  schema: string;
  exported_at: string;
  c1_labels_count: number;
  c4_ratings_count: number;
  c1_labels: any[];
  c4_ratings: any[];
}

export const staffValidationApi = {
  getC1Queue: async (params?: { course_id?: string; limit?: number; blind?: boolean }): Promise<C1QueueItemResponse[]> => {
    const response = await apiClient.get<C1QueueItemResponse[]>('/staff/validation/c1/queue', {
      params: {
        course_id: params?.course_id || undefined,
        limit: params?.limit || 10,
        blind: params?.blind !== undefined ? params.blind : true,
      },
    });
    return response.data;
  },

  submitC1Label: async (payload: C1LabelCreateRequest): Promise<C1LabelCreateResponse> => {
    const response = await apiClient.post<C1LabelCreateResponse>('/staff/validation/c1/labels', payload);
    return response.data;
  },

  getC1Summary: async (courseId?: string): Promise<C1SummaryResponse> => {
    const response = await apiClient.get<C1SummaryResponse>('/staff/validation/c1/summary', {
      params: courseId ? { course_id: courseId } : undefined,
    });
    return response.data;
  },

  getC4Queue: async (limit?: number): Promise<C4QueueItemResponse[]> => {
    const response = await apiClient.get<C4QueueItemResponse[]>('/staff/validation/c4/queue', {
      params: { limit: limit || 10 },
    });
    return response.data;
  },

  submitC4Rating: async (payload: C4RatingCreateRequest): Promise<C4RatingCreateResponse> => {
    const response = await apiClient.post<C4RatingCreateResponse>('/staff/validation/c4/ratings', payload);
    return response.data;
  },

  getC4Summary: async (): Promise<C4SummaryResponse> => {
    const response = await apiClient.get<C4SummaryResponse>('/staff/validation/c4/summary');
    return response.data;
  },

  exportValidationData: async (): Promise<ValidationExportResponse> => {
    const response = await apiClient.get<ValidationExportResponse>('/staff/validation/export');
    return response.data;
  },
};
