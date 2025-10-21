"""
Archon MCP Client Wrapper
Provides Python interface to Archon MCP tools for project/task management.
"""
import logging
import time
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ArchonClient:
    """
    Wrapper for Archon MCP tools.

    Provides methods to:
    - Create and manage projects
    - Break features into tasks
    - Track task status
    - Store documents and version history
    - Search knowledge base (RAG) for Cloppy AI patterns
    """

    def __init__(self):
        """Initialize Archon client."""
        self.enabled = True
        self.use_real_mcp = True  # Use HTTP API instead of MCP
        self.archon_api_url = "http://host.docker.internal:8181/api"
        logger.info(f"ArchonClient initialized (real_mcp={self.use_real_mcp}, api={self.archon_api_url})")

    def create_project(
        self,
        title: str,
        description: str,
        github_repo: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new project in Archon.

        Args:
            title: Project title
            description: Project description and scope
            github_repo: Optional GitHub repository URL

        Returns:
            Dict with success, project_id, message
        """
        try:
            if not self.use_real_mcp:
                # Mock mode
                logger.info(f"Creating project (mock): {title}")
                return {
                    'success': True,
                    'project_id': f'proj_{int(time.time())}',
                    'title': title,
                    'description': description,
                    'message': f'Project "{title}" created successfully (mock)'
                }

            # Real Archon HTTP API
            import requests

            logger.info(f"Creating project via Archon API: {title}")

            response = requests.post(
                f"{self.archon_api_url}/projects",
                json={
                    "title": title,
                    "description": description,
                    "github_repo": github_repo
                },
                timeout=10
            )

            if response.status_code in [200, 201]:
                data = response.json()
                project_id = data.get('project_id') or data.get('project', {}).get('id')
                logger.info(f"✅ Project created in Archon: {project_id}")
                return {
                    'success': True,
                    'project_id': project_id,
                    'title': title,
                    'description': description,
                    'message': f'Project "{title}" created successfully'
                }
            else:
                logger.error(f"Archon API error: {response.status_code}")
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'message': f'Failed to create project: {response.text[:200]}'
                }

        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to create project: {str(e)}'
            }

    def create_task(
        self,
        project_id: str,
        title: str,
        description: str,
        assignee: str = "Scribe",
        feature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a task in a project.

        Args:
            project_id: Project UUID
            title: Task title
            description: Detailed task description
            assignee: Agent or user assigned (default: Scribe)
            feature: Feature label for grouping

        Returns:
            Dict with success, task_id, message
        """
        try:
            if not self.use_real_mcp:
                # Mock mode
                logger.info(f"Creating task (mock) in project {project_id}: {title}")
                return {
                    'success': True,
                    'task_id': f'task_{int(time.time())}',
                    'project_id': project_id,
                    'title': title,
                    'description': description,
                    'status': 'todo',
                    'assignee': assignee,
                    'feature': feature,
                    'message': f'Task "{title}" created successfully (mock)'
                }

            # Real Archon HTTP API
            import requests

            logger.info(f"Creating task via Archon API: {title}")

            response = requests.post(
                f"{self.archon_api_url}/tasks",
                json={
                    "project_id": project_id,
                    "title": title,
                    "description": description,
                    "assignee": assignee,
                    "status": "todo"
                },
                timeout=10
            )

            if response.status_code in [200, 201]:
                data = response.json()
                task = data.get('task', {})
                task_id = task.get('id')
                logger.info(f"✅ Task created in Archon: {task_id}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'project_id': project_id,
                    'title': title,
                    'description': description,
                    'status': task.get('status', 'todo'),
                    'assignee': assignee,
                    'feature': feature,
                    'message': f'Task "{title}" created successfully'
                }
            else:
                logger.error(f"Archon API error: {response.status_code}")
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'message': f'Failed to create task: {response.text[:200]}'
                }

        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to create task: {str(e)}'
            }

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update task status.

        Args:
            task_id: Task UUID
            status: New status (todo, doing, review, done)
            result_data: Optional result data from agent execution

        Returns:
            Dict with success, message
        """
        try:
            if not self.use_real_mcp:
                # Mock mode
                logger.info(f"Updating task (mock) {task_id} to status: {status}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'status': status,
                    'message': f'Task status updated to {status} (mock)'
                }

            # Real Archon HTTP API
            import requests

            logger.info(f"Updating task via Archon API: {task_id} -> {status}")

            response = requests.put(
                f"{self.archon_api_url}/tasks/{task_id}",
                json={"status": status},
                timeout=10
            )

            if response.status_code in [200, 201]:
                logger.info(f"✅ Task status updated in Archon: {status}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'status': status,
                    'message': f'Task status updated to {status}'
                }
            else:
                logger.error(f"Archon API error: {response.status_code}")
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'message': f'Failed to update task status: {response.text[:200]}'
                }

        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to update task status: {str(e)}'
            }

    def find_tasks(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find tasks by project and/or status.

        Args:
            project_id: Optional project UUID filter
            status: Optional status filter (todo, doing, review, done)

        Returns:
            Dict with success, tasks list
        """
        try:
            if not self.use_real_mcp:
                # Mock mode
                logger.info(f"Finding tasks (mock) for project {project_id}, status {status}")
                return {
                    'success': True,
                    'tasks': [],
                    'count': 0,
                    'message': 'No tasks found (mock mode)'
                }

            # Real Archon HTTP API
            import requests

            logger.info(f"Finding tasks via Archon API: project={project_id}, status={status}")

            params = {}
            if project_id:
                params['project_id'] = project_id
            if status:
                params['status'] = status

            response = requests.get(
                f"{self.archon_api_url}/tasks",
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                tasks = data.get('tasks', [])
                logger.info(f"✅ Found {len(tasks)} tasks in Archon")
                return {
                    'success': True,
                    'tasks': tasks,
                    'count': len(tasks),
                    'message': f'Found {len(tasks)} tasks'
                }
            else:
                logger.error(f"Archon API error: {response.status_code}")
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'tasks': [],
                    'count': 0
                }

        except Exception as e:
            logger.error(f"Failed to find tasks: {e}")
            return {
                'success': False,
                'error': str(e),
                'tasks': [],
                'count': 0
            }

    def search_knowledge_base(
        self,
        query: str,
        match_count: int = 5
    ) -> Dict[str, Any]:
        """
        Search Archon knowledge base for relevant documentation and code examples.

        Uses direct Supabase full-text search to find:
        - Cloppy AI patterns
        - Data-testid selectors
        - Code examples
        - Documentation

        Args:
            query: Search query (keep short, 2-5 keywords)
            match_count: Number of results to return

        Returns:
            Dict with success, results list
        """
        try:
            if not self.use_real_mcp:
                return {'success': False, 'results': [], 'message': 'RAG not enabled'}

            # Use direct Supabase search (bypasses embedding requirement)
            from supabase import create_client
            import os

            logger.info(f"RAG search via Supabase full-text: {query}")

            # Connect to Supabase
            supabase_url = os.getenv('SUPABASE_URL', 'https://hrrpicijvdfzoxwwjequ.supabase.co')
            supabase_key = os.getenv('SUPABASE_KEY')

            if not supabase_key:
                logger.error("SUPABASE_KEY not found in environment")
                return {'success': False, 'results': [], 'error': 'Missing SUPABASE_KEY'}

            supabase = create_client(supabase_url, supabase_key)

            # Split query into keywords for ILIKE search
            keywords = query.lower().split()

            # Build search query
            search = supabase.table('archon_crawled_pages').select('url, content, metadata')

            # Apply ILIKE filters for each keyword
            for keyword in keywords:
                search = search.ilike('content', f'%{keyword}%')

            # Execute search with limit
            result = search.limit(match_count).execute()

            if result.data:
                # Format results to match expected structure
                formatted_results = []
                for page in result.data:
                    # Extract snippet around first keyword
                    content = page.get('content', '')
                    first_keyword = keywords[0] if keywords else ''
                    idx = content.lower().find(first_keyword)

                    if idx >= 0:
                        snippet_start = max(0, idx - 100)
                        snippet_end = min(len(content), idx + 400)
                        snippet = content[snippet_start:snippet_end]
                    else:
                        snippet = content[:500]

                    formatted_results.append({
                        'url': page.get('url', ''),
                        'content': snippet,
                        'metadata': page.get('metadata', {}),
                        'relevance': 'full-text match'
                    })

                logger.info(f"✅ RAG search found {len(formatted_results)} matches from Supabase")
                return {
                    'success': True,
                    'results': formatted_results,
                    'total_found': len(formatted_results),
                    'search_method': 'supabase_fulltext'
                }
            else:
                logger.warning(f"⚠️  No results found for query: {query}")
                return {'success': True, 'results': [], 'total_found': 0}

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return {'success': False, 'results': [], 'error': str(e)}

    def breakdown_feature_to_tasks(
        self,
        feature_description: str,
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        Break down a feature description into granular tasks.

        Uses heuristics to determine appropriate task granularity:
        - Multi-step features: break into implementation steps
        - Complex features: separate setup, implement, test, document
        - Simple features: single implementation task

        Args:
            feature_description: High-level feature description
            project_id: Project UUID for task creation

        Returns:
            List of task dicts with title, description, assignee
        """
        tasks = []
        feature_lower = feature_description.lower()

        # Analyze complexity keywords
        has_auth = any(word in feature_lower for word in ['auth', 'login', 'oauth', 'password'])
        has_database = any(word in feature_lower for word in ['database', 'migration', 'schema', 'postgres'])
        has_ui = any(word in feature_lower for word in ['ui', 'interface', 'component', 'page', 'view'])
        has_api = any(word in feature_lower for word in ['api', 'endpoint', 'route', 'rest'])
        has_test = 'test' in feature_lower

        # Determine granularity
        if has_auth or has_database:
            # High complexity - detailed breakdown
            tasks.append({
                'title': f'Set up {feature_description} foundation',
                'description': f'Initialize project structure, dependencies, and configuration for {feature_description}',
                'assignee': 'Scribe',
                'feature': feature_description
            })
            tasks.append({
                'title': f'Implement core {feature_description} logic',
                'description': f'Write main implementation for {feature_description} with proper error handling',
                'assignee': 'Scribe',
                'feature': feature_description
            })
            if has_database:
                tasks.append({
                    'title': f'Create database schema for {feature_description}',
                    'description': f'Define and migrate database schema required for {feature_description}',
                    'assignee': 'Scribe',
                    'feature': feature_description
                })
            if has_ui:
                tasks.append({
                    'title': f'Build UI components for {feature_description}',
                    'description': f'Create user interface components with proper data-testid selectors',
                    'assignee': 'Scribe',
                    'feature': feature_description
                })
            tasks.append({
                'title': f'Write tests for {feature_description}',
                'description': f'Create comprehensive test suite covering happy paths and error cases',
                'assignee': 'Scribe',
                'feature': feature_description
            })
            tasks.append({
                'title': f'Document {feature_description}',
                'description': f'Add documentation, API specs, and usage examples',
                'assignee': 'Scribe',
                'feature': feature_description
            })
        elif has_test:
            # Test creation - single focused task
            tasks.append({
                'title': f'Generate test: {feature_description}',
                'description': feature_description,
                'assignee': 'Scribe',
                'feature': 'test_generation'
            })
        else:
            # Medium complexity - basic breakdown
            tasks.append({
                'title': f'Implement {feature_description}',
                'description': f'Build {feature_description} with proper error handling and validation',
                'assignee': 'Scribe',
                'feature': feature_description
            })
            tasks.append({
                'title': f'Test {feature_description}',
                'description': f'Write and validate tests for {feature_description}',
                'assignee': 'Scribe',
                'feature': feature_description
            })

        return tasks


# Global singleton instance
_archon_client = None

def get_archon_client() -> ArchonClient:
    """Get or create the global Archon client instance."""
    global _archon_client
    if _archon_client is None:
        _archon_client = ArchonClient()
    return _archon_client
