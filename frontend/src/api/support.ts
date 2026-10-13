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

export interface BookedSlotItem {
  id: string;
  counsellor_id: string;
  counsellor_name?: string | null;
  start_at: string;
  duration_minutes: number;
  mode: 'in_person' | 'online';
  location_or_link?: string | null;
  booked_at?: string | null;
}

export interface AvailableSlotItem {
  id: string;
  counsellor_id: string;
  counsellor_name?: string | null;
  start_at: string;
  duration_minutes: number;
  mode: 'in_person' | 'online';
}

export interface AvailableSlotListResponse {
  items: AvailableSlotItem[];
  total_count: number;
}

export interface SlotBookingResult {
  success: boolean;
  slot: BookedSlotItem;
  intervention_id: string;
  status: string;
  message: string;
}

export interface SlotCancelResult {
  success: boolean;
  message: string;
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
  slot?: BookedSlotItem | null;
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

  getAvailableSlots: async (
    interventionId: string
  ): Promise<AvailableSlotListResponse> => {
    const response = await apiClient.get<AvailableSlotListResponse>(
      '/support/me/slots',
      {
        params: { intervention_id: interventionId },
      }
    );
    return response.data;
  },

  bookSlot: async (
    interventionId: string,
    slotId: string
  ): Promise<SlotBookingResult> => {
    const response = await apiClient.post<SlotBookingResult>(
      `/support/me/interventions/${encodeURIComponent(interventionId)}/book`,
      { slot_id: slotId }
    );
    return response.data;
  },

  cancelBooking: async (
    interventionId: string
  ): Promise<SlotCancelResult> => {
    const response = await apiClient.post<SlotCancelResult>(
      `/support/me/interventions/${encodeURIComponent(interventionId)}/cancel-booking`
    );
    return response.data;
  },
};

