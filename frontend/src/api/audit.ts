import { apiClient } from './client';

export type AuditAction =
  | 'LOGIN_SUCCESS'
  | 'LOGIN_FAILED'
  | 'ACCESS_DENIED'
  | 'IDENTITY_REVEAL'
  | 'CONSENT_ACCEPTED'
  | 'CONSENT_DECLINED'
  | 'CONSENT_WITHDRAWN'
  | 'AUDIT_LOG_VIEWED'
  | 'EXPORT_GENERATED';

export type AuditOutcome = 'success' | 'failed' | 'denied';

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  actor_id: string;
  actor_role: string;
  action: AuditAction;
  target_type?: string | null;
  target_id?: string | null;
  outcome: AuditOutcome;
  reason?: string | null;
  ip_address: string;
  user_agent: string;
  request_id: string;
  details?: Record<string, any> | null;
  schema_version: number;
}

export interface AuditFilterParams {
  actor_id?: string;
  target_id?: string;
  action?: AuditAction | '';
  outcome?: AuditOutcome | '';
  start_date?: string;
  end_date?: string;
  page?: number;
  limit?: number;
}

export interface AuditLogQueryResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}


/**
 * Queries paginated immutable audit logs with filter criteria.
 * Role-restricted to Admin and Auditor.
 */
export const queryAuditLogs = async (
  params: AuditFilterParams = {}
): Promise<AuditLogQueryResponse> => {
  const cleanParams: Record<string, any> = {};
  if (params.actor_id?.trim()) cleanParams.actor_id = params.actor_id.trim();
  if (params.target_id?.trim()) cleanParams.target_id = params.target_id.trim();
  if (params.action) cleanParams.action = params.action;
  if (params.outcome) cleanParams.outcome = params.outcome;
  if (params.start_date) cleanParams.start_date = params.start_date;
  if (params.end_date) cleanParams.end_date = params.end_date;
  if (params.page) cleanParams.page = params.page;
  if (params.limit) cleanParams.limit = params.limit;

  const response = await apiClient.get<AuditLogQueryResponse>('/audit', {
    params: cleanParams,
  });
  return response.data;
};

/**
 * Downloads a sanitized CSV export of audit logs matching current filters.
 */
export const downloadAuditExport = async (
  params: Omit<AuditFilterParams, 'page' | 'limit'> = {}
): Promise<void> => {
  const cleanParams: Record<string, any> = {};
  if (params.actor_id?.trim()) cleanParams.actor_id = params.actor_id.trim();
  if (params.target_id?.trim()) cleanParams.target_id = params.target_id.trim();
  if (params.action) cleanParams.action = params.action;
  if (params.outcome) cleanParams.outcome = params.outcome;
  if (params.start_date) cleanParams.start_date = params.start_date;
  if (params.end_date) cleanParams.end_date = params.end_date;

  const response = await apiClient.get('/audit/export', {
    params: cleanParams,
    responseType: 'blob',
  });

  const blob = new Blob([response.data], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute(
    'download',
    `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`
  );
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const auditApi = {
  queryAuditLogs,
  downloadAuditExport,
};
