/**
 * src/api/staffAffective.ts
 *
 * API client and types for Feature 30: Staff Affective Analytics & Explainability (C1).
 */

import { apiClient } from './client';

export interface HighlightedSegment {
  text: string;
  weight: number | null;
}

export interface StaffStudentSummaryItem {
  pid: string;
  course_id: string;
  week_index: number;
  dominant_class: string;
  dominant_score: number;
  stress_label: string;
  confidence: number;
  message_count: number;
}

export interface StaffStudentListResponse {
  items: StaffStudentSummaryItem[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TopDriverItem {
  token_or_marker: string;
  weight: number;
}

export interface StaffAffectiveHistoryItem {
  week_index: number;
  emotion_scores: Record<string, number>;
  stress_label: string;
  confidence: number;
  message_count: number;
  top_drivers: TopDriverItem[];
  dominant_class: string;
  dominant_score: number;
  rationale: string;
}

export interface StaffAffectiveHistoryResponse {
  pid: string;
  course_id: string;
  history: StaffAffectiveHistoryItem[];
}

export interface StaffScrubbedMessageItem {
  message_id: string;
  source_type: string;
  timestamp: string;
  segments: HighlightedSegment[];
}

export const staffAffectiveApi = {
  getStudents: async (params?: {
    course_id?: string;
    week_index?: number;
    page?: number;
    page_size?: number;
  }): Promise<StaffStudentListResponse> => {
    const response = await apiClient.get<StaffStudentListResponse>(
      '/staff/affective/students',
      { params }
    );
    return response.data;
  },

  getStudentHistory: async (
    pid: string,
    course_id: string
  ): Promise<StaffAffectiveHistoryResponse> => {
    const response = await apiClient.get<StaffAffectiveHistoryResponse>(
      `/staff/affective/students/${pid}`,
      { params: { course_id } }
    );
    return response.data;
  },

  getStudentMessages: async (
    pid: string,
    course_id: string,
    week_index: number
  ): Promise<StaffScrubbedMessageItem[]> => {
    const response = await apiClient.get<StaffScrubbedMessageItem[]>(
      `/staff/affective/students/${pid}/messages`,
      { params: { course_id, week_index } }
    );
    return response.data;
  },
};
