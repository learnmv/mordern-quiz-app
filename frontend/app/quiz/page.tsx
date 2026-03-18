'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, Check, X, Eraser, Palette, Trash2, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { useQuiz } from '@/hooks/useQuiz';
import { DiagramRenderer } from '../components/quiz/DiagramRenderer';
import type { Question } from '@/types';

export default function QuizPage() {
  const searchParams = useSearchParams();
  const grade = searchParams.get('grade') || '6';
  const topics = searchParams.get('topics')?.split(',') || [];
  const difficulty = searchParams.get('difficulty') || 'easy';
  const count = parseInt(searchParams.get('count') || '5');

  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string[]>>({});
  const [answered, setAnswered] = useState<Record<number, boolean>>({});
  const [showFeedback, setShowFeedback] = useState<Record<number, boolean>>({});
  const [score, setScore] = useState({ correct: 0, wrong: 0 });
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [quizComplete, setQuizComplete] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  const { generateQuiz, generateDiagramQuiz, submitAnswer, retryLastOperation, loadingState, errorMessage, retryCount, isGenerating, isGeneratingDiagram, quizData, diagramQuizData } = useQuiz();

  // Canvas refs
  const [canvasSnapshots, setCanvasSnapshots] = useState<Record<number, string>>({});
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentTool, setCurrentTool] = useState('pen');
  const [currentColor, setCurrentColor] = useState('#1e293b');
  const [lineWidth, setLineWidth] = useState(3);
  const lastPos = useRef({ x: 0, y: 0 });

  // Load first question
  useEffect(() => {
    if (!isInitialized) {
      loadNextQuestion();
      setIsInitialized(true);
    }
  }, [isInitialized]);

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

  // Restore canvas when question changes
  useEffect(() => {
    restoreCanvasSnapshot(currentQ);
  }, [currentQ]);
  useEffect(() => {
    if (quizComplete) return;
    const timer = setInterval(() => {
      setElapsedSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [quizComplete]);

  const loadNextQuestion = async () => {
    try {
      // If topics are specified, use diagram quiz generation
      if (topics.length > 0) {
        // Use the first topic for diagram quiz generation
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

  const saveCanvasSnapshot = () => {
    const canvas = canvasRef.current;
    if (canvas) {
      const dataUrl = canvas.toDataURL('image/png');
      setCanvasSnapshots(prev => ({
        ...prev,
        [currentQ]: dataUrl
      }));
    }
  };

  const restoreCanvasSnapshot = (questionIndex: number) => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    const snapshot = canvasSnapshots[questionIndex];
    if (snapshot) {
      const img = new Image();
      img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
      };
      img.src = snapshot;
    } else {
      // Clear canvas if no snapshot
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
  };

  const changeQuestion = async (dir: number) => {
    // Save current canvas before navigating
    saveCanvasSnapshot();

    const newIdx = currentQ + dir;

    if (dir === 1 && newIdx >= questions.length) {
      await loadNextQuestion();
      return;
    }

    if (newIdx >= 0 && newIdx < questions.length) {
      setCurrentQ(newIdx);
    }
  };

  const finishQuiz = () => {
    setQuizComplete(true);
  };

  // Canvas functions
  const getCanvasPos = (e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };

    const rect = canvas.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;

    return {
      x: clientX - rect.left,
      y: clientY - rect.top,
    };
  };

  const startDrawing = (e: React.MouseEvent | React.TouchEvent) => {
    setIsDrawing(true);
    const pos = getCanvasPos(e);
    lastPos.current = pos;
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawing) return;
    e.preventDefault();

    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    const pos = getCanvasPos(e);

    ctx.beginPath();
    ctx.moveTo(lastPos.current.x, lastPos.current.y);
    ctx.lineTo(pos.x, pos.y);
    ctx.strokeStyle = currentTool === 'eraser' ? '#ffffff' : currentColor;
    ctx.lineWidth = currentTool === 'eraser' ? lineWidth * 4 : lineWidth;
    ctx.lineCap = 'round';
    ctx.stroke();

    lastPos.current = pos;
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  };

  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const container = canvas?.parentElement;
    if (!canvas || !container) return;

    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight - 56;
    clearCanvas();
  }, []);

  useEffect(() => {
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    return () => window.removeEventListener('resize', resizeCanvas);
  }, [resizeCanvas]);

  const currentQuestion = questions[currentQ];

  // Keyboard navigation
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Ignore if no current question or if typing in an input
      if (!currentQuestion || quizComplete || document.activeElement?.tagName === 'INPUT') {
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
        if (answered[currentQ] && currentQ < questions.length - 1) {
          changeQuestion(1);
        }
      }

      // Arrow left for previous question
      if (e.key === 'ArrowLeft') {
        if (currentQ > 0) {
          changeQuestion(-1);
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [currentQuestion, currentQ, questions.length, answered, quizComplete]);

  if (quizComplete) {
    const total = score.correct + score.wrong;
    const percent = total > 0 ? Math.round((score.correct / total) * 100) : 0;

    let message = '';
    if (percent >= 90) message = 'Outstanding! 🌟';
    else if (percent >= 70) message = 'Great job! 👍';
    else if (percent >= 50) message = 'Good effort! 💪';
    else message = 'Keep practicing! 📚';

    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md text-center">
          <CardContent className="pt-8 pb-8">
            <h1 className="text-3xl font-bold mb-4">Quiz Complete!</h1>
            <div className="text-6xl font-bold text-primary mb-4">
              {score.correct}/{total}
            </div>
            <p className="text-xl text-muted-foreground mb-2">
              {percent}% {message}
            </p>
            <div className="flex justify-center gap-8 mt-6">
              <div className="text-green-600">
                <Check className="inline h-5 w-5 mr-1" />
                {score.correct} Correct
              </div>
              <div className="text-red-600">
                <X className="inline h-5 w-5 mr-1" />
                {score.wrong} Incorrect
              </div>
            </div>
            <Link href="/">
              <Button className="mt-8">Back to Home</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
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
          style={{ width: `${((currentQ + 1) / questions.length) * 100}%` }}
        />
      </div>

      <div className="flex h-[calc(100vh-65px)]">
        {/* Question Panel */}
        <div className="flex-1 overflow-y-auto p-6">
          {!currentQuestion || isGenerating || isGeneratingDiagram ? (
            <div className="flex flex-col items-center justify-center h-full">
              <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mb-4" />
              <span className="text-muted-foreground">
                {loadingState === 'retrying' ? (
                  <>
                    Retrying... (attempt {retryCount}/{3})
                  </>
                ) : loadingState === 'generating' ? (
                  'Generating questions...'
                ) : (
                  'Loading questions...'
                )}
              </span>
            </div>
          ) : errorMessage ? (
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
            <div className="max-w-2xl mx-auto">
              <div className="flex items-center gap-2 mb-4">
                <Badge>Q{currentQ + 1}</Badge>
                <Badge variant="secondary">{currentQuestion.topic || 'General'}</Badge>
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
                  onClick={() => changeQuestion(-1)}
                  disabled={currentQ === 0}
                >
                  <ArrowLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>

                {answered[currentQ] ? (
                  <Button onClick={() => changeQuestion(1)}>
                    Next
                    <ArrowRight className="h-4 w-4 ml-1" />
                  </Button>
                ) : (
                  <Button variant="outline" onClick={finishQuiz}>
                    Finish
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Canvas Panel */}
        <div className="w-80 border-l bg-card flex flex-col">
          {/* Canvas Toolbar */}
          <div className="p-3 border-b flex items-center gap-2 flex-wrap">
            <Button
              variant={currentTool === 'pen' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setCurrentTool('pen')}
            >
              <Palette className="h-4 w-4" />
            </Button>
            <Button
              variant={currentTool === 'eraser' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setCurrentTool('eraser')}
            >
              <Eraser className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={clearCanvas}>
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>

            <div className="flex gap-1 ml-auto">
              {['#1e293b', '#ef4444', '#3b82f6', '#10b981'].map((color) => (
                <button
                  key={color}
                  className={`w-6 h-6 rounded-full border-2 ${
                    currentColor === color && currentTool === 'pen'
                      ? 'border-primary'
                      : 'border-transparent'
                  }`}
                  style={{ backgroundColor: color }}
                  onClick={() => {
                    setCurrentColor(color);
                    setCurrentTool('pen');
                  }}
                />
              ))}
            </div>

            <input
              type="range"
              min="1"
              max="10"
              value={lineWidth}
              onChange={(e) => setLineWidth(parseInt(e.target.value))}
              className="w-16"
            />
          </div>

          {/* Canvas */}
          <div className="flex-1 relative">
            <canvas
              ref={canvasRef}
              className="absolute inset-0 cursor-crosshair touch-none"
              onMouseDown={startDrawing}
              onMouseMove={draw}
              onMouseUp={stopDrawing}
              onMouseLeave={stopDrawing}
              onTouchStart={startDrawing}
              onTouchMove={draw}
              onTouchEnd={stopDrawing}
              style={{ background: 'white' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}