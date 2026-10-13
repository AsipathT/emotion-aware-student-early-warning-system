/**
 * src/api/staffSlots.ts
 *
 * Feature 38-B: Staff Counselling Slot API Client.
 * Connects to /api/v1/support/slots for publishing and managing
 * confidential appointment slots for counselling interventions.
 */

import { apiClient } from './client';

export type SlotMode = 'in_person' | 'online';

export interface CounsellingSlotItem {
  id: string;
  counsellor_id: string;
  counsellor_name?: string | null;
  start_at: string;
  duration_minutes: number;
  mode: SlotMode;
  location_or_link?: string | null;
  is_booked: boolean;
  booked_by_user_id?: string | null;
  intervention_id?: string | null;
  booked_at?: string | null;
  cancelled_at?: string | null;
  created_at: string;
}

export interface SlotListResponse {
  items: CounsellingSlotItem[];
  total_count: number;
}

export interface SlotCreatePayload {
  start_at: string;
  duration_minutes: number;
  mode: SlotMode;
  location_or_link: string;
}

export const staffSlotsApi = {
  /**
   * Publishes a new counselling appointment slot.
   */
  createSlot: async (payload: SlotCreatePayload): Promise<CounsellingSlotItem> => {
    const res = await apiClient.post<CounsellingSlotItem>('/support/slots', payload);
    return res.data;
  },

  /**
   * Retrieves the authenticated counsellor's published slots with optional date filters.
   */
  getMySlots: async (params?: { from?: string; to?: string }): Promise<SlotListResponse> => {
    const res = await apiClient.get<SlotListResponse>('/support/slots/mine', { params });
    return res.data;
  },

  /**
   * Deletes an unbooked slot.
   */
  deleteSlot: async (id: string): Promise<{ success: boolean; message: string }> => {
    const res = await apiClient.delete<{ success: boolean; message: string }>(
      `/support/slots/${encodeURIComponent(id)}`
    );
    return res.data;
  },

  /**
   * Cancels a booked appointment slot, notifies the student, and unschedules the intervention.
   */
  cancelSlot: async (id: string): Promise<CounsellingSlotItem> => {
    const res = await apiClient.post<CounsellingSlotItem>(
      `/support/slots/${encodeURIComponent(id)}/cancel`
    );
    return res.data;
  },
};
