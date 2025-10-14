"""
Voice Intent Parser for SuperAgent

Parses transcribed voice commands into structured intents with slot extraction.
Handles ambiguous commands with clarification prompts.

Supported intents:
- create_test: Extract feature name and optional scope
- run_test: Extract test path
- fix_failure: Extract task_id
- validate: Extract test path and optional high_priority flag
- status: Extract task_id
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class VoiceIntent:
    """Structured representation of a parsed voice command."""

    type: str  # Intent type: create_test, run_test, fix_failure, validate, status, unknown
    slots: Dict[str, str] = field(default_factory=dict)  # Extracted slot values
    raw_command: str = ""  # Original command text
    confidence: float = 0.0  # Confidence score (0.0 to 1.0)
    needs_clarification: bool = False  # Whether command is ambiguous
    clarification_prompt: Optional[str] = None  # Prompt for user clarification

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'type': self.type,
            'slots': self.slots,
            'raw_command': self.raw_command,
            'confidence': self.confidence,
            'needs_clarification': self.needs_clarification,
            'clarification_prompt': self.clarification_prompt
        }


class IntentParser:
    """Parser for voice commands with pattern matching and slot extraction."""

    # Intent patterns with regex and slot extraction rules
    # Patterns are ordered by specificity - more specific patterns first
    INTENT_PATTERNS = [
        # RUN_TEST intent patterns (check before CREATE_TEST to avoid conflicts)
        {
            'type': 'run_test',
            'patterns': [
                r'(?:run|execute|start)\s+(?:the\s+)?tests?\s+(.+\.spec\.ts)',
                r'(?:run|execute|start)\s+(.+\.spec\.ts)',
                r'(?:run|execute|start)\s+(tests?/.+)',  # Paths starting with tests/
                r'(?:run|execute|start)\s+(?:all\s+)?(.+?)\s+tests?',
                r'(?:run|execute|start)\s+(?:the\s+)?(.+?)\s+test',
            ],
            'slot_names': ['test_path'],
            'required_slots': ['test_path']
        },
        # STATUS intent patterns (specific task IDs)
        {
            'type': 'status',
            'patterns': [
                r'(?:what\'?s|what is|show|get)\s+(?:the\s+)?status\s+(?:of\s+)?(?:task\s+)?(t_[a-z0-9_]+)',
                r'status\s+(?:of\s+)?(?:task\s+)?(t_[a-z0-9_]+)',
                r'(?:what\'?s|what is)\s+happening\s+(?:with\s+)?(?:task\s+)?(t_[a-z0-9_]+)',
                r'(?:check|show|get)\s+(?:the\s+)?(?:task\s+)?(t_[a-z0-9_]+)\s+status',
            ],
            'slot_names': ['task_id'],
            'required_slots': ['task_id']
        },
        # FIX_FAILURE intent patterns (check before general patterns)
        {
            'type': 'fix_failure',
            'patterns': [
                r'(?:fix|repair|patch)\s+(?:task\s+)?(t_[a-z0-9_]+)',
                r'(?:fix|repair|patch)\s+(?:the\s+)?(?:failed\s+)?(.+?)\s+test',
                r'(?:fix|repair|patch)\s+(?:the\s+)?failure\s+(?:in|for)\s+(.+)',
            ],
            'slot_names': ['task_id'],
            'required_slots': ['task_id']
        },
        # VALIDATE intent patterns
        {
            'type': 'validate',
            'patterns': [
                r'(?:validate|verify|check)\s+(?:the\s+)?(.+?)(?:\s+with\s+gemini)',  # with gemini
                r'(?:validate|verify|check)\s+(?:the\s+)?(.+?)(?:\s+[-–]\s+(critical|important|high[\s-]?priority))',  # priority
                r'(?:validate|verify|check)\s+(?:the\s+)?test\s+(?:for|on)\s+(.+)',  # the test for X
                r'(?:validate|verify|check)\s+(?:the\s+)?(.+)',  # General validate
            ],
            'slot_names': ['test_path', 'high_priority'],
            'required_slots': ['test_path']
        },
        # CREATE_TEST intent patterns (more general, check last)
        {
            'type': 'create_test',
            'patterns': [
                r'(?:write|create|generate|make)\s+(?:a\s+)?test\s+for\s+(.+?)(?:\s+scope[:\s]+(.+))?$',
                r'(?:write|create|generate|make)\s+(?:a\s+)?test\s+(?:about|on)\s+(.+?)(?:\s+scope[:\s]+(.+))?$',
            ],
            'slot_names': ['feature', 'scope'],
            'required_slots': ['feature']
        }
    ]

    # Keywords that indicate intent category (for clarification)
    INTENT_KEYWORDS = {
        'create_test': ['write', 'create', 'generate', 'make', 'test'],
        'run_test': ['run', 'execute', 'start'],
        'fix_failure': ['fix', 'repair', 'patch', 'failure'],
        'validate': ['validate', 'verify', 'check'],
        'status': ['status', 'what', 'show', 'get']
    }

    def __init__(self):
        """Initialize the intent parser."""
        pass

    def parse(self, command: str) -> VoiceIntent:
        """
        Parse a voice command into a structured intent with slots.

        Args:
            command: Raw voice command text

        Returns:
            VoiceIntent object with parsed intent type, slots, and metadata
        """
        # Normalize command
        normalized = command.lower().strip()

        # Remove common prefixes like "kaya" or "hey kaya"
        normalized = re.sub(r'^(?:hey\s+)?kaya[,\s]+', '', normalized, flags=re.IGNORECASE)

        intent = VoiceIntent(
            type='unknown',
            raw_command=command,
            confidence=0.0
        )

        # Try to match patterns for each intent type
        for pattern_group in self.INTENT_PATTERNS:
            matched_intent = self._match_intent_patterns(
                normalized,
                pattern_group['type'],
                pattern_group['patterns'],
                pattern_group['slot_names'],
                pattern_group.get('required_slots', [])
            )

            if matched_intent:
                intent.type = matched_intent['type']
                intent.slots = matched_intent['slots']
                intent.confidence = matched_intent['confidence']

                # Post-process slots for specific intents
                self._post_process_slots(intent)

                return intent

        # No pattern matched - check if clarification is needed
        self._handle_ambiguous_command(normalized, intent)

        return intent

    def _match_intent_patterns(
        self,
        command: str,
        intent_type: str,
        patterns: List[str],
        slot_names: List[str],
        required_slots: List[str]
    ) -> Optional[Dict]:
        """
        Try to match command against intent patterns.

        Args:
            command: Normalized command text
            intent_type: Intent type to match
            patterns: List of regex patterns
            slot_names: Names of slots to extract
            required_slots: Required slot names

        Returns:
            Dict with type, slots, and confidence if matched, None otherwise
        """
        for pattern in patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                slots = {}

                # Extract slots from regex groups
                for i, slot_name in enumerate(slot_names):
                    if i + 1 <= len(match.groups()):
                        value = match.group(i + 1)
                        if value:
                            slots[slot_name] = value.strip()

                # Check if all required slots are present
                has_required = all(
                    slot in slots and slots[slot]
                    for slot in required_slots
                )

                if has_required:
                    return {
                        'type': intent_type,
                        'slots': slots,
                        'confidence': 0.9  # High confidence for pattern match
                    }

        return None

    def _post_process_slots(self, intent: VoiceIntent) -> None:
        """
        Post-process extracted slots for specific intent types.

        Args:
            intent: Intent object to modify in-place
        """
        # VALIDATE intent: Extract high_priority flag and clean test_path
        if intent.type == 'validate':
            priority_keywords = ['critical', 'important', 'high priority', 'high-priority']

            # Check if priority was captured in slot
            if 'high_priority' in intent.slots and intent.slots['high_priority']:
                intent.slots['high_priority'] = 'true'
            # Check in test_path for priority keywords
            elif 'test_path' in intent.slots:
                test_path = intent.slots['test_path'].lower()
                if any(kw in test_path for kw in priority_keywords):
                    intent.slots['high_priority'] = 'true'
                    # Remove priority keyword from test_path
                    for kw in priority_keywords:
                        test_path = re.sub(rf'\s*[-–]\s*{kw}\s*', '', test_path, flags=re.IGNORECASE)
                    intent.slots['test_path'] = test_path.strip()

            # Remove "with gemini" from test_path
            if 'test_path' in intent.slots:
                intent.slots['test_path'] = re.sub(
                    r'\s+with\s+gemini\s*$',
                    '',
                    intent.slots['test_path'],
                    flags=re.IGNORECASE
                ).strip()

        # CREATE_TEST intent: Extract scope if mentioned
        if intent.type == 'create_test':
            feature = intent.slots.get('feature', '')

            # Look for scope indicators
            scope_match = re.search(r'\bscope[:\s]+(.+)', feature, re.IGNORECASE)
            if scope_match:
                intent.slots['scope'] = scope_match.group(1).strip()
                # Remove scope from feature
                intent.slots['feature'] = re.sub(r'\s*\bscope[:\s]+.+', '', feature, flags=re.IGNORECASE).strip()

        # Normalize test paths for RUN_TEST
        if 'test_path' in intent.slots:
            test_path = intent.slots['test_path']
            # If path doesn't end with .spec.ts but looks like a file path, add extension
            if '/' in test_path and not test_path.endswith('.spec.ts'):
                if not test_path.endswith('.ts'):
                    intent.slots['test_path'] = f"{test_path}.spec.ts"

    def _handle_ambiguous_command(self, command: str, intent: VoiceIntent) -> None:
        """
        Check if command is ambiguous and needs clarification.

        Args:
            command: Normalized command text
            intent: Intent object to modify in-place
        """
        # Check for intent keywords without clear action
        has_test_keyword = any(kw in command for kw in ['test', 'testing'])
        has_run_keyword = any(kw in command for kw in ['run', 'execute', 'start'])
        has_fix_keyword = any(kw in command for kw in ['fix', 'repair', 'patch'])
        has_validate_keyword = any(kw in command for kw in ['validate', 'verify', 'check'])
        has_status_keyword = any(kw in command for kw in ['status', 'what', 'show'])
        has_write_keyword = any(kw in command for kw in ['write', 'create', 'generate', 'make'])

        # Command wants to fix something but no task ID
        if has_fix_keyword and not re.search(r't_[a-z0-9_]+', command):
            intent.needs_clarification = True
            intent.clarification_prompt = (
                "I can help fix a failed test. Could you provide the task ID? "
                "It should look like 't_123'."
            )
            return

        # Command wants status but no task ID
        if has_status_keyword and 'status' in command and not re.search(r't_[a-z0-9_]+', command):
            intent.needs_clarification = True
            intent.clarification_prompt = (
                "I can check the status of a task. Could you provide the task ID? "
                "It should look like 't_123'."
            )
            return

        # Command is too vague (very short and no clear action)
        if len(command.split()) <= 2 and not any([
            has_write_keyword, has_run_keyword, has_fix_keyword,
            has_validate_keyword
        ]):
            intent.needs_clarification = True
            intent.clarification_prompt = (
                "I'm not sure what you want me to do. Could you try rephrasing that? "
                "For example, you can say 'write a test for login', 'run tests/cart.spec.ts', "
                "or 'what's the status of task t_123'."
            )
            return

    def parse_batch(self, commands: List[str]) -> List[VoiceIntent]:
        """
        Parse multiple commands in batch.

        Args:
            commands: List of voice command strings

        Returns:
            List of VoiceIntent objects
        """
        return [self.parse(cmd) for cmd in commands]

    def get_supported_intents(self) -> List[str]:
        """
        Get list of supported intent types.

        Returns:
            List of intent type strings
        """
        return ['create_test', 'run_test', 'fix_failure', 'validate', 'status']

    def get_intent_examples(self, intent_type: str) -> List[str]:
        """
        Get example commands for a given intent type.

        Args:
            intent_type: Intent type to get examples for

        Returns:
            List of example command strings
        """
        examples = {
            'create_test': [
                "Kaya, write a test for user login",
                "Create a test for checkout happy path",
                "Generate a test about password reset",
                "Test the shopping cart feature"
            ],
            'run_test': [
                "Kaya, run tests/cart.spec.ts",
                "Execute the login test",
                "Run all authentication tests",
                "Start the checkout test"
            ],
            'fix_failure': [
                "Kaya, fix task t_123",
                "Patch task t_abc456 and retry",
                "Repair the failed checkout test",
                "Fix the failure in login"
            ],
            'validate': [
                "Kaya, validate payment flow - critical",
                "Verify the login test",
                "Validate checkout with Gemini",
                "Check the authentication test"
            ],
            'status': [
                "Kaya, what's the status of task t_123?",
                "Show status of task t_456",
                "What is happening with task t_789",
                "Get task t_abc status"
            ]
        }

        return examples.get(intent_type, [])


# Convenience function for single command parsing
def parse_voice_command(command: str) -> VoiceIntent:
    """
    Parse a single voice command.

    Args:
        command: Raw voice command text

    Returns:
        VoiceIntent object
    """
    parser = IntentParser()
    return parser.parse(command)


# CLI for testing
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python intent_parser.py <command>")
        print("\nExamples:")
        parser = IntentParser()
        for intent_type in parser.get_supported_intents():
            print(f"\n{intent_type}:")
            for example in parser.get_intent_examples(intent_type):
                print(f"  - {example}")
        sys.exit(1)

    command = ' '.join(sys.argv[1:])
    intent = parse_voice_command(command)

    print(json.dumps(intent.to_dict(), indent=2))
