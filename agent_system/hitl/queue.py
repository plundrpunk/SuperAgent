"""
HITL Queue Management
Handles Human-in-the-Loop escalation workflow.
"""
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient


class HITLQueue:
    """
    Manages Human-in-the-Loop escalation queue.

    Responsibilities:
    - Add failed tasks to queue
    - Calculate priority scores
    - List queue items sorted by priority
    - Mark items as resolved
    - Store human annotations in vector DB
    """

    QUEUE_KEY = "hitl:queue"
    TASK_KEY_PREFIX = "hitl:task:"

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        vector_client: Optional[VectorClient] = None
    ):
        """
        Initialize HITL queue.

        Args:
            redis_client: Redis client for queue storage
            vector_client: Vector DB client for annotations
        """
        self.redis = redis_client or RedisClient()
        self.vector = vector_client or VectorClient()

    def add(self, task: Dict[str, Any]) -> bool:
        """
        Add task to HITL queue.

        Args:
            task: Task dict matching schema.json

        Returns:
            True if added successfully
        """
        task_id = task.get('task_id')
        if not task_id:
            raise ValueError("task_id is required")

        # Add timestamp if not present
        if 'created_at' not in task:
            task['created_at'] = datetime.utcnow().isoformat()

        # Calculate priority if not set
        if 'priority' not in task or task['priority'] is None:
            task['priority'] = self._calculate_priority(task)

        # Store task data in Redis
        task_key = f"{self.TASK_KEY_PREFIX}{task_id}"
        self.redis.set(task_key, task, ttl=86400)  # 24h TTL

        # Add to queue (sorted by priority)
        self.redis.client.zadd(self.QUEUE_KEY, {task_id: task['priority']})

        return True

    def list(
        self,
        include_resolved: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List tasks in queue, sorted by priority (highest first).

        Args:
            include_resolved: Whether to include resolved tasks
            limit: Maximum number of tasks to return

        Returns:
            List of task dicts
        """
        # Get task IDs sorted by priority (descending)
        task_ids = self.redis.client.zrevrange(
            self.QUEUE_KEY,
            0,
            limit - 1 if limit else -1
        )

        tasks = []
        for task_id in task_ids:
            task_key = f"{self.TASK_KEY_PREFIX}{task_id}"
            task_data = self.redis.get(task_key)

            if task_data:
                # Filter resolved if requested
                if not include_resolved and task_data.get('resolved', False):
                    continue

                tasks.append(task_data)

        return tasks

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task details.

        Args:
            task_id: Task identifier

        Returns:
            Task dict or None if not found
        """
        task_key = f"{self.TASK_KEY_PREFIX}{task_id}"
        return self.redis.get(task_key)

    def resolve(
        self,
        task_id: str,
        annotation: Dict[str, Any]
    ) -> bool:
        """
        Mark task as resolved with human annotation.

        Args:
            task_id: Task identifier
            annotation: Human annotation dict with root_cause, fix_strategy, etc.

        Returns:
            True if resolved successfully
        """
        # Get task
        task = self.get(task_id)
        if not task:
            return False

        # Update task
        task['resolved'] = True
        task['resolved_at'] = datetime.utcnow().isoformat()
        task.update(annotation)

        # Store updated task
        task_key = f"{self.TASK_KEY_PREFIX}{task_id}"
        self.redis.set(task_key, task, ttl=86400)

        # Remove from active queue
        self.redis.client.zrem(self.QUEUE_KEY, task_id)

        # Store annotation in vector DB for learning
        self.vector.store_hitl_annotation(
            annotation_id=f"hitl_{task_id}_{int(time.time())}",
            task_description=task.get('feature', ''),
            annotation=annotation
        )

        return True

    def _calculate_priority(self, task: Dict[str, Any]) -> float:
        """
        Calculate priority score (0-1, higher = more urgent).

        Factors:
        - attempts (more attempts = higher priority)
        - feature criticality (auth/payment = higher priority)
        - time in queue

        Args:
            task: Task dict

        Returns:
            Priority score 0.0-1.0
        """
        score = 0.0

        # Attempts factor (0-0.4)
        attempts = task.get('attempts', 1)
        attempts_score = min(attempts / 10, 0.4)
        score += attempts_score

        # Feature criticality (0-0.3)
        feature = task.get('feature', '').lower()
        if any(keyword in feature for keyword in ['auth', 'login', 'payment', 'checkout']):
            score += 0.3

        # Time in queue (0-0.3)
        created_at = task.get('created_at')
        if created_at:
            try:
                created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                hours_old = (datetime.utcnow() - created_time).total_seconds() / 3600
                time_score = min(hours_old / 24, 0.3)  # Max score after 24h
                score += time_score
            except Exception:
                pass

        return min(score, 1.0)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dict with queue stats
        """
        all_tasks = self.list(include_resolved=True)
        active_tasks = [t for t in all_tasks if not t.get('resolved', False)]
        resolved_tasks = [t for t in all_tasks if t.get('resolved', False)]

        return {
            'total_count': len(all_tasks),
            'active_count': len(active_tasks),
            'resolved_count': len(resolved_tasks),
            'avg_priority': sum(t['priority'] for t in active_tasks) / len(active_tasks) if active_tasks else 0.0,
            'high_priority_count': len([t for t in active_tasks if t['priority'] > 0.7])
        }
