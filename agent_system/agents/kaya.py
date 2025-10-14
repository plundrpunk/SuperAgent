"""
Kaya - Router/Orchestrator Agent
Coordinates all other agents, routes tasks, and manages session flow.
"""
import re
from typing import Dict, Any, Optional, List
import time

from agent_system.agents.base_agent import BaseAgent, AgentResult
from agent_system.router import Router


class KayaAgent(BaseAgent):
    """
    Kaya orchestrates the multi-agent system.

    Responsibilities:
    - Parse user intents from voice/text commands
    - Route tasks to appropriate agents via router.py
    - Dispatch and coordinate agent execution
    - Aggregate results from multiple agents
    - Track session costs and enforce budgets
    - Report clear status updates
    """

    # Intent patterns for command parsing
    INTENT_PATTERNS = {
        'create_test': [
            r'create.*test.*for\s+(.+)',
            r'write.*test.*for\s+(.+)',
            r'generate.*test.*for\s+(.+)',
        ],
        'run_test': [
            r'run.*test[s]?\s+(.+)',
            r'execute.*test[s]?\s+(.+)',
        ],
        'fix_failure': [
            r'fix.*task\s+(\w+)',
            r'patch.*task\s+(\w+)',
            r'repair.*task\s+(\w+)',
        ],
        'validate': [
            r'validate\s+(.+)',
            r'verify\s+(.+)',
        ],
        'status': [
            r'status.*task\s+(\w+)',
            r'what.*status.*task\s+(\w+)',
        ]
    }

    def __init__(self):
        """Initialize Kaya orchestrator."""
        super().__init__('kaya')
        self.router = Router()
        self.session_cost = 0.0

    def execute(self, command: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Execute user command.

        Args:
            command: User command (voice or text)
            context: Optional context (session_id, previous tasks, etc.)

        Returns:
            AgentResult with orchestration outcome
        """
        start_time = time.time()

        try:
            # 1. Parse intent
            intent_result = self.parse_intent(command)
            if not intent_result['success']:
                return AgentResult(
                    success=False,
                    error=f"Could not understand command: {command}",
                    execution_time_ms=self._track_execution(start_time)
                )

            intent_type = intent_result['intent']
            slots = intent_result['slots']

            # 2. Route to appropriate workflow
            if intent_type == 'create_test':
                result = self._handle_create_test(slots, context)
            elif intent_type == 'run_test':
                result = self._handle_run_test(slots, context)
            elif intent_type == 'fix_failure':
                result = self._handle_fix_failure(slots, context)
            elif intent_type == 'validate':
                result = self._handle_validate(slots, context)
            elif intent_type == 'status':
                result = self._handle_status(slots, context)
            else:
                result = AgentResult(
                    success=False,
                    error=f"Unknown intent type: {intent_type}"
                )

            # 3. Track costs
            execution_time = self._track_execution(start_time, result.cost_usd)
            result.execution_time_ms = execution_time

            return result

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Orchestration error: {str(e)}",
                execution_time_ms=self._track_execution(start_time)
            )

    def parse_intent(self, command: str) -> Dict[str, Any]:
        """
        Parse user command into structured intent.

        Args:
            command: User command text

        Returns:
            Dict with success, intent, slots
        """
        command_lower = command.lower().strip()

        for intent_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, command_lower)
                if match:
                    # Extract slots from regex groups
                    slots = {'raw_value': match.group(1) if match.groups() else ''}
                    return {
                        'success': True,
                        'intent': intent_type,
                        'slots': slots
                    }

        return {
            'success': False,
            'intent': None,
            'slots': {}
        }

    def _handle_create_test(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """Handle create_test intent."""
        feature = slots.get('raw_value', '')

        # Route to Scribe agent
        routing_decision = self.router.route(
            task_type='write_test',
            task_description=feature,
            task_scope=''
        )

        return AgentResult(
            success=True,
            data={
                'action': 'route_to_scribe',
                'feature': feature,
                'agent': routing_decision.agent,
                'model': routing_decision.model,
                'max_cost': routing_decision.max_cost_usd
            },
            metadata={'routing_decision': routing_decision}
        )

    def _handle_run_test(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """Handle run_test intent."""
        test_path = slots.get('raw_value', '')

        # Route to Runner agent
        routing_decision = self.router.route(
            task_type='execute_test',
            task_description=test_path
        )

        return AgentResult(
            success=True,
            data={
                'action': 'route_to_runner',
                'test_path': test_path,
                'agent': routing_decision.agent,
                'model': routing_decision.model
            },
            metadata={'routing_decision': routing_decision}
        )

    def _handle_fix_failure(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """Handle fix_failure intent."""
        task_id = slots.get('raw_value', '')

        # Route to Medic agent
        routing_decision = self.router.route(
            task_type='fix_bug',
            task_description=f"Fix failed task {task_id}"
        )

        return AgentResult(
            success=True,
            data={
                'action': 'route_to_medic',
                'task_id': task_id,
                'agent': routing_decision.agent,
                'model': routing_decision.model
            },
            metadata={'routing_decision': routing_decision}
        )

    def _handle_validate(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """Handle validate intent."""
        test_path = slots.get('raw_value', '')

        # Route to Gemini agent
        routing_decision = self.router.route(
            task_type='validate',
            task_description=test_path,
            test_path=test_path
        )

        return AgentResult(
            success=True,
            data={
                'action': 'route_to_gemini',
                'test_path': test_path,
                'agent': routing_decision.agent,
                'model': routing_decision.model
            },
            metadata={'routing_decision': routing_decision}
        )

    def _handle_status(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """Handle status inquiry."""
        task_id = slots.get('raw_value', '')

        return AgentResult(
            success=True,
            data={
                'action': 'get_status',
                'task_id': task_id,
                'message': f"Status check requested for task {task_id}"
            }
        )

    def check_budget(self, budget_type: str = 'per_session') -> Dict[str, Any]:
        """
        Check current budget status.

        Args:
            budget_type: 'per_session' or 'daily'

        Returns:
            Budget status dict
        """
        return self.router.check_budget(self.session_cost, budget_type)


def main():
    """CLI entry point for Kaya."""
    import sys

    kaya = KayaAgent()

    if len(sys.argv) > 1:
        command = ' '.join(sys.argv[1:])
        result = kaya.execute(command)
        print(f"Result: {result}")
    else:
        print("Kaya Agent - Interactive Mode")
        print("Enter commands or 'quit' to exit")

        while True:
            try:
                command = input("\n> ")
                if command.lower() in ['quit', 'exit']:
                    break

                result = kaya.execute(command)
                print(f"\nSuccess: {result.success}")
                if result.data:
                    print(f"Data: {result.data}")
                if result.error:
                    print(f"Error: {result.error}")

            except KeyboardInterrupt:
                print("\nExiting...")
                break


if __name__ == '__main__':
    main()
