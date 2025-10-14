# Scribe Agent - RAG Quick Start Guide

## What Changed?

Scribe now uses **RAG (Retrieval-Augmented Generation)** to learn from successful test patterns stored in the vector database.

## Basic Usage (No Changes Required!)

```python
from agent_system.agents.scribe import ScribeAgent

# Initialize (RAG automatically enabled)
scribe = ScribeAgent()

# Use normally - RAG happens automatically
result = scribe.execute(
    task_description="user login with email and password",
    feature_name="Authentication",
    output_path="tests/auth.spec.ts"
)

# Check if RAG was used
print(f"Used RAG: {result.data['used_rag']}")
print(f"Patterns: {result.data['rag_patterns_used']}")
```

## RAG Workflow (Automatic)

1. **Query** - Scribe queries vector DB for similar tests
2. **Format** - Similar patterns formatted as examples
3. **Enhance** - Patterns included in LLM prompt
4. **Generate** - Test generated with RAG context

## Check RAG Metrics

```python
stats = scribe.get_validation_stats()

print(f"RAG Queries: {stats['rag_queries']}")
print(f"RAG Hits: {stats['rag_hits']}")
print(f"Hit Rate: {stats['rag_hit_rate']:.1%}")
```

## Populate Vector DB (To Get Value)

```python
from agent_system.state.vector_client import VectorClient

vector_client = VectorClient()

# Store successful test
vector_client.store_test_pattern(
    test_id='test_login_001',
    test_code=test_content,
    metadata={
        'feature': 'authentication',
        'complexity': 'easy',
        'validated': True
    }
)
```

## Configuration (Optional)

```python
scribe = ScribeAgent()

# Adjust RAG settings
scribe.rag_config['similarity_threshold'] = 0.6  # Lower = more patterns
scribe.rag_config['max_patterns'] = 10          # More examples
```

## Key Points

- ✅ **Automatic** - RAG runs automatically, no code changes needed
- ✅ **Graceful** - Falls back to template if no patterns found
- ✅ **Tracked** - All RAG queries and hits are tracked
- ✅ **Learning** - Gets better as you store more patterns

## When RAG Helps

- ✅ After 50+ patterns stored: Significant improvement
- ✅ Similar features: Patterns from auth tests help new auth tests
- ✅ Over time: Consistency improves with more validated tests

## When RAG Has No Effect

- ⚠️ Empty vector DB (no patterns stored yet)
- ⚠️ Very unique features (no similar patterns)
- ⚠️ Threshold too high (lower to 0.6 or 0.5)

## Integration with Validation Pipeline

```python
# After Gemini validates successfully
if gemini_result.data['test_passed']:
    vector_client.store_test_pattern(
        test_id=task_id,
        test_code=test_content,
        metadata={
            'feature': feature_name,
            'validated_by': 'gemini',
            'timestamp': time.time()
        }
    )
```

## That's It!

RAG is now integrated and working. No changes to your existing code needed. The system will automatically improve as you validate and store more test patterns.

For detailed documentation, see: `SCRIBE_RAG_DOCS.md`
