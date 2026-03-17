'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { authApi } from '@/lib/api';
import { useAuthStore } from '@/store/authStore';

export function useAuth() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, user, isAuthenticated, setAuth, logout: clearAuth } = useAuthStore();

  const loginMutation = useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      authApi.login(username, password),
    onSuccess: (response) => {
      const { access_token } = response.data;
      if (typeof window !== 'undefined') {
        localStorage.setItem('token', access_token);
      }
      queryClient.invalidateQueries({ queryKey: ['me'] });
      router.push('/');
    },
  });

  const registerMutation = useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      authApi.register(username, password),
    onSuccess: (response) => {
      const { access_token } = response.data;
      if (typeof window !== 'undefined') {
        localStorage.setItem('token', access_token);
      }
      queryClient.invalidateQueries({ queryKey: ['me'] });
      router.push('/');
    },
  });

  const logoutMutation = useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('token');
      }
      clearAuth();
      queryClient.clear();
      router.push('/login');
    },
  });

  const { data: meData, isLoading: isLoadingMe } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const response = await authApi.me();
      if (response.data.logged_in && typeof window !== 'undefined') {
        setAuth(localStorage.getItem('token') || '', {
          id: response.data.user_id,
          username: response.data.username,
        });
      }
      return response.data;
    },
    enabled: typeof window !== 'undefined' ? !!localStorage.getItem('token') : false,
  });

  return {
    user: meData || user,
    isAuthenticated: meData?.logged_in || isAuthenticated,
    isLoading: isLoadingMe,
    login: loginMutation.mutate,
    register: registerMutation.mutate,
    logout: logoutMutation.mutate,
    isLoggingIn: loginMutation.isPending,
    isRegistering: registerMutation.isPending,
    isLoggingOut: logoutMutation.isPending,
    loginError: loginMutation.error,
    registerError: registerMutation.error,
  };
}