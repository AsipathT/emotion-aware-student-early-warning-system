/**
 * src/api/staffMentoring.ts
 *
 * Feature 38-D: Staff Peer Mentoring API Client.
 * Connects to /api/v1/support/mentoring for searching candidate student mentors,
 * creating peer mentoring pairings, and concluding assignments.
 */

import { apiClient } from './client';

export interface CandidateStudent {
  id: string;
  full_name: string;
}

export interface CandidateListResponse {
  items: CandidateStudent[];
  total_count: number;
}

export interface MentoringAssignmentResponse {
  id: string;
  intervention_id: string;
  mentee_user_id: string;
  mentee_name?: string | null;
  mentor_user_id: string;
  mentor_name?: string | null;
  status: 'active' | 'ended';
  created_by: string;
  created_at: string;
  ended_at?: string | null;
}

export const staffMentoringApi = {
  /**
   * Searches active students eligible for peer mentor assignment.
   */
  getCandidates: async (
    q?: string,
    interventionId?: string
  ): Promise<CandidateListResponse> => {
    const res = await apiClient.get<CandidateListResponse>('/support/mentoring/candidates', {
      params: {
        ...(q ? { q } : {}),
        ...(interventionId ? { intervention_id: interventionId } : {}),
      },
    });
    return res.data;
  },

  /**
   * Retrieves the current or most recent mentoring assignment for an intervention.
   */
  getAssignment: async (
    interventionId: string
  ): Promise<MentoringAssignmentResponse | null> => {
    const res = await apiClient.get<MentoringAssignmentResponse | null>(
      `/support/mentoring/interventions/${encodeURIComponent(interventionId)}`
    );
    return res.data;
  },

  /**
   * Matches an active student peer mentor with an accepted mentee intervention.
   */
  assignMentor: async (
    interventionId: string,
    mentorUserId: string
  ): Promise<MentoringAssignmentResponse> => {
    const res = await apiClient.post<MentoringAssignmentResponse>(
      `/support/mentoring/interventions/${encodeURIComponent(interventionId)}`,
      { mentor_user_id: mentorUserId }
    );
    return res.data;
  },

  /**
   * Concludes an active peer mentoring assignment.
   */
  endAssignment: async (
    assignmentId: string
  ): Promise<MentoringAssignmentResponse> => {
    const res = await apiClient.post<MentoringAssignmentResponse>(
      `/support/mentoring/${encodeURIComponent(assignmentId)}/end`
    );
    return res.data;
  },
};
