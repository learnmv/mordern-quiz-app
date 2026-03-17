'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { quizApi } from '@/lib/api';
import type { QuizResponse, Question, DiagramQuizResponse } from '@/types';

export function useQuiz() {
  const queryClient = useQueryClient();

  const generateQuizMutation = useMutation({
    mutationFn: ({ grade, count }: { grade: string; count: number }) =>
      quizApi.generate(grade, count),
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
    mutationFn: () => quizApi.getWeakTopicsQuiz(),
  });

  const generateDiagramQuizMutation = useMutation({
    mutationFn: ({ grade, topic, difficulty, count }: { grade: string; topic: string; difficulty: string; count: number }) =>
      quizApi.generateDiagramQuiz(grade, topic, difficulty, count),
  });

  return {
    generateQuiz: generateQuizMutation.mutate,
    submitAnswer: submitAnswerMutation.mutate,
    getWeakTopicsQuiz: weakTopicsQuizMutation.mutate,
    generateDiagramQuiz: generateDiagramQuizMutation.mutate,
    isGenerating: generateQuizMutation.isPending,
    isSubmitting: submitAnswerMutation.isPending,
    isLoadingWeakTopics: weakTopicsQuizMutation.isPending,
    isGeneratingDiagram: generateDiagramQuizMutation.isPending,
    quizData: generateQuizMutation.data?.data as QuizResponse | undefined,
    diagramQuizData: generateDiagramQuizMutation.data?.data as DiagramQuizResponse | undefined,
    weakTopicsData: weakTopicsQuizMutation.data?.data,
    generateError: generateQuizMutation.error,
    generateDiagramError: generateDiagramQuizMutation.error,
  };
}