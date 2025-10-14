"""
HITL Dashboard Backend Server
Provides REST API for HITL queue management.
"""
import os
import sys
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_system.hitl.queue import HITLQueue
from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for frontend development

# Initialize clients
redis_client = RedisClient()
vector_client = VectorClient()
hitl_queue = HITLQueue(redis_client=redis_client, vector_client=vector_client)


@app.route('/')
def index():
    """Serve the dashboard UI."""
    return send_from_directory('static', 'index.html')


@app.route('/api/queue', methods=['GET'])
def get_queue():
    """
    Get all tasks in HITL queue.

    Query params:
        - include_resolved: Include resolved tasks (default: false)
        - limit: Maximum number of tasks to return
    """
    include_resolved = request.args.get('include_resolved', 'false').lower() == 'true'
    limit = request.args.get('limit', type=int)

    try:
        tasks = hitl_queue.list(include_resolved=include_resolved, limit=limit)
        return jsonify({
            'success': True,
            'tasks': tasks,
            'count': len(tasks)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/queue/stats', methods=['GET'])
def get_stats():
    """Get queue statistics."""
    try:
        stats = hitl_queue.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/queue/<task_id>', methods=['GET'])
def get_task(task_id):
    """Get specific task details."""
    try:
        task = hitl_queue.get(task_id)
        if task:
            return jsonify({
                'success': True,
                'task': task
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/queue/<task_id>/resolve', methods=['POST'])
def resolve_task(task_id):
    """
    Mark task as resolved with human annotation.

    Body:
        {
            "root_cause_category": "selector_flaky",
            "fix_strategy": "update_selectors",
            "severity": "medium",
            "human_notes": "Updated data-testid selectors...",
            "patch_diff": "Optional diff string"
        }
    """
    try:
        annotation = request.json

        # Validate required fields
        required_fields = ['root_cause_category', 'fix_strategy', 'severity', 'human_notes']
        missing_fields = [f for f in required_fields if f not in annotation]

        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400

        success = hitl_queue.resolve(task_id, annotation)

        if success:
            return jsonify({
                'success': True,
                'message': f'Task {task_id} resolved successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Task not found or already resolved'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        # Check Redis connection
        redis_healthy = redis_client.health_check()

        return jsonify({
            'success': True,
            'redis': redis_healthy,
            'message': 'HITL Dashboard API is running'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('HITL_DASHBOARD_PORT', 5001))
    print(f"Starting HITL Dashboard server on http://localhost:{port}")
    print(f"Dashboard UI: http://localhost:{port}")
    print(f"API Base URL: http://localhost:{port}/api")
    app.run(host='0.0.0.0', port=port, debug=True)
