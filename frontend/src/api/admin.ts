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
};

