#!/usr/bin/env python3
"""Cron runner script for executing individual cron jobs.

This script is called by the system crontab to run specific grade/difficulty
combinations for automated question generation.

Usage:
    python cron_runner.py <grade> <difficulty>

Examples:
    python cron_runner.py 6 easy
    python cron_runner.py 7 medium
    python cron_runner.py 8 hard
"""
import asyncio
import logging
import sys
import os

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tasks.cron_jobs import generate_questions_for_grade_difficulty

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_cron_job(grade: str, difficulty: str) -> None:
    """Run a single cron job for the specified grade and difficulty."""
    logger.info(f"Starting cron job: grade={grade}, difficulty={difficulty}")

    try:
        result = await generate_questions_for_grade_difficulty(grade, difficulty)

        status = result.get("status", "unknown")
        topic = result.get("topic", "unknown")

        if status == "success":
            logger.info(
                f"Cron job completed successfully: "
                f"grade={grade}, difficulty={difficulty}, "
                f"topic={topic}, generated={result.get('generated', 0)}, "
                f"stored={result.get('stored', 0)}"
            )
        elif status == "skipped":
            logger.info(
                f"Cron job skipped: grade={grade}, difficulty={difficulty}, "
                f"topic={topic}, reason={result.get('reason', 'unknown')}"
            )
        elif status == "failed":
            logger.error(
                f"Cron job failed: grade={grade}, difficulty={difficulty}, "
                f"topic={topic}, reason={result.get('reason', 'unknown')}"
            )
            sys.exit(1)
        elif status == "error":
            logger.error(
                f"Cron job error: grade={grade}, difficulty={difficulty}, "
                f"error={result.get('error', 'unknown')}"
            )
            sys.exit(1)
        else:
            logger.warning(f"Cron job completed with unknown status: {status}")

    except Exception as e:
        logger.exception(f"Unhandled exception in cron job: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: python cron_runner.py <grade> <difficulty>")
        print("Example: python cron_runner.py 6 easy")
        sys.exit(1)

    grade = sys.argv[1]
    difficulty = sys.argv[2]

    # Validate inputs
    valid_grades = ["6", "7", "8"]
    valid_difficulties = ["easy", "medium", "hard"]

    if grade not in valid_grades:
        print(f"Invalid grade: {grade}. Must be one of: {valid_grades}")
        sys.exit(1)

    if difficulty not in valid_difficulties:
        print(f"Invalid difficulty: {difficulty}. Must be one of: {valid_difficulties}")
        sys.exit(1)

    asyncio.run(run_cron_job(grade, difficulty))


if __name__ == "__main__":
    main()
