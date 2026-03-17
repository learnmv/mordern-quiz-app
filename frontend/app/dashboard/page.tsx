'use client';

import Link from 'next/link';
import { ArrowLeft, Trophy, Target, TrendingUp, Award } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { useProgress } from '@/hooks/useProgress';

export default function DashboardPage() {
  const { progress, isLoading } = useProgress();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!progress) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-muted-foreground">Failed to load progress data</p>
            <Link href="/">
              <Button className="mt-4">Back to Home</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card px-4 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-1" />
                Back
              </Button>
            </Link>
            <h1 className="text-xl font-bold">Your Progress Dashboard</h1>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto p-6">
        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Trophy className="h-4 w-4 text-amber-500" />
                Total Questions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{progress.stats.total_questions}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Target className="h-4 w-4 text-green-500" />
                Accuracy
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{progress.stats.overall_accuracy}%</div>
              <Progress value={progress.stats.overall_accuracy} className="mt-2" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-blue-500" />
                Topics
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{progress.stats.topics_attempted}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Award className="h-4 w-4 text-violet-500" />
                Badges
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{progress.badges.length}</div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Weak Topics */}
          <Card>
            <CardHeader>
              <CardTitle>Areas to Improve</CardTitle>
            </CardHeader>
            <CardContent>
              {progress.weak_topics.length === 0 ? (
                <p className="text-muted-foreground">No weak topics! Great job! 🎉</p>
              ) : (
                <div className="space-y-4">
                  {progress.weak_topics.slice(0, 5).map((topic) => (
                    <div key={topic.topic}>
                      <div className="flex justify-between mb-1">
                        <span className="font-medium">{topic.topic}</span>
                        <span className="text-sm text-muted-foreground">
                          {topic.accuracy}% ({topic.total} questions)
                        </span>
                      </div>
                      <Progress value={topic.accuracy} className="h-2" />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Strong Topics */}
          <Card>
            <CardHeader>
              <CardTitle>Strong Areas</CardTitle>
            </CardHeader>
            <CardContent>
              {progress.strong_topics.length === 0 ? (
                <p className="text-muted-foreground">Keep practicing to build strong areas! 💪</p>
              ) : (
                <div className="space-y-4">
                  {progress.strong_topics.slice(0, 5).map((topic) => (
                    <div key={topic.topic}>
                      <div className="flex justify-between mb-1">
                        <span className="font-medium">{topic.topic}</span>
                        <span className="text-sm text-green-600">
                          {topic.accuracy}% ({topic.total} questions)
                        </span>
                      </div>
                      <Progress value={topic.accuracy} className="h-2" />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Badges */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Earned Badges</CardTitle>
            </CardHeader>
            <CardContent>
              {progress.badges.length === 0 ? (
                <p className="text-muted-foreground">
                  Complete quizzes to earn badges! 🏆
                </p>
              ) : (
                <div className="flex flex-wrap gap-3">
                  {progress.badges.map((badge) => (
                    <div
                      key={badge.id}
                      className="flex items-center gap-2 px-4 py-2 bg-secondary rounded-full"
                    >
                      <span className="text-2xl">{badge.icon}</span>
                      <div>
                        <p className="font-medium text-sm">{badge.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {badge.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* In Progress Topics */}
          <Card>
            <CardHeader>
              <CardTitle>In Progress</CardTitle>
            </CardHeader>
            <CardContent>
              {progress.in_progress.length === 0 ? (
                <p className="text-muted-foreground">No topics in progress</p>
              ) : (
                <div className="space-y-3">
                  {progress.in_progress.map((topic) => (
                    <div
                      key={topic.topic}
                      className="flex items-center justify-between p-3 bg-secondary rounded-lg"
                    >
                      <span>{topic.topic}</span>
                      <Badge variant="secondary">
                        {topic.total} questions
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Topic Streaks */}
          <Card>
            <CardHeader>
              <CardTitle>Current Streaks</CardTitle>
            </CardHeader>
            <CardContent>
              {Object.entries(progress.streaks).length === 0 ? (
                <p className="text-muted-foreground">No streaks yet</p>
              ) : (
                <div className="space-y-3">
                  {Object.entries(progress.streaks)
                    .sort((a, b) => b[1].current - a[1].current)
                    .slice(0, 5)
                    .map(([topic, streak]) => (
                      <div
                        key={topic}
                        className="flex items-center justify-between p-3 bg-secondary rounded-lg"
                      >
                        <span>{topic}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-amber-500">🔥</span>
                          <span className="font-medium">{streak.current}</span>
                          <span className="text-muted-foreground text-sm">
                            (max: {streak.max})
                          </span>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}