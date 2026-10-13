/**
 * src/api/support.ts
 *
 * API client and TypeScript interfaces for Feature 38-A:
 * Student Support Hub & Uptake Response (Component 4 Uptake Metric).
 */

import { apiClient } from './client';

export type DeclineReason =
  | 'no_time'
  | 'not_needed'
  | 'prefer_other_support'
  | 'other';

export interface StudentSupportResponse {
  response: 'accept' | 'decline';
  reason?: DeclineReason | string | null;
  at: string;
}

export interface StudentSharedResourceItem {
  id: string;
  resource_id: string;
  title: string;
  description: string;
  resource_type: 'resource' | 'guidance' | 'referral';
  type: 'resource' | 'guidance' | 'referral';
  url?: string | null;
  contact_info?: string | null;
  message?: string | null;
  shared_at?: string | null;
  viewed: boolean;
  viewed_at?: string | null;
}

export interface MarkResourceViewedResponse {
  success: boolean;
  resource_id: string;
  viewed_at?: string | null;
}

export interface StudentSupportInterventionItem {
  id: string;
  student_label: string;
  description: string;
  status: string;
  delivery_module: string;
  scheduled_for?: string | null;
  offered_at?: string | null;
  assigned_staff_name?: string | null;
  student_response?: StudentSupportResponse | null;

  // Extension placeholders for Parts B, C, D
  slot?: Record<string, any> | null;
  resources?: StudentSharedResourceItem[] | null;
  mentor?: Record<string, any> | null;
}

export interface StudentSupportListResponse {
  items: StudentSupportInterventionItem[];
  total_count: number;
}

export interface StudentSupportResponseRequest {
  response: 'accept' | 'decline';
  decline_reason?: DeclineReason | null;
}

export interface StudentSupportResponseResult {
  id: string;
  status: string;
  student_response: Record<string, any>;
  message: string;
}

export const supportApi = {
  getMyInterventions: async (): Promise<StudentSupportListResponse> => {
    const response = await apiClient.get<StudentSupportListResponse>(
      '/support/me/interventions'
    );
    return response.data;
  },

  respondToIntervention: async (
    interventionId: string,
    payload: StudentSupportResponseRequest
  ): Promise<StudentSupportResponseResult> => {
    const response = await apiClient.post<StudentSupportResponseResult>(
      `/support/me/interventions/${encodeURIComponent(interventionId)}/respond`,
      payload
    );
    return response.data;
  },

  markResourceViewed: async (
    interventionId: string,
    resourceId: string
  ): Promise<MarkResourceViewedResponse> => {
    const response = await apiClient.post<MarkResourceViewedResponse>(
      `/support/me/interventions/${encodeURIComponent(interventionId)}/resources/${encodeURIComponent(resourceId)}/viewed`
    );
    return response.data;
  },
};

