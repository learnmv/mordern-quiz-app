'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Check, X, Flag, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { useQuiz } from '@/hooks/useQuiz';
import { useQuizPersistence } from '@/hooks/useQuizPersistence';
import { DiagramRenderer } from '../components/quiz/DiagramRenderer';
import { QuestionNavigator } from '../components/quiz/QuestionNavigator';
import { CanvasPanel } from '../components/quiz/CanvasPanel';
import { QuizReview } from '../components/quiz/QuizReview';
import { QuizSkeleton } from '../components/quiz/QuizSkeleton';
import { GenerationProgress } from '../components/quiz/GenerationProgress';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import type { Question } from '@/types';

export default function QuizPage() {
  const searchParams = useSearchParams();
  const grade = searchParams.get('grade') || '6';
  const topics = searchParams.get('topics')?.split(',') || [];
  const difficulty = searchParams.get('difficulty') || 'easy';
  const count = parseInt(searchParams.get('count') || '5');

  // Quiz state
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string[]>>({});
  const [answered, setAnswered] = useState<Record<number, boolean>>({});
  const [showFeedback, setShowFeedback] = useState<Record<number, boolean>>({});
  const [score, setScore] = useState({ correct: 0, wrong: 0 });
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [quizComplete, setQuizComplete] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [showReview, setShowReview] = useState(false);

  // UI state
  const [isCanvasOpen, setIsCanvasOpen] = useState(true);
  const [flagged, setFlagged] = useState<Record<number, boolean>>({});
  const [canvasSnapshots, setCanvasSnapshots] = useState<Record<number, string>>({});
  const [showRecoveryDialog, setShowRecoveryDialog] = useState(false);
  const [pendingSession, setPendingSession] = useState<ReturnType<typeof loadSession> | null>(null);

  const { generateQuiz, generateDiagramQuiz, submitAnswer, retryLastOperation, loadingState, errorMessage, retryCount, isGenerating, isGeneratingDiagram, quizData, diagramQuizData } = useQuiz();
  const { saveSession, loadSession, clearSession, hasActiveSession } = useQuizPersistence();

  // Check for existing session on mount
  useEffect(() => {
    if (!isInitialized && hasActiveSession()) {
      const session = loadSession();
      if (session) {
        // Check if session matches current params
        const sessionGrade = session.grade;
        const sessionTopics = session.topics?.join(',') || '';
        const sessionDifficulty = session.difficulty;
        const currentTopics = topics.join(',');

        // Only show recovery dialog if params match
        if (sessionGrade === grade && sessionTopics === currentTopics && sessionDifficulty === difficulty) {
          setPendingSession(session);
          setShowRecoveryDialog(true);
        } else {
          // Different quiz params, clear old session
          clearSession();
        }
      }
    }
  }, [isInitialized, hasActiveSession, loadSession, clearSession, grade, topics, difficulty]);

  // Load first question
  useEffect(() => {
    if (!isInitialized && !showRecoveryDialog) {
      loadNextQuestion();
      setIsInitialized(true);
    }
  }, [isInitialized, showRecoveryDialog]);

  // Handle quiz data when generated
  useEffect(() => {
    if (quizData?.questions) {
      setQuestions((prev) => {
        const newQuestions = [...prev, ...quizData.questions];
        if (currentQ >= prev.length && newQuestions.length > prev.length) {
          setCurrentQ(prev.length);
        }
        return newQuestions;
      });
    }
  }, [quizData, currentQ]);

  // Handle diagram quiz data when generated
  useEffect(() => {
    if (diagramQuizData?.questions) {
      setQuestions((prev) => {
        const newQuestions = [...prev, ...diagramQuizData.questions];
        if (currentQ >= prev.length && newQuestions.length > prev.length) {
          setCurrentQ(prev.length);
        }
        return newQuestions;
      });
    }
  }, [diagramQuizData, currentQ]);

  // Timer
  useEffect(() => {
    if (quizComplete || showReview) return;
    const timer = setInterval(() => {
      setElapsedSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [quizComplete, showReview]);

  // Save session on state changes
  useEffect(() => {
    if (isInitialized && questions.length > 0 && !quizComplete && !showReview) {
      saveSession({
        questions,
        currentQ,
        answers,
        answered,
        score,
        elapsedSeconds,
        canvasSnapshots,
        grade,
        topics,
        difficulty,
        startedAt: new Date().toISOString(),
        flagged,
      });
    }
  }, [questions, currentQ, answers, answered, score, elapsedSeconds, canvasSnapshots, isInitialized, quizComplete, showReview, saveSession, grade, topics, difficulty, flagged]);

  const loadNextQuestion = async () => {
    try {
      // If topics are specified, use diagram quiz generation
      if (topics.length > 0) {
        await generateDiagramQuiz({
          grade,
          topic: topics[0],
          difficulty,
          count: count || 1,
        });
      } else {
        // Use standard quiz generation
        await generateQuiz({ grade, count: count || 1 });
      }
    } catch (error) {
      console.error('Error loading question:', error);
    }
  };

  const handleRestoreSession = () => {
    if (pendingSession) {
      setQuestions(pendingSession.questions);
      setCurrentQ(pendingSession.currentQ);
      setAnswers(pendingSession.answers);
      setAnswered(pendingSession.answered);
      setScore(pendingSession.score);
      setElapsedSeconds(pendingSession.elapsedSeconds);
      setCanvasSnapshots(pendingSession.canvasSnapshots);
      setFlagged(pendingSession.flagged || {});
      setIsInitialized(true);
    }
    setShowRecoveryDialog(false);
  };

  const handleStartFresh = () => {
    clearSession();
    setShowRecoveryDialog(false);
    loadNextQuestion();
    setIsInitialized(true);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleOptionSelect = async (qIdx: number, value: string) => {
    if (answered[qIdx]) return;

    const question = questions[qIdx];
    const isCorrect = question.correct.includes(value);

    setAnswers((prev) => ({ ...prev, [qIdx]: [value] }));
    setAnswered((prev) => ({ ...prev, [qIdx]: true }));
    setShowFeedback((prev) => ({ ...prev, [qIdx]: true }));

    if (isCorrect) {
      setScore((s) => ({ ...s, correct: s.correct + 1 }));
    } else {
      setScore((s) => ({ ...s, wrong: s.wrong + 1 }));
    }

    // Submit to backend
    await submitAnswer({
      question_hash: question.hash || `q${qIdx}`,
      topic: question.topic || 'general',
      was_correct: isCorrect,
      time_spent: elapsedSeconds,
    });
  };

  const handleSaveCanvasSnapshot = useCallback((qIndex: number, dataUrl: string) => {
    setCanvasSnapshots(prev => ({
      ...prev,
      [qIndex]: dataUrl
    }));
  }, []);

  const changeQuestion = async (newIdx: number) => {
    if (newIdx >= 0 && newIdx < questions.length) {
      setCurrentQ(newIdx);
    }
  };

  const handleNavigate = (index: number) => {
    changeQuestion(index);
  };

  const handleToggleFlag = (index: number) => {
    setFlagged(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const finishQuiz = () => {
    setQuizComplete(true);
    setShowReview(true);
    clearSession();
  };

  const handleRetryQuiz = () => {
    // Reset all state
    setQuestions([]);
    setCurrentQ(0);
    setAnswers({});
    setAnswered({});
    setShowFeedback({});
    setScore({ correct: 0, wrong: 0 });
    setElapsedSeconds(0);
    setCanvasSnapshots({});
    setFlagged({});
    setQuizComplete(false);
    setShowReview(false);
    setIsInitialized(false);
    clearSession();
  };

  const currentQuestion = questions[currentQ];

  // Keyboard navigation
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Ignore if no current question or if typing in an input
      if (!currentQuestion || quizComplete || showReview || document.activeElement?.tagName === 'INPUT') {
        return;
      }

      // Number keys 1-4 for selecting options
      if (e.key >= '1' && e.key <= '4') {
        const optionIndex = parseInt(e.key) - 1;
        if (currentQuestion.options[optionIndex] && !answered[currentQ]) {
          const value = currentQuestion.options[optionIndex].charAt(0);
          handleOptionSelect(currentQ, value);
        }
      }

      // Arrow right for next question
      if (e.key === 'ArrowRight') {
        if (currentQ < questions.length - 1) {
          changeQuestion(currentQ + 1);
        }
      }

      // Arrow left for previous question
      if (e.key === 'ArrowLeft') {
        if (currentQ > 0) {
          changeQuestion(currentQ - 1);
        }
      }

      // F key to flag current question
      if (e.key === 'f' || e.key === 'F') {
        handleToggleFlag(currentQ);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [currentQuestion, currentQ, questions.length, answered, quizComplete, showReview]);
  const isLoading = isGenerating || isGeneratingDiagram;
  const loadingStage = loadingState === 'retrying' ? 'retrying' : loadingState === 'generating' ? 'generating' : 'pregenerated';

  // Show review mode
  if (showReview) {
    return (
      <QuizReview
        questions={questions}
        answers={answers}
        score={score}
        elapsedSeconds={elapsedSeconds}
        onRetry={handleRetryQuiz}
      />
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Session Recovery Dialog */}
      <Dialog open={showRecoveryDialog} onOpenChange={setShowRecoveryDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Resume Previous Quiz?</DialogTitle>
            <DialogDescription>
              You have an unfinished quiz from earlier. Would you like to resume where you left off?
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {pendingSession && (
              <div className="text-sm text-muted-foreground space-y-1">
                <p>Progress: {Object.keys(pendingSession.answered).length} / {pendingSession.questions.length} questions answered</p>
                <p>Time elapsed: {formatTime(pendingSession.elapsedSeconds)}</p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleStartFresh}>
              Start Fresh
            </Button>
            <Button onClick={handleRestoreSession}>
              Resume Quiz
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Header */}
      <header className="border-b bg-card px-4 py-3">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              if (Object.keys(answers).length > 0 && !quizComplete) {
                const confirmed = window.confirm(
                  'You have unsaved progress. Your answers are saved, but you\'ll exit the quiz. Continue?'
                );
                if (confirmed) {
                  window.location.href = '/';
                }
              } else {
                window.location.href = '/';
              }
            }}
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Exit
          </Button>

          <div className="flex items-center gap-4">
            <div className="text-sm text-muted-foreground">
              Time: {formatTime(elapsedSeconds)}
            </div>
            <div className="flex gap-4 text-sm">
              <span className="text-green-600"><Check className="inline h-4 w-4 mr-1" />{score.correct}</span>
              <span className="text-red-600"><X className="inline h-4 w-4 mr-1" />{score.wrong}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Progress bar */}
      <div className="w-full bg-secondary">
        <div
          className="h-1 bg-primary transition-all duration-300"
          style={{ width: `${questions.length > 0 ? ((currentQ + 1) / questions.length) * 100 : 0}%` }}
        />
      </div>

      <div className="flex h-[calc(100vh-65px)]">
        {/* Left Sidebar - Question Navigator */}
        <div className="w-64 border-r bg-card flex flex-col hidden lg:flex">
          <QuestionNavigator
            totalQuestions={questions.length || count}
            currentQ={currentQ}
            answered={answered}
            flagged={flagged}
            onNavigate={handleNavigate}
          />

          {/* Flag Button */}
          <div className="p-4 border-t mt-auto">
            <Button
              variant={flagged[currentQ] ? 'default' : 'outline'}
              size="sm"
              className="w-full"
              onClick={() => handleToggleFlag(currentQ)}
            >
              <Flag className={`h-4 w-4 mr-2 ${flagged[currentQ] ? 'fill-current' : ''}`} />
              {flagged[currentQ] ? 'Flagged for Review' : 'Flag for Review'}
            </Button>
            <p className="text-xs text-muted-foreground mt-2 text-center">
              Press &apos;F&apos; to toggle flag
            </p>
          </div>
        </div>

        {/* Question Panel */}
        <div className="flex-1 overflow-y-auto p-6">
          {!currentQuestion || isLoading ? (
            errorMessage ? (
              <div className="flex flex-col items-center justify-center h-full">
                <div className="text-red-500 mb-4">
                  <AlertCircle className="h-12 w-12 mx-auto mb-2" />
                  <p className="text-lg font-medium">{errorMessage}</p>
                </div>
                <Button onClick={retryLastOperation} variant="outline" className="mt-4">
                  Try Again
                </Button>
              </div>
            ) : (
              <GenerationProgress
                stage={loadingStage}
                retryCount={retryCount}
                maxRetries={3}
              />
            )
          ) : (
            <div className="max-w-2xl mx-auto">
              {/* Mobile Question Navigator */}
              <div className="lg:hidden mb-4">
                <QuestionNavigator
                  totalQuestions={questions.length}
                  currentQ={currentQ}
                  answered={answered}
                  flagged={flagged}
                  onNavigate={handleNavigate}
                />
              </div>

              <div className="flex items-center gap-2 mb-4">
                <Badge>Q{currentQ + 1}</Badge>
                <Badge variant="secondary">{currentQuestion.topic || 'General'}</Badge>
                {flagged[currentQ] && (
                  <Badge className="bg-amber-100 text-amber-800">
                    <Flag className="h-3 w-3 mr-1" />
                    Flagged
                  </Badge>
                )}
              </div>

              <h2 className="text-xl font-medium mb-6">{currentQuestion.text}</h2>

              {/* Diagram Display */}
              {(currentQuestion as any).diagram && (
                <div className="mb-6 flex justify-center">
                  <DiagramRenderer
                    diagram={(currentQuestion as any).diagram}
                    interactive={(currentQuestion as any).requires_canvas}
                    onDraw={(data) => console.log('User drew:', data)}
                  />
                </div>
              )}

              <div className="space-y-3">
                {currentQuestion.options.map((option, idx) => {
                  const value = option.charAt(0);
                  const isSelected = answers[currentQ]?.includes(value);
                  const isCorrect = currentQuestion.correct.includes(value);
                  const showResult = answered[currentQ];

                  let className =
                    'w-full text-left p-4 rounded-lg border-2 transition-all ';
                  if (showResult) {
                    if (isCorrect) {
                      className += 'border-green-500 bg-green-50 dark:bg-green-900/20';
                    } else if (isSelected) {
                      className += 'border-red-500 bg-red-50 dark:bg-red-900/20';
                    } else {
                      className += 'border-border';
                    }
                  } else {
                    className += isSelected
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50';
                  }

                  return (
                    <button
                      key={idx}
                      className={className}
                      onClick={() => handleOptionSelect(currentQ, value)}
                      disabled={answered[currentQ]}
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex-shrink-0 w-8 h-8 rounded bg-secondary flex items-center justify-center font-medium">
                          {value}
                        </span>
                        <span>{option.substring(3)}</span>
                        {showResult && isCorrect && (
                          <Check className="ml-auto h-5 w-5 text-green-500" />
                        )}
                        {showResult && isSelected && !isCorrect && (
                          <X className="ml-auto h-5 w-5 text-red-500" />
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>

              {showFeedback[currentQ] && (
                <div className="mt-6 p-4 rounded-lg bg-secondary">
                  <p className="font-medium mb-1">Explanation:</p>
                  <p className="text-muted-foreground">{currentQuestion.explanation}</p>
                </div>
              )}

              {/* Navigation */}
              <div className="flex justify-between mt-8">
                <Button
                  variant="outline"
                  onClick={() => changeQuestion(currentQ - 1)}
                  disabled={currentQ === 0}
                >
                  <ArrowLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>

                {currentQ === questions.length - 1 ? (
                  <Button onClick={finishQuiz} variant="default">
                    Finish Quiz
                  </Button>
                ) : (
                  <Button onClick={() => changeQuestion(currentQ + 1)}>
                    Next
                  </Button>
                )}
              </div>

              {/* Finish button for answered questions */}
              {Object.keys(answered).length > 0 && (
                <div className="mt-4 text-center">
                  <Button variant="outline" onClick={finishQuiz}>
                    Finish Quiz ({Object.keys(answered).length}/{questions.length} answered)
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Canvas Panel */}
        <CanvasPanel
          isOpen={isCanvasOpen}
          onToggle={() => setIsCanvasOpen(!isCanvasOpen)}
          currentQ={currentQ}
          onSaveSnapshot={handleSaveCanvasSnapshot}
          snapshot={canvasSnapshots[currentQ]}
        />
      </div>
    </div>
  );
}
