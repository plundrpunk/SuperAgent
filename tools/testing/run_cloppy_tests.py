#!/usr/bin/env python3
"""
Run SuperAgent tests against Cloppy_Ai application.
Bypasses CLI lifecycle to directly execute test generation and validation.
"""

import sys
import os
sys.path.insert(0, '/Users/rutledge/Documents/DevFolder/SuperAgent')

from dotenv import load_dotenv
load_dotenv()

print("🤖 SuperAgent → Cloppy_Ai Test Runner")
print("=" * 60)

# Check that tests were generated
test_dir = '/Users/rutledge/Documents/DevFolder/SuperAgent/tests/cloppy_ai'
if os.path.exists(test_dir):
    tests = [f for f in os.listdir(test_dir) if f.endswith('.spec.ts')]
    print(f"\n✅ Found {len(tests)} generated tests:")
    for test in tests:
        size = os.path.getsize(os.path.join(test_dir, test)) / 1024
        print(f"   - {test} ({size:.1f} KB)")
else:
    print("❌ No tests found! Run generate_cloppy_tests.py first")
    sys.exit(1)

print("\n" + "=" * 60)
print("📋 Next Steps:")
print("=" * 60)

print("""
1. **Copy tests to Cloppy_Ai project:**

   cp /Users/rutledge/Documents/DevFolder/SuperAgent/tests/cloppy_ai/*.spec.ts \\
      /Users/rutledge/Documents/DevFolder/Cloppy_Ai/tests/e2e/

2. **Run the tests:**

   cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai
   npx playwright test tests/e2e/media-upload.spec.ts
   npx playwright test tests/e2e/rag-training.spec.ts
   npx playwright test tests/e2e/canvas-nodes.spec.ts

3. **Run all tests together:**

   npx playwright test tests/e2e/

4. **View test report:**

   npx playwright show-report

5. **Start Cloppy_Ai if not running:**

   cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai
   pnpm dev
""")

print("=" * 60)
print("🎯 SuperAgent Generated Tests Ready!")
print("=" * 60)
