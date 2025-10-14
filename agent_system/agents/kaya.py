"""
Kaya - Router/Orchestrator Agent
Coordinates all other agents, routes tasks, and manages session flow.
"""
import re
from typing import Dict, Any, Optional, List, Tuple
import time
import logging

from agent_system.agents.base_agent import BaseAgent, AgentResult
from agent_system.router import Router
from agent_system.lifecycle import get_lifecycle
from agent_system.metrics_aggregator import get_metrics_aggregator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        ],
        'full_pipeline': [
            r'full.*pipeline.*for\s+(.+)',
            r'end.*to.*end.*test.*for\s+(.+)',
            r'complete.*flow.*for\s+(.+)',
        ]
    }

    def __init__(self):
        """Initialize Kaya orchestrator."""
        super().__init__('kaya')
        self.router = Router()
        self.session_cost = 0.0
        self.task_history = []

        # Metrics aggregator for performance tracking
        self.metrics = get_metrics_aggregator()

        # Lazy load agents to avoid circular imports
        self._scribe = None
        self._runner = None
        self._critic = None
        self._medic = None
        self._gemini = None

    def _get_agent(self, agent_name: str):
        """
        Lazy load agent by name to avoid circular imports.

        Args:
            agent_name: Name of agent to load

        Returns:
            Agent instance
        """
        if agent_name == 'scribe':
            if self._scribe is None:
                from agent_system.agents.scribe import ScribeAgent
                self._scribe = ScribeAgent()
            return self._scribe
        elif agent_name == 'runner':
            if self._runner is None:
                from agent_system.agents.runner import RunnerAgent
                self._runner = RunnerAgent()
            return self._runner
        elif agent_name == 'critic':
            if self._critic is None:
                from agent_system.agents.critic import CriticAgent
                self._critic = CriticAgent()
            return self._critic
        elif agent_name == 'medic':
            if self._medic is None:
                from agent_system.agents.medic import MedicAgent
                self._medic = MedicAgent()
            return self._medic
        elif agent_name == 'gemini':
            if self._gemini is None:
                from agent_system.agents.gemini import GeminiAgent
                self._gemini = GeminiAgent()
            return self._gemini
        else:
            raise ValueError(f"Unknown agent: {agent_name}")

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
        lifecycle = get_lifecycle()

        # Check if shutting down
        if lifecycle.is_shutting_down():
            return AgentResult(
                success=False,
                error="Service is shutting down - cannot accept new tasks",
                execution_time_ms=self._track_execution(start_time)
            )

        try:
            # Check budget before starting
            budget_status = self.check_budget()
            if budget_status['status'] == 'exceeded':
                logger.error(f"Budget exceeded: {budget_status['warning']}")
                return AgentResult(
                    success=False,
                    error=budget_status['warning'],
                    metadata={'budget_status': budget_status},
                    execution_time_ms=self._track_execution(start_time)
                )

            # Log budget warning if approaching limit
            if budget_status['status'] == 'warning':
                logger.warning(budget_status['warning'])

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

            logger.info(f"Parsed intent: {intent_type} with slots: {slots}")

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
            elif intent_type == 'full_pipeline':
                result = self._handle_full_pipeline(slots, context)
            else:
                result = AgentResult(
                    success=False,
                    error=f"Unknown intent type: {intent_type}"
                )

            # 3. Track costs
            if result.cost_usd > 0:
                self.session_cost += result.cost_usd

            execution_time = self._track_execution(start_time, result.cost_usd)
            result.execution_time_ms = execution_time

            # Add to task history
            self.task_history.append({
                'command': command,
                'intent': intent_type,
                'success': result.success,
                'cost': result.cost_usd,
                'timestamp': time.time()
            })

            return result

        except Exception as e:
            logger.exception(f"Orchestration error: {e}")
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
        """
        Handle create_test intent - writes test using Scribe.

        Args:
            slots: Parsed intent slots
            context: Optional context

        Returns:
            AgentResult with test creation outcome
        """
        feature = slots.get('raw_value', '')

        # Route to Scribe agent
        routing_decision = self.router.route(
            task_type='write_test',
            task_description=feature,
            task_scope=''
        )

        logger.info(f"Routing to {routing_decision.agent} with {routing_decision.model} (complexity: {routing_decision.difficulty})")

        # Dispatch to Scribe
        try:
            scribe = self._get_agent('scribe')

            # Extract feature name for test file
            feature_name = feature.split()[:3]  # First 3 words
            feature_name = '_'.join(feature_name).lower().replace(',', '')

            # Generate output path
            output_path = f"tests/{feature_name}.spec.ts"

            # Execute Scribe
            scribe_result = scribe.execute(
                task_description=feature,
                feature_name=feature,
                output_path=output_path,
                complexity=routing_decision.difficulty
            )

            # Record metrics
            if scribe_result.execution_time_ms > 0:
                self.metrics.record_agent_activity(
                    agent='scribe',
                    duration_ms=scribe_result.execution_time_ms,
                    cost_usd=scribe_result.cost_usd,
                    model=routing_decision.model
                )

            # Prepare result
            return AgentResult(
                success=scribe_result.success,
                data={
                    'action': 'test_created',
                    'feature': feature,
                    'test_path': scribe_result.data.get('test_path') if scribe_result.success else None,
                    'agent': routing_decision.agent,
                    'model': routing_decision.model,
                    'complexity': routing_decision.difficulty,
                    'scribe_result': scribe_result.data
                },
                error=scribe_result.error,
                cost_usd=scribe_result.cost_usd,
                metadata={
                    'routing_decision': routing_decision.__dict__,
                    'scribe_metadata': scribe_result.metadata
                }
            )

        except Exception as e:
            logger.exception(f"Failed to dispatch to Scribe: {e}")
            return AgentResult(
                success=False,
                error=f"Failed to create test: {str(e)}",
                metadata={'routing_decision': routing_decision.__dict__}
            )

    def _handle_run_test(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """
        Handle run_test intent - executes test using Runner.

        Args:
            slots: Parsed intent slots
            context: Optional context

        Returns:
            AgentResult with test execution outcome
        """
        test_path = slots.get('raw_value', '')

        # Route to Runner agent
        routing_decision = self.router.route(
            task_type='execute_test',
            task_description=test_path
        )

        logger.info(f"Routing to {routing_decision.agent} with {routing_decision.model}")

        # Dispatch to Runner
        try:
            runner = self._get_agent('runner')

            # Execute Runner
            runner_result = runner.execute(test_path=test_path)

            # Record metrics
            if runner_result.execution_time_ms > 0:
                self.metrics.record_agent_activity(
                    agent='runner',
                    duration_ms=runner_result.execution_time_ms,
                    cost_usd=runner_result.cost_usd,
                    model=routing_decision.model
                )

            # Prepare result
            return AgentResult(
                success=runner_result.success,
                data={
                    'action': 'test_executed',
                    'test_path': test_path,
                    'agent': routing_decision.agent,
                    'model': routing_decision.model,
                    'runner_result': runner_result.data
                },
                error=runner_result.error,
                cost_usd=runner_result.cost_usd,
                metadata={
                    'routing_decision': routing_decision.__dict__,
                    'runner_metadata': runner_result.metadata
                }
            )

        except Exception as e:
            logger.exception(f"Failed to dispatch to Runner: {e}")
            return AgentResult(
                success=False,
                error=f"Failed to execute test: {str(e)}",
                metadata={'routing_decision': routing_decision.__dict__}
            )

    def _handle_fix_failure(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """
        Handle fix_failure intent - fixes bug using Medic.

        Args:
            slots: Parsed intent slots
            context: Optional context (should contain test_path and error_info)

        Returns:
            AgentResult with bug fix outcome
        """
        task_id = slots.get('raw_value', '')

        # Get test path and error from context
        test_path = context.get('test_path', 'tests/unknown.spec.ts') if context else 'tests/unknown.spec.ts'
        error_info = context.get('error_info', {}) if context else {}

        # Route to Medic agent
        routing_decision = self.router.route(
            task_type='fix_bug',
            task_description=f"Fix failed task {task_id}"
        )

        logger.info(f"Routing to {routing_decision.agent} with {routing_decision.model}")

        # Dispatch to Medic
        try:
            medic = self._get_agent('medic')

            # Execute Medic
            medic_result = medic.execute(
                test_path=test_path,
                error_info=error_info
            )

            # Prepare result
            return AgentResult(
                success=medic_result.success,
                data={
                    'action': 'bug_fixed',
                    'task_id': task_id,
                    'test_path': test_path,
                    'agent': routing_decision.agent,
                    'model': routing_decision.model,
                    'medic_result': medic_result.data
                },
                error=medic_result.error,
                cost_usd=medic_result.cost_usd,
                metadata={
                    'routing_decision': routing_decision.__dict__,
                    'medic_metadata': medic_result.metadata
                }
            )

        except Exception as e:
            logger.exception(f"Failed to dispatch to Medic: {e}")
            return AgentResult(
                success=False,
                error=f"Failed to fix bug: {str(e)}",
                metadata={'routing_decision': routing_decision.__dict__}
            )

    def _handle_validate(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """
        Handle validate intent - validates test using Gemini.

        Args:
            slots: Parsed intent slots
            context: Optional context

        Returns:
            AgentResult with validation outcome
        """
        test_path = slots.get('raw_value', '')

        # Route to Gemini agent
        routing_decision = self.router.route(
            task_type='validate',
            task_description=test_path,
            test_path=test_path
        )

        logger.info(f"Routing to {routing_decision.agent} with {routing_decision.model}")

        # Dispatch to Gemini
        try:
            gemini = self._get_agent('gemini')

            # Execute Gemini
            gemini_result = gemini.execute(test_path=test_path)

            # Prepare result
            return AgentResult(
                success=gemini_result.success,
                data={
                    'action': 'test_validated',
                    'test_path': test_path,
                    'agent': routing_decision.agent,
                    'model': routing_decision.model,
                    'gemini_result': gemini_result.data
                },
                error=gemini_result.error,
                cost_usd=gemini_result.cost_usd,
                metadata={
                    'routing_decision': routing_decision.__dict__,
                    'gemini_metadata': gemini_result.metadata
                }
            )

        except Exception as e:
            logger.exception(f"Failed to dispatch to Gemini: {e}")
            return AgentResult(
                success=False,
                error=f"Failed to validate test: {str(e)}",
                metadata={'routing_decision': routing_decision.__dict__}
            )

    def _handle_status(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """
        Handle status inquiry - returns session and budget stats.

        Args:
            slots: Parsed intent slots
            context: Optional context

        Returns:
            AgentResult with status information
        """
        task_id = slots.get('raw_value', '')

        # Get budget status
        budget_status = self.check_budget()

        # Get session stats
        total_tasks = len(self.task_history)
        successful_tasks = sum(1 for t in self.task_history if t['success'])

        return AgentResult(
            success=True,
            data={
                'action': 'status_report',
                'task_id': task_id,
                'session_cost': self.session_cost,
                'total_tasks': total_tasks,
                'successful_tasks': successful_tasks,
                'budget_status': budget_status,
                'task_history': self.task_history[-5:],  # Last 5 tasks
                'message': f"Session cost: ${self.session_cost:.2f} | Tasks: {successful_tasks}/{total_tasks} successful"
            }
        )

    def _handle_full_pipeline(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """
        Handle full_pipeline intent - complete end-to-end workflow.

        Workflow:
        1. Scribe writes test (with self-validation)
        2. Critic pre-validates
        3. Runner executes test
        4. If test fails → Medic fixes → retry Runner
        5. Gemini validates with browser
        6. Return aggregated results

        Args:
            slots: Parsed intent slots
            context: Optional context

        Returns:
            AgentResult with complete pipeline outcome
        """
        feature = slots.get('raw_value', '')
        pipeline_results = []
        total_cost = 0.0
        lifecycle = get_lifecycle()

        # Generate task ID and track it
        task_id = f"pipeline_{int(time.time())}"
        lifecycle.add_active_task(task_id, agent='kaya', feature=feature)

        logger.info(f"Starting full pipeline for: {feature}")

        try:

            # Check for shutdown before each step
            if lifecycle.is_shutting_down():
                lifecycle.remove_active_task(task_id)
                return self._aggregate_pipeline_results(
                    'shutdown_interrupted',
                    pipeline_results,
                    total_cost,
                    error="Pipeline interrupted by shutdown"
                )

            # Step 1: Scribe writes test
            logger.info("Step 1: Scribe writes test")
            scribe_result = self._handle_create_test(slots, context)
            pipeline_results.append(('scribe', scribe_result))
            total_cost += scribe_result.cost_usd

            if not scribe_result.success:
                return self._aggregate_pipeline_results(
                    'scribe_failed',
                    pipeline_results,
                    total_cost,
                    error="Scribe failed to write test"
                )

            test_path = scribe_result.data['test_path']
            logger.info(f"Test written: {test_path}")

            # Step 2: Critic pre-validates
            logger.info("Step 2: Critic pre-validates")
            try:
                critic = self._get_agent('critic')
                critic_result = critic.execute(test_path=test_path)
                pipeline_results.append(('critic', critic_result))
                total_cost += critic_result.cost_usd

                # Record critic decision metrics
                decision = 'rejected' if not critic_result.success else 'approved'
                reason = critic_result.error if not critic_result.success else None
                self.metrics.record_critic_decision(test_path, decision, reason)

                # Record critic agent activity
                if critic_result.execution_time_ms > 0:
                    self.metrics.record_agent_activity(
                        agent='critic',
                        duration_ms=critic_result.execution_time_ms,
                        cost_usd=critic_result.cost_usd,
                        model='haiku'  # Critic always uses Haiku
                    )

                if not critic_result.success:
                    # Get fallback action from router
                    fallback = self.router.get_fallback('critic_fail')
                    logger.warning(f"Critic rejected test, fallback: {fallback}")

                    return self._aggregate_pipeline_results(
                        'critic_rejected',
                        pipeline_results,
                        total_cost,
                        error="Critic rejected test - quality issues detected"
                    )

                logger.info("Critic approved test")

            except Exception as e:
                logger.warning(f"Critic failed: {e}, continuing anyway")

            # Step 3: Runner executes test
            logger.info("Step 3: Runner executes test")
            runner_slots = {'raw_value': test_path}
            runner_result = self._handle_run_test(runner_slots, context)
            pipeline_results.append(('runner', runner_result))
            total_cost += runner_result.cost_usd

            # Step 4: If test fails, dispatch Medic
            max_retries = self.router.get_max_retries()
            retry_count = 0

            while not runner_result.success and retry_count < max_retries and not lifecycle.is_shutting_down():
                logger.info(f"Step 4: Test failed, dispatching Medic (retry {retry_count + 1}/{max_retries})")

                medic_context = {
                    'test_path': test_path,
                    'error_info': runner_result.data.get('runner_result', {}).get('errors', [])
                }

                medic_slots = {'raw_value': f'task_{retry_count}'}
                medic_result = self._handle_fix_failure(medic_slots, medic_context)
                pipeline_results.append(('medic', medic_result))
                total_cost += medic_result.cost_usd

                if not medic_result.success:
                    fallback = self.router.get_fallback('medic_escalation')
                    logger.error(f"Medic failed, fallback: {fallback}")
                    break

                # Retry runner
                logger.info("Re-running test after Medic fix")
                runner_result = self._handle_run_test(runner_slots, context)
                pipeline_results.append(('runner_retry', runner_result))
                total_cost += runner_result.cost_usd

                retry_count += 1

            # If still failing after retries, escalate
            if not runner_result.success:
                return self._aggregate_pipeline_results(
                    'execution_failed',
                    pipeline_results,
                    total_cost,
                    error=f"Test execution failed after {retry_count} Medic attempts"
                )

            logger.info("Test execution successful")

            # Step 5: Gemini validates
            logger.info("Step 5: Gemini validates in real browser")
            validate_slots = {'raw_value': test_path}
            gemini_result = self._handle_validate(validate_slots, context)
            pipeline_results.append(('gemini', gemini_result))
            total_cost += gemini_result.cost_usd

            # Record validation result metrics
            self.metrics.record_validation_result(
                test_id=test_path,
                passed=gemini_result.success,
                duration_ms=gemini_result.execution_time_ms,
                cost_usd=gemini_result.cost_usd
            )

            # Record Gemini agent activity
            if gemini_result.execution_time_ms > 0:
                self.metrics.record_agent_activity(
                    agent='gemini',
                    duration_ms=gemini_result.execution_time_ms,
                    cost_usd=gemini_result.cost_usd,
                    model='gemini-2.5-pro'
                )

            # Record feature completion metrics (end-to-end pipeline)
            pipeline_duration = int((time.time() - lifecycle.get_task_start_time(task_id)) * 1000) if task_id in lifecycle.active_tasks else 0
            self.metrics.record_feature_completion(
                feature=feature,
                total_cost=total_cost,
                duration_ms=pipeline_duration,
                retry_count=retry_count,
                task_id=task_id
            )

            # Final result
            pipeline_result = self._aggregate_pipeline_results(
                'completed',
                pipeline_results,
                total_cost,
                success=gemini_result.success
            )

            # Remove task from active tracking
            lifecycle.remove_active_task(task_id)
            return pipeline_result

        except Exception as e:
            logger.exception(f"Pipeline error: {e}")
            lifecycle.remove_active_task(task_id)
            return self._aggregate_pipeline_results(
                'pipeline_error',
                pipeline_results,
                total_cost,
                error=f"Pipeline error: {str(e)}"
            )
        finally:
            # Ensure task is removed even if exception occurs
            if task_id in lifecycle.active_tasks:
                lifecycle.remove_active_task(task_id)

    def _aggregate_pipeline_results(
        self,
        stage: str,
        results: List[Tuple[str, AgentResult]],
        total_cost: float,
        success: bool = False,
        error: Optional[str] = None
    ) -> AgentResult:
        """
        Aggregate results from multi-agent pipeline.

        Args:
            stage: Final stage reached
            results: List of (agent_name, AgentResult) tuples
            total_cost: Total cost across all agents
            success: Overall success status
            error: Error message if failed

        Returns:
            Aggregated AgentResult
        """
        # Build summary
        agent_summary = {}
        for agent_name, result in results:
            agent_summary[agent_name] = {
                'success': result.success,
                'cost': result.cost_usd,
                'execution_time_ms': result.execution_time_ms,
                'error': result.error
            }

        return AgentResult(
            success=success,
            data={
                'action': 'full_pipeline',
                'stage': stage,
                'agent_summary': agent_summary,
                'total_agents_used': len(results),
                'message': self._build_pipeline_message(stage, results)
            },
            error=error,
            cost_usd=total_cost,
            metadata={
                'pipeline_results': [
                    {
                        'agent': agent_name,
                        'data': result.data,
                        'metadata': result.metadata
                    }
                    for agent_name, result in results
                ]
            }
        )

    def _build_pipeline_message(self, stage: str, results: List[Tuple[str, AgentResult]]) -> str:
        """
        Build human-readable pipeline status message.

        Args:
            stage: Current stage
            results: Pipeline results

        Returns:
            Status message string
        """
        agent_names = [name for name, _ in results]

        if stage == 'completed':
            return f"Pipeline completed successfully: {' → '.join(agent_names)}"
        elif stage == 'scribe_failed':
            return "Pipeline failed at Scribe (test writing)"
        elif stage == 'critic_rejected':
            return "Pipeline stopped: Critic rejected test quality"
        elif stage == 'execution_failed':
            return f"Pipeline failed: Test execution failed after {len([n for n in agent_names if n == 'medic'])} Medic attempts"
        elif stage == 'pipeline_error':
            return "Pipeline encountered unexpected error"
        else:
            return f"Pipeline in progress: {' → '.join(agent_names)}"

    def check_budget(self, budget_type: str = 'per_session') -> Dict[str, Any]:
        """
        Check current budget status.

        Args:
            budget_type: 'per_session' or 'daily'

        Returns:
            Budget status dict
        """
        return self.router.check_budget(self.session_cost, budget_type)

    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive session statistics.

        Returns:
            Dict with session stats including costs, success rates, and agent usage
        """
        total_tasks = len(self.task_history)
        successful_tasks = sum(1 for t in self.task_history if t['success'])

        # Calculate per-intent stats
        intent_stats = {}
        for task in self.task_history:
            intent = task['intent']
            if intent not in intent_stats:
                intent_stats[intent] = {'total': 0, 'success': 0, 'cost': 0.0}

            intent_stats[intent]['total'] += 1
            if task['success']:
                intent_stats[intent]['success'] += 1
            intent_stats[intent]['cost'] += task['cost']

        return {
            'session_cost': self.session_cost,
            'total_tasks': total_tasks,
            'successful_tasks': successful_tasks,
            'success_rate': successful_tasks / total_tasks if total_tasks > 0 else 0.0,
            'intent_stats': intent_stats,
            'budget_status': self.check_budget(),
            'task_history': self.task_history
        }


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
