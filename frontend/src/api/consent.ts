import { apiClient } from './client';

export type ConsentDecision = 'accepted' | 'declined' | 'withdrawn';

export interface ConsentNotice {
  id?: string;
  version: number;
  text: string;
  effective_from: string;
  is_active: boolean;
}

export interface ConsentRecord {
  id?: string;
  pid: string;
  notice_version: number;
  decision: ConsentDecision;
  timestamp: string;
  ip_or_client?: string;
}

export interface ConsentDecisionPayload {
  decision: 'accepted' | 'declined';
}

export interface ConsentStatusResponse {
  has_consented: boolean;
  latest_decision: ConsentDecision | null;
  notice_version: number | null;
  timestamp: string | null;
  consent_required: boolean;
  active_notice: ConsentNotice | null;
  history: ConsentRecord[];
}

/**
 * Fetches the currently active ethics & consent notice.
 */
export const getActiveConsentNotice = async (): Promise<ConsentNotice> => {
  const response = await apiClient.get<ConsentNotice>('/consent/notice');
  return response.data;
};

/**
 * Fetches the logged-in student's consent status and decision history.
 */
export const getMyConsentStatus = async (): Promise<ConsentStatusResponse> => {
  const response = await apiClient.get<ConsentStatusResponse>('/consent/me');
  return response.data;
};

/**
 * Submits student's consent decision ('accepted' or 'declined').
 */
export const submitConsentDecision = async (
  decision: 'accepted' | 'declined'
): Promise<ConsentRecord> => {
  const response = await apiClient.post<ConsentRecord>('/consent/me', { decision });
  return response.data;
};

/**
 * Withdraws student consent, halting ongoing sentiment and engagement analytics.
 */
export const withdrawConsent = async (): Promise<ConsentRecord> => {
  const response = await apiClient.post<ConsentRecord>('/consent/me/withdraw');
  return response.data;
};

/**
 * Publishes a new notice version (Admin only).
 */
export const publishConsentNotice = async (text: string): Promise<ConsentNotice> => {
  const response = await apiClient.post<ConsentNotice>('/consent/notices', { text });
  return response.data;
};

export const consentApi = {
  getActiveConsentNotice,
  getMyConsentStatus,
  submitConsentDecision,
  withdrawConsent,
  publishConsentNotice,
};
