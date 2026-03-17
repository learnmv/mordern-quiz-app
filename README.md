# Quiz App - FastAPI + Next.js Migration

A modern quiz application rebuilt with FastAPI backend and Next.js frontend, featuring PostgreSQL database, JWT authentication, and a responsive UI with dark mode support.

## Architecture

- **Backend**: FastAPI with async SQLAlchemy 2.0 + PostgreSQL
- **Frontend**: Next.js 14 with TypeScript, Tailwind CSS, and shadcn/ui
- **Database**: PostgreSQL with JSONB support for flexible question storage
- **Authentication**: JWT tokens with automatic refresh
- **State Management**: Zustand for auth, React Query for server state

## Project Structure

```
mordern-quiz-app/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py         # FastAPI app entry
│   │   ├── config.py       # Settings management
│   │   ├── database.py     # SQLAlchemy setup
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── routers/         # API endpoints
│   │   ├── services/        # Business logic
│   │   └── utils/           # Security utilities
│   ├── scripts/
│   │   └── migrate_sqlite_to_pg.py  # Migration script
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Next.js frontend
│   ├── app/                 # App Router pages
│   ├── components/          # UI components
│   ├── hooks/               # Custom React hooks
│   ├── lib/                 # API client and utilities
│   ├── store/               # Zustand stores
│   ├── types/               # TypeScript types
│   └── Dockerfile
├── docker-compose.yml       # Full stack deployment
└── .env.example             # Environment variables template
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Running with Docker Compose

1. Clone the repository and navigate to the project:
```bash
cd mordern-quiz-app
```

2. Copy the environment file:
```bash
cp .env.example .env
```

3. Update the `.env` file with your settings (especially `SECRET_KEY` and Ollama configuration)

4. Start all services:
```bash
docker-compose up -d
```

5. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Database Migration

To migrate data from the old SQLite database:

1. Ensure the old SQLite database is at `/home/sysadmin/quiz-app/data/quiz_database.db`

2. Run the migration script:
```bash
cd backend
pip install -r requirements.txt
python scripts/migrate_sqlite_to_pg.py
```

## Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## Features

### Backend Features
- ✅ Async FastAPI with automatic OpenAPI docs
- ✅ JWT authentication with secure password hashing
- ✅ Adaptive quiz generation with Ollama AI
- ✅ Question caching with PostgreSQL JSONB
- ✅ User progress tracking and analytics
- ✅ Gamification with badges and streaks
- ✅ Weak/strong topic identification

### Frontend Features
- ✅ Next.js 14 App Router with TypeScript
- ✅ Tailwind CSS with dark mode support
- ✅ shadcn/ui components
- ✅ Drawing canvas for working out problems
- ✅ Real-time progress tracking
- ✅ Responsive design
- ✅ Dashboard with analytics

## API Endpoints

### Authentication
- `POST /api/register` - Register new user
- `POST /api/login` - Login user
- `POST /api/logout` - Logout user
- `GET /api/me` - Get current user

### Quiz
- `POST /api/generate-quiz` - Generate quiz questions
- `POST /api/answer` - Submit answer
- `GET /api/answered-questions` - Get answered question hashes
- `POST /api/generate-weak-topics-quiz` - Generate quiz for weak topics

### Progress
- `GET /api/progress` - Get user progress
- `GET /api/weak-topics` - Get weak topics
- `GET /api/recommend-difficulty` - Get recommended difficulty

### Analytics
- `GET /api/stats` - Get daily stats
- `GET /api/popular` - Get popular combinations
- `GET /api/grade-stats` - Get grade distribution
- `GET /api/topic-stats` - Get topic coverage

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://quizuser:quizpass@db:5432/quizdb` |
| `SECRET_KEY` | JWT secret key | Required |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |
| `OLLAMA_API_KEY` | Ollama API key | Optional |
| `OLLAMA_MODEL` | Ollama model name | `kimi-k2.5:cloud` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |

## License

MIT