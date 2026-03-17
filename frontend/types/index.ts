export interface User {
  id: number;
  username: string;
  created_at: string;
}

export interface Question {
  id: number;
  type: string;
  text: string;
  options: string[];
  correct: string[];
  explanation: string;
  hash?: string;
  topic?: string;
}

export interface QuizResponse {
  questions: Question[];
}

export interface TopicProgress {
  correct: number;
  total: number;
  accuracy: number;
  last_quiz?: string;
}

export interface WeakTopic {
  topic: string;
  accuracy: number;
  total: number;
  streak: number;
  max_streak: number;
}

export interface StrongTopic {
  topic: string;
  accuracy: number;
  total: number;
  streak: number;
  max_streak: number;
}

export interface InProgressTopic {
  topic: string;
  accuracy: number;
  total: number;
}

export interface TopicStreak {
  current: number;
  max: number;
}

export interface Badge {
  id: string;
  name: string;
  description: string;
  icon: string;
  achieved: boolean;
}

export interface UserStats {
  total_questions: number;
  overall_accuracy: number;
  topics_attempted: number;
  active_days_week: number;
}

export interface ProgressResponse {
  progress: Record<string, TopicProgress>;
  weak_topics: WeakTopic[];
  strong_topics: StrongTopic[];
  in_progress: InProgressTopic[];
  streaks: Record<string, TopicStreak>;
  badges: Badge[];
  stats: UserStats;
}

export interface DailyStats {
  topic_questions_today: number;
  complete_quizzes_today: number;
  requests_today: number;
  by_source: Record<string, number>;
}

export interface PopularCombination {
  grade: string;
  topics: string[];
  difficulty: string;
  count: number;
}

export interface GradeStats {
  by_grade: Record<string, Record<string, number>>;
  by_difficulty: Record<string, number>;
}

export interface CurriculumDomain {
  id: string;
  name: string;
  color: string;
  topics: string[];
}

export interface CurriculumGrade {
  grade: string;
  code: string;
  domains: CurriculumDomain[];
}

// Diagram-related types
export interface DiagramSpec {
  type: 'coordinate' | 'chart' | 'svg';
  data: Record<string, any>;
  width: number;
  height: number;
}

export interface DiagramQuestion extends Question {
  diagram?: DiagramSpec;
  requires_canvas: boolean;
}

export interface DiagramQuizRequest {
  grade: string;
  topic: string;
  difficulty: string;
  count: number;
}

export interface DiagramQuizResponse {
  questions: DiagramQuestion[];
}