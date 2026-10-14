/**
 * src/api/staffFeedback.ts
 *
 * Feature 39: Staff Intervention Feedback API client (Component 4 Feedback Loop).
 * Supports:
 *   - Detail feedback retrieval for intervention inspector panel
 *   - Aggregate feedback summary & response rate
 *   - Admin-only pseudonymous research export
 */

import { apiClient } from './client';

export interface StaffFeedbackDetailResponse {
  id: string;
  intervention_id: string;
  pid: string;
  intervention_type: string;
  helpfulness: number;
  attended: 'yes' | 'partly' | 'no';
  barrier?: 'time' | 'not_relevant' | 'uncomfortable' | 'technical' | 'other' | null;
  comment?: string | null;
  created_at: string;
}

export interface FeedbackSummaryResponse {
  n: number;
  completed_interventions: number;
  response_rate: number;
  mean_helpfulness: number;
  mean_helpfulness_by_type: Record<string, number>;
  barrier_counts: Record<string, number>;
  attended_counts: Record<string, number>;
}

export interface FeedbackExportRow {
  pid: string;
  intervention_type: string;
  helpfulness: number;
  attended: string;
  barrier?: string | null;
  created_at: string;
}

export interface FeedbackExportResponse {
  schema: string;
  exported_at: string;
  total_count: number;
  data: FeedbackExportRow[];
}

export const staffFeedbackApi = {
  getInterventionFeedback: async (interventionId: string): Promise<StaffFeedbackDetailResponse> => {
    const response = await apiClient.get<StaffFeedbackDetailResponse>(
      `/staff/feedback/interventions/${interventionId}`
    );
    return response.data;
  },

  getFeedbackSummary: async (interventionType?: string): Promise<FeedbackSummaryResponse> => {
    const response = await apiClient.get<FeedbackSummaryResponse>('/staff/feedback/summary', {
      params: interventionType ? { intervention_type: interventionType } : undefined,
    });
    return response.data;
  },

  exportFeedback: async (interventionType?: string): Promise<FeedbackExportResponse> => {
    const response = await apiClient.get<FeedbackExportResponse>('/staff/feedback/export', {
      params: interventionType ? { intervention_type: interventionType } : undefined,
    });
    return response.data;
  },
};
