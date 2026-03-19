'use client';

import { useState, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/lib/api';

export function useAdmin() {
  const queryClient = useQueryClient();
  const [generationStatus, setGenerationStatus] = useState<'idle' | 'generating' | 'success' | 'error'>('idle');
  const [generationMessage, setGenerationMessage] = useState('');

  // Get topics by grade
  const useTopicsByGrade = (grade: string) => {
    return useQuery({
      queryKey: ['admin', 'topics', grade],
      queryFn: async () => {
        const response = await adminApi.getTopicsByGrade(grade);
        return response.data;
      },
      enabled: !!grade,
    });
  };

  // Get question stats
  const statsQuery = useQuery({
    queryKey: ['admin', 'question-stats'],
    queryFn: async () => {
      const response = await adminApi.getQuestionStats();
      return response.data;
    },
  });

  // Get question count for specific combination
  const getQuestionCount = useCallback(async (
    grade: string,
    topic: string,
    difficulty: string
  ) => {
    const response = await adminApi.getQuestionCount(grade, topic, difficulty);
    return response.data.count;
  }, []);

  // Generate questions mutation
  const generateMutation = useMutation({
    mutationFn: async (data: {
      grade: string;
      topic: string;
      difficulty: string;
      count: number;
    }) => {
      setGenerationStatus('generating');
      setGenerationMessage('Generating questions...');
      const response = await adminApi.generateQuestions(data);
      return response.data;
    },
    onSuccess: (data) => {
      setGenerationStatus('success');
      setGenerationMessage(data.message);
      // Invalidate stats query to refresh counts
      queryClient.invalidateQueries({ queryKey: ['admin', 'question-stats'] });
    },
    onError: (error: any) => {
      setGenerationStatus('error');
      setGenerationMessage(error.response?.data?.detail || 'Failed to generate questions');
    },
  });

  return {
    // Queries
    stats: statsQuery.data,
    isLoadingStats: statsQuery.isLoading,
    refetchStats: statsQuery.refetch,
    useTopicsByGrade,

    // Actions
    getQuestionCount,
    generateQuestions: generateMutation.mutateAsync,

    // Status
    generationStatus,
    generationMessage,
    isGenerating: generateMutation.isPending,

    // Reset
    resetStatus: () => {
      setGenerationStatus('idle');
      setGenerationMessage('');
    },
  };
}
