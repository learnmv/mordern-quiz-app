import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Handle 401 responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  // Backend requires form-urlencoded for OAuth2PasswordRequestForm (FastAPI)
  login: (username: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    return api.post('/api/login', formData.toString(), {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
  },
  register: (username: string, password: string) =>
    api.post('/api/register', { username, password }),
  logout: () => api.post('/api/logout'),
  me: () => api.get('/api/me'),
};

// Quiz API
export const quizApi = {
  generate: (grade: string, count: number = 1) =>
    api.post('/api/generate-quiz', { grade, count }),
  generateDiagramQuiz: (grade: string, topic: string, difficulty: string = 'medium', count: number = 1) =>
    api.post('/api/generate-diagram-quiz', { grade, topic, difficulty, count }),
  submitAnswer: (data: {
    question_hash: string;
    topic: string;
    was_correct: boolean;
    time_spent: number;
  }) => api.post('/api/answer', data),
  getAnswered: (topics: string[]) =>
    api.get(`/api/answered-questions?topics=${topics.join(',')}`),
  getWeakTopicsQuiz: () => api.post('/api/generate-weak-topics-quiz', {}),
};

// Progress API
export const progressApi = {
  getProgress: () => api.get('/api/progress'),
  getWeakTopics: () => api.get('/api/weak-topics'),
  getRecommendedDifficulty: (topic: string) =>
    api.get(`/api/recommend-difficulty?topic=${topic}`),
};

// Analytics API
export const analyticsApi = {
  getStats: () => api.get('/api/stats'),
  getPopular: (limit: number = 20) =>
    api.get(`/api/popular?limit=${limit}`),
  getGradeStats: () => api.get('/api/grade-stats'),
  getTopicStats: () => api.get('/api/topic-stats'),
};

// Admin API
export const adminApi = {
  // Generate questions for specific topic
  generateQuestions: (data: {
    grade: string;
    topic: string;
    difficulty: string;
    count: number;
  }) => api.post('/api/admin/generate-questions', data),

  // Get topics for a grade
  getTopicsByGrade: (grade: string) =>
    api.get(`/api/admin/topics/${grade}`),

  // Get question count for specific combination
  getQuestionCount: (grade: string, topic: string, difficulty: string) =>
    api.get(`/api/admin/question-count/${grade}/${topic}/${difficulty}`),

  // Get all question stats
  getQuestionStats: () =>
    api.get('/api/admin/question-stats'),

  // Get stats for specific combination
  getCombinationStats: (grade: string, topic: string, difficulty: string) =>
    api.get(`/api/admin/question-stats/${grade}/${topic}/${difficulty}`),

  // Trigger pre-generation
  pregenerate: (data: {
    grades?: string[];
    topics?: string[];
    difficulties?: string[];
    count_per_combo?: number;
  }) => api.post('/api/admin/pregenerate', data),

  // Get pregeneration status
  getPregenerateStatus: (taskId: string) =>
    api.get(`/api/admin/pregenerate/status/${taskId}`),
};