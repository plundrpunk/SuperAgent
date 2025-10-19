"""
Test script to populate HITL queue with sample tasks for testing the dashboard.
Run this to add mock tasks to the queue for development/testing.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_system.hitl.queue import HITLQueue
from agent_system.state.redis_client import RedisClient

# Sample tasks
SAMPLE_TASKS = [
    {
        "task_id": "task_001",
        "feature": "User Authentication - Login Flow",
        "code_path": "tests/auth/login.spec.ts",
        "logs_path": "logs/login_test_2025_10_14.log",
        "screenshots": [
            "artifacts/login_001_before.png",
            "artifacts/login_001_after.png"
        ],
        "attempts": 3,
        "last_error": "Error: Selector 'button[data-testid=\"login-submit\"]' not found\n  at Page.click (playwright/lib/page.js:1234)\n  at test (login.spec.ts:45:18)",
        "severity": "high",
        "escalation_reason": "max_retries_exceeded",
        "ai_diagnosis": "The login button selector has changed. The data-testid attribute may have been modified in the latest deploy.",
        "ai_confidence": 0.65,
        "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        "attempt_history": [
            {"attempt": 1, "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat()},
            {"attempt": 2, "timestamp": (datetime.utcnow() - timedelta(hours=1, minutes=30)).isoformat()},
            {"attempt": 3, "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat()}
        ],
        "artifacts": {
            "diff": "- await page.click('button.login-btn');\n+ await page.click('button[data-testid=\"login-submit\"]');",
            "baseline": {"passed": 5, "failed": 1},
            "after_fix": {"passed": 5, "failed": 1}
        }
    },
    {
        "task_id": "task_002",
        "feature": "Checkout Flow - Payment Processing",
        "code_path": "tests/checkout/payment.spec.ts",
        "logs_path": "logs/payment_test_2025_10_14.log",
        "screenshots": [
            "artifacts/payment_002_step1.png",
            "artifacts/payment_002_step2.png",
            "artifacts/payment_002_error.png"
        ],
        "attempts": 5,
        "last_error": "TimeoutError: Timeout 30000ms exceeded.\n  waiting for selector \"#payment-complete\"\n  at test (payment.spec.ts:78:25)",
        "severity": "critical",
        "escalation_reason": "max_retries_exceeded",
        "ai_diagnosis": "Payment confirmation screen not appearing within timeout. Possible API delay or race condition.",
        "ai_confidence": 0.45,
        "created_at": (datetime.utcnow() - timedelta(hours=5)).isoformat(),
        "attempt_history": [
            {"attempt": 1, "timestamp": (datetime.utcnow() - timedelta(hours=5)).isoformat()},
            {"attempt": 2, "timestamp": (datetime.utcnow() - timedelta(hours=4, minutes=30)).isoformat()},
            {"attempt": 3, "timestamp": (datetime.utcnow() - timedelta(hours=4)).isoformat()},
            {"attempt": 4, "timestamp": (datetime.utcnow() - timedelta(hours=3, minutes=30)).isoformat()},
            {"attempt": 5, "timestamp": (datetime.utcnow() - timedelta(hours=3)).isoformat()}
        ]
    },
    {
        "task_id": "task_003",
        "feature": "Shopping Cart - Add Item",
        "code_path": "tests/cart/add_item.spec.ts",
        "logs_path": "logs/cart_test_2025_10_14.log",
        "screenshots": [
            "artifacts/cart_003_initial.png"
        ],
        "attempts": 2,
        "last_error": "AssertionError: Expected 1 but received 0\n  at expect (cart.spec.ts:34:5)",
        "severity": "medium",
        "escalation_reason": "low_confidence",
        "ai_diagnosis": "Cart item count assertion failing. May be a data synchronization issue or API response delay.",
        "ai_confidence": 0.55,
        "created_at": (datetime.utcnow() - timedelta(minutes=45)).isoformat(),
        "attempt_history": [
            {"attempt": 1, "timestamp": (datetime.utcnow() - timedelta(minutes=45)).isoformat()},
            {"attempt": 2, "timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat()}
        ]
    },
    {
        "task_id": "task_004",
        "feature": "Profile Settings - Update Email",
        "code_path": "tests/profile/email_update.spec.ts",
        "logs_path": "logs/profile_test_2025_10_14.log",
        "screenshots": [
            "artifacts/profile_004_before.png",
            "artifacts/profile_004_after.png"
        ],
        "attempts": 1,
        "last_error": "Error: page.locator: Unknown engine \"css\" while parsing selector 'css=.user-email'",
        "severity": "low",
        "escalation_reason": "regression_detected",
        "ai_diagnosis": "Regression detected: Fix introduced 2 new failures in related tests.",
        "ai_confidence": 0.8,
        "created_at": (datetime.utcnow() - timedelta(minutes=15)).isoformat(),
        "attempt_history": [
            {"attempt": 1, "timestamp": (datetime.utcnow() - timedelta(minutes=15)).isoformat()}
        ],
        "artifacts": {
            "comparison": {"new_failures": 2}
        }
    }
]


def main():
    """Populate HITL queue with sample tasks."""
    print("Populating HITL queue with sample tasks...")
    print("=" * 50)

    # Initialize queue
    redis_client = RedisClient()
    hitl_queue = HITLQueue(redis_client=redis_client)

    # Check Redis health
    if not redis_client.health_check():
        print("Error: Redis is not running or not accessible")
        print("Please start Redis with: redis-server")
        return 1

    print(f"✓ Redis connected")
    print()

    # Add tasks
    for task in SAMPLE_TASKS:
        try:
            hitl_queue.add(task)
            print(f"✓ Added task: {task['task_id']} - {task['feature']}")
            print(f"  Priority: {task.get('priority', 'auto-calculated'):.2f}")
            print(f"  Severity: {task['severity']}")
            print(f"  Attempts: {task['attempts']}")
            print()
        except Exception as e:
            print(f"✗ Failed to add task {task['task_id']}: {e}")
            print()

    # Print stats
    print("=" * 50)
    stats = hitl_queue.get_stats()
    print(f"Queue Statistics:")
    print(f"  Total tasks: {stats['total_count']}")
    print(f"  Active tasks: {stats['active_count']}")
    print(f"  Resolved tasks: {stats['resolved_count']}")
    print(f"  High priority tasks: {stats['high_priority_count']}")
    print(f"  Average priority: {stats['avg_priority']:.2f}")
    print()
    print("✓ Sample data loaded successfully!")
    print()
    print("Start the dashboard with: ./start.sh")
    print("Or: python server.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
