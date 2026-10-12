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
};
