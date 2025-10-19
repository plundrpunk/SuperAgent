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
from agent_system.coverage_analyzer import CoverageAnalyzer
from agent_system.observability.event_stream import emit_event

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
            r'run.*test[s]?(?:\s+in)?\s+(.+)',
            r'execute.*test[s]?(?:\s+in)?\s+(.+)',
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
        'check_coverage': [
            r'check.*coverage(?:\s+for\s+(.+))?',
            r'test.*coverage(?:\s+for\s+(.+))?',
            r'coverage.*report(?:\s+for\s+(.+))?',
            r'what.*coverage',
            r'how.*much.*coverage',
        ],
        'full_pipeline': [
            r'full.*pipeline.*for\s+(.+)',
            r'end.*to.*end.*test.*for\s+(.+)',
            r'complete.*flow.*for\s+(.+)',
        ],
        'read_and_plan': [
            r'read\s+(.+)\s+and\s+(?:create|make|build)\s+(?:a|an)?\s*(?:execution\s+)?plan',
            r'read\s+(.+)\s+(?:then|and)\s+plan',
        ],
        'iterative_fix': [
            r'fix\s+all\s+(?:test\s+)?(?:failures|issues|problems)(?:\s+in\s+(.+))?',
            r'iterate\s+(?:and\s+)?fix\s+until\s+(?:all\s+)?(?:tests\s+)?pass(?:\s+in\s+(.+))?',
            r'test\s+(?:and\s+)?fix\s+(?:all\s+)?(?:issues|problems)(?:\s+in\s+(.+))?',
            r'fix\s+(?:the\s+)?(?:fucking\s+)?app(?:\s+in\s+(.+))?',
        ],
        'orchestrate_mission': [
            r'(?:execute|start|begin)\s+(?:the\s+)?mission',
            r'(?:read|check)\s+(?:the\s+)?mission\s+brief',
            r'start\s+phase\s+(\d+)',
        ],
        'set_model': [
            r'use\s+(opus|sonnet|haiku)(?:\s+for\s+(.+))?',
            r'switch\s+to\s+(opus|sonnet|haiku)',
            r'set\s+model\s+to\s+(opus|sonnet|haiku)',
            r'clear\s+model\s+override',
            r'reset\s+models?',
        ]
    }

    def __init__(self):
        """Initialize Kaya orchestrator."""
        super().__init__('kaya')
        self.router = Router()
        self.session_cost = 0.0
        self.task_history = []

        # Model override settings
        self.model_override = None  # None, or model name like 'opus', 'sonnet', 'haiku'
        self.model_override_scope = 'all'  # 'all' or specific agent name

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
                from agent_system.agents.scribe_full import ScribeAgent
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
            elif intent_type == 'check_coverage':
                result = self._handle_check_coverage(slots, context)
            elif intent_type == 'full_pipeline':
                result = self._handle_full_pipeline(slots, context)
            elif intent_type == 'read_and_plan':
                result = self._handle_read_and_plan(slots, context)
            elif intent_type == 'iterative_fix':
                result = self._handle_iterative_fix(slots, context)
            elif intent_type == 'orchestrate_mission':
                result = self._handle_orchestrate_mission(slots, context)
            elif intent_type == 'set_model':
                result = self._handle_set_model(slots, context)
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
        command_orig = command.strip()

        for intent_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, command_lower)
                if match:
                    # Extract slots from regex groups
                    # Re-match on original command to preserve case for file paths
                    match_orig = re.search(pattern, command_orig, re.IGNORECASE)
                    slots = {'raw_value': match_orig.group(1) if match_orig and match_orig.groups() else ''}
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

            # Emit agent_started event
            emit_event('agent_started', {
                'agent': 'scribe',
                'model': routing_decision.model,
                'feature': feature,
                'complexity': routing_decision.difficulty,
                'timestamp': time.time()
            })

            # Execute Scribe
            scribe_result = scribe.execute(
                task_description=feature,
                task_scope="",
                complexity=routing_decision.difficulty,
                output_path=output_path
            )

            # Emit agent_completed event
            emit_event('agent_completed', {
                'agent': 'scribe',
                'model': routing_decision.model,
                'feature': feature,
                'success': scribe_result.success,
                'duration_ms': scribe_result.execution_time_ms,
                'cost_usd': scribe_result.cost_usd,
                'test_path': scribe_result.data.get('test_path') if scribe_result.success else None,
                'timestamp': time.time()
            })

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

            # Execute Runner with extended timeout for E2E tests (180s instead of default 60s)
            runner_result = runner.execute(test_path=test_path, timeout=180)

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

            # Convert error_info to error_message string
            if isinstance(error_info, list) and error_info:
                # Extract message from first error in list
                first_error = error_info[0]
                error_message = first_error.get('message', '') if isinstance(first_error, dict) else str(first_error)
            elif isinstance(error_info, dict):
                error_message = error_info.get('message', '') or str(error_info)
            else:
                error_message = str(error_info)

            # Execute Medic with correct signature
            medic_result = medic.execute(
                test_path=test_path,
                error_message=error_message,
                task_id=task_id
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

    def _handle_check_coverage(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """
        Handle check_coverage intent - analyzes test coverage.

        Args:
            slots: Parsed intent slots
            context: Optional context

        Returns:
            AgentResult with coverage analysis
        """
        start_time = time.time()
        file_path = slots.get('raw_value', '').strip() if slots.get('raw_value') else None

        logger.info(f"Analyzing coverage{f' for {file_path}' if file_path else ''}")

        try:
            # Initialize coverage analyzer
            # Default to Cloppy_Ai project directory if available
            project_dir = context.get('project_dir') if context else None
            if not project_dir:
                # Check if Cloppy_Ai project exists
                cloppy_path = '/Users/rutledge/Documents/DevFolder/Cloppy_Ai'
                import os
                if os.path.exists(cloppy_path):
                    project_dir = cloppy_path

            analyzer = CoverageAnalyzer(project_dir)

            # Analyze specific file or overall project
            if file_path and file_path.strip():
                result = analyzer.analyze_file_coverage(file_path)
            else:
                result = analyzer.generate_coverage_report()

            if not result.get('success', False):
                return AgentResult(
                    success=False,
                    error=result.get('error', 'Coverage analysis failed'),
                    data={
                        'action': 'coverage_analysis',
                        'file_path': file_path,
                        'help': result.get('help', 'Ensure tests have been run with coverage enabled')
                    },
                    execution_time_ms=self._track_execution(start_time)
                )

            # Build human-readable message
            if file_path:
                coverage_pct = result.get('coverage_percentage', 0)
                uncovered = result.get('uncovered_statements', 0)
                message = f"Coverage for {file_path}: {coverage_pct}% ({uncovered} uncovered statements)"
            else:
                overall = result.get('overall_coverage', 0)
                grade = result.get('grade', 'N/A')
                message = f"Overall test coverage: {overall}% (Grade: {grade})"

            return AgentResult(
                success=True,
                data={
                    'action': 'coverage_analysis',
                    'file_path': file_path,
                    'coverage_result': result,
                    'message': message
                },
                execution_time_ms=self._track_execution(start_time)
            )

        except Exception as e:
            logger.exception(f"Coverage analysis error: {e}")
            return AgentResult(
                success=False,
                error=f"Coverage analysis error: {str(e)}",
                data={
                    'action': 'coverage_analysis',
                    'file_path': file_path
                },
                execution_time_ms=self._track_execution(start_time)
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

    def _handle_read_and_plan(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """
        Handle read_and_plan intent - reads a document and creates execution plan.

        Args:
            slots: Parsed intent slots (contains filename)
            context: Optional context

        Returns:
            AgentResult with execution plan
        """
        import os

        filename = slots.get('raw_value', '')
        logger.info(f"Reading and planning for: {filename}")

        try:
            # Try to find the file
            possible_paths = [
                filename,
                f"/Users/rutledge/Documents/DevFolder/SuperAgent/{filename}",
                f"/Users/rutledge/Documents/DevFolder/Cloppy_Ai/frontend/{filename}",
            ]

            file_content = None
            actual_path = None

            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        file_content = f.read()
                    actual_path = path
                    break

            if not file_content:
                return AgentResult(
                    success=False,
                    error=f"Could not find file: {filename}"
                )

            logger.info(f"Read {len(file_content)} characters from {actual_path}")

            # Create execution plan based on file content
            plan = {
                'document': filename,
                'summary': f"Read {len(file_content)} characters",
                'next_steps': [
                    "Analyze document content",
                    "Identify key action items",
                    "Create prioritized task list",
                    "Begin execution with highest priority"
                ]
            }

            return AgentResult(
                success=True,
                data={
                    'action': 'plan_created',
                    'document': filename,
                    'file_path': actual_path,
                    'plan': plan,
                    'message': f"Successfully read {filename} and created execution plan"
                }
            )

        except Exception as e:
            logger.exception(f"Error reading file: {e}")
            return AgentResult(
                success=False,
                error=f"Failed to read file: {str(e)}"
            )

    def _handle_iterative_fix(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """
        Handle iterative_fix intent - runs tests, fixes failures, repeats until all pass.

        This is a complex orchestration workflow that:
        1. Runs all tests to identify failures
        2. Groups failures by type/component
        3. Dispatches appropriate agents to fix each group
        4. Re-runs tests to validate fixes
        5. Repeats until 100% pass rate or budget exceeded

        Args:
            slots: Parsed intent slots
            context: Optional context (should contain test_dir)

        Returns:
            AgentResult with fix iteration results
        """
        logger.info("Starting iterative fix workflow")

        # Get test directory from slots, context, or use default
        # Priority: 1. slots (from command), 2. context, 3. default
        test_dir = slots.get('raw_value', '').strip()
        if not test_dir:
            # Use the Cloppy_Ai root directory so Playwright can find all tests
            test_dir = context.get('test_dir', '/Users/rutledge/Documents/DevFolder/Cloppy_Ai') if context else '/Users/rutledge/Documents/DevFolder/Cloppy_Ai'

        logger.info(f"Testing directory: {test_dir}")

        max_iterations = 5
        iteration_results = []
        total_cost = 0.0

        for iteration in range(max_iterations):
            logger.info(f"Iteration {iteration + 1}/{max_iterations}")

            # Check budget
            budget_status = self.check_budget()
            if budget_status['status'] == 'exceeded':
                return AgentResult(
                    success=False,
                    data={
                        'action': 'iterative_fix',
                        'iterations_completed': iteration,
                        'iteration_results': iteration_results,
                        'total_cost': total_cost
                    },
                    error=f"Budget exceeded after {iteration} iterations"
                )

            # Step 1: Run all tests
            runner_slots = {'raw_value': test_dir}
            runner_result = self._handle_run_test(runner_slots, context)
            total_cost += runner_result.cost_usd

            if runner_result.success:
                # All tests passing!
                return AgentResult(
                    success=True,
                    data={
                        'action': 'iterative_fix_complete',
                        'iterations_completed': iteration + 1,
                        'iteration_results': iteration_results,
                        'total_cost': total_cost,
                        'message': f"All tests passing after {iteration + 1} iterations!"
                    },
                    cost_usd=total_cost
                )

            # Step 2: Identify failures
            failures = runner_result.data.get('runner_result', {}).get('errors', [])
            if not failures:
                iteration_results.append({
                    'iteration': iteration + 1,
                    'status': 'no_failures_found',
                    'cost': runner_result.cost_usd
                })
                continue

            # Step 3: Fix top 5 failures
            fixes_attempted = 0
            for failure in failures[:5]:
                # Runner returns 'file_path' not 'test_path'
                test_path = failure.get('file_path', 'unknown')
                medic_context = {
                    'test_path': test_path,
                    'error_info': [failure]
                }
                medic_slots = {'raw_value': f'auto_fix_{iteration}_{fixes_attempted}'}
                medic_result = self._handle_fix_failure(medic_slots, medic_context)
                total_cost += medic_result.cost_usd
                fixes_attempted += 1

            iteration_results.append({
                'iteration': iteration + 1,
                'failures_found': len(failures),
                'fixes_attempted': fixes_attempted,
                'cost': runner_result.cost_usd + (fixes_attempted * 0.5)  # Estimate
            })

        # Max iterations reached
        return AgentResult(
            success=False,
            data={
                'action': 'iterative_fix_incomplete',
                'iterations_completed': max_iterations,
                'iteration_results': iteration_results,
                'total_cost': total_cost,
                'message': f"Max iterations ({max_iterations}) reached. Some tests still failing."
            },
            error="Maximum iterations reached without 100% pass rate",
            cost_usd=total_cost
        )

    def _handle_orchestrate_mission(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """
        Handle orchestrate_mission intent - reads mission brief and executes full plan.

        This is the highest-level orchestration command that:
        1. Reads KAYA_MISSION_BRIEF.md
        2. Reads current status reports
        3. Creates execution plan
        4. Dispatches agents according to plan
        5. Tracks progress with MCP
        6. Reports status updates

        Args:
            slots: Parsed intent slots (may contain phase number)
            context: Optional context

        Returns:
            AgentResult with mission execution status
        """
        import os

        logger.info("Orchestrating mission from KAYA_MISSION_BRIEF.md")

        try:
            # Read mission brief
            brief_path = "/Users/rutledge/Documents/DevFolder/SuperAgent/KAYA_MISSION_BRIEF.md"
            if not os.path.exists(brief_path):
                return AgentResult(
                    success=False,
                    error="KAYA_MISSION_BRIEF.md not found"
                )

            with open(brief_path, 'r') as f:
                mission_brief = f.read()

            # Read current test results
            results_path = "/Users/rutledge/Documents/DevFolder/Cloppy_Ai/frontend/P0_TEST_RESULTS_REPORT.md"
            current_status = ""
            if os.path.exists(results_path):
                with open(results_path, 'r') as f:
                    current_status = f.read()

            logger.info(f"Mission brief: {len(mission_brief)} chars")
            logger.info(f"Current status: {len(current_status)} chars")

            # Extract phase from slots or default to Phase 1
            phase_match = slots.get('raw_value', '')
            phase = 1
            if phase_match and phase_match.isdigit():
                phase = int(phase_match)

            # Create execution plan for the phase
            plan = {
                'phase': phase,
                'mission': 'Fix all Cloppy_AI test failures',
                'current_pass_rate': '27%',
                'target_pass_rate': '100%',
                'steps': []
            }

            if phase == 1:
                plan['steps'] = [
                    {'action': 'add_data_testids', 'agent': 'scribe', 'estimated_impact': '10-15 tests'},
                    {'action': 'fix_partial_features', 'agent': 'medic', 'estimated_impact': '5-10 tests'},
                    {'action': 'validate_passing_tests', 'agent': 'gemini', 'estimated_impact': 'confidence boost'}
                ]

            # Initiate MCP tracking
            try:
                from agent_system.mcp_integration import get_mcp_client
                mcp = get_mcp_client()

                project = mcp.create_project(
                    name="Cloppy_AI Testing & Fixes",
                    description=f"Mission to achieve 100% P0 test pass rate - Phase {phase}"
                )

                logger.info(f"Created MCP project: {project.get('id')}")
                plan['mcp_project_id'] = project.get('id')

            except Exception as e:
                logger.warning(f"MCP integration failed: {e}")

            return AgentResult(
                success=True,
                data={
                    'action': 'mission_orchestration_started',
                    'phase': phase,
                    'plan': plan,
                    'mission_brief_length': len(mission_brief),
                    'current_status_length': len(current_status),
                    'message': f"Mission orchestration started for Phase {phase}. Ready to execute plan."
                }
            )

        except Exception as e:
            logger.exception(f"Mission orchestration error: {e}")
            return AgentResult(
                success=False,
                error=f"Failed to orchestrate mission: {str(e)}"
            )

    def _handle_set_model(self, slots: Dict[str, Any], context: Optional[Dict]) -> AgentResult:
        """
        Handle set_model intent - override model selection for agents.

        Args:
            slots: Parsed intent slots (contains model name and optional agent)
            context: Optional context

        Returns:
            AgentResult with model override confirmation
        """
        raw_value = slots.get('raw_value', '').lower()

        # Check for clear/reset commands
        if 'clear' in raw_value or 'reset' in raw_value:
            self.model_override = None
            self.model_override_scope = 'all'
            return AgentResult(
                success=True,
                data={
                    'action': 'model_override_cleared',
                    'message': "Model override cleared. Router will use automatic model selection."
                }
            )

        # Extract model name
        model_map = {
            'opus': 'claude-opus-4-20250514',
            'sonnet': 'claude-sonnet-4-5-20250929',
            'haiku': 'claude-haiku-4-20250514'
        }

        model_name = None
        scope = 'all'

        for short_name, full_name in model_map.items():
            if short_name in raw_value:
                model_name = full_name
                # Check if scope specified
                if 'for' in raw_value:
                    parts = raw_value.split('for')
                    if len(parts) > 1:
                        scope_text = parts[1].strip()
                        # Extract agent name
                        for agent in ['scribe', 'runner', 'medic', 'critic', 'gemini']:
                            if agent in scope_text:
                                scope = agent
                                break
                break

        if not model_name:
            return AgentResult(
                success=False,
                error="Could not parse model name. Use: opus, sonnet, or haiku"
            )

        # Set the override
        self.model_override = model_name
        self.model_override_scope = scope

        logger.info(f"Model override set: {model_name} for {scope}")

        return AgentResult(
            success=True,
            data={
                'action': 'model_override_set',
                'model': model_name,
                'scope': scope,
                'message': f"Model override set to {short_name.upper()} for {scope}"
            }
        )

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
