#!/usr/bin/env python3
"""
Direct test generation for Cloppy_Ai using SuperAgent's Scribe agent.
Bypasses CLI lifecycle to generate tests for Cloppy_Ai features.
"""

import sys
import os
import anthropic

# Add agent_system to path
sys.path.insert(0, '/Users/rutledge/Documents/DevFolder/SuperAgent')

from dotenv import load_dotenv
load_dotenv()

def generate_test_with_anthropic(feature_description: str, test_name: str):
    """Generate a Playwright test using Claude API directly."""

    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    prompt = f"""You are Scribe, a test writing agent for Playwright tests.

Generate a complete Playwright test for Cloppy.ai based on this feature description:

{feature_description}

Requirements:
1. Use data-testid selectors only (format: [data-testid="element-name"])
2. Include proper test setup with beforeEach
3. Add multiple test cases (happy path + error cases)
4. Take screenshots at key steps
5. Include clear assertions
6. Follow Playwright best practices
7. Use TypeScript

Return ONLY the test code, no explanations."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    test_code = message.content[0].text

    # Save test file
    output_path = f'/Users/rutledge/Documents/DevFolder/SuperAgent/tests/cloppy_ai/{test_name}.spec.ts'
    with open(output_path, 'w') as f:
        f.write(test_code)

    print(f"✓ Generated: {output_path}")
    print(f"  Cost: ~${(message.usage.input_tokens * 0.003 / 1000 + message.usage.output_tokens * 0.015 / 1000):.4f}")
    return output_path

if __name__ == '__main__':
    print("🤖 SuperAgent → Cloppy_Ai Test Generator")
    print("=" * 50)

    # Tests to generate based on Cloppy_Ai README
    tests = [
        {
            "name": "media-upload",
            "description": """
Test the media upload and processing pipeline in Cloppy.ai:
- Upload video file to board
- Upload audio file
- Upload PDF document
- Upload image
- Verify processing status
- Check transcription results (video/audio)
- Check OCR results (PDF/image)
- Verify media appears on canvas
            """
        },
        {
            "name": "rag-training",
            "description": """
Test the RAG (Retrieval-Augmented Generation) training feature:
- Navigate to RAG training section
- Upload training documents
- Configure brand voice settings
- Start training process
- Verify training completion
- Test AI responses with trained context
- Validate brand voice consistency
            """
        },
        {
            "name": "canvas-nodes",
            "description": """
Test the infinite canvas node management:
- Create text node
- Create media node
- Create AI chat node
- Move nodes around canvas
- Resize nodes
- Connect nodes with edges
- Delete nodes
- Undo/redo operations
- Save canvas state
            """
        }
    ]

    for test in tests:
        print(f"\n📝 Generating: {test['name']}.spec.ts")
        try:
            generate_test_with_anthropic(test['description'], test['name'])
        except Exception as e:
            print(f"   ✗ Error: {e}")

    print("\n" + "=" * 50)
    print("✓ Test generation complete!")
    print(f"📁 Location: /Users/rutledge/Documents/DevFolder/SuperAgent/tests/cloppy_ai/")
