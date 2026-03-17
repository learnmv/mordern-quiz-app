'use client';

import { useQuery } from '@tanstack/react-query';
import { progressApi } from '@/lib/api';
import type { ProgressResponse } from '@/types';

export function useProgress() {
  const { data, isLoading, error } = useQuery<ProgressResponse>({
    queryKey: ['progress'],
    queryFn: async () => {
      const response = await progressApi.getProgress();
      return response.data;
    },
  });

  const { data: weakTopics, isLoading: isLoadingWeak } = useQuery({
    queryKey: ['weak-topics'],
    queryFn: async () => {
      const response = await progressApi.getWeakTopics();
      return response.data;
    },
  });

  return {
    progress: data,
    isLoading,
    error,
    weakTopics,
    isLoadingWeak,
  };
}