import { apiClient } from './client';
import { UserRole } from './auth';
import { ProfileResponse } from './users';

export interface SystemStatsResponse {
  total_users: number;
  active_users: number;
  total_courses: number;
  published_courses: number;
  total_students: number;
  total_lecturers: number;
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
  profile: ProfileResponse | null;
}

export interface UserStatusUpdatePayload {
  is_active: boolean;
}

export interface UserRoleUpdatePayload {
  role: UserRole;
}

/**
 * Fetches platform-wide statistics and resource metrics. (Admin only)
 */
export const getAdminStats = async (): Promise<SystemStatsResponse> => {
  const response = await apiClient.get<SystemStatsResponse>('/admin/stats');
  return response.data;
};

/**
 * Fetches all registered users with nested profiles. (Admin only)
 */
export const getAdminUsers = async (): Promise<AdminUserResponse[]> => {
  const response = await apiClient.get<AdminUserResponse[]>('/admin/users');
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

export const adminApi = {
  getAdminStats,
  getAdminUsers,
  updateUserStatus,
  updateUserRole,
};
