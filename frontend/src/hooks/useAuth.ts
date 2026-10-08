import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi, LoginPayload } from '../api/auth';

export const useAuth = () => {
  const queryClient = useQueryClient();
  const token = localStorage.getItem('access_token');

  // Fetch current user if token exists
  const {
    data: user,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['currentUser'],
    queryFn: authApi.getMe,
    enabled: !!token,
    retry: false,
  });

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: (credentials: LoginPayload) => authApi.login(credentials),
    onSuccess: (data) => {
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
    },
  });

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    queryClient.setQueryData(['currentUser'], null);
    window.location.href = '/login';
  };

  return {
    user,
    isAuthenticated: !!token && !isError,
    isLoading,
    login: loginMutation.mutateAsync,
    isLoggingIn: loginMutation.isPending,
    loginError: loginMutation.error,
    logout,
    refetchUser: refetch,
  };
};
