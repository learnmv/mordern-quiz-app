'use client';

import { useState, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { quizApi } from '@/lib/api';
import type { QuizResponse, Question, DiagramQuizResponse } from '@/types';

// Retry configuration
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1000;

// Delay helper
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export type LoadingState = 'idle' | 'loading' | 'generating' | 'retrying' | 'error';

export function useQuiz() {
  const queryClient = useQueryClient();
  const [loadingState, setLoadingState] = useState<LoadingState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const generateQuizMutation = useMutation({
    mutationFn: async ({ grade, count }: { grade: string; count: number }) => {
      setLoadingState('generating');
      setErrorMessage(null);

      let lastError: Error | null = null;

      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
          if (attempt > 0) {
            setLoadingState('retrying');
            setRetryCount(attempt);
            await delay(RETRY_DELAY_MS * attempt); // Exponential backoff
          }

          const result = await quizApi.generate(grade, count);
          setLoadingState('idle');
          setRetryCount(0);
          return result;
        } catch (error) {
          lastError = error as Error;
          console.error(`Quiz generation attempt ${attempt + 1} failed:`, error);

          if (attempt === MAX_RETRIES) {
            setLoadingState('error');
            setErrorMessage('Failed to generate quiz after multiple attempts. Please try again.');
            throw lastError;
          }
        }
      }

      throw lastError;
    },
  });

  const submitAnswerMutation = useMutation({
    mutationFn: (data: {
      question_hash: string;
      topic: string;
      was_correct: boolean;
      time_spent: number;
    }) => quizApi.submitAnswer(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['progress'] });
    },
  });

  const weakTopicsQuizMutation = useMutation({
    mutationFn: async () => {
      setLoadingState('loading');
      try {
        const result = await quizApi.getWeakTopicsQuiz();
        setLoadingState('idle');
        return result;
      } catch (error) {
        setLoadingState('error');
        throw error;
      }
    },
  });

  const generateDiagramQuizMutation = useMutation({
    mutationFn: async ({ grade, topic, difficulty, count }: { grade: string; topic: string; difficulty: string; count: number }) => {
      setLoadingState('generating');
      setErrorMessage(null);

      let lastError: Error | null = null;

      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
          if (attempt > 0) {
            setLoadingState('retrying');
            setRetryCount(attempt);
            await delay(RETRY_DELAY_MS * attempt);
          }

          const result = await quizApi.generateDiagramQuiz(grade, topic, difficulty, count);
          setLoadingState('idle');
          setRetryCount(0);
          return result;
        } catch (error) {
          lastError = error as Error;
          console.error(`Diagram quiz generation attempt ${attempt + 1} failed:`, error);

          if (attempt === MAX_RETRIES) {
            setLoadingState('error');
            setErrorMessage('Failed to generate quiz after multiple attempts. Please try again.');
            throw lastError;
          }
        }
      }

      throw lastError;
    },
  });

  // Manual retry function
  const retryLastOperation = useCallback(() => {
    setLoadingState('idle');
    setErrorMessage(null);
    setRetryCount(0);
  }, []);

  return {
    generateQuiz: generateQuizMutation.mutate,
    submitAnswer: submitAnswerMutation.mutate,
    getWeakTopicsQuiz: weakTopicsQuizMutation.mutate,
    generateDiagramQuiz: generateDiagramQuizMutation.mutate,
    retryLastOperation,
    isGenerating: generateQuizMutation.isPending || loadingState === 'generating',
    isSubmitting: submitAnswerMutation.isPending,
    isLoadingWeakTopics: weakTopicsQuizMutation.isPending,
    isGeneratingDiagram: generateDiagramQuizMutation.isPending || loadingState === 'generating',
    loadingState,
    errorMessage,
    retryCount,
    quizData: generateQuizMutation.data?.data as QuizResponse | undefined,
    diagramQuizData: generateDiagramQuizMutation.data?.data as DiagramQuizResponse | undefined,
    weakTopicsData: weakTopicsQuizMutation.data?.data,
    generateError: generateQuizMutation.error,
    generateDiagramError: generateDiagramQuizMutation.error,
  };
}