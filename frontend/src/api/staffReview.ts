/**
 * src/api/staffReview.ts
 *
 * API client and TypeScript interfaces for Feature 33:
 * Human-in-the-Loop Recommendation Review (Component 4 FR7 & Human Control NFR).
 */

import { apiClient } from './client';

export type ReviewDecision = 'approved' | 'modified' | 'rejected';

export interface StaffReviewRequest {
  decision: ReviewDecision;
  selected_rank?: number | null;
  modified_intervention_type?: string | null;
  reason?: string | null;
  course_id?: string | null;
}

export interface StaffReviewResponse {
  recommendation_id: string;
  decision: string;
  status: string;
  intervention_id: string | null;
  chosen_intervention_type: string | null;
  reviewed_at: string;
  message: string;
}

export interface StaffReviewStatsResponse {
  total: number;
  pending: number;
  approved: number;
  modified: number;
  rejected: number;
  reviewed: number;
  review_rate: number;
}

export const staffReviewApi = {
  submitRecommendationReview: async (
    recommendationId: string,
    payload: StaffReviewRequest
  ): Promise<StaffReviewResponse> => {
    const response = await apiClient.post<StaffReviewResponse>(
      `/staff/review/${encodeURIComponent(recommendationId)}`,
      payload
    );
    return response.data;
  },

  getReviewStats: async (): Promise<StaffReviewStatsResponse> => {
    const response = await apiClient.get<StaffReviewStatsResponse>(
      '/staff/review/stats'
    );
    return response.data;
  },
};
