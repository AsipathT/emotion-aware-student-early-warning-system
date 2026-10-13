/**
 * src/api/staffInterventions.ts
 *
 * API client and TypeScript interfaces for Feature 34:
 * Staff Intervention Management (Component 4 FR10).
 */

import { apiClient } from './client';

export interface StaffMemberItem {
  id: string;
  full_name: string;
  role: string;
}

export interface StaffInterventionListItem {
  id: string;
  recommendation_id?: string | null;
  origin: string;
  pid: string;
  course_id: string;
  intervention_type: string;
  label: string;
  student_label: string;
  delivery_module: string;
  status: string;
  created_by: string;
  assigned_to?: string | null;
  assigned_staff_name?: string | null;
  scheduled_for?: string | null;
  created_at: string;
  updated_at: string;
}

export interface StaffInterventionListResponse {
  items: StaffInterventionListItem[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface StaffInterventionNoteItem {
  note_id: string;
  author_id: string;
  author_role: string;
  content: string;
  created_at: string;
}

export interface StatusHistoryEntry {
  from_status?: string | null;
  to_status: string;
  changed_at: string;
  changed_by: string;
  note?: string | null;
}

export interface StaffInterventionDetailResponse {
  id: string;
  recommendation_id?: string | null;
  origin: string;
  pid: string;
  course_id: string;
  intervention_type: string;
  label: string;
  student_label: string;
  delivery_module: string;
  description: string;
  status: string;
  created_by: string;
  assigned_to?: string | null;
  assigned_staff_name?: string | null;
  scheduled_for?: string | null;
  baseline_snapshot: Record<string, any>;
  status_history: StatusHistoryEntry[];
  notes: StaffInterventionNoteItem[];
  created_at: string;
  updated_at: string;
}

export interface ManualInterventionCreateRequest {
  pid: string;
  course_id: string;
  intervention_type: string;
  reason: string;
}

export interface StaffInterventionPatchRequest {
  assigned_to?: string | null;
  scheduled_for?: string | null;
  status?: string | null;
  note?: string | null;
}

export interface StaffInterventionNoteCreateRequest {
  content: string;
}

export interface StaffInterventionNoteCreateResponse {
  note: StaffInterventionNoteItem;
  total_notes: number;
}

export const staffInterventionsApi = {
  getInterventions: async (params?: {
    status?: string;
    pid?: string;
    assigned_to?: string;
    origin?: string;
    page?: number;
    page_size?: number;
  }): Promise<StaffInterventionListResponse> => {
    const response = await apiClient.get<StaffInterventionListResponse>(
      '/staff/interventions',
      { params }
    );
    return response.data;
  },

  getStaffMembers: async (): Promise<StaffMemberItem[]> => {
    const response = await apiClient.get<StaffMemberItem[]>(
      '/staff/interventions/staff-members'
    );
    return response.data;
  },

  getInterventionDetail: async (
    interventionId: string
  ): Promise<StaffInterventionDetailResponse> => {
    const response = await apiClient.get<StaffInterventionDetailResponse>(
      `/staff/interventions/${encodeURIComponent(interventionId)}`
    );
    return response.data;
  },

  createManualIntervention: async (
    payload: ManualInterventionCreateRequest
  ): Promise<StaffInterventionDetailResponse> => {
    const response = await apiClient.post<StaffInterventionDetailResponse>(
      '/staff/interventions',
      payload
    );
    return response.data;
  },

  patchIntervention: async (
    interventionId: string,
    payload: StaffInterventionPatchRequest
  ): Promise<StaffInterventionDetailResponse> => {
    const response = await apiClient.patch<StaffInterventionDetailResponse>(
      `/staff/interventions/${encodeURIComponent(interventionId)}`,
      payload
    );
    return response.data;
  },

  addInterventionNote: async (
    interventionId: string,
    payload: StaffInterventionNoteCreateRequest
  ): Promise<StaffInterventionNoteCreateResponse> => {
    const response = await apiClient.post<StaffInterventionNoteCreateResponse>(
      `/staff/interventions/${encodeURIComponent(interventionId)}/notes`,
      payload
    );
    return response.data;
  },
};
