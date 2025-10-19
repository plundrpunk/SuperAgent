// HITL Dashboard Application

const API_BASE = window.location.origin + '/api';

// State
let currentTasks = [];
let selectedTask = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadQueue();
    loadStats();
    setupEventListeners();
});

// Event Listeners
function setupEventListeners() {
    document.getElementById('refresh-btn').addEventListener('click', () => {
        loadQueue();
        loadStats();
    });

    document.getElementById('show-resolved').addEventListener('change', (e) => {
        loadQueue(e.target.checked);
    });

    // Modal close
    document.querySelector('.close').addEventListener('click', closeModal);
    window.addEventListener('click', (e) => {
        if (e.target.id === 'modal') closeModal();
    });
}

// API Functions
async function loadQueue(includeResolved = false) {
    try {
        showLoading();
        const response = await fetch(`${API_BASE}/queue?include_resolved=${includeResolved}`);
        const data = await response.json();

        if (data.success) {
            currentTasks = data.tasks;
            renderQueue(data.tasks);
        } else {
            showError('Failed to load queue: ' + data.error);
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/queue/stats`);
        const data = await response.json();

        if (data.success) {
            renderStats(data.stats);
        }
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function loadTaskDetails(taskId) {
    try {
        const response = await fetch(`${API_BASE}/queue/${taskId}`);
        const data = await response.json();

        if (data.success) {
            selectedTask = data.task;
            renderTaskModal(data.task);
        } else {
            showError('Failed to load task details: ' + data.error);
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    }
}

async function resolveTask(taskId, annotation) {
    try {
        const response = await fetch(`${API_BASE}/queue/${taskId}/resolve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(annotation)
        });

        const data = await response.json();

        if (data.success) {
            closeModal();
            loadQueue(document.getElementById('show-resolved').checked);
            loadStats();
            showSuccess('Task resolved successfully!');
        } else {
            showError('Failed to resolve task: ' + data.error);
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    }
}

// Render Functions
function renderStats(stats) {
    document.getElementById('active-count').textContent = stats.active_count || 0;
    document.getElementById('resolved-count').textContent = stats.resolved_count || 0;
    document.getElementById('high-priority-count').textContent = stats.high_priority_count || 0;
    document.getElementById('avg-priority').textContent = (stats.avg_priority || 0).toFixed(2);
}

function renderQueue(tasks) {
    const container = document.getElementById('queue-list');
    const emptyState = document.getElementById('empty-state');

    if (tasks.length === 0) {
        container.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';
    container.innerHTML = tasks.map(task => createTaskCard(task)).join('');

    // Add click listeners
    tasks.forEach(task => {
        const card = document.querySelector(`[data-task-id="${task.task_id}"]`);
        if (card) {
            card.addEventListener('click', () => {
                loadTaskDetails(task.task_id);
            });
        }
    });
}

function createTaskCard(task) {
    const priorityClass = getPriorityClass(task.priority);
    const priorityLabel = getPriorityLabel(task.priority);
    const resolved = task.resolved ? 'resolved' : '';

    return `
        <div class="task-card ${resolved}" data-task-id="${task.task_id}">
            <div class="task-header">
                <div>
                    <div class="task-title">${escapeHtml(task.feature || 'Unnamed Task')}</div>
                    <div class="task-id">${escapeHtml(task.task_id)}</div>
                </div>
                <div>
                    <span class="priority-badge priority-${priorityClass}">${priorityLabel}</span>
                    ${task.resolved ? '<span class="status-badge status-resolved">Resolved</span>' : '<span class="status-badge status-pending">Pending</span>'}
                </div>
            </div>

            <div class="task-meta">
                <div class="meta-item">
                    <span class="meta-label">Attempts:</span>
                    <span>${task.attempts || 0}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Created:</span>
                    <span>${formatDate(task.created_at)}</span>
                </div>
                ${task.escalation_reason ? `
                    <div class="meta-item">
                        <span class="meta-label">Reason:</span>
                        <span>${escapeHtml(task.escalation_reason)}</span>
                    </div>
                ` : ''}
            </div>

            ${task.last_error ? `
                <div class="task-error">
                    ${escapeHtml(truncate(task.last_error, 200))}
                </div>
            ` : ''}
        </div>
    `;
}

function renderTaskModal(task) {
    const modalBody = document.getElementById('modal-body');

    modalBody.innerHTML = `
        <h2>${escapeHtml(task.feature || 'Task Details')}</h2>

        <div class="detail-section">
            <h3>Task Information</h3>
            <div class="detail-grid">
                <div class="detail-item">
                    <div class="detail-label">Task ID</div>
                    <div class="detail-value">${escapeHtml(task.task_id)}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Priority</div>
                    <div class="detail-value">${task.priority.toFixed(2)} (${getPriorityLabel(task.priority)})</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Attempts</div>
                    <div class="detail-value">${task.attempts}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Severity</div>
                    <div class="detail-value">${escapeHtml(task.severity || 'N/A')}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Created At</div>
                    <div class="detail-value">${formatDate(task.created_at)}</div>
                </div>
                ${task.escalation_reason ? `
                    <div class="detail-item">
                        <div class="detail-label">Escalation Reason</div>
                        <div class="detail-value">${escapeHtml(task.escalation_reason)}</div>
                    </div>
                ` : ''}
            </div>
        </div>

        <div class="detail-section">
            <h3>Test Information</h3>
            <div class="detail-grid">
                <div class="detail-item">
                    <div class="detail-label">Test File</div>
                    <div class="detail-value"><code>${escapeHtml(task.code_path)}</code></div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Logs</div>
                    <div class="detail-value"><code>${escapeHtml(task.logs_path || 'N/A')}</code></div>
                </div>
            </div>
        </div>

        ${task.last_error ? `
            <div class="detail-section">
                <h3>Error Message</h3>
                <div class="code-block">${escapeHtml(task.last_error)}</div>
            </div>
        ` : ''}

        ${task.ai_diagnosis ? `
            <div class="detail-section">
                <h3>AI Diagnosis</h3>
                <div class="code-block">${escapeHtml(task.ai_diagnosis)}</div>
            </div>
        ` : ''}

        ${task.artifacts && task.artifacts.diff ? `
            <div class="detail-section">
                <h3>Code Changes</h3>
                <div class="code-block">${escapeHtml(task.artifacts.diff)}</div>
            </div>
        ` : ''}

        ${task.screenshots && task.screenshots.length > 0 ? `
            <div class="detail-section">
                <h3>Screenshots</h3>
                <div class="screenshots-grid">
                    ${task.screenshots.map(path => `
                        <div class="screenshot-item">
                            <div class="screenshot-path">${escapeHtml(path)}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : ''}

        ${task.attempt_history && task.attempt_history.length > 0 ? `
            <div class="detail-section">
                <h3>Attempt History</h3>
                <ul class="attempt-list">
                    ${task.attempt_history.map(attempt => `
                        <li class="attempt-item">
                            <div class="attempt-number">Attempt ${attempt.attempt}</div>
                            <div class="attempt-timestamp">${formatDate(attempt.timestamp)}</div>
                        </li>
                    `).join('')}
                </ul>
            </div>
        ` : ''}

        ${!task.resolved ? renderAnnotationForm(task) : renderResolvedAnnotation(task)}
    `;

    // Setup form submission if not resolved
    if (!task.resolved) {
        document.getElementById('annotation-form').addEventListener('submit', handleAnnotationSubmit);
    }

    showModal();
}

function renderAnnotationForm(task) {
    return `
        <div class="detail-section">
            <h3>Resolve Task</h3>
            <form id="annotation-form" class="annotation-form">
                <div class="form-group">
                    <label for="root_cause">Root Cause Category *</label>
                    <select id="root_cause" name="root_cause_category" required>
                        <option value="">Select root cause...</option>
                        <option value="selector_flaky">Selector Flaky</option>
                        <option value="timing_race_condition">Timing/Race Condition</option>
                        <option value="data_dependency">Data Dependency</option>
                        <option value="environment_config">Environment Configuration</option>
                        <option value="api_contract_changed">API Contract Changed</option>
                        <option value="browser_compatibility">Browser Compatibility</option>
                        <option value="authentication_issue">Authentication Issue</option>
                        <option value="unknown">Unknown</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="fix_strategy">Fix Strategy *</label>
                    <select id="fix_strategy" name="fix_strategy" required>
                        <option value="">Select strategy...</option>
                        <option value="update_selectors">Update Selectors</option>
                        <option value="add_explicit_waits">Add Explicit Waits</option>
                        <option value="mock_external_api">Mock External API</option>
                        <option value="fix_test_data">Fix Test Data</option>
                        <option value="update_assertions">Update Assertions</option>
                        <option value="refactor_test_logic">Refactor Test Logic</option>
                        <option value="report_bug">Report Bug</option>
                        <option value="other">Other</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="severity">Severity *</label>
                    <select id="severity" name="severity" required>
                        <option value="">Select severity...</option>
                        <option value="low">Low</option>
                        <option value="medium" selected>Medium</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="human_notes">Human Notes *</label>
                    <textarea id="human_notes" name="human_notes"
                              placeholder="Describe your findings, analysis, and resolution..."
                              required></textarea>
                </div>

                <div class="form-group">
                    <label for="patch_diff">Patch/Diff (Optional)</label>
                    <textarea id="patch_diff" name="patch_diff"
                              placeholder="Paste any code changes or patches applied..."></textarea>
                </div>

                <div class="form-actions">
                    <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-success">Resolve Task</button>
                </div>
            </form>
        </div>
    `;
}

function renderResolvedAnnotation(task) {
    return `
        <div class="detail-section">
            <h3>Resolution Details</h3>
            <div class="detail-grid">
                ${task.root_cause_category ? `
                    <div class="detail-item">
                        <div class="detail-label">Root Cause</div>
                        <div class="detail-value">${escapeHtml(task.root_cause_category)}</div>
                    </div>
                ` : ''}
                ${task.fix_strategy ? `
                    <div class="detail-item">
                        <div class="detail-label">Fix Strategy</div>
                        <div class="detail-value">${escapeHtml(task.fix_strategy)}</div>
                    </div>
                ` : ''}
                ${task.severity ? `
                    <div class="detail-item">
                        <div class="detail-label">Severity</div>
                        <div class="detail-value">${escapeHtml(task.severity)}</div>
                    </div>
                ` : ''}
                ${task.resolved_at ? `
                    <div class="detail-item">
                        <div class="detail-label">Resolved At</div>
                        <div class="detail-value">${formatDate(task.resolved_at)}</div>
                    </div>
                ` : ''}
            </div>
            ${task.human_notes ? `
                <div style="margin-top: 15px;">
                    <div class="detail-label">Human Notes</div>
                    <div class="code-block">${escapeHtml(task.human_notes)}</div>
                </div>
            ` : ''}
            ${task.patch_diff ? `
                <div style="margin-top: 15px;">
                    <div class="detail-label">Applied Patch</div>
                    <div class="code-block">${escapeHtml(task.patch_diff)}</div>
                </div>
            ` : ''}
        </div>
    `;
}

// Event Handlers
function handleAnnotationSubmit(e) {
    e.preventDefault();

    const formData = new FormData(e.target);
    const annotation = {
        root_cause_category: formData.get('root_cause_category'),
        fix_strategy: formData.get('fix_strategy'),
        severity: formData.get('severity'),
        human_notes: formData.get('human_notes'),
        patch_diff: formData.get('patch_diff') || ''
    };

    resolveTask(selectedTask.task_id, annotation);
}

// Modal Functions
function showModal() {
    document.getElementById('modal').style.display = 'block';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
    selectedTask = null;
}

// Utility Functions
function getPriorityClass(priority) {
    if (priority >= 0.7) return 'high';
    if (priority >= 0.3) return 'medium';
    return 'low';
}

function getPriorityLabel(priority) {
    if (priority >= 0.7) return 'High';
    if (priority >= 0.3) return 'Medium';
    return 'Low';
}

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleString();
}

function truncate(str, length) {
    if (!str) return '';
    return str.length > length ? str.substring(0, length) + '...' : str;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showLoading() {
    const container = document.getElementById('queue-list');
    container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading tasks...</p></div>';
}

function showError(message) {
    alert('Error: ' + message);
}

function showSuccess(message) {
    alert('Success: ' + message);
}
