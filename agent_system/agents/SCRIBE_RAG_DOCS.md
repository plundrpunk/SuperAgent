# Scribe Agent - RAG Integration Documentation

## Overview

The Scribe agent now includes Retrieval-Augmented Generation (RAG) to improve test generation quality by learning from successful test patterns stored in the vector database.

## What is RAG?

RAG enhances LLM generation by:
1. **Querying** the vector DB for similar successful test patterns
2. **Formatting** retrieved patterns as context for the LLM
3. **Including** patterns in the system prompt
4. **Generating** tests using both template + retrieved patterns

This approach improves consistency, quality, and adherence to established patterns over time.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Scribe Agent                         │
│                                                         │
│  ┌──────────────┐                                      │
│  │   execute()  │                                      │
│  └──────┬───────┘                                      │
│         │                                               │
│         v                                               │
│  ┌──────────────────────────┐                         │
│  │ _generate_with_validation│                         │
│  └──────────┬───────────────┘                         │
│             │                                           │
│             v                                           │
│  ┌──────────────────────────┐                         │
│  │ _generate_test_with_rag  │                         │
│  └──────┬───────────────────┘                         │
│         │                                               │
│    ┌────┴────┐                                         │
│    │         │                                         │
│    v         v                                         │
│  ┌─────┐  ┌─────────────────┐                        │
│  │ RAG │  │  LLM Generation │                        │
│  │Query│  │   (with RAG     │                        │
│  │     │  │    context)     │                        │
│  └──┬──┘  └─────────────────┘                        │
│     │                                                   │
│     v                                                   │
│  ┌──────────────┐                                     │
│  │ Vector DB    │                                     │
│  │ (ChromaDB)   │                                     │
│  └──────────────┘                                     │
└─────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Automatic Pattern Retrieval
- Queries vector DB before each test generation
- Uses task description as search query
- Returns top 5 similar patterns by default
- Filters by similarity threshold (0.7 default)

### 2. Smart Context Formatting
- Formats retrieved patterns as LLM examples
- Includes metadata (feature, complexity, type)
- Truncates long patterns (>1000 chars)
- Shows similarity percentage for each pattern

### 3. Graceful Fallback
- Falls back to template-only generation if:
  - No patterns found above threshold
  - Vector DB query fails
  - Collection is empty
- Logs warnings for debugging

### 4. Comprehensive Metrics
- Tracks RAG queries and hits
- Calculates hit rate
- Counts total patterns retrieved
- Reports average patterns per hit

## Configuration

```python
# RAG configuration in Scribe.__init__()
self.rag_config = {
    'similarity_threshold': 0.7,  # Min similarity to include pattern
    'max_patterns': 5,            # Max patterns to retrieve
    'collection': 'test_success'  # Vector DB collection name
}
```

## RAG Workflow

### Step 1: Query Similar Patterns

```python
def _query_similar_patterns(self, query: str) -> List[Dict[str, Any]]:
    """
    Query vector DB for similar test patterns.

    Returns patterns above similarity threshold.
    Logs info/warnings for visibility.
    Falls back gracefully on errors.
    """
```

**What it does:**
- Calls `vector_client.search_test_patterns(query, n_results=5)`
- Filters results by `similarity >= threshold`
- Increments `rag_queries` counter
- Increments `rag_hits` if patterns found
- Tracks `total_patterns_retrieved`

### Step 2: Format Patterns as Context

```python
def _format_patterns_as_context(self, patterns: List[Dict[str, Any]]) -> str:
    """
    Format retrieved patterns as LLM context.

    Returns empty string if no patterns.
    Formats with metadata and code snippets.
    """
```

**Example Output:**
```
Here are similar successful tests for reference:

--- Example 1 (similarity: 85%) ---
Feature: User Login
Complexity: easy
Type: authentication

import { test, expect } from '@playwright/test';
const S = (id: string) => `[data-testid="${id}"]`;
...

--- Example 2 (similarity: 78%) ---
Feature: OAuth Login
Complexity: hard
...
```

### Step 3: Build Enhanced Prompt

```python
def _build_enhanced_prompt(
    self,
    description: str,
    feature_name: str,
    similar_patterns: List[Dict[str, Any]]
) -> str:
    """
    Build enhanced prompt with RAG context.

    Includes:
    - Base requirements (data-testid, assertions, etc.)
    - Similar patterns (if available)
    - Task description and feature name
    """
```

**Prompt Structure:**
1. System message (expert Playwright test writer)
2. Critical requirements (selectors, screenshots, assertions)
3. **RAG context** (if patterns found)
4. Task details (feature + description)

### Step 4: Generate Test

```python
def _generate_test_with_rag(
    self,
    description: str,
    feature_name: str
) -> Dict[str, Any]:
    """
    Generate test code with RAG enhancement.

    Returns:
        {
            'test_content': str,      # Generated test code
            'patterns_used': List[str],  # Pattern IDs used
            'used_rag': bool          # Whether RAG was used
        }
    """
```

## Usage Example

### Basic Usage

```python
from agent_system.agents.scribe import ScribeAgent

# Initialize with default vector client
scribe = ScribeAgent()

# Generate test (RAG automatically applied)
result = scribe.execute(
    task_description="user checkout with credit card payment",
    feature_name="E-commerce Checkout",
    output_path="tests/checkout.spec.ts"
)

# Check RAG usage
print(f"Used RAG: {result.data['used_rag']}")
print(f"Patterns: {result.data['rag_patterns_used']}")
```

### With Custom Vector Client

```python
from agent_system.agents.scribe import ScribeAgent
from agent_system.state.vector_client import VectorClient, VectorConfig

# Custom vector config
config = VectorConfig(
    persist_directory='./custom_vector_db',
    collection_prefix='myapp'
)

vector_client = VectorClient(config)
scribe = ScribeAgent(vector_client=vector_client)

# Use as normal
result = scribe.execute(...)
```

### Checking RAG Metrics

```python
# Get comprehensive stats
stats = scribe.get_validation_stats()

print(f"RAG Queries: {stats['rag_queries']}")
print(f"RAG Hits: {stats['rag_hits']}")
print(f"Hit Rate: {stats['rag_hit_rate']:.1%}")
print(f"Total Patterns: {stats['total_patterns_retrieved']}")
print(f"Avg Patterns/Hit: {stats['avg_patterns_per_hit']:.1f}")
print(f"Threshold: {stats['rag_threshold']}")
```

## Populating the Vector DB

To get value from RAG, you need to populate the vector DB with successful test patterns:

```python
from agent_system.state.vector_client import VectorClient

vector_client = VectorClient()

# Store successful test pattern
vector_client.store_test_pattern(
    test_id='test_login_001',
    test_code='''
    import { test, expect } from '@playwright/test';
    const S = (id: string) => `[data-testid="${id}"]`;

    test('user login', async ({ page }) => {
        await page.goto(process.env.BASE_URL!);
        await page.fill(S('email-input'), 'user@example.com');
        await page.fill(S('password-input'), 'password');
        await page.click(S('login-button'));
        await expect(page.locator(S('dashboard'))).toBeVisible();
    });
    ''',
    metadata={
        'feature': 'authentication',
        'complexity': 'easy',
        'test_type': 'login',
        'validated': True,
        'pass_rate': 1.0
    }
)
```

### Automated Storage

In production, store patterns automatically after successful validation:

```python
# After Gemini validates a test
if validation_result['test_passed']:
    vector_client.store_test_pattern(
        test_id=task_id,
        test_code=test_content,
        metadata={
            'feature': feature_name,
            'complexity': complexity,
            'validated_by': 'gemini',
            'timestamp': time.time()
        }
    )
```

## RAG Metadata in Results

The `execute()` method returns RAG metadata:

```python
result = scribe.execute(...)

# Data fields
result.data['test_content']        # Generated test code
result.data['used_rag']           # bool: RAG was used
result.data['rag_patterns_used']  # List[str]: Pattern IDs
result.data['validation_passed']  # bool: Passed Critic

# Metadata fields
result.metadata['rag_patterns_count']  # int: Number of patterns used
result.metadata['complexity']          # str: easy/hard
```

## Benefits of RAG Integration

### 1. Consistency Over Time
- Tests follow established patterns
- Selector conventions are maintained
- Error handling becomes standardized

### 2. Improved Quality
- Learn from successful tests
- Avoid patterns that failed in the past
- Better edge case coverage

### 3. Reduced Iteration
- Fewer validation retries needed
- LLM starts with good examples
- Less trial-and-error

### 4. Domain Adaptation
- Learns project-specific patterns
- Adapts to your app's structure
- Improves with usage

## Performance Characteristics

### Query Performance
- Vector DB query: ~50-200ms (depends on collection size)
- Embedding generation: ~20-50ms per query
- Minimal overhead (~5-10% of total generation time)

### Memory Usage
- Embedding model: ~90MB (all-MiniLM-L6-v2)
- ChromaDB: Scales with pattern count
- Patterns cached in memory during session

### Cost Impact
- No additional LLM API costs
- Local vector DB (no external API)
- One-time embedding model download

## Troubleshooting

### No Patterns Found

**Symptom:** `rag_hits = 0`, `used_rag = False`

**Causes:**
1. Vector DB is empty (no patterns stored yet)
2. Similarity threshold too high (0.7 default)
3. Query doesn't match stored patterns

**Solutions:**
- Populate vector DB with successful tests
- Lower threshold: `scribe.rag_config['similarity_threshold'] = 0.6`
- Check collection: `vector_client.get_collection_count('test_success')`

### Vector DB Query Errors

**Symptom:** Warnings in logs, fallback to template-only

**Causes:**
- ChromaDB not initialized
- Collection doesn't exist
- Embedding model not downloaded

**Solutions:**
- Initialize VectorClient early: `VectorClient()` (downloads model)
- Check persist directory exists
- Verify ChromaDB installation: `pip install chromadb`

### Low Hit Rate

**Symptom:** `rag_hit_rate < 30%`

**Causes:**
- Too few patterns in DB
- Patterns not diverse enough
- Threshold too strict

**Solutions:**
- Store more patterns (aim for 50+ minimum)
- Store patterns for different features
- Adjust threshold based on use case

## Integration with Other Agents

### With Gemini Validator

After Gemini validates a test, store it:

```python
# In validation workflow
if gemini_result.data['test_passed']:
    vector_client.store_test_pattern(
        test_id=f"validated_{task_id}",
        test_code=test_content,
        metadata={
            'feature': feature_name,
            'validated_by': 'gemini',
            'gemini_score': gemini_result.data['validation_score'],
            'screenshots_count': len(gemini_result.data['screenshots'])
        }
    )
```

### With Medic Agent

Store successful bug fixes as patterns:

```python
# After Medic fixes and validates
if fix_result['regression_passed']:
    vector_client.store_bug_fix(
        fix_id=f"fix_{task_id}",
        error_message=original_error,
        fix_code=fix_diff,
        metadata={
            'root_cause': medic_result['root_cause'],
            'fix_strategy': medic_result['strategy']
        }
    )
```

## Future Enhancements

### Planned Features
1. **Semantic clustering** - Group similar patterns
2. **Pattern versioning** - Track pattern evolution
3. **Confidence scoring** - Weight patterns by success rate
4. **Active learning** - Prioritize patterns that need improvement
5. **Cross-project patterns** - Share patterns across projects

### Configuration Options
- Adjustable similarity threshold per task
- Pattern filtering by metadata
- Time-based pattern decay
- Custom embedding models

## Summary

The RAG integration in Scribe agent:
- ✅ Queries vector DB for similar successful tests
- ✅ Formats patterns as LLM context
- ✅ Generates tests with enhanced prompts
- ✅ Gracefully falls back when no patterns found
- ✅ Tracks comprehensive RAG metrics
- ✅ Integrates seamlessly with existing workflow

**Key Takeaway:** RAG makes Scribe smarter over time by learning from successful test patterns, improving consistency and quality with every validated test.
