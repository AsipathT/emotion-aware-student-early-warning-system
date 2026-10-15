import { apiClient } from './client';
import { UserRole } from './auth';

export interface SystemStatsResponse {
  total_users: number;
  active_users: number;
  total_courses: number;
  published_courses: number;
  total_students: number;
  total_lecturers: number;
}

export interface AdminProfileResponse {
  id?: string;
  user_id?: string;
  full_name?: string;
  email?: string;
  phone?: string | null;
  student_id?: string | null;
  department?: string | null;
  bio?: string | null;
  avatar_url?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface AdminUserResponse {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  pid?: string | null;
  profile?: AdminProfileResponse | null;
}

export interface AdminPaginatedUsersResponse {
  items: AdminUserResponse[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AdminEnrolmentSummary {
  course_id: string;
  course_name?: string | null;
  course_code?: string | null;
  enrolled_at?: string | null;
  status: string;
}

export interface AdminConsentSummary {
  has_decision: boolean;
  decision?: string | null;
  decided_at?: string | null;
  notice_version?: string | null;
}

export interface AdminUserDetailResponse {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  pid?: string | null;
  profile?: AdminProfileResponse | null;
  enrolments: AdminEnrolmentSummary[];
  consent?: AdminConsentSummary | null;
}

export interface AdminUserCreatePayload {
  email: string;
  full_name: string;
  password: string;
  role: UserRole;
  phone?: string;
  bio?: string;
  department?: string;
}

export interface AdminUserUpdatePayload {
  full_name?: string;
  phone?: string;
  bio?: string;
  department?: string;
}

export interface AdminOverviewResponse {
  total_users: number;
  active_users: number;
  suspended_users: number;
  users_by_role: Record<string, number>;
  total_courses: number;
  published_courses: number;
  draft_courses: number;
  total_enrolments: number;
  consent_coverage: {
    total_students: number;
    accepted: number;
    declined: number;
    withdrawn: number;
    pending: number;
    coverage_percentage: number;
  };
  pipeline_summary: {
    active_runs_count: number;
    latest_run?: {
      course_id: string;
      week_index: number;
      overall_status: string;
      current_stage: string;
      created_at: string;
      updated_at: string;
    } | null;
  };
  ingestion_summary: Record<string, {
    component: string;
    configured: boolean;
    last_run?: string | null;
    status: string;
    records_processed: number;
  }>;
  recent_audit_events: Array<{
    id: string;
    timestamp: string;
    action: string;
    actor_id: string;
    actor_role: string;
    outcome: string;
    target_type?: string | null;
    target_id?: string | null;
    ip_address?: string | null;
  }>;
  database_health: {
    status: string;
    ping_ms: number;
    database_name: string;
  };
}

export interface UserStatusUpdatePayload {
  is_active: boolean;
}

export interface UserRoleUpdatePayload {
  role: UserRole;
}

export interface AdminUserFilterParams {
  page?: number;
  page_size?: number;
  q?: string;
  role?: string;
  status?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

/**
 * Fetches platform-wide overview metrics and health KPIs. (Admin & Auditor)
 */
export const getAdminOverview = async (): Promise<AdminOverviewResponse> => {
  const response = await apiClient.get<AdminOverviewResponse>('/admin/overview');
  return response.data;
};

/**
 * Fetches paginated users with search and filters. (Admin only)
 */
export const getAdminUsersPaginated = async (
  params?: AdminUserFilterParams
): Promise<AdminPaginatedUsersResponse> => {
  const response = await apiClient.get<AdminPaginatedUsersResponse>('/admin/users', {
    params,
  });
  return response.data;
};

/**
 * Legacy user listing. (Admin only)
 */
export const getAdminUsers = async (): Promise<AdminUserResponse[]> => {
  const response = await apiClient.get<AdminPaginatedUsersResponse>('/admin/users', {
    params: { page: 1, page_size: 100 },
  });
  return response.data.items || [];
};

/**
 * Provisions a new user account. (Admin only)
 */
export const createAdminUser = async (
  payload: AdminUserCreatePayload
): Promise<AdminUserResponse> => {
  const response = await apiClient.post<AdminUserResponse>('/admin/users', payload);
  return response.data;
};

/**
 * Fetches comprehensive detail for a specific user. (Admin only)
 */
export const getAdminUserDetail = async (
  userId: string
): Promise<AdminUserDetailResponse> => {
  const response = await apiClient.get<AdminUserDetailResponse>(`/admin/users/${userId}`);
  return response.data;
};

/**
 * Updates editable profile attributes of a user. (Admin only)
 */
export const updateAdminUserProfile = async (
  userId: string,
  payload: AdminUserUpdatePayload
): Promise<AdminUserResponse> => {
  const response = await apiClient.put<AdminUserResponse>(
    `/admin/users/${userId}/profile`,
    payload
  );
  return response.data;
};

/**
 * Updates a user's active/suspended status. (Admin only)
 */
export const updateUserStatus = async (
  userId: string,
  isActive: boolean
): Promise<AdminUserResponse> => {
  const response = await apiClient.put<AdminUserResponse>(
    `/admin/users/${userId}/status`,
    { is_active: isActive }
  );
  return response.data;
};

/**
 * Updates a user's authorization role. (Admin only)
 */
export const updateUserRole = async (
  userId: string,
  role: UserRole
): Promise<AdminUserResponse> => {
  const response = await apiClient.put<AdminUserResponse>(
    `/admin/users/${userId}/role`,
    { role }
  );
  return response.data;
};

/**
 * Legacy stats endpoint. (Admin only)
 */
export const getAdminStats = async (): Promise<SystemStatsResponse> => {
  const response = await apiClient.get<SystemStatsResponse>('/admin/stats');
  return response.data;
};

// ── Phase 2: Course Administration Interfaces ────────────────────────────────

export interface AdminCourseSummary {
  id: string;
  course_id: string;
  title: string;
  description?: string | null;
  lecturer_id?: string | null;
  lecturer_name?: string | null;
  lecturer_email?: string | null;
  is_published: boolean;
  enrolment_count: number;
  module_count: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AdminPaginatedCoursesResponse {
  items: AdminCourseSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AdminCourseFilterParams {
  page?: number;
  page_size?: number;
  q?: string;
  is_published?: boolean;
  lecturer_id?: string;
}

export interface AdminCoursePublishUpdate {
  is_published: boolean;
}

export interface AdminCourseLecturerUpdate {
  lecturer_id: string;
}

// ── Phase 2: Enrolment Administration Interfaces ──────────────────────────────

export interface AdminEnrolmentItem {
  id: string;
  course_id: string;
  course_title?: string | null;
  student_id?: string | null;
  student_name?: string | null;
  student_email?: string | null;
  pid?: string | null;
  status: string; // 'active' | 'dropped'
  enrolled_at?: string | null;
  enrolment_end?: string | null;
  updated_at?: string | null;
}

export interface AdminPaginatedEnrolmentsResponse {
  items: AdminEnrolmentItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AdminEnrolmentFilterParams {
  page?: number;
  page_size?: number;
  course_id?: string;
  student_id?: string;
  pid?: string;
  status?: string;
  q?: string;
}

export interface AdminEnrolmentCreatePayload {
  course_id: string;
  student_identifier: string;
}

export interface BulkEnrolmentRowResult {
  identifier: string;
  status: 'enrolled' | 'skipped' | 'failed';
  reason?: string | null;
  student_id?: string | null;
  pid?: string | null;
}

export interface AdminBulkEnrolmentPayload {
  course_id: string;
  student_identifiers: string[];
}

export interface AdminBulkEnrolmentResponse {
  course_id: string;
  total: number;
  enrolled_count: number;
  skipped_count: number;
  failed_count: number;
  results: BulkEnrolmentRowResult[];
}

// ── Phase 2: Consent Governance Interfaces ────────────────────────────────────

export interface AdminCourseConsentBreakdown {
  course_id: string;
  course_title: string;
  enrolled_students: number;
  accepted: number;
  withdrawn: number;
  declined: number;
  pending: number;
  coverage_percentage: number;
}

export interface AdminConsentNoticeHistoryItem {
  id: string;
  version: number;
  text: string;
  effective_from: string;
  is_active: boolean;
}

export interface AdminConsentCoverageResponse {
  active_notice?: {
    id: string;
    version: number;
    text: string;
    effective_from?: string;
    is_active: boolean;
  } | null;
  active_version?: number | null;
  total_students: number;
  accepted: number;
  withdrawn: number;
  declined: number;
  pending: number;
  coverage_percentage: number;
  course_breakdown: AdminCourseConsentBreakdown[];
  notice_history: AdminConsentNoticeHistoryItem[];
}

export interface AdminNoticeCreatePayload {
  text: string;
}

// ── Phase 2 API Functions ─────────────────────────────────────────────────────

/**
 * Lists courses with admin metadata, instructor profile, and student counts. (Admin & Auditor)
 */
export const getAdminCoursesPaginated = async (
  params?: AdminCourseFilterParams
): Promise<AdminPaginatedCoursesResponse> => {
  const response = await apiClient.get<AdminPaginatedCoursesResponse>('/admin/courses', {
    params,
  });
  return response.data;
};

/**
 * Updates course publication status with Feature 7 audit log. (Admin only)
 */
export const updateCoursePublishStatus = async (
  courseId: string,
  isPublished: boolean
): Promise<AdminCourseSummary> => {
  const response = await apiClient.put<AdminCourseSummary>(
    `/admin/courses/${courseId}/publish`,
    { is_published: isPublished }
  );
  return response.data;
};

/**
 * Assigns or reassigns course instructor with Feature 7 audit log. (Admin only)
 */
export const updateCourseLecturer = async (
  courseId: string,
  lecturerId: string
): Promise<AdminCourseSummary> => {
  const response = await apiClient.put<AdminCourseSummary>(
    `/admin/courses/${courseId}/lecturer`,
    { lecturer_id: lecturerId }
  );
  return response.data;
};

/**
 * Lists student enrolments with course/student metadata and filters. (Admin & Auditor)
 */
export const getAdminEnrolmentsPaginated = async (
  params?: AdminEnrolmentFilterParams
): Promise<AdminPaginatedEnrolmentsResponse> => {
  const response = await apiClient.get<AdminPaginatedEnrolmentsResponse>('/admin/enrolments', {
    params,
  });
  return response.data;
};

/**
 * Enrols a single student by email, ID, or PID with Feature 7 audit log. (Admin only)
 */
export const createAdminEnrolment = async (
  payload: AdminEnrolmentCreatePayload
): Promise<AdminEnrolmentItem> => {
  const response = await apiClient.post<AdminEnrolmentItem>('/admin/enrolments', payload);
  return response.data;
};

/**
 * Soft-removes a student enrolment (marks as dropped, preserves records). (Admin only)
 */
export const deleteAdminEnrolment = async (
  enrolmentId: string
): Promise<{ message: string; id: string; status: string }> => {
  const response = await apiClient.delete<{ message: string; id: string; status: string }>(
    `/admin/enrolments/${enrolmentId}`
  );
  return response.data;
};

/**
 * Idempotent bulk student enrolment with per-row results and Feature 7 audit log. (Admin only)
 */
export const bulkAdminEnrolment = async (
  payload: AdminBulkEnrolmentPayload
): Promise<AdminBulkEnrolmentResponse> => {
  const response = await apiClient.post<AdminBulkEnrolmentResponse>(
    '/admin/enrolments/bulk',
    payload
  );
  return response.data;
};

/**
 * Fetches consent posture, per-course breakdown, and version history. (Admin & Auditor)
 */
export const getAdminConsentCoverage = async (): Promise<AdminConsentCoverageResponse> => {
  const response = await apiClient.get<AdminConsentCoverageResponse>('/admin/consent/coverage');
  return response.data;
};

/**
 * Publishes a new consent notice version and archives previous. (Admin only)
 */
export const publishAdminConsentNotice = async (
  payload: AdminNoticeCreatePayload
): Promise<{ id: string; version: number; text: string; effective_from: string; is_active: boolean }> => {
  const response = await apiClient.post<{ id: string; version: number; text: string; effective_from: string; is_active: boolean }>(
    '/consent/notices',
    payload
  );
  return response.data;
};

// ── Phase 3: Pipeline Orchestrator Types & Methods ───────────────────────────

export interface PipelineStageInfo {
  status: 'pending' | 'running' | 'complete' | 'failed' | 'skipped';
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  input_summary?: Record<string, any>;
  output_summary?: Record<string, any>;
}

export interface PipelineRunStorage {
  course_id: string;
  week_index: number;
  trigger: 'scheduler' | 'manual';
  triggered_by: string;
  status: 'pending' | 'running' | 'complete' | 'failed' | 'partial';
  current_stage?: string | null;
  started_at: string;
  finished_at?: string | null;
  error_message?: string | null;
  stages: {
    lms_aggregation?: PipelineStageInfo;
    c1_affective?: PipelineStageInfo;
    c2_trajectory?: PipelineStageInfo;
    c3_risk?: PipelineStageInfo;
    c4_intervention?: PipelineStageInfo;
  };
}

export interface PaginatedPipelineRunsResponse {
  items: PipelineRunStorage[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PipelineTriggerPayload {
  course_id: string;
  week_index: number;
  force?: boolean;
}

export const getPipelineRuns = async (params?: {
  course_id?: string;
  week_index?: number;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedPipelineRunsResponse> => {
  const response = await apiClient.get<PaginatedPipelineRunsResponse>('/pipeline/runs', { params });
  return response.data;
};

export const getPipelineRunDetail = async (
  courseId: string,
  weekIndex: number
): Promise<PipelineRunStorage> => {
  const response = await apiClient.get<PipelineRunStorage>(`/pipeline/runs/${courseId}/${weekIndex}`);
  return response.data;
};

export const triggerPipelineRun = async (
  payload: PipelineTriggerPayload
): Promise<{ status: string; message: string; run?: PipelineRunStorage }> => {
  const response = await apiClient.post<{ status: string; message: string; run?: PipelineRunStorage }>(
    '/pipeline/trigger',
    payload
  );
  return response.data;
};

export const advancePipelineRun = async (
  courseId: string,
  weekIndex: number
): Promise<{ status: string; message: string; run?: PipelineRunStorage }> => {
  const response = await apiClient.post<{ status: string; message: string; run?: PipelineRunStorage }>(
    `/pipeline/runs/${courseId}/${weekIndex}/advance`
  );
  return response.data;
};

export const getPipelineStatus = async (): Promise<Record<string, any>> => {
  const response = await apiClient.get<Record<string, any>>('/pipeline/status');
  return response.data;
};

// ── Phase 3: Ingestion Health Types & Methods ────────────────────────────────

export interface ComponentIngestionHealth {
  component: string;
  title: string;
  api_key_configured: boolean;
  status: 'idle' | 'success' | 'partial' | 'failed';
  last_run_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  contract_version?: string | null;
  records_accepted_total: number;
  records_rejected_total: number;
  records_processed_total: number;
}

export interface AdminIngestionStatusResponse {
  components: Record<string, ComponentIngestionHealth>;
  total_runs: number;
  active_runs: number;
}

export interface AdminIngestionRunItem {
  id: string;
  component: string;
  started_at: string;
  finished_at?: string | null;
  status: 'success' | 'partial' | 'failed';
  records_processed: number;
  records_accepted: number;
  records_rejected: number;
  dry_run: boolean;
  contract_version?: string | null;
  error_message?: string | null;
}

export interface AdminPaginatedIngestionRunsResponse {
  items: AdminIngestionRunItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export const getAdminIngestionStatus = async (): Promise<AdminIngestionStatusResponse> => {
  const response = await apiClient.get<AdminIngestionStatusResponse>('/admin/ingestion/status');
  return response.data;
};

export const getAdminIngestionRuns = async (params?: {
  component?: string;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<AdminPaginatedIngestionRunsResponse> => {
  const response = await apiClient.get<AdminPaginatedIngestionRunsResponse>('/admin/ingestion/runs', {
    params,
  });
  return response.data;
};

// ── Phase 3: Privacy & Controlled Reveal Types & Methods ─────────────────────

export interface AdminIdentityRevealPayload {
  pid: string;
  justification: string;
}

export interface AdminIdentityRevealResponse {
  pid: string;
  student_id: string;
  name: string;
  email: string;
}

export interface AdminRevealHistoryItem {
  id: string;
  timestamp: string;
  actor_id: string;
  actor_role: string;
  pid: string;
  reason: string;
  outcome: string;
}

export interface AdminPaginatedRevealHistoryResponse {
  items: AdminRevealHistoryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AdminScrubTestPayload {
  text: string;
  known_names?: string[];
}

export interface AdminScrubTestResponse {
  clean_text: string;
  redaction_report: Record<string, number>;
}

export const breakglassRevealIdentity = async (
  payload: AdminIdentityRevealPayload
): Promise<AdminIdentityRevealResponse> => {
  const response = await apiClient.post<AdminIdentityRevealResponse>('/admin/privacy/reveal', payload);
  return response.data;
};

export const getRevealHistory = async (params?: {
  page?: number;
  page_size?: number;
}): Promise<AdminPaginatedRevealHistoryResponse> => {
  const response = await apiClient.get<AdminPaginatedRevealHistoryResponse>('/admin/privacy/reveal-history', {
    params,
  });
  return response.data;
};

export const testScrubContent = async (
  payload: AdminScrubTestPayload
): Promise<AdminScrubTestResponse> => {
  const response = await apiClient.post<AdminScrubTestResponse>('/admin/privacy/scrub-test', payload);
  return response.data;
};

// ── Phase 3: Exports & History Types & Methods ───────────────────────────────

export interface AdminExportHistoryItem {
  id: string;
  timestamp: string;
  actor_id: string;
  actor_role: string;
  dataset: string;
  format: string;
  row_count: number;
  filters: Record<string, any>;
}

export interface AdminPaginatedExportHistoryResponse {
  items: AdminExportHistoryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export const downloadAdminExport = async (
  dataset: string,
  format: 'csv' | 'json',
  courseId?: string,
  weekIndex?: number
): Promise<Blob> => {
  const response = await apiClient.get('/admin/exports/download', {
    params: {
      dataset,
      format,
      course_id: courseId || undefined,
      week_index: weekIndex !== undefined ? weekIndex : undefined,
    },
    responseType: 'blob',
  });
  return response.data;
};

export const getExportHistory = async (params?: {
  page?: number;
  page_size?: number;
}): Promise<AdminPaginatedExportHistoryResponse> => {
  const response = await apiClient.get<AdminPaginatedExportHistoryResponse>('/admin/exports/history', {
    params,
  });
  return response.data;
};

// ── Phase 3: System Diagnostics Types & Methods ──────────────────────────────

export interface AdminMigrationItem {
  migration_id: string;
  applied_at: string;
}

export interface AdminSystemHealthResponse {
  status: string;
  db_status: string;
  db_ping_ms: number;
  contract_version: string;
  contract_schemas: string[];
  applied_migrations: AdminMigrationItem[];
  total_migrations_applied: number;
  oulad_status: {
    is_imported: boolean;
    imported_students: number;
    imported_courses: number;
    imported_enrolments: number;
    cli_command: string;
  };
}

export const getAdminSystemHealth = async (): Promise<AdminSystemHealthResponse> => {
  const response = await apiClient.get<AdminSystemHealthResponse>('/admin/system/health');
  return response.data;
};

export const adminApi = {
  getAdminOverview,
  getAdminUsersPaginated,
  getAdminUsers,
  createAdminUser,
  getAdminUserDetail,
  updateAdminUserProfile,
  updateUserStatus,
  updateUserRole,
  getAdminStats,
  // Phase 2
  getAdminCoursesPaginated,
  updateCoursePublishStatus,
  updateCourseLecturer,
  getAdminEnrolmentsPaginated,
  createAdminEnrolment,
  deleteAdminEnrolment,
  bulkAdminEnrolment,
  getAdminConsentCoverage,
  publishAdminConsentNotice,
  // Phase 3
  getPipelineRuns,
  getPipelineRunDetail,
  triggerPipelineRun,
  advancePipelineRun,
  getPipelineStatus,
  getAdminIngestionStatus,
  getAdminIngestionRuns,
  breakglassRevealIdentity,
  getRevealHistory,
  testScrubContent,
  downloadAdminExport,
  getExportHistory,
  getAdminSystemHealth,
};


