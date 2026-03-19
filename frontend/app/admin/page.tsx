'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  Brain,
  BarChart3,
  Plus,
  Loader2,
  CheckCircle2,
  AlertCircle,
  BookOpen,
  Layers,
  Eye,
  X,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Progress } from '../components/ui/progress';
import { useAdmin } from '@/hooks/useAdmin';
import { useAuth } from '@/hooks/useAuth';
import { useRouter } from 'next/navigation';

// Curriculum data (same as main page)
const CURRICULUM = {
  "6": {
    grade: "6th Grade",
    domains: [
      { id: "6-rp", name: "Ratios & Proportional Relationships", topics: ["Unit Rates", "Ratios", "Percentages", "Ratio Reasoning"] },
      { id: "6-ns", name: "The Number System", topics: ["Fractions", "Decimals", "Negative Numbers", "GCF", "LCM", "Absolute Value", "Number Line", "Coordinate Plane"] },
      { id: "6-ee", name: "Expressions & Equations", topics: ["Variables", "Writing Expressions", "One-Step Equations", "One-Step Inequalities", "Evaluating Expressions", "Order of Operations", "Equivalent Expressions"] },
      { id: "6-g", name: "Geometry", topics: ["Area of Polygons", "Volume of Prisms", "Surface Area", "Coordinate Plane Polygons"] },
      { id: "6-sp", name: "Statistics & Probability", topics: ["Statistical Questions", "Mean", "Median", "Mode", "Range", "Dot Plots", "Histograms", "Box Plots"] },
    ]
  },
  "7": {
    grade: "7th Grade",
    domains: [
      { id: "7-rp", name: "Ratios & Proportional Relationships", topics: ["Unit Rates", "Proportional Relationships", "Constant of Proportionality", "Percentages", "Markup & Discount", "Simple Interest", "Scale Drawings"] },
      { id: "7-ns", name: "The Number System", topics: ["Add & Subtract Rationals", "Multiply & Divide Rationals", "Convert to Decimals", "Real-World Problems", "Properties of Operations", "Complex Fractions"] },
      { id: "7-ee", name: "Expressions & Equations", topics: ["Factor & Expand Linear Expressions", "Rewriting Expressions", "Two-Step Equations", "Two-Step Inequalities", "Word Problems", "Multi-Step Equations"] },
      { id: "7-g", name: "Geometry", topics: ["Scale Drawings", "Drawing Geometric Shapes", "Cross-Sections", "Circles (Area & Circumference)", "Angles", "Area & Perimeter", "Volume & Surface Area", "Surveying Areas"] },
      { id: "7-sp", name: "Statistics & Probability", topics: ["Populations & Samples", "Random Sampling", "Comparing Data Sets", "Mean, Median, IQR", "Probability", "Compound Events", "Tree Diagrams"] },
    ]
  },
  "8": {
    grade: "8th Grade",
    domains: [
      { id: "8-ns", name: "The Number System", topics: ["Rational Numbers", "Irrational Numbers", "Approximate Irrationals", "Compare Real Numbers", "Scientific Notation", "Operations with Sci Notation"] },
      { id: "8-ee", name: "Expressions & Equations", topics: ["Integer Exponents", "Laws of Exponents", "Scientific Notation", "Linear Equations", "Solving for Variables", "Systems of Equations", "Graphing Lines", "Slope-Intercept Form", "Slope & Rate of Change", "Proportional Relationships"] },
      { id: "8-g", name: "Geometry", topics: ["Transformations", "Congruence", "Similarity", "Pythagorean Theorem", "Volume of Cylinders/Cones/Spheres", "Surface Area", "Coordinate Geometry"] },
      { id: "8-sp", name: "Statistics & Probability", topics: ["Scatter Plots", "Line of Best Fit", "Two-Way Tables", "Probability"] },
    ]
  },
};

const DIFFICULTIES = ['easy', 'medium', 'hard'];

interface Question {
  id: number;
  hash: string;
  type: string;
  text: string;
  options: string[];
  correct: string[];
  explanation: string;
  difficulty: string;
  topic: string;
  created_date: string;
}

export default function AdminPage() {
  const router = useRouter();
  const { user, isLoading: isAuthLoading } = useAuth();
  const {
    stats,
    isLoadingStats,
    refetchStats,
    getQuestionCount,
    getQuestions,
    generateQuestions,
    generationStatus,
    generationMessage,
    isGenerating,
    resetStatus,
  } = useAdmin();

  // Form state
  const [selectedGrade, setSelectedGrade] = useState<string>('');
  const [selectedTopic, setSelectedTopic] = useState<string>('');
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>('medium');
  const [questionCount, setQuestionCount] = useState<number>(10);
  const [topicQuestionCount, setTopicQuestionCount] = useState<number | null>(null);

  // View questions state
  const [viewQuestions, setViewQuestions] = useState<Question[]>([]);
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(false);
  const [showQuestionsDialog, setShowQuestionsDialog] = useState(false);
  const [expandedQuestion, setExpandedQuestion] = useState<number | null>(null);

  // Get available topics for selected grade
  const availableTopics = selectedGrade
    ? CURRICULUM[selectedGrade as keyof typeof CURRICULUM]?.domains.flatMap(d => d.topics) || []
    : [];

  // Check if user is admin
  useEffect(() => {
    if (!isAuthLoading && user && !user.is_admin) {
      router.push('/');
    }
  }, [user, isAuthLoading, router]);

  // Fetch question count when topic/difficulty changes
  useEffect(() => {
    if (selectedGrade && selectedTopic && selectedDifficulty) {
      getQuestionCount(selectedGrade, selectedTopic, selectedDifficulty)
        .then(count => setTopicQuestionCount(count))
        .catch(() => setTopicQuestionCount(null));
    }
  }, [selectedGrade, selectedTopic, selectedDifficulty, getQuestionCount]);

  // Handle generate
  const handleGenerate = async () => {
    if (!selectedGrade || !selectedTopic || !selectedDifficulty) return;

    await generateQuestions({
      grade: selectedGrade,
      topic: selectedTopic,
      difficulty: selectedDifficulty,
      count: questionCount,
    });

    // Refresh count
    const count = await getQuestionCount(selectedGrade, selectedTopic, selectedDifficulty);
    setTopicQuestionCount(count);
  };

  // Handle view questions
  const handleViewQuestions = async () => {
    if (!selectedGrade || !selectedTopic || !selectedDifficulty) return;

    setIsLoadingQuestions(true);
    setShowQuestionsDialog(true);
    try {
      const data = await getQuestions(selectedGrade, selectedTopic, selectedDifficulty);
      setViewQuestions(data.questions || []);
    } catch (error) {
      setViewQuestions([]);
    } finally {
      setIsLoadingQuestions(false);
    }
  };

  if (isAuthLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!user?.is_admin) {
    return null; // Will redirect
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
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Brain className="h-5 w-5 text-primary" />
              Admin Dashboard
            </h1>
          </div>
          <Badge variant="secondary">Admin</Badge>
        </div>
      </header>

      <div className="max-w-6xl mx-auto p-6">
        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-blue-500" />
                Total Questions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {isLoadingStats ? '-' : stats?.total_questions || 0}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Layers className="h-4 w-4 text-green-500" />
                Coverage
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {isLoadingStats ? '-' : `${Math.round(stats?.coverage_percent || 0)}%`}
              </div>
              <Progress value={stats?.coverage_percent || 0} className="mt-2" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                Covered Combos
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {isLoadingStats ? '-' : `${stats?.covered_combinations || 0}/${stats?.total_combinations || 0}`}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-amber-500" />
                Low Stock
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {isLoadingStats ? '-' : stats?.low_stock_count || 0}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Generate Questions Form */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Plus className="h-5 w-5" />
                Generate Questions
              </CardTitle>
              <CardDescription>
                Generate new questions for a specific topic and difficulty
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Grade Selection */}
              <div className="space-y-2">
                <Label>Grade</Label>
                <Select value={selectedGrade} onValueChange={(value: string) => {
                  setSelectedGrade(value);
                  setSelectedTopic('');
                  resetStatus();
                }}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select grade" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="6">6th Grade</SelectItem>
                    <SelectItem value="7">7th Grade</SelectItem>
                    <SelectItem value="8">8th Grade</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Topic Selection */}
              <div className="space-y-2">
                <Label>Topic</Label>
                <Select
                  value={selectedTopic}
                  onValueChange={setSelectedTopic}
                  disabled={!selectedGrade}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={selectedGrade ? "Select topic" : "Select grade first"} />
                  </SelectTrigger>
                  <SelectContent>
                    {availableTopics.map((topic) => (
                      <SelectItem key={topic} value={topic}>
                        {topic}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Difficulty Selection */}
              <div className="space-y-2">
                <Label>Difficulty</Label>
                <Select value={selectedDifficulty} onValueChange={setSelectedDifficulty}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DIFFICULTIES.map((d) => (
                      <SelectItem key={d} value={d}>
                        {d.charAt(0).toUpperCase() + d.slice(1)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Question Count */}
              <div className="space-y-2">
                <Label>Number of Questions (1-50)</Label>
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={questionCount}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuestionCount(parseInt(e.target.value) || 1)}
                />
              </div>

              {/* Current Count Display */}
              {selectedGrade && selectedTopic && selectedDifficulty && (
                <div className="p-3 bg-secondary rounded-lg">
                  <p className="text-sm">
                    Current questions for this combination:{' '}
                    <span className="font-bold">
                      {topicQuestionCount !== null ? topicQuestionCount : 'Loading...'}
                    </span>
                  </p>
                </div>
              )}

              {/* Status Message */}
              {generationStatus !== 'idle' && (
                <div className={`p-3 rounded-lg ${
                  generationStatus === 'success' ? 'bg-green-100 text-green-800' :
                  generationStatus === 'error' ? 'bg-red-100 text-red-800' :
                  'bg-blue-100 text-blue-800'
                }`}>
                  <div className="flex items-center gap-2">
                    {generationStatus === 'generating' && <Loader2 className="h-4 w-4 animate-spin" />}
                    {generationStatus === 'success' && <CheckCircle2 className="h-4 w-4" />}
                    {generationStatus === 'error' && <AlertCircle className="h-4 w-4" />}
                    <p className="text-sm">{generationMessage}</p>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  onClick={handleGenerate}
                  disabled={!selectedGrade || !selectedTopic || isGenerating}
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Plus className="h-4 w-4 mr-2" />
                      Generate {questionCount}
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleViewQuestions}
                  disabled={!selectedGrade || !selectedTopic || isLoadingQuestions}
                >
                  <Eye className="h-4 w-4 mr-2" />
                  View
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Low Stock Combinations */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Low Stock Combinations
              </CardTitle>
              <CardDescription>
                Combinations with fewer than 5 questions
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingStats ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : stats?.low_stock_combinations?.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No low stock combinations! All topics have sufficient questions.
                </p>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {stats?.low_stock_combinations?.map((combo: any) => (
                    <div
                      key={`${combo.grade}-${combo.topic}-${combo.difficulty}`}
                      className="flex items-center justify-between p-3 bg-secondary rounded-lg cursor-pointer hover:bg-secondary/80"
                      onClick={() => {
                        setSelectedGrade(combo.grade);
                        setSelectedTopic(combo.topic);
                        setSelectedDifficulty(combo.difficulty);
                      }}
                    >
                      <div>
                        <p className="font-medium text-sm">{combo.topic}</p>
                        <p className="text-xs text-muted-foreground">
                          Grade {combo.grade} • {combo.difficulty}
                        </p>
                      </div>
                      <Badge variant={combo.count < 3 ? "destructive" : "secondary"}>
                        {combo.count} questions
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* All Combinations Table */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>All Topic Combinations</CardTitle>
            <CardDescription>
              Question counts for all grade/topic/difficulty combinations
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingStats ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-4 font-medium">Grade</th>
                      <th className="text-left py-2 px-4 font-medium">Topic</th>
                      <th className="text-left py-2 px-4 font-medium">Difficulty</th>
                      <th className="text-right py-2 px-4 font-medium">Count</th>
                      <th className="text-right py-2 px-4 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats?.by_combination?.map((combo: any, index: number) => (
                      <tr key={index} className="border-b last:border-0 hover:bg-secondary/50">
                        <td className="py-2 px-4">{combo.grade}</td>
                        <td className="py-2 px-4">{combo.topic}</td>
                        <td className="py-2 px-4">
                          <Badge variant="outline">{combo.difficulty}</Badge>
                        </td>
                        <td className="py-2 px-4 text-right">
                          <Badge variant={combo.count < 5 ? "destructive" : "secondary"}>
                            {combo.count}
                          </Badge>
                        </td>
                        <td className="py-2 px-4 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setSelectedGrade(combo.grade);
                              setSelectedTopic(combo.topic);
                              setSelectedDifficulty(combo.difficulty);
                              handleViewQuestions();
                            }}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Questions Dialog */}
      {showQuestionsDialog && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-background rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="p-4 border-b flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold">
                  Questions: {selectedTopic}
                </h2>
                <p className="text-sm text-muted-foreground">
                  Grade {selectedGrade} • {selectedDifficulty} • {viewQuestions.length} questions
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  setShowQuestionsDialog(false);
                  setViewQuestions([]);
                  setExpandedQuestion(null);
                }}
              >
                <X className="h-5 w-5" />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {isLoadingQuestions ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin" />
                </div>
              ) : viewQuestions.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">
                  No questions found for this combination.
                </p>
              ) : (
                viewQuestions.map((question, index) => (
                  <div
                    key={question.hash || index}
                    className="border rounded-lg overflow-hidden"
                  >
                    <button
                      className="w-full p-4 text-left flex items-start justify-between hover:bg-secondary/50"
                      onClick={() => setExpandedQuestion(
                        expandedQuestion === index ? null : index
                      )}
                    >
                      <div className="flex-1">
                        <p className="font-medium">
                          {index + 1}. {question.text.substring(0, 100)}
                          {question.text.length > 100 ? '...' : ''}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Type: {question.type} • Hash: {question.hash?.substring(0, 8)}...
                        </p>
                      </div>
                      {expandedQuestion === index ? (
                        <ChevronUp className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      )}
                    </button>

                    {expandedQuestion === index && (
                      <div className="p-4 border-t bg-secondary/30">
                        <div className="space-y-4">
                          <div>
                            <p className="font-medium mb-2">Question:</p>
                            <p className="text-sm">{question.text}</p>
                          </div>

                          <div>
                            <p className="font-medium mb-2">Options:</p>
                            <div className="space-y-1">
                              {question.options?.map((option, optIndex) => (
                                <div
                                  key={optIndex}
                                  className={`p-2 rounded text-sm ${
                                    question.correct?.includes(option)
                                      ? 'bg-green-100 text-green-800 font-medium'
                                      : 'bg-background'
                                  }`}
                                >
                                  {String.fromCharCode(65 + optIndex)}. {option}
                                  {question.correct?.includes(option) && (
                                    <span className="ml-2 text-xs">(Correct)</span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>

                          <div>
                            <p className="font-medium mb-1">Explanation:</p>
                            <p className="text-sm text-muted-foreground">
                              {question.explanation}
                            </p>
                          </div>

                          <div className="text-xs text-muted-foreground pt-2 border-t">
                            <p>Hash: {question.hash}</p>
                            <p>Created: {question.created_date}</p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
