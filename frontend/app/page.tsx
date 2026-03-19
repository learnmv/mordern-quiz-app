'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useTheme } from 'next-themes';
import { Moon, Sun, Trophy, BookOpen, TrendingUp, User, Shield } from 'lucide-react';
import { Button } from './components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { useAuth } from '@/hooks/useAuth';
import { useProgress } from '@/hooks/useProgress';

const CURRICULUM = {
  "6": {
    grade: "6th Grade",
    code: "6",
    domains: [
      {
        id: "6-rp",
        name: "Ratios & Proportional Relationships",
        color: "bg-amber-500",
        topics: ["Unit Rates", "Ratios", "Percentages", "Ratio Reasoning"]
      },
      {
        id: "6-ns",
        name: "The Number System",
        color: "bg-emerald-500",
        topics: ["Fractions", "Decimals", "Negative Numbers", "GCF", "LCM", "Absolute Value", "Number Line", "Coordinate Plane"]
      },
      {
        id: "6-ee",
        name: "Expressions & Equations",
        color: "bg-blue-500",
        topics: ["Variables", "Writing Expressions", "One-Step Equations", "One-Step Inequalities", "Evaluating Expressions", "Order of Operations", "Equivalent Expressions"]
      },
      {
        id: "6-g",
        name: "Geometry",
        color: "bg-pink-500",
        topics: ["Area of Polygons", "Volume of Prisms", "Surface Area", "Coordinate Plane Polygons"]
      },
      {
        id: "6-sp",
        name: "Statistics & Probability",
        color: "bg-violet-500",
        topics: ["Statistical Questions", "Mean", "Median", "Mode", "Range", "Dot Plots", "Histograms", "Box Plots"]
      }
    ]
  },
  "7": {
    grade: "7th Grade",
    code: "7",
    domains: [
      {
        id: "7-rp",
        name: "Ratios & Proportional Relationships",
        color: "bg-amber-500",
        topics: ["Unit Rates", "Proportional Relationships", "Constant of Proportionality", "Percentages", "Markup & Discount", "Simple Interest", "Scale Drawings"]
      },
      {
        id: "7-ns",
        name: "The Number System",
        color: "bg-emerald-500",
        topics: ["Add & Subtract Rationals", "Multiply & Divide Rationals", "Convert to Decimals", "Real-World Problems", "Properties of Operations", "Complex Fractions"]
      },
      {
        id: "7-ee",
        name: "Expressions & Equations",
        color: "bg-blue-500",
        topics: ["Factor & Expand Linear Expressions", "Rewriting Expressions", "Two-Step Equations", "Two-Step Inequalities", "Word Problems", "Multi-Step Equations"]
      },
      {
        id: "7-g",
        name: "Geometry",
        color: "bg-pink-500",
        topics: ["Scale Drawings", "Drawing Geometric Shapes", "Cross-Sections", "Circles (Area & Circumference)", "Angles", "Area & Perimeter", "Volume & Surface Area", "Surveying Areas"]
      },
      {
        id: "7-sp",
        name: "Statistics & Probability",
        color: "bg-violet-500",
        topics: ["Populations & Samples", "Random Sampling", "Comparing Data Sets", "Mean, Median, IQR", "Probability", "Compound Events", "Tree Diagrams"]
      }
    ]
  },
  "8": {
    grade: "8th Grade",
    code: "8",
    domains: [
      {
        id: "8-ns",
        name: "The Number System",
        color: "bg-emerald-500",
        topics: ["Rational Numbers", "Irrational Numbers", "Approximate Irrationals", "Compare Real Numbers", "Scientific Notation", "Operations with Sci Notation"]
      },
      {
        id: "8-ee",
        name: "Expressions & Equations",
        color: "bg-blue-500",
        topics: ["Integer Exponents", "Laws of Exponents", "Scientific Notation", "Linear Equations", "Solving for Variables", "Systems of Equations", "Graphing Lines", "Slope-Intercept Form", "Slope & Rate of Change", "Proportional Relationships"]
      },
      {
        id: "8-f",
        name: "Functions",
        color: "bg-orange-500",
        topics: ["Functions as Rules", "Function Notation", "Linear Functions", "Rate of Change", "Initial Value", "Function Tables", "Graphing Functions", "Comparing Functions", "Nonlinear Functions"]
      },
      {
        id: "8-g",
        name: "Geometry",
        color: "bg-pink-500",
        topics: ["Transformations", "Translations", "Reflections", "Rotations", "Dilations", "Congruence", "Similar Figures", "Angle Relationships", "Parallel Lines", "Pythagorean Theorem", "Distance Between Points", "Volume of Cylinders", "Volume of Cones", "Volume of Spheres"]
      },
      {
        id: "8-sp",
        name: "Statistics & Probability",
        color: "bg-violet-500",
        topics: ["Scatter Plots", "Patterns in Scatter Plots", "Linear Models", "Association", "Outliers", "Line of Best Fit", "Bivariate Data", "Two-Way Tables"]
      }
    ]
  }
};

export default function Home() {
  const { theme, setTheme } = useTheme();
  const [selectedGrade, setSelectedGrade] = useState<string>("6");
  const { user, isAuthenticated, logout } = useAuth();
  const { progress, isLoading } = useProgress();

  const gradeData = CURRICULUM[selectedGrade as keyof typeof CURRICULUM];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-primary" />
            <h1 className="text-xl font-bold">Math Quiz</h1>
          </div>

          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            >
              {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>

            {isAuthenticated ? (
              <>
                {user?.is_admin && (
                  <Link href="/admin">
                    <Button variant="ghost" className="gap-2">
                      <Shield className="h-4 w-4" />
                      Admin
                    </Button>
                  </Link>
                )}
                <Link href="/dashboard">
                  <Button variant="ghost" className="gap-2">
                    <TrendingUp className="h-4 w-4" />
                    Dashboard
                  </Button>
                </Link>
                <Button variant="ghost" className="gap-2" onClick={() => logout()}>
                  <User className="h-4 w-4" />
                  {user?.username}
                </Button>
              </>
            ) : (
              <Link href="/login">
                <Button>Login</Button>
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {/* Welcome Section */}
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-2">California Common Core Math Quiz</h2>
          <p className="text-muted-foreground">
            Practice math concepts aligned with California Common Core standards
          </p>
        </div>

        {/* Stats Cards */}
        {isAuthenticated && progress && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Questions Answered</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{progress.stats.total_questions}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Accuracy</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{progress.stats.overall_accuracy}%</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Topics Attempted</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{progress.stats.topics_attempted}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Active Days (7d)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{progress.stats.active_days_week}</div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Grade Selector */}
        <div className="flex justify-center gap-2 mb-8">
          {Object.entries(CURRICULUM).map(([code, data]) => (
            <Button
              key={code}
              variant={selectedGrade === code ? 'default' : 'outline'}
              onClick={() => setSelectedGrade(code)}
            >
              {data.grade}
            </Button>
          ))}
        </div>

        {/* Start Quiz Button */}
        <div className="text-center mb-8">
          <Link href={`/quiz?grade=${selectedGrade}`}>
            <Button size="lg" className="gap-2">
              <Trophy className="h-5 w-5" />
              Start {gradeData.grade} Quiz
            </Button>
          </Link>
        </div>

        {/* Domains */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {gradeData.domains.map((domain) => (
            <Card key={domain.id} className="hover:border-primary transition-colors">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${domain.color}`} />
                  <CardTitle className="text-lg">{domain.name}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {domain.topics.map((topic) => (
                    <Badge key={topic} variant="secondary">
                      {topic}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
    </div>
  );
}