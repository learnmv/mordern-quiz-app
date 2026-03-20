'use client';

import { useCallback } from 'react';
import { Question } from '@/types';

interface QuizSession {
  questions: Question[];
  currentQ: number;
  answers: Record<number, string[]>;
  answered: Record<number, boolean>;
  score: { correct: number; wrong: number };
  elapsedSeconds: number;
  canvasSnapshots: Record<number, string>;
  grade: string;
  topics: string[];
  difficulty: string;
  startedAt: string;
  flagged?: Record<number, boolean>;
}

const STORAGE_KEY = 'quiz_session';

export function useQuizPersistence() {
  const saveSession = useCallback((session: QuizSession) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } catch (e) {
      console.error('Failed to save quiz session:', e);
    }
  }, []);

  const loadSession = useCallback((): QuizSession | null => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      console.error('Failed to load quiz session:', e);
    }
    return null;
  }, []);

  const clearSession = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const hasActiveSession = useCallback((): boolean => {
    const session = loadSession();
    if (!session) return false;
    // Check if session is less than 24 hours old
    const started = new Date(session.startedAt);
    const now = new Date();
    const hoursDiff = (now.getTime() - started.getTime()) / (1000 * 60 * 60);
    return hoursDiff < 24;
  }, [loadSession]);

  return {
    saveSession,
    loadSession,
    clearSession,
    hasActiveSession,
  };
}
