/**
 * src/api/journal.ts
 *
 * API module for Reflective Learning Journal (Feature 16).
 */

import { apiClient } from './client';

// ── Interfaces ───────────────────────────────────────────────────────────────

export interface JournalCurrentStatus {
  course_id: string;
  week_start: string;
  week_end: string;
  submitted: boolean;
  entry_id: string | null;
}

export interface JournalEntryResponse {
  id: string;
  author_id: string;
  author_role: string;
  course_id: string;
  source_type: string;
  week_start: string;
  body: string;
  created_at: string;
  metadata: {
    char_count?: number;
    word_count?: number;
    seconds_since_week_start?: number;
    [key: string]: any;
  };
}

export interface JournalEntryCreate {
  course_id: string;
  body: string;
}

// ── API functions ────────────────────────────────────────────────────────────

export const getCurrentWeekStatus = async (
  courseId: string
): Promise<JournalCurrentStatus> => {
  const response = await apiClient.get<JournalCurrentStatus>(
    `/journal/courses/${courseId}/current`
  );
  return response.data;
};

export const createJournalEntry = async (
  payload: JournalEntryCreate
): Promise<JournalEntryResponse> => {
  const response = await apiClient.post<JournalEntryResponse>(
    '/journal/entries',
    payload
  );
  return response.data;
};

export const getJournalEntries = async (params?: {
  course_id?: string;
  limit?: number;
  skip?: number;
}): Promise<JournalEntryResponse[]> => {
  const response = await apiClient.get<JournalEntryResponse[]>(
    '/journal/entries',
    { params }
  );
  return response.data;
};

export const getJournalEntryById = async (
  entryId: string
): Promise<JournalEntryResponse> => {
  const response = await apiClient.get<JournalEntryResponse>(
    `/journal/entries/${entryId}`
  );
  return response.data;
};

export const journalApi = {
  getCurrentWeekStatus,
  createJournalEntry,
  getJournalEntries,
  getJournalEntryById,
};
