import { apiClient } from './client';

export type UserRole = 'student' | 'lecturer' | 'counsellor' | 'admin' | 'auditor';


export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  role?: UserRole;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  consent_required?: boolean;
}


export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  profile?: {
    id: string;
    student_id: string | null;
    department: string | null;
    bio: string | null;
    avatar_url: string | null;
  } | null;
}

/**
 * Logs in a user using application/x-www-form-urlencoded format
 * conforming to OAuth2 password flow specification.
 */
export const loginUser = async (credentials: LoginPayload): Promise<TokenResponse> => {
  const params = new URLSearchParams();
  // FastAPI OAuth2PasswordRequestForm expects 'username' field
  params.append('username', credentials.email.trim());
  params.append('password', credentials.password);

  const response = await apiClient.post<TokenResponse>('/auth/login', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
};

/**
 * Registers a new user account with JSON payload.
 */
export const registerUser = async (payload: RegisterPayload): Promise<UserProfile> => {
  const response = await apiClient.post<UserProfile>('/auth/register', {
    ...payload,
    email: payload.email.trim().toLowerCase(),
    full_name: payload.full_name.trim(),
  });
  return response.data;
};

/**
 * Retrieves the currently authenticated user's profile.
 */
export const getMe = async (): Promise<UserProfile> => {
  const response = await apiClient.get<UserProfile>('/users/me');
  return response.data;
};

// Unified authApi export for backward compatibility and convenience
export const authApi = {
  login: loginUser,
  register: registerUser,
  getMe,
};
