"""
Complexity Estimator for SuperAgent
Analyzes task descriptions to determine complexity and appropriate model selection.
"""
import re
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class ComplexityScore:
    """Represents a task complexity score."""
    score: int
    difficulty: str  # "easy" or "hard"
    model_recommendation: str  # "haiku" or "sonnet"
    breakdown: Dict[str, int]  # Score breakdown by category


class ComplexityEstimator:
    """
    Estimates task complexity based on rule-based heuristics.

    Scoring rules:
    - Steps > 4: +2
    - Auth/OAuth: +3
    - File operations: +2
    - WebSocket: +3
    - Payment: +4
    - Mocking: +2

    Threshold: ≥5 = hard (Sonnet), <5 = easy (Haiku)
    """

    # Scoring rules
    RULES = {
        'steps': {'pattern': r'\b(step|action|phase|stage)\b.*(\d+)', 'score': 2, 'threshold': 4},
        'auth': {'patterns': [r'\bauth\b', r'\boauth\b', r'\blogin\b', r'\bcredential'], 'score': 3},
        'file_ops': {'patterns': [r'\bfile\b', r'\bupload\b', r'\bdownload\b', r'\battachment'], 'score': 2},
        'websocket': {'patterns': [r'\bwebsocket\b', r'\bws\b', r'\breal-?time\b'], 'score': 3},
        'payment': {'patterns': [r'\bpay\b', r'\bpurchase\b', r'\bcheckout\b', r'\bstripe\b'], 'score': 4},
        'mocking': {'patterns': [r'\bmock\b', r'\bstub\b', r'\bfake\b'], 'score': 2},
    }

    # Complexity threshold
    THRESHOLD = 5

    def estimate(self, task_description: str, task_scope: str = "") -> ComplexityScore:
        """
        Estimate complexity of a task.

        Args:
            task_description: Description of the task
            task_scope: Optional scope/context

        Returns:
            ComplexityScore with score, difficulty, model recommendation, and breakdown
        """
        combined_text = f"{task_description} {task_scope}".lower()
        breakdown = {}
        total_score = 0

        # Check for steps count
        steps_match = re.search(self.RULES['steps']['pattern'], combined_text, re.IGNORECASE)
        if steps_match:
            try:
                num_steps = int(steps_match.group(2))
                if num_steps > self.RULES['steps']['threshold']:
                    score = self.RULES['steps']['score']
                    breakdown['steps'] = score
                    total_score += score
            except (ValueError, IndexError):
                pass

        # Check other patterns
        for category, rule in self.RULES.items():
            if category == 'steps':
                continue  # Already handled

            patterns = rule.get('patterns', [])
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    score = rule['score']
                    breakdown[category] = score
                    total_score += score
                    break  # Only count once per category

        # Determine difficulty and model
        if total_score >= self.THRESHOLD:
            difficulty = "hard"
            model = "sonnet"
        else:
            difficulty = "easy"
            model = "haiku"

        return ComplexityScore(
            score=total_score,
            difficulty=difficulty,
            model_recommendation=model,
            breakdown=breakdown
        )

    def estimate_batch(self, tasks: list) -> Dict[str, ComplexityScore]:
        """
        Estimate complexity for multiple tasks.

        Args:
            tasks: List of dict with 'id', 'description', 'scope' keys

        Returns:
            Dict mapping task_id to ComplexityScore
        """
        results = {}
        for task in tasks:
            task_id = task.get('id', task.get('task_id'))
            description = task.get('description', '')
            scope = task.get('scope', '')
            results[task_id] = self.estimate(description, scope)
        return results


def estimate_complexity(task_description: str, task_scope: str = "") -> Dict[str, Any]:
    """
    Convenience function for single complexity estimation.

    Args:
        task_description: Description of the task
        task_scope: Optional scope/context

    Returns:
        Dict with score, difficulty, model, and breakdown
    """
    estimator = ComplexityEstimator()
    result = estimator.estimate(task_description, task_scope)
    return {
        'score': result.score,
        'difficulty': result.difficulty,
        'model': result.model_recommendation,
        'breakdown': result.breakdown
    }
