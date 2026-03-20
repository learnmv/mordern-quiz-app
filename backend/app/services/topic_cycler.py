import redis
from datetime import datetime
from typing import Optional, Tuple, Dict, List
from app.config import settings

# Grade-specific topics from the curriculum
GRADE_TOPICS = {
    "6": [
        "Unit Rates", "Ratios", "Percentages", "Ratio Reasoning",
        "Fractions", "Decimals", "Negative Numbers", "GCF", "LCM",
        "Absolute Value", "Number Line", "Coordinate Plane",
        "Variables", "Writing Expressions", "One-Step Equations",
        "One-Step Inequalities", "Evaluating Expressions",
        "Order of Operations", "Equivalent Expressions",
        "Area of Polygons", "Volume of Prisms", "Surface Area",
        "Coordinate Plane Polygons",
        "Statistical Questions", "Mean", "Median", "Mode", "Range",
        "Dot Plots", "Histograms", "Box Plots"
    ],
    "7": [
        "Unit Rates", "Proportional Relationships", "Constant of Proportionality",
        "Percentages", "Markup & Discount", "Simple Interest", "Scale Drawings",
        "Add & Subtract Rationals", "Multiply & Divide Rationals",
        "Convert to Decimals", "Real-World Problems", "Properties of Operations",
        "Complex Fractions",
        "Factor & Expand Linear Expressions", "Rewriting Expressions",
        "Two-Step Equations", "Two-Step Inequalities", "Word Problems",
        "Multi-Step Equations",
        "Scale Drawings", "Drawing Geometric Shapes", "Cross-Sections",
        "Circles (Area & Circumference)", "Angles", "Area & Perimeter",
        "Volume & Surface Area", "Surveying Areas",
        "Populations & Samples", "Random Sampling", "Comparing Data Sets",
        "Mean, Median, IQR", "Probability", "Compound Events", "Tree Diagrams"
    ],
    "8": [
        "Rational Numbers", "Irrational Numbers", "Approximate Irrationals",
        "Compare Real Numbers", "Scientific Notation", "Operations with Sci Notation",
        "Integer Exponents", "Laws of Exponents", "Scientific Notation",
        "Linear Equations", "Solving for Variables", "Systems of Equations",
        "Graphing Lines", "Slope-Intercept Form", "Slope & Rate of Change",
        "Proportional Relationships",
        "Transformations", "Congruence", "Similarity", "Pythagorean Theorem",
        "Volume of Cylinders/Cones/Spheres", "Surface Area", "Coordinate Geometry",
        "Scatter Plots", "Line of Best Fit", "Two-Way Tables", "Probability"
    ]
}


class TopicCycler:
    """Manages cycling through topics for each grade/difficulty combination.

    Each grade has its own topic list and cycles independently.
    """

    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def get_topics_for_grade(self, grade: str) -> List[str]:
        """Get the list of topics for a specific grade."""
        return GRADE_TOPICS.get(grade, [])

    def get_next_topic(self, grade: str, difficulty: str) -> Tuple[str, int]:
        """Get the next topic to generate for given grade/difficulty.

        Each grade cycles through its own topic list independently.

        Returns:
            Tuple of (topic_name, topic_index)
        """
        topics = self.get_topics_for_grade(grade)
        if not topics:
            raise ValueError(f"No topics defined for grade {grade}")

        key = f"cron:topic_index:{grade}:{difficulty}"
        current_index_str = self.redis_client.get(key)

        if current_index_str is None:
            current_index = 0
        else:
            current_index = int(current_index_str)

        # Get topic (cycle through grade-specific topics)
        topic = topics[current_index % len(topics)]

        # Increment for next time
        next_index = (current_index + 1) % len(topics)
        self.redis_client.set(key, next_index)

        return topic, current_index

    def get_current_state(self, grade: str, difficulty: str) -> dict:
        """Get current cycling state for monitoring."""
        topics = self.get_topics_for_grade(grade)
        key = f"cron:topic_index:{grade}:{difficulty}"
        current_index_str = self.redis_client.get(key)
        current_index = int(current_index_str) if current_index_str else 0

        return {
            "grade": grade,
            "difficulty": difficulty,
            "current_index": current_index,
            "total_topics": len(topics),
            "current_topic": topics[current_index % len(topics)] if topics else None,
            "topics": topics
        }

    def get_all_states(self) -> List[dict]:
        """Get current cycling state for all grade/difficulty combinations."""
        grades = ["6", "7", "8"]
        difficulties = ["easy", "medium", "hard"]

        states = []
        for grade in grades:
            for difficulty in difficulties:
                states.append(self.get_current_state(grade, difficulty))

        return states

    def reset_index(self, grade: str, difficulty: str) -> None:
        """Reset the topic index for a specific grade/difficulty."""
        key = f"cron:topic_index:{grade}:{difficulty}"
        self.redis_client.delete(key)

    def reset_all(self) -> None:
        """Reset all topic indices."""
        grades = ["6", "7", "8"]
        difficulties = ["easy", "medium", "hard"]

        for grade in grades:
            for difficulty in difficulties:
                self.reset_index(grade, difficulty)
