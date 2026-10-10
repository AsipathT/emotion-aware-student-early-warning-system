/**
 * src/api/forum.ts
 *
 * API module for the discussion forum (Feature 14).
 */

import { apiClient } from './client';

// ── Interfaces ───────────────────────────────────────────────────────────────

export interface AuthorSummary {
  id: string;
  full_name: string;
  role: string;
}

export interface ThreadListItem {
  id: string;
  course_id: string;
  author_id: string;
  author_role: string;
  title: string;
  body: string;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
  reply_count: number;
  is_pinned: boolean;
  is_locked: boolean;
  metadata: Record<string, any>;
  author?: AuthorSummary | null;
}

export interface PostResponse {
  id: string;
  thread_id: string;
  course_id: string;
  author_id: string;
  author_role: string;
  parent_post_id: string | null;
  body: string;
  created_at: string;
  metadata: Record<string, any>;
  author?: AuthorSummary | null;
}

export interface ThreadDetail extends ThreadListItem {
  posts: PostResponse[];
}

export interface ThreadCreatePayload {
  title: string;
  body: string;
}

export interface PostCreatePayload {
  body: string;
  parent_post_id?: string | null;
}

export interface ThreadModerationPayload {
  is_pinned?: boolean;
  is_locked?: boolean;
}

// ── API functions ────────────────────────────────────────────────────────────

export const getThreads = async (
  courseId: string,
  params?: { skip?: number; limit?: number; search?: string }
): Promise<ThreadListItem[]> => {
  const response = await apiClient.get<ThreadListItem[]>(
    `/forum/courses/${courseId}/threads`,
    { params }
  );
  return response.data;
};

export const createThread = async (
  courseId: string,
  payload: ThreadCreatePayload
): Promise<ThreadListItem> => {
  const response = await apiClient.post<ThreadListItem>(
    `/forum/courses/${courseId}/threads`,
    payload
  );
  return response.data;
};

export const getThreadDetail = async (
  threadId: string
): Promise<ThreadDetail> => {
  const response = await apiClient.get<ThreadDetail>(
    `/forum/threads/${threadId}`
  );
  return response.data;
};

export const createPost = async (
  threadId: string,
  payload: PostCreatePayload
): Promise<PostResponse> => {
  const response = await apiClient.post<PostResponse>(
    `/forum/threads/${threadId}/posts`,
    payload
  );
  return response.data;
};

export const moderateThread = async (
  threadId: string,
  payload: ThreadModerationPayload
): Promise<ThreadListItem> => {
  const response = await apiClient.patch<ThreadListItem>(
    `/forum/threads/${threadId}/moderation`,
    payload
  );
  return response.data;
};

export const forumApi = {
  getThreads,
  createThread,
  getThreadDetail,
  createPost,
  moderateThread,
};
