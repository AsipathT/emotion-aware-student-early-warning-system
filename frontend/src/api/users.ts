import { apiClient } from './client';
import { UserRole } from './auth';

export interface ProfileResponse {
  id: string;
  student_id: string | null;
  department: string | null;
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserMeResponse {
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

export interface ProfileUpdatePayload {
  student_id?: string | null;
  department?: string | null;
  bio?: string | null;
  avatar_url?: string | null;
}

/**
 * Fetches the currently authenticated user's account and profile.
 * Automatically attaches Authorization: Bearer <token> via apiClient interceptor.
 */
export const getCurrentUser = async (): Promise<UserMeResponse> => {
  const response = await apiClient.get<UserMeResponse>('/users/me');
  return response.data;
};

/**
 * Creates or updates the authenticated user's profile with partial attributes.
 * Automatically attaches Authorization: Bearer <token> via apiClient interceptor.
 */
export const updateUserProfile = async (
  payload: ProfileUpdatePayload
): Promise<ProfileResponse> => {
  const response = await apiClient.put<ProfileResponse>('/users/me/profile', payload);
  return response.data;
};

export const usersApi = {
  getCurrentUser,
  updateUserProfile,
};
