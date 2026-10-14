/**
 * src/api/staffRecommendations.ts
 *
 * API client and TypeScript interfaces for Feature 32:
 * Staff Intervention Recommendation Panel (Component 4 Adaptive Interventions).
 */

import { apiClient } from './client';

export interface StaffRecommendationTopCandidate {
  rank: number;
  intervention_type: string;
  label: string;
  suitability_score: number;
}

export interface StaffRecommendationListItem {
  recommendation_id: string;
  pid: string;
  week_index: number;
  status: string;
  candidate_count: number;
  top_candidate: StaffRecommendationTopCandidate | null;
  risk_tier: string | null;
  reviewed_at?: string | null;
  reviewer_id?: string | null;
}

export interface StaffRecommendationListResponse {
  items: StaffRecommendationListItem[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface StaffRecommendationCandidateDetail {
  rank: number;
  intervention_type: string;
  label: string;
  student_label: string;
  delivery_module: string;
  suitability_score: number;
  rationale: string;
}

export interface StaffRecommendationDetailResponse {
  recommendation_id: string;
  pid: string;
  week_index: number;
  status: string;
  candidates: StaffRecommendationCandidateDetail[];
  risk_tier: string | null;
  context_course_id: string | null;
  reviewed_at?: string | null;
  reviewer_id?: string | null;
}

export const staffRecommendationsApi = {
  getRecommendations: async (params?: {
    review?: 'pending' | 'reviewed' | 'all';
    pid?: string;
    tier?: string;
    page?: number;
    page_size?: number;
  }): Promise<StaffRecommendationListResponse> => {
    const response = await apiClient.get<StaffRecommendationListResponse>(
      '/staff/recommendations',
      { params }
    );
    return response.data;
  },

  getRecommendationDetail: async (
    recommendationId: string
  ): Promise<StaffRecommendationDetailResponse> => {
    const response = await apiClient.get<StaffRecommendationDetailResponse>(
      `/staff/recommendations/${encodeURIComponent(recommendationId)}`
    );
    return response.data;
  },
};
