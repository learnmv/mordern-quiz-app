#!/usr/bin/env python3
"""
Migration script to transfer data from SQLite to PostgreSQL.
Run this after setting up the PostgreSQL database.
"""

import asyncio
import sqlite3
import json
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal, engine
from app.models.user import User
from app.models.quiz import TopicQuestion, CompleteQuiz, QuizRequest
from app.models.progress import UserProgress, UserQuizHistory
from app.models.gamification import Badge, UserBadge
from app.database import Base


async def create_tables():
    """Create all tables in PostgreSQL"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully")


# SQLite database path
SQLITE_DB_PATH = "/home/sysadmin/quiz-app/data/quiz_database.db"


def get_sqlite_connection():
    """Get SQLite connection"""
    return sqlite3.connect(SQLITE_DB_PATH)


async def migrate_users(async_db: AsyncSession, sqlite_conn: sqlite3.Connection):
    """Migrate users table"""
    print("Migrating users...")
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT id, username, password_hash, created_at FROM users")
    rows = cursor.fetchall()

    user_id_map = {}
    for row in rows:
        old_id, username, password_hash, created_at = row

        # Parse created_at string to datetime if needed
        if isinstance(created_at, str):
            created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")

        # Create new user
        user = User(
            username=username,
            password_hash=password_hash,  # SHA256 hashes will work
            created_at=created_at
        )
        async_db.add(user)
        await async_db.flush()
        user_id_map[old_id] = user.id

    await async_db.commit()
    print(f"Migrated {len(rows)} users")
    return user_id_map


async def migrate_topic_questions(async_db: AsyncSession, sqlite_conn: sqlite3.Connection):
    """Migrate topic_questions table"""
    print("Migrating topic_questions...")
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT grade, topic, difficulty, question_data, created_date FROM topic_questions")
    rows = cursor.fetchall()

    for row in rows:
        grade, topic, difficulty, question_data, created_date = row

        # Parse question_data JSON
        try:
            data = json.loads(question_data)
        except:
            data = {"questions": []}

        # Convert created_date string to date object if needed
        if isinstance(created_date, str):
            created_date = datetime.strptime(created_date, "%Y-%m-%d").date()

        tq = TopicQuestion(
            grade=grade,
            topic=topic,
            difficulty=difficulty,
            question_data=data,
            created_date=created_date
        )
        async_db.add(tq)

    await async_db.commit()
    print(f"Migrated {len(rows)} topic questions")


async def migrate_complete_quizzes(async_db: AsyncSession, sqlite_conn: sqlite3.Connection):
    """Migrate complete_quizzes table"""
    print("Migrating complete_quizzes...")
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT grade, difficulty, topics_hash, question_data, created_date, use_count FROM complete_quizzes")
    rows = cursor.fetchall()

    for row in rows:
        grade, difficulty, topics_hash, question_data, created_date, use_count = row

        # Parse question_data JSON
        try:
            data = json.loads(question_data)
        except:
            data = {"questions": []}

        # Convert created_date string to date object if needed
        if isinstance(created_date, str):
            created_date = datetime.strptime(created_date, "%Y-%m-%d").date()

        cq = CompleteQuiz(
            grade=grade,
            difficulty=difficulty,
            topics_hash=topics_hash,
            question_data=data,
            created_date=created_date,
            use_count=use_count or 0
        )
        async_db.add(cq)

    await async_db.commit()
    print(f"Migrated {len(rows)} complete quizzes")


async def migrate_quiz_requests(async_db: AsyncSession, sqlite_conn: sqlite3.Connection, user_id_map: dict):
    """Migrate quiz_requests table"""
    print("Migrating quiz_requests...")
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT user_id, grade, topics, difficulty, request_date, served_from FROM quiz_requests")
    rows = cursor.fetchall()

    for row in rows:
        old_user_id, grade, topics, difficulty, request_date, served_from = row

        # Parse topics JSON
        try:
            topics_data = json.loads(topics) if topics else None
        except:
            topics_data = None

        # Convert request_date string to date object if needed
        if isinstance(request_date, str):
            request_date = datetime.strptime(request_date, "%Y-%m-%d").date()

        # Map user_id
        new_user_id = user_id_map.get(old_user_id) if old_user_id else None

        qr = QuizRequest(
            user_id=new_user_id,
            grade=grade,
            topics=topics_data,
            difficulty=difficulty,
            request_date=request_date,
            served_from=served_from
        )
        async_db.add(qr)

    await async_db.commit()
    print(f"Migrated {len(rows)} quiz requests")


async def migrate_user_progress(async_db: AsyncSession, sqlite_conn: sqlite3.Connection, user_id_map: dict):
    """Migrate user_progress table"""
    print("Migrating user_progress...")
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT user_id, topic, correct_count, total_count, last_quiz_date FROM user_progress")
    rows = cursor.fetchall()

    for row in rows:
        old_user_id, topic, correct_count, total_count, last_quiz_date = row

        # Convert last_quiz_date string to date object if needed
        if isinstance(last_quiz_date, str):
            last_quiz_date = datetime.strptime(last_quiz_date, "%Y-%m-%d").date()

        # Map user_id
        new_user_id = user_id_map.get(old_user_id)
        if not new_user_id:
            continue

        up = UserProgress(
            user_id=new_user_id,
            topic=topic,
            correct_count=correct_count or 0,
            total_count=total_count or 0,
            last_quiz_date=last_quiz_date
        )
        async_db.add(up)

    await async_db.commit()
    print(f"Migrated {len(rows)} user progress entries")


async def migrate_user_quiz_history(async_db: AsyncSession, sqlite_conn: sqlite3.Connection, user_id_map: dict):
    """Migrate user_quiz_history table"""
    print("Migrating user_quiz_history...")
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT user_id, question_hash, topic, was_correct, time_spent, answered_at FROM user_quiz_history")
    rows = cursor.fetchall()

    for row in rows:
        old_user_id, question_hash, topic, was_correct, time_spent, answered_at = row

        # Map user_id
        new_user_id = user_id_map.get(old_user_id)
        if not new_user_id:
            continue

        # Parse answered_at string to datetime if needed
        if isinstance(answered_at, str):
            answered_at = datetime.strptime(answered_at, "%Y-%m-%d %H:%M:%S")

        uqh = UserQuizHistory(
            user_id=new_user_id,
            question_hash=question_hash,
            topic=topic,
            was_correct=was_correct,
            time_spent=time_spent or 0,
            answered_at=answered_at
        )
        async_db.add(uqh)

    await async_db.commit()
    print(f"Migrated {len(rows)} user quiz history entries")


async def verify_migration(async_db: AsyncSession, sqlite_conn: sqlite3.Connection):
    """Verify migration by comparing row counts"""
    print("\nVerifying migration...")

    tables = [
        ("users", User),
        ("topic_questions", TopicQuestion),
        ("complete_quizzes", CompleteQuiz),
        ("quiz_requests", QuizRequest),
        ("user_progress", UserProgress),
        ("user_quiz_history", UserQuizHistory),
    ]

    cursor = sqlite_conn.cursor()

    for table_name, model in tables:
        # Get SQLite count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        sqlite_count = cursor.fetchone()[0]

        # Get PostgreSQL count
        from sqlalchemy import select, func
        result = await async_db.execute(select(func.count()).select_from(model))
        pg_count = result.scalar()

        status = "✓" if sqlite_count == pg_count else "✗"
        print(f"{status} {table_name}: SQLite={sqlite_count}, PostgreSQL={pg_count}")


async def main():
    """Main migration function"""
    print("Starting migration from SQLite to PostgreSQL...")
    print(f"SQLite DB: {SQLITE_DB_PATH}")
    print()

    # Check if SQLite database exists
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"Error: SQLite database not found at {SQLITE_DB_PATH}")
        return

    # Connect to SQLite
    sqlite_conn = get_sqlite_connection()

    try:
        # Create tables first
        await create_tables()

        async with AsyncSessionLocal() as async_db:
            # Migrate tables in order (respecting foreign keys)
            user_id_map = await migrate_users(async_db, sqlite_conn)
            await migrate_topic_questions(async_db, sqlite_conn)
            await migrate_complete_quizzes(async_db, sqlite_conn)
            await migrate_quiz_requests(async_db, sqlite_conn, user_id_map)
            await migrate_user_progress(async_db, sqlite_conn, user_id_map)
            await migrate_user_quiz_history(async_db, sqlite_conn, user_id_map)

            # Verify migration
            await verify_migration(async_db, sqlite_conn)

        print("\nMigration completed successfully!")

    except Exception as e:
        print(f"\nError during migration: {e}")
        import traceback
        traceback.print_exc()

    finally:
        sqlite_conn.close()


if __name__ == "__main__":
    asyncio.run(main())