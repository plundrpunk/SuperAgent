# Using the OpenAPI Specification

This guide shows how to use the SuperAgent HITL Dashboard API OpenAPI specification (`openapi-hitl.yaml`) with various tools.

## Quick Links

- **OpenAPI Spec**: [openapi-hitl.yaml](./openapi-hitl.yaml)
- **API Documentation**: [API_HITL_ENDPOINTS.md](./API_HITL_ENDPOINTS.md)
- **Dashboard**: http://localhost:5001

---

## What is OpenAPI?

The OpenAPI Specification (formerly Swagger) is a standard, language-agnostic interface description for REST APIs. It allows both humans and computers to discover and understand the API's capabilities without access to source code.

**Benefits**:
- Generate client libraries in multiple languages
- Interactive API documentation
- API testing and validation
- Mock server generation
- Contract testing

---

## Swagger UI (Interactive Documentation)

### Using Docker

The easiest way to view the API documentation:

```bash
# From SuperAgent root directory
cd /Users/rutledge/Documents/DevFolder/SuperAgent

# Run Swagger UI
docker run -p 8080:8080 \
  -e SWAGGER_JSON=/docs/openapi-hitl.yaml \
  -v $(pwd)/docs:/docs \
  swaggerapi/swagger-ui

# Open browser to http://localhost:8080
```

### Using npx (No Installation)

```bash
# From docs directory
cd /Users/rutledge/Documents/DevFolder/SuperAgent/docs

# Start Swagger UI server
npx @apidevtools/swagger-ui-cli openapi-hitl.yaml

# Open browser to http://localhost:8000
```

### Features

- **Interactive API Explorer**: Try endpoints directly from the browser
- **Request Builder**: Automatically generates request code
- **Schema Viewer**: Browse all data models
- **Response Examples**: See example responses for all endpoints

---

## Postman

### Import Specification

1. Open Postman
2. Click **Import** button
3. Select **File** tab
4. Choose `docs/openapi-hitl.yaml`
5. Click **Import**

### Features

- All endpoints automatically imported as requests
- Example requests pre-filled
- Environment variables supported
- Collection runner for testing

### Example Collection

After import, you'll have:

```
SuperAgent HITL Dashboard API
├── queue
│   ├── List HITL tasks
│   ├── Get queue statistics
│   └── Get task details
├── resolve
│   └── Resolve task
└── health
    └── Health check
```

---

## Code Generation

Generate client libraries in your preferred language.

### OpenAPI Generator

**Install**:
```bash
npm install -g @openapitools/openapi-generator-cli
# or
brew install openapi-generator
```

**Generate Python Client**:
```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent

openapi-generator-cli generate \
  -i docs/openapi-hitl.yaml \
  -g python \
  -o clients/python-hitl \
  --additional-properties=packageName=hitl_client

# Install generated client
cd clients/python-hitl
pip install .
```

**Usage**:
```python
from hitl_client import ApiClient, Configuration
from hitl_client.api.queue_api import QueueApi

# Configure client
config = Configuration(host="http://localhost:5001/api")
client = ApiClient(config)
api = QueueApi(client)

# List tasks
tasks = api.list_tasks(include_resolved=False, limit=10)
print(f"Found {len(tasks.tasks)} tasks")

# Get task details
task = api.get_task("task_123")
print(f"Task: {task.feature}")

# Resolve task
api.resolve_task("task_123", {
    "root_cause_category": "selector_flaky",
    "fix_strategy": "update_selectors",
    "severity": "medium",
    "human_notes": "Fixed selectors"
})
```

**Generate TypeScript Client**:
```bash
openapi-generator-cli generate \
  -i docs/openapi-hitl.yaml \
  -g typescript-fetch \
  -o clients/typescript-hitl \
  --additional-properties=npmName=@superagent/hitl-client

# Install
cd clients/typescript-hitl
npm install
npm run build
```

**Usage**:
```typescript
import { Configuration, QueueApi } from '@superagent/hitl-client';

const config = new Configuration({
  basePath: 'http://localhost:5001/api'
});

const api = new QueueApi(config);

// List tasks
const response = await api.listTasks({
  includeResolved: false,
  limit: 10
});
console.log(`Found ${response.tasks.length} tasks`);

// Resolve task
await api.resolveTask({
  taskId: 'task_123',
  taskAnnotation: {
    root_cause_category: 'selector_flaky',
    fix_strategy: 'update_selectors',
    severity: 'medium',
    human_notes: 'Fixed selectors'
  }
});
```

**Supported Languages**:
- Python
- TypeScript/JavaScript
- Go
- Java
- C#
- Ruby
- PHP
- Swift
- Kotlin
- Rust
- [And many more...](https://openapi-generator.tech/docs/generators)

---

## Mock Server

Generate a mock API server for testing without the real backend.

### Using Prism

**Install**:
```bash
npm install -g @stoplight/prism-cli
```

**Start Mock Server**:
```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/docs

# Start mock server on port 4010
prism mock openapi-hitl.yaml --port 4010

# Server starts at http://localhost:4010
```

**Test Mock Server**:
```bash
# Get mock tasks
curl http://localhost:4010/api/queue

# Get mock task details
curl http://localhost:4010/api/queue/task_123

# Resolve mock task
curl -X POST http://localhost:4010/api/queue/task_123/resolve \
  -H "Content-Type: application/json" \
  -d '{"root_cause_category": "selector_flaky", "fix_strategy": "update_selectors", "severity": "medium", "human_notes": "Fixed"}'
```

**Features**:
- Returns example responses from spec
- Validates request schemas
- Useful for frontend development
- Contract testing

---

## VS Code Extensions

### OpenAPI (Swagger) Editor

**Install**: Search for "OpenAPI (Swagger) Editor" in VS Code extensions

**Features**:
- Syntax highlighting for YAML
- Auto-completion
- Real-time validation
- Preview documentation
- Generate code snippets

**Usage**:
1. Open `docs/openapi-hitl.yaml` in VS Code
2. Right-click → "Preview Swagger"
3. Interactive documentation opens in editor

### REST Client

**Install**: Search for "REST Client" in VS Code extensions

**Create Request File** (`hitl-requests.http`):
```http
### Variables
@baseUrl = http://localhost:5001/api

### List tasks
GET {{baseUrl}}/queue
Content-Type: application/json

### Get task details
GET {{baseUrl}}/queue/task_123

### Resolve task
POST {{baseUrl}}/queue/task_123/resolve
Content-Type: application/json

{
  "root_cause_category": "selector_flaky",
  "fix_strategy": "update_selectors",
  "severity": "medium",
  "human_notes": "Updated selectors to use data-testid"
}

### Get statistics
GET {{baseUrl}}/queue/stats

### Health check
GET {{baseUrl}}/health
```

Click "Send Request" above each request to execute.

---

## Validation Tools

### Spectral (Linting)

**Install**:
```bash
npm install -g @stoplight/spectral-cli
```

**Validate Spec**:
```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/docs

# Validate against OpenAPI rules
spectral lint openapi-hitl.yaml

# Use custom ruleset
spectral lint openapi-hitl.yaml --ruleset .spectral.yaml
```

**Create Custom Rules** (`.spectral.yaml`):
```yaml
extends: spectral:oas
rules:
  operation-description: error
  operation-operationId: error
  operation-tags: error
  info-contact: error
  info-description: error
```

### Swagger Editor

**Online**: https://editor.swagger.io/

1. Go to editor.swagger.io
2. File → Import file
3. Select `openapi-hitl.yaml`
4. View validation errors/warnings

---

## Contract Testing

### Dredd

**Install**:
```bash
npm install -g dredd
```

**Test API Against Spec**:
```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/docs

# Start HITL Dashboard on port 5001
# Then run Dredd tests
dredd openapi-hitl.yaml http://localhost:5001
```

**Features**:
- Validates API responses match spec
- Ensures backward compatibility
- CI/CD integration

### Schemathesis

**Install**:
```bash
pip install schemathesis
```

**Property-Based Testing**:
```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/docs

# Start HITL Dashboard, then:
schemathesis run openapi-hitl.yaml \
  --base-url http://localhost:5001 \
  --checks all

# Run specific endpoint
schemathesis run openapi-hitl.yaml \
  --base-url http://localhost:5001 \
  --endpoint /api/queue
```

**Features**:
- Generates test cases from spec
- Finds edge cases
- Property-based testing

---

## Integration with CI/CD

### GitHub Actions

**.github/workflows/api-validation.yml**:
```yaml
name: API Validation

on: [push, pull_request]

jobs:
  validate-openapi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Validate OpenAPI Spec
        uses: char0n/swagger-editor-validate@v1
        with:
          definition-file: docs/openapi-hitl.yaml

      - name: Lint with Spectral
        run: |
          npm install -g @stoplight/spectral-cli
          spectral lint docs/openapi-hitl.yaml

      - name: Run Contract Tests
        run: |
          # Start services
          docker compose up -d
          sleep 10

          # Run Dredd tests
          npm install -g dredd
          dredd docs/openapi-hitl.yaml http://localhost:5001
```

---

## Documentation Generation

### ReDoc

**Install**:
```bash
npm install -g redoc-cli
```

**Generate Static HTML**:
```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/docs

# Generate beautiful documentation
redoc-cli bundle openapi-hitl.yaml \
  --output hitl-api-docs.html \
  --title "SuperAgent HITL API"

# Open in browser
open hitl-api-docs.html
```

**Features**:
- Beautiful, responsive documentation
- Three-panel layout
- Code samples in multiple languages
- Search functionality

### Slate

**Install**:
```bash
gem install slate
```

**Convert to Markdown**:
```bash
# Use widdershins to convert OpenAPI to Markdown
npm install -g widdershins

widdershins docs/openapi-hitl.yaml \
  -o docs/api-reference.md \
  --language_tabs 'python:Python' 'typescript:TypeScript' 'shell:cURL'
```

---

## Keeping Spec Updated

### Best Practices

1. **Version Control**: Keep spec in git alongside code
2. **Sync with Code**: Update spec when API changes
3. **Validate on CI**: Run spectral lint on every commit
4. **Generate Docs**: Auto-generate docs from spec
5. **Contract Tests**: Run Dredd/Schemathesis in CI

### Automation Script

**update-api-docs.sh**:
```bash
#!/bin/bash
set -e

cd /Users/rutledge/Documents/DevFolder/SuperAgent

echo "Validating OpenAPI spec..."
spectral lint docs/openapi-hitl.yaml

echo "Generating ReDoc HTML..."
redoc-cli bundle docs/openapi-hitl.yaml \
  --output docs/hitl-api-docs.html

echo "Running contract tests..."
dredd docs/openapi-hitl.yaml http://localhost:5001

echo "API documentation updated successfully!"
```

---

## Troubleshooting

### Spec Validation Errors

**Error**: `should have required property 'components'`

**Solution**: Ensure all schema references exist in components section

**Error**: `Paths object has no keys`

**Solution**: Add at least one path definition

### Mock Server Issues

**Error**: `Cannot find module`

**Solution**: Install prism globally: `npm install -g @stoplight/prism-cli`

### Code Generation Fails

**Error**: `Unknown generator: python`

**Solution**: Update openapi-generator: `npm update -g @openapitools/openapi-generator-cli`

---

## Additional Resources

- **OpenAPI Specification**: https://spec.openapis.org/oas/v3.0.3
- **OpenAPI Generator**: https://openapi-generator.tech/
- **Swagger Tools**: https://swagger.io/tools/
- **Prism Mock Server**: https://stoplight.io/open-source/prism
- **Spectral Linter**: https://stoplight.io/open-source/spectral
- **ReDoc**: https://redocly.com/redoc/

---

## Related Documentation

- [API_HITL_ENDPOINTS.md](./API_HITL_ENDPOINTS.md) - Human-readable API documentation
- [HITL Dashboard README](../hitl_dashboard/README.md) - Dashboard usage guide
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture

---

**Last Updated**: 2025-10-14
**OpenAPI Version**: 3.0.3
**API Version**: 1.0.0
