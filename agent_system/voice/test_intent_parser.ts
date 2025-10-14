/**
 * Test suite for Voice Intent Parser
 * Demonstrates intent parsing, slot extraction, and clarification handling
 */

import VoiceOrchestrator, { VoiceIntent } from './orchestrator';

// Test cases for intent parsing
const testCases = [
  // CREATE_TEST intent
  {
    command: 'Kaya, write a test for user login',
    expected: {
      type: 'create_test',
      slots: { feature: 'user login' },
      confidence: 0.9
    }
  },
  {
    command: 'create a test for checkout happy path',
    expected: {
      type: 'create_test',
      slots: { feature: 'checkout happy path' },
      confidence: 0.9
    }
  },
  {
    command: 'generate a test about password reset',
    expected: {
      type: 'create_test',
      slots: { feature: 'password reset' },
      confidence: 0.9
    }
  },

  // RUN_TEST intent
  {
    command: 'Kaya, run tests/cart.spec.ts',
    expected: {
      type: 'run_test',
      slots: { test_path: 'tests/cart.spec.ts' },
      confidence: 0.9
    }
  },
  {
    command: 'execute the login test',
    expected: {
      type: 'run_test',
      slots: { test_path: 'login test' },
      confidence: 0.9
    }
  },
  {
    command: 'run all authentication tests',
    expected: {
      type: 'run_test',
      slots: { test_path: 'authentication' },
      confidence: 0.9
    }
  },

  // FIX_FAILURE intent
  {
    command: 'Kaya, fix task t_abc123',
    expected: {
      type: 'fix_failure',
      slots: { task_id: 't_abc123' },
      confidence: 0.9
    }
  },
  {
    command: 'patch task t_xyz789 and retry',
    expected: {
      type: 'fix_failure',
      slots: { task_id: 't_xyz789' },
      confidence: 0.9
    }
  },
  {
    command: 'repair the failed checkout test',
    expected: {
      type: 'fix_failure',
      slots: { task_id: 'checkout' },
      confidence: 0.9
    }
  },

  // VALIDATE intent
  {
    command: 'Kaya, validate payment flow - critical',
    expected: {
      type: 'validate',
      slots: { test_path: 'payment flow', high_priority: 'true' },
      confidence: 0.9
    }
  },
  {
    command: 'verify the login test',
    expected: {
      type: 'validate',
      slots: { test_path: 'login test' },
      confidence: 0.9
    }
  },
  {
    command: 'validate checkout with Gemini',
    expected: {
      type: 'validate',
      slots: { test_path: 'checkout' },
      confidence: 0.9
    }
  },

  // STATUS intent
  {
    command: 'Kaya, what\'s the status of task t_123?',
    expected: {
      type: 'status',
      slots: { task_id: 't_123' },
      confidence: 0.9
    }
  },
  {
    command: 'show status of task t_456',
    expected: {
      type: 'status',
      slots: { task_id: 't_456' },
      confidence: 0.9
    }
  },
  {
    command: 'what is happening with task t_789',
    expected: {
      type: 'status',
      slots: { task_id: 't_789' },
      confidence: 0.9
    }
  },

  // Ambiguous commands requiring clarification
  {
    command: 'Kaya, test something',
    expected: {
      type: 'unknown',
      needs_clarification: true
    }
  },
  {
    command: 'fix it',
    expected: {
      type: 'unknown',
      needs_clarification: true
    }
  },
  {
    command: 'status please',
    expected: {
      type: 'unknown',
      needs_clarification: true
    }
  }
];

/**
 * Run intent parser tests (without connecting to OpenAI API)
 */
async function testIntentParser() {
  console.log('========================================');
  console.log('Voice Intent Parser Test Suite');
  console.log('========================================\n');

  // We need to access private method, so we'll use a workaround
  // In production, you'd expose a public parseIntent method or use proper testing
  const orchestrator = new VoiceOrchestrator({
    apiKey: 'dummy-key-for-testing'
  });

  let passed = 0;
  let failed = 0;

  for (const testCase of testCases) {
    try {
      // Access private parseVoiceIntent method via type assertion
      const parseIntent = (orchestrator as any).parseVoiceIntent.bind(orchestrator);
      const result: VoiceIntent = parseIntent(testCase.command);

      // Check if intent type matches
      const typeMatch = result.type === testCase.expected.type;

      // Check if slots match
      let slotsMatch = true;
      if (testCase.expected.slots) {
        for (const [key, value] of Object.entries(testCase.expected.slots)) {
          if (result.slots[key] !== value) {
            slotsMatch = false;
            break;
          }
        }
      }

      // Check clarification
      const clarificationMatch = testCase.expected.needs_clarification
        ? result.needs_clarification === true
        : true;

      const success = typeMatch && slotsMatch && clarificationMatch;

      if (success) {
        console.log(`✓ PASS: "${testCase.command}"`);
        console.log(`  → Intent: ${result.type}`);
        if (Object.keys(result.slots).length > 0) {
          console.log(`  → Slots:`, result.slots);
        }
        if (result.needs_clarification) {
          console.log(`  → Needs clarification: ${result.clarification_prompt}`);
        }
        passed++;
      } else {
        console.log(`✗ FAIL: "${testCase.command}"`);
        console.log(`  Expected:`, testCase.expected);
        console.log(`  Got:`, { type: result.type, slots: result.slots, needs_clarification: result.needs_clarification });
        failed++;
      }
      console.log();

    } catch (error: any) {
      console.log(`✗ ERROR: "${testCase.command}"`);
      console.log(`  ${error.message}\n`);
      failed++;
    }
  }

  console.log('========================================');
  console.log('Test Results');
  console.log('========================================');
  console.log(`Total: ${testCases.length}`);
  console.log(`Passed: ${passed} (${Math.round(passed / testCases.length * 100)}%)`);
  console.log(`Failed: ${failed} (${Math.round(failed / testCases.length * 100)}%)`);
  console.log();

  return failed === 0;
}

/**
 * Main test runner
 */
async function main() {
  try {
    const success = await testIntentParser();
    process.exit(success ? 0 : 1);
  } catch (error) {
    console.error('Test suite error:', error);
    process.exit(1);
  }
}

// Run tests if executed directly
if (require.main === module) {
  main().catch(console.error);
}

export { testIntentParser };
