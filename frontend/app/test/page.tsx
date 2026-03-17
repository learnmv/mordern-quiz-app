'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { Label } from '../components/ui/label';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { BookOpen, Calculator, Ruler, BarChart3, Brain, CheckCircle2 } from 'lucide-react';

// 6th Grade Topics from curriculum
const GRADE_6_TOPICS = [
  {
    id: '6-rp',
    name: 'Ratios & Proportional Relationships',
    icon: Calculator,
    color: 'bg-blue-100 text-blue-700',
    topics: ['Unit Rates', 'Ratios', 'Percentages', 'Ratio Reasoning'],
  },
  {
    id: '6-ns',
    name: 'The Number System',
    icon: Brain,
    color: 'bg-purple-100 text-purple-700',
    topics: ['Fractions', 'Decimals', 'Negative Numbers', 'GCF', 'LCM', 'Absolute Value', 'Number Line', 'Coordinate Plane'],
  },
  {
    id: '6-ee',
    name: 'Expressions & Equations',
    icon: BookOpen,
    color: 'bg-green-100 text-green-700',
    topics: ['Variables', 'Writing Expressions', 'One-Step Equations', 'One-Step Inequalities', 'Evaluating Expressions', 'Order of Operations', 'Equivalent Expressions'],
  },
  {
    id: '6-g',
    name: 'Geometry',
    icon: Ruler,
    color: 'bg-orange-100 text-orange-700',
    topics: ['Area of Polygons', 'Volume of Prisms', 'Surface Area', 'Coordinate Plane Polygons'],
  },
  {
    id: '6-sp',
    name: 'Statistics & Probability',
    icon: BarChart3,
    color: 'bg-pink-100 text-pink-700',
    topics: ['Statistical Questions', 'Mean', 'Median', 'Mode', 'Range', 'Dot Plots', 'Histograms', 'Box Plots'],
  },
];

// Diagram topics that have migrated questions
const DIAGRAM_TOPICS = ['data_analysis', 'geometry'];

export default function TestPage() {
  const router = useRouter();
  const [selectedDomain, setSelectedDomain] = useState<string>('6-rp');
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [difficulty, setDifficulty] = useState<string>('easy');
  const [questionCount, setQuestionCount] = useState<number>(5);
  const [isGenerating, setIsGenerating] = useState(false);

  const currentDomain = GRADE_6_TOPICS.find((d) => d.id === selectedDomain);

  const toggleTopic = (topic: string) => {
    setSelectedTopics((prev) =>
      prev.includes(topic) ? prev.filter((t) => t !== topic) : [...prev, topic]
    );
  };

  const selectAllTopics = () => {
    if (currentDomain) {
      setSelectedTopics(currentDomain.topics);
    }
  };

  const clearAllTopics = () => {
    setSelectedTopics([]);
  };

  const handleGenerateQuiz = async () => {
    if (selectedTopics.length === 0) return;

    setIsGenerating(true);

    // Build query params
    const params = new URLSearchParams({
      grade: '6',
      topics: selectedTopics.join(','),
      difficulty,
      count: questionCount.toString(),
    });

    // Navigate to quiz page with params
    router.push(`/quiz?${params.toString()}`);
  };

  const isDiagramTopic = selectedTopics.some(
    (t) =>
      DIAGRAM_TOPICS.includes(t.toLowerCase()) ||
      ['Area of Polygons', 'Coordinate Plane Polygons', 'Volume of Prisms', 'Surface Area'].includes(t)
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-secondary/20 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold mb-2">6th Grade Quiz Generator</h1>
          <p className="text-muted-foreground">
            Select topics and generate a customized quiz
          </p>
        </div>

        {/* Domain Selection */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5" />
              Select Domain
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {GRADE_6_TOPICS.map((domain) => {
                const Icon = domain.icon;
                const isSelected = selectedDomain === domain.id;
                return (
                  <button
                    key={domain.id}
                    onClick={() => {
                      setSelectedDomain(domain.id);
                      setSelectedTopics([]);
                    }}
                    className={`p-4 rounded-lg border-2 text-left transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <div className={`inline-flex p-2 rounded-lg mb-3 ${domain.color}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <h3 className="font-semibold text-sm">{domain.name}</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      {domain.topics.length} topics
                    </p>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Topic Selection */}
        {currentDomain && (
          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5" />
                  Select Topics from {currentDomain.name}
                </CardTitle>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={selectAllTopics}>
                    Select All
                  </Button>
                  <Button variant="outline" size="sm" onClick={clearAllTopics}>
                    Clear
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {currentDomain.topics.map((topic) => (
                  <div key={topic} className="flex items-center space-x-2">
                    <Checkbox
                      id={topic}
                      checked={selectedTopics.includes(topic)}
                      onCheckedChange={() => toggleTopic(topic)}
                    />
                    <Label htmlFor={topic} className="cursor-pointer">
                      {topic}
                    </Label>
                  </div>
                ))}
              </div>

              {selectedTopics.length > 0 && (
                <div className="mt-4 p-3 bg-secondary rounded-lg">
                  <p className="text-sm font-medium mb-2">Selected Topics:</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedTopics.map((topic) => (
                      <Badge key={topic} variant="secondary">
                        {topic}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Quiz Options */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Quiz Options</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Difficulty */}
              <div>
                <Label className="mb-3 block">Difficulty Level</Label>
                <RadioGroup
                  value={difficulty}
                  onValueChange={setDifficulty}
                  className="flex gap-4"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="easy" id="easy" />
                    <Label htmlFor="easy">Easy</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="medium" id="medium" />
                    <Label htmlFor="medium">Medium</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="hard" id="hard" />
                    <Label htmlFor="hard">Hard</Label>
                  </div>
                </RadioGroup>
              </div>

              {/* Question Count */}
              <div>
                <Label className="mb-3 block">Number of Questions</Label>
                <RadioGroup
                  value={questionCount.toString()}
                  onValueChange={(v) => setQuestionCount(parseInt(v))}
                  className="flex gap-4"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="5" id="q5" />
                    <Label htmlFor="q5">5</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="10" id="q10" />
                    <Label htmlFor="q10">10</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="15" id="q15" />
                    <Label htmlFor="q15">15</Label>
                  </div>
                </RadioGroup>
              </div>
            </div>

            {isDiagramTopic && (
              <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <p className="text-sm text-blue-700 dark:text-blue-300">
                  <BarChart3 className="inline h-4 w-4 mr-1" />
                  Selected topics include diagram-based questions that will be
                  rendered with interactive visuals.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Generate Button */}
        <div className="flex justify-center">
          <Button
            size="lg"
            onClick={handleGenerateQuiz}
            disabled={selectedTopics.length === 0 || isGenerating}
            className="w-full md:w-auto px-8"
          >
            {isGenerating ? (
              <>
                <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full mr-2" />
                Generating...
              </>
            ) : (
              <>
                <Brain className="h-5 w-5 mr-2" />
                Generate Quiz ({selectedTopics.length} topics, {questionCount} questions)
              </>
            )}
          </Button>
        </div>

        {/* Quick Test Section */}
        <Card className="mt-8 border-dashed">
          <CardHeader>
            <CardTitle className="text-lg">Quick Test: Migrated Diagram Questions</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              Test the newly migrated diagram questions directly:
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() =>
                  router.push(
                    '/quiz?grade=6&topics=data_analysis&difficulty=easy&count=5'
                  )
                }
              >
                <BarChart3 className="h-4 w-4 mr-2" />
                Data Analysis (Bar Charts)
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  router.push(
                    '/quiz?grade=7&topics=data_analysis&difficulty=medium&count=5'
                  )
                }
              >
                <BarChart3 className="h-4 w-4 mr-2" />
                Data Analysis (Line & Pie Charts)
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  router.push(
                    '/quiz?grade=6&topics=geometry&difficulty=easy&count=5'
                  )
                }
              >
                <Ruler className="h-4 w-4 mr-2" />
                Geometry (Coordinate Plane)
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
