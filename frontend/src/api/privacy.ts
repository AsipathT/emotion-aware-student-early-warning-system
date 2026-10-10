import { apiClient } from './client';

export interface IdentityRevealResponse {
  pid: string;
  student_id: string;
  name: string;
  email: string;
}

export interface ScrubTextRequest {
  text: string;
  known_names?: string[];
}

export interface ScrubTextResponse {
  clean_text: string;
  redaction_report: Record<string, number>;
}

/**
 * Controlled identity reveal for authorized personnel (Counsellors, Academic Staff, Admins).
 * Calls GET /api/v1/reveal/{pid} with Bearer token authentication.
 * Triggers Feature 7 audit logging on the backend.
 */
export const revealStudentIdentity = async (
  pid: string
): Promise<IdentityRevealResponse> => {
  const response = await apiClient.get<IdentityRevealResponse>(`/reveal/${encodeURIComponent(pid)}`);
  return response.data;
};

/**
 * Text scrubber utility to sanitize sensitive PII from free text.
 */
export const scrubContent = async (
  payload: ScrubTextRequest
): Promise<ScrubTextResponse> => {
  const response = await apiClient.post<ScrubTextResponse>('/privacy/scrub', payload);
  return response.data;
};

export const privacyApi = {
  revealStudentIdentity,
  scrubContent,
};
