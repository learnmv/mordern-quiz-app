'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Check, X, ArrowLeft, ArrowRight, RotateCcw, Home } from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Question } from '@/types';

interface QuizReviewProps {
  questions: Question[];
  answers: Record<number, string[]>;
  score: { correct: number; wrong: number };
  elapsedSeconds: number;
  onRetry: () => void;
}

export function QuizReview({
  questions,
  answers,
  score,
  elapsedSeconds,
  onRetry,
}: QuizReviewProps) {
  const [reviewQ, setReviewQ] = useState(0);
  const total = score.correct + score.wrong;
  const percent = total > 0 ? Math.round((score.correct / total) * 100) : 0;

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getMessage = () => {
    if (percent >= 90) return { text: 'Outstanding!', color: 'text-green-600' };
    if (percent >= 70) return { text: 'Great job!', color: 'text-blue-600' };
    if (percent >= 50) return { text: 'Good effort!', color: 'text-amber-600' };
    return { text: 'Keep practicing!', color: 'text-muted-foreground' };
  };

  const message = getMessage();
  const currentQuestion = questions[reviewQ];
  const userAnswer = answers[reviewQ]?.[0];
  const wasCorrect = currentQuestion?.correct.includes(userAnswer);

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-4xl mx-auto">
        {/* Summary Card */}
        <Card className="mb-6">
          <CardContent className="pt-6 pb-6 text-center">
            <h1 className="text-3xl font-bold mb-4">Quiz Complete!</h1>
            <div className="text-6xl font-bold text-primary mb-2">
              {score.correct}/{total}
            </div>
            <p className={`text-xl mb-4 ${message.color}`}>
              {percent}% - {message.text}
            </p>
            <div className="flex justify-center gap-8 text-sm text-muted-foreground">
              <span>Time: {formatTime(elapsedSeconds)}</span>
              <span className="text-green-600">{score.correct} Correct</span>
              <span className="text-red-600">{score.wrong} Incorrect</span>
            </div>
          </CardContent>
        </Card>

        {/* Review Section */}
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Review Answers</h2>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={onRetry}>
                  <RotateCcw className="h-4 w-4 mr-1" />
                  Retry Quiz
                </Button>
                <Link href="/">
                  <Button size="sm">
                    <Home className="h-4 w-4 mr-1" />
                    Back to Home
                  </Button>
                </Link>
              </div>
            </div>

            {/* Question Grid */}
            <div className="grid grid-cols-10 gap-2 mb-6">
              {questions.map((q, i) => {
                const ans = answers[i]?.[0];
                const isCorrect = q.correct.includes(ans);
                return (
                  <button
                    key={i}
                    onClick={() => setReviewQ(i)}
                    className={`h-10 rounded text-sm font-medium transition-colors ${
                      reviewQ === i
                        ? 'bg-primary text-primary-foreground'
                        : isCorrect
                        ? 'bg-green-100 text-green-800 hover:bg-green-200'
                        : 'bg-red-100 text-red-800 hover:bg-red-200'
                    }`}
                  >
                    {i + 1}
                  </button>
                );
              })}
            </div>

            {/* Current Review Question */}
            {currentQuestion && (
              <div className="border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Badge>Q{reviewQ + 1}</Badge>
                  <Badge variant="secondary">{currentQuestion.topic}</Badge>
                  {wasCorrect ? (
                    <Badge className="bg-green-100 text-green-800">
                      <Check className="h-3 w-3 mr-1" /> Correct
                    </Badge>
                  ) : (
                    <Badge className="bg-red-100 text-red-800">
                      <X className="h-3 w-3 mr-1" /> Incorrect
                    </Badge>
                  )}
                </div>

                <p className="text-lg mb-4">{currentQuestion.text}</p>

                <div className="space-y-2 mb-4">
                  {currentQuestion.options.map((option, idx) => {
                    const value = option.charAt(0);
                    const isSelected = userAnswer === value;
                    const isCorrectOption = currentQuestion.correct.includes(value);

                    let className = 'p-3 rounded-lg border ';
                    if (isCorrectOption) {
                      className += 'border-green-500 bg-green-50';
                    } else if (isSelected && !isCorrectOption) {
                      className += 'border-red-500 bg-red-50';
                    } else {
                      className += 'border-border';
                    }

                    return (
                      <div key={idx} className={className}>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{value}.</span>
                          <span>{option.substring(3)}</span>
                          {isCorrectOption && <Check className="h-4 w-4 text-green-500 ml-auto" />}
                          {isSelected && !isCorrectOption && (
                            <X className="h-4 w-4 text-red-500 ml-auto" />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="bg-secondary p-3 rounded-lg">
                  <p className="font-medium text-sm mb-1">Explanation:</p>
                  <p className="text-sm text-muted-foreground">
                    {currentQuestion.explanation}
                  </p>
                </div>

                {/* Navigation */}
                <div className="flex justify-between mt-4">
                  <Button
                    variant="outline"
                    onClick={() => setReviewQ(Math.max(0, reviewQ - 1))}
                    disabled={reviewQ === 0}
                  >
                    <ArrowLeft className="h-4 w-4 mr-1" />
                    Previous
                  </Button>
                  <Button
                    onClick={() => setReviewQ(Math.min(questions.length - 1, reviewQ + 1))}
                    disabled={reviewQ === questions.length - 1}
                  >
                    Next
                    <ArrowRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
