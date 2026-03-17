#!/usr/bin/env python3
"""
Migration script to add diagrams to existing questions that require them.

This script queries the TopicQuestion table for questions belonging to diagram-requiring
topics that don't have a diagram field, generates diagrams using the quiz generator,
and updates the question_data JSONB column.

Usage:
    python migrate_diagrams.py --dry-run          # Preview what would be migrated
    python migrate_diagrams.py --topic "Area of Polygons"  # Migrate specific topic
    python migrate_diagrams.py --batch-size 10 --delay 2   # Custom batch/delay
    python migrate_diagrams.py                  # Run full migration
"""

import asyncio
import json
import argparse
import logging
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import select, and_, func
from sqlalchemy.dialects.postgresql import JSONB

# Add parent directory to path for imports
sys.path.insert(0, '/home/sysadmin/mordern-quiz-app/backend')

from app.database import AsyncSessionLocal
from app.models.quiz import TopicQuestion
from app.services.quiz_generator import DIAGRAM_TOPICS, generate_diagram_for_question

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def get_questions_without_diagrams(
    session,
    topic_filter: Optional[str] = None
) -> List[TopicQuestion]:
    """
    Query TopicQuestion table for questions that need diagrams but don't have them.

    Args:
        session: Database session
        topic_filter: Optional specific topic to filter by

    Returns:
        List of TopicQuestion records that need diagram migration
    """
    # Build list of topics to check
    topics_to_check = [topic_filter] if topic_filter else DIAGRAM_TOPICS

    # Query for questions in diagram topics
    conditions = [
        TopicQuestion.topic.in_(topics_to_check)
    ]

    result = await session.execute(
        select(TopicQuestion).where(and_(*conditions))
    )

    questions_needing_diagrams = []

    for row in result.scalars().all():
        questions = row.question_data.get('questions', [])

        # Check if any question lacks a diagram field
        needs_update = False
        for question in questions:
            if 'diagram' not in question:
                needs_update = True
                break

        if needs_update:
            questions_needing_diagrams.append(row)

    return questions_needing_diagrams


async def migrate_question(
    session,
    topic_question: TopicQuestion,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Migrate a single TopicQuestion record by generating diagrams for questions that need them.

    Args:
        session: Database session
        topic_question: The TopicQuestion record to migrate
        dry_run: If True, don't actually update the database

    Returns:
        Dict with migration results
    """
    result = {
        'id': topic_question.id,
        'topic': topic_question.topic,
        'grade': topic_question.grade,
        'difficulty': topic_question.difficulty,
        'questions_processed': 0,
        'diagrams_generated': 0,
        'errors': []
    }

    questions = topic_question.question_data.get('questions', [])
    updated_questions = []

    for question in questions:
        result['questions_processed'] += 1

        # Skip if already has diagram
        if 'diagram' in question and question['diagram'] is not None:
            updated_questions.append(question)
            continue

        try:
            # Generate diagram for this question
            diagram = await generate_diagram_for_question(
                question_text=question.get('text', ''),
                topic=topic_question.topic,
                grade=topic_question.grade
            )

            if diagram:
                question['diagram'] = diagram
                question['requires_canvas'] = True
                result['diagrams_generated'] += 1
            else:
                # Set diagram to None if generation failed
                question['diagram'] = None
                question['requires_canvas'] = False
                result['errors'].append(f"Failed to generate diagram for question: {question.get('text', '')[:50]}...")

        except Exception as e:
            question['diagram'] = None
            question['requires_canvas'] = False
            result['errors'].append(f"Error generating diagram: {str(e)}")
            logger.error(f"Error generating diagram for question {question.get('id', 'unknown')}: {e}")

        updated_questions.append(question)

    # Update the question_data
    new_question_data = {'questions': updated_questions}

    if not dry_run:
        topic_question.question_data = new_question_data
        await session.commit()
        logger.info(f"Migrated TopicQuestion {topic_question.id}: {result['diagrams_generated']} diagrams generated")
    else:
        logger.info(f"[DRY RUN] Would migrate TopicQuestion {topic_question.id}: {result['diagrams_generated']} diagrams")

    return result


async def run_migration(
    dry_run: bool = False,
    topic_filter: Optional[str] = None,
    batch_size: int = 5,
    delay: float = 1.0
) -> Dict[str, Any]:
    """
    Run the migration process on all questions needing diagrams.

    Args:
        dry_run: If True, don't actually update the database
        topic_filter: Optional specific topic to filter by
        batch_size: Number of questions to process before committing/delaying
        delay: Delay in seconds between API calls to avoid rate limiting

    Returns:
        Dict with overall migration statistics
    """
    stats = {
        'total_records': 0,
        'total_questions': 0,
        'diagrams_generated': 0,
        'errors': 0,
        'start_time': datetime.now().isoformat(),
        'end_time': None
    }

    async with AsyncSessionLocal() as session:
        try:
            # Get all questions needing diagrams
            logger.info(f"Fetching questions without diagrams (topic filter: {topic_filter or 'all diagram topics'})...")
            questions_to_migrate = await get_questions_without_diagrams(session, topic_filter)

            stats['total_records'] = len(questions_to_migrate)
            logger.info(f"Found {len(questions_to_migrate)} TopicQuestion records needing migration")

            if dry_run:
                logger.info("DRY RUN MODE: No database changes will be made")

            # Process in batches
            for i, topic_question in enumerate(questions_to_migrate):
                logger.info(f"Processing record {i + 1}/{len(questions_to_migrate)} (ID: {topic_question.id})...")

                result = await migrate_question(session, topic_question, dry_run)

                stats['total_questions'] += result['questions_processed']
                stats['diagrams_generated'] += result['diagrams_generated']
                stats['errors'] += len(result['errors'])

                # Delay between API calls to avoid rate limiting
                if i < len(questions_to_migrate) - 1 and not dry_run:
                    await asyncio.sleep(delay)

                # Periodic commit every batch_size records
                if (i + 1) % batch_size == 0 and not dry_run:
                    logger.info(f"Committed batch of {batch_size} records")

            stats['end_time'] = datetime.now().isoformat()

            # Final summary
            logger.info("=" * 60)
            logger.info("MIGRATION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total records processed: {stats['total_records']}")
            logger.info(f"Total questions processed: {stats['total_questions']}")
            logger.info(f"Diagrams generated: {stats['diagrams_generated']}")
            logger.info(f"Errors encountered: {stats['errors']}")
            logger.info(f"Start time: {stats['start_time']}")
            logger.info(f"End time: {stats['end_time']}")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await session.rollback()
            raise

    return stats


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Migrate existing questions to add diagram fields'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be migrated without making changes'
    )
    parser.add_argument(
        '--topic',
        type=str,
        choices=DIAGRAM_TOPICS,
        help=f'Filter to specific topic. Choices: {", ".join(DIAGRAM_TOPICS)}'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Number of records to process before committing (default: 5)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay in seconds between API calls (default: 1.0)'
    )

    args = parser.parse_args()

    # Validate topic if provided
    if args.topic and args.topic not in DIAGRAM_TOPICS:
        logger.error(f"Invalid topic: {args.topic}")
        logger.error(f"Valid topics: {', '.join(DIAGRAM_TOPICS)}")
        sys.exit(1)

    # Run the migration
    try:
        stats = asyncio.run(run_migration(
            dry_run=args.dry_run,
            topic_filter=args.topic,
            batch_size=args.batch_size,
            delay=args.delay
        ))

        # Exit with error code if there were errors
        if stats['errors'] > 0:
            logger.warning(f"Migration completed with {stats['errors']} errors")
            sys.exit(2)

        sys.exit(0)

    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
