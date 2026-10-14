/**
 * src/api/staffOutcomes.ts
 *
 * API client and TypeScript interfaces for Feature 35:
 * Staff Intervention Outcome Recording (Component 4 FR8/FR9).
 */

import { apiClient } from './client';

export type OutcomeDirection = 'improved' | 'no_change' | 'worsened' | 'unknown';
export type OutcomeResult = 'completed' | 'not_completed';
export type OutcomeCategory = 'improved' | 'no_change' | 'worsened' | 'unknown';

export interface OutcomeDeltaItem {
  risk_score_delta?: number | null;
  tier_change: string;
  trajectory_change: string;
  dominant_distress_delta?: number | null;
  direction: OutcomeDirection;
}

export interface OutcomeSuggestionResponse {
  intervention_id: string;
  current_status: string;
  can_record: boolean;
  baseline: Record<string, any>;
  latest: Record<string, any>;
  delta: OutcomeDeltaItem;
  weeks_to_improvement?: number | null;
  suggested_direction: OutcomeDirection;
  is_recorded: boolean;
  outcome?: Record<string, any> | null;
}

export interface OutcomeRecordRequest {
  result: OutcomeResult;
  staff_category: OutcomeCategory;
  summary?: string | null;
  staff_notes?: string | null;
}

export interface OutcomeRecordResponse {
  intervention_id: string;
  result: string;
  category: string;
  status: string;
  observed_change?: string | null;
  weeks_to_improvement?: number | null;
  recorded_at: string;
  message: string;
}

export const staffOutcomesApi = {
  getOutcomeSuggestion: async (
    interventionId: string
  ): Promise<OutcomeSuggestionResponse> => {
    const response = await apiClient.get<OutcomeSuggestionResponse>(
      `/staff/outcomes/${encodeURIComponent(interventionId)}/suggestion`
    );
    return response.data;
  },

  recordOutcome: async (
    interventionId: string,
    payload: OutcomeRecordRequest
  ): Promise<OutcomeRecordResponse> => {
    const response = await apiClient.post<OutcomeRecordResponse>(
      `/staff/outcomes/${encodeURIComponent(interventionId)}`,
      payload
    );
    return response.data;
  },
};
