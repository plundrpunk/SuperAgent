"""
Router for SuperAgent
Makes intelligent agent/model selection decisions based on task complexity and cost policies.
"""
import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import fnmatch

from agent_system.complexity_estimator import ComplexityEstimator


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    agent: str
    model: str
    max_cost_usd: float
    reason: str
    complexity_score: int
    difficulty: str


class Router:
    """
    Routes tasks to appropriate agents with model selection and cost enforcement.

    Responsibilities:
    - Load router_policy.yaml configuration
    - Use complexity_estimator to score tasks
    - Match routing rules based on task type and complexity
    - Apply cost overrides for critical paths (auth/payment)
    - Return agent/model/max_cost decision
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize router with policy configuration.

        Args:
            config_path: Path to router_policy.yaml (defaults to .claude/router_policy.yaml)
        """
        if config_path is None:
            # Default to .claude/router_policy.yaml
            config_path = Path(__file__).parent.parent / '.claude' / 'router_policy.yaml'

        self.config_path = config_path
        self.policy = self._load_policy()
        self.estimator = ComplexityEstimator()

    def _load_policy(self) -> Dict[str, Any]:
        """
        Load routing policy from YAML file.

        Returns:
            Policy configuration dict
        """
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Router policy not found at {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in router policy: {e}")

    def route(
        self,
        task_type: str,
        task_description: str = "",
        task_scope: str = "",
        test_path: Optional[str] = None
    ) -> RoutingDecision:
        """
        Route task to appropriate agent/model.

        Args:
            task_type: Type of task (write_test, execute_test, fix_bug, pre_validate, validate)
            task_description: Task description for complexity estimation
            task_scope: Task scope/context
            test_path: Optional path to test file (for cost override matching)

        Returns:
            RoutingDecision with agent, model, max_cost, and reasoning
        """
        # 1. Estimate complexity
        complexity = self.estimator.estimate(task_description, task_scope)

        # 2. Find matching routing rule
        routing_rule = self._find_routing_rule(task_type, complexity.difficulty)

        if not routing_rule:
            raise ValueError(f"No routing rule found for task_type={task_type}, difficulty={complexity.difficulty}")

        # 3. Extract agent/model from rule
        agent = routing_rule['agent']
        model = routing_rule['model']
        reason = routing_rule.get('reason', 'Default routing')

        # 4. Determine base cost limit
        base_cost = self.policy.get('cost_targets', {}).get('max_cost_per_feature_usd', 0.50)

        # 5. Apply cost overrides for critical paths
        max_cost = self._apply_cost_override(test_path, base_cost)

        return RoutingDecision(
            agent=agent,
            model=model,
            max_cost_usd=max_cost,
            reason=reason,
            complexity_score=complexity.score,
            difficulty=complexity.difficulty
        )

    def _find_routing_rule(self, task_type: str, complexity: str) -> Optional[Dict[str, Any]]:
        """
        Find matching routing rule from policy.

        Args:
            task_type: Task type (write_test, execute_test, etc.)
            complexity: Complexity level (easy, hard, any)

        Returns:
            Matching rule dict or None
        """
        routing_rules = self.policy.get('routing', [])

        for rule in routing_rules:
            # Match task type
            if rule.get('task') != task_type:
                continue

            # Match complexity
            rule_complexity = rule.get('complexity', 'any')
            if rule_complexity == 'any' or rule_complexity == complexity:
                return rule

        return None

    def _apply_cost_override(self, test_path: Optional[str], base_cost: float) -> float:
        """
        Apply cost overrides for critical paths.

        Args:
            test_path: Path to test file
            base_cost: Base cost limit

        Returns:
            Final cost limit (may be overridden)
        """
        if not test_path:
            return base_cost

        # Get cost overrides from policy
        cost_overrides = self.policy.get('cost_overrides', {}).get('critical_paths', [])

        for override in cost_overrides:
            pattern = override.get('pattern', '')
            override_cost = override.get('max_cost_usd')

            # Match glob pattern
            if fnmatch.fnmatch(test_path, pattern) and override_cost:
                return override_cost

        return base_cost

    def get_fallback(self, failure_type: str) -> str:
        """
        Get fallback action for failure type.

        Args:
            failure_type: Type of failure (critic_fail, validation_timeout, medic_escalation)

        Returns:
            Fallback action string
        """
        fallbacks = self.policy.get('fallbacks', {})
        return fallbacks.get(failure_type, 'queue_for_hitl')

    def get_max_retries(self) -> int:
        """
        Get maximum retry count from policy.

        Returns:
            Max retries (default 3)
        """
        return self.policy.get('fallbacks', {}).get('max_retries', 3)

    def check_budget(self, current_spend: float, budget_type: str = 'per_session') -> Dict[str, Any]:
        """
        Check if current spending is within budget limits.

        Args:
            current_spend: Current spending in USD
            budget_type: 'per_session' or 'daily'

        Returns:
            Dict with status, limit, remaining, warning
        """
        budget_key = f"{budget_type}_budget_usd"
        budget = self.policy.get('budget_enforcement', {}).get(budget_key, 5.00)

        # Calculate thresholds
        soft_limit = self.policy.get('budget_enforcement', {}).get('soft_limit_warning', 0.80)
        hard_limit = self.policy.get('budget_enforcement', {}).get('hard_limit_stop', 1.00)

        soft_threshold = budget * soft_limit
        hard_threshold = budget * hard_limit

        remaining = budget - current_spend
        percent_used = (current_spend / budget) * 100 if budget > 0 else 0

        # Determine status
        if current_spend >= hard_threshold:
            status = 'exceeded'
            warning = f"Budget exceeded! {current_spend:.2f} >= {hard_threshold:.2f}"
        elif current_spend >= soft_threshold:
            status = 'warning'
            warning = f"Budget warning: {percent_used:.1f}% used ({current_spend:.2f}/{budget:.2f})"
        else:
            status = 'ok'
            warning = None

        return {
            'status': status,
            'limit': budget,
            'remaining': remaining,
            'percent_used': percent_used,
            'warning': warning
        }

    def get_haiku_ratio_target(self) -> float:
        """
        Get target ratio for Haiku usage.

        Returns:
            Haiku ratio target (0.0-1.0)
        """
        return self.policy.get('cost_targets', {}).get('use_haiku_ratio', 0.7)


def route_task(
    task_type: str,
    task_description: str = "",
    task_scope: str = "",
    test_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function for routing a single task.

    Args:
        task_type: Type of task
        task_description: Task description
        task_scope: Task scope
        test_path: Optional test file path

    Returns:
        Dict with agent, model, max_cost_usd, reason, complexity_score, difficulty
    """
    router = Router()
    decision = router.route(task_type, task_description, task_scope, test_path)
    return {
        'agent': decision.agent,
        'model': decision.model,
        'max_cost_usd': decision.max_cost_usd,
        'reason': decision.reason,
        'complexity_score': decision.complexity_score,
        'difficulty': decision.difficulty
    }
