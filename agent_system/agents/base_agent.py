"""
Base Agent class for SuperAgent
Provides common functionality for all agents.
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import time

from agent_system.secrets_manager import get_secrets_manager


@dataclass
class AgentResult:
    """Standard result format for all agents."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: int = 0
    cost_usd: float = 0.0


class BaseAgent:
    """
    Base class for all SuperAgent agents.

    Provides:
    - Config loading from YAML
    - Standard result format
    - Error handling
    - Execution timing
    - Cost tracking
    """

    def __init__(self, agent_name: str, config_path: Optional[str] = None):
        """
        Initialize base agent.

        Args:
            agent_name: Name of the agent (kaya, scribe, runner, critic, medic, gemini)
            config_path: Optional path to agent config YAML
        """
        self.name = agent_name

        # Load config
        if config_path is None:
            # Default to .claude/agents/{agent_name}.yaml
            config_path = Path(__file__).parent.parent.parent / '.claude' / 'agents' / f'{agent_name}.yaml'

        self.config = self._load_config(config_path) if Path(config_path).exists() else {}

        # Initialize secrets manager for API key management
        self.secrets_manager = get_secrets_manager()

        # Track costs and execution time
        self.total_cost = 0.0
        self.execution_count = 0

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """
        Load agent configuration from YAML.

        Args:
            config_path: Path to config file

        Returns:
            Config dict
        """
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
            return {}

    def execute(self, **kwargs) -> AgentResult:
        """
        Execute agent task. Override in subclasses.

        Args:
            **kwargs: Task-specific arguments

        Returns:
            AgentResult with success/failure and data
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def _track_execution(self, start_time: float, cost: float = 0.0):
        """
        Track execution metrics.

        Args:
            start_time: Start time from time.time()
            cost: Cost in USD
        """
        execution_time_ms = int((time.time() - start_time) * 1000)
        self.total_cost += cost
        self.execution_count += 1
        return execution_time_ms

    def get_stats(self) -> Dict[str, Any]:
        """
        Get agent statistics.

        Returns:
            Dict with total_cost, execution_count, avg_cost
        """
        avg_cost = self.total_cost / self.execution_count if self.execution_count > 0 else 0.0
        return {
            'agent': self.name,
            'total_cost_usd': self.total_cost,
            'execution_count': self.execution_count,
            'avg_cost_usd': avg_cost
        }
