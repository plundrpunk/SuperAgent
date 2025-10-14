// SuperAgent Observability Dashboard - Real-Time WebSocket Client

// Configuration
const WEBSOCKET_URL = 'ws://localhost:3010/agent-events';
const METRICS_REFRESH_INTERVAL = 5000; // 5 seconds
const MAX_EVENTS_DISPLAY = 50;

// Global state
let ws = null;
let reconnectInterval = null;
let metricsInterval = null;
let isConnected = false;

// State tracking
const state = {
    costs: {
        current: 0,
        budget: 10.0,
        remaining: 10.0
    },
    agents: {
        kaya: { tasks: 0, cost: 0, active: false },
        scribe: { tasks: 0, cost: 0, active: false },
        runner: { tasks: 0, cost: 0, active: false },
        medic: { tasks: 0, cost: 0, active: false },
        critic: { tasks: 0, cost: 0, active: false },
        gemini: { tasks: 0, cost: 0, active: false }
    },
    activeTasks: new Map(),
    metrics: {
        testPassRate: 0,
        criticRejectionRate: 0,
        avgCompletionTime: 0,
        avgRetryCount: 0,
        hitlQueueDepth: 0,
        agentUtilization: 0
    },
    events: []
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing SuperAgent Observability Dashboard...');
    setupEventListeners();
    connectWebSocket();
    startMetricsRefresh();
});

// Event Listeners
function setupEventListeners() {
    document.getElementById('clear-events-btn').addEventListener('click', clearEvents);
}

// WebSocket Connection
function connectWebSocket() {
    console.log(`Connecting to WebSocket: ${WEBSOCKET_URL}`);

    try {
        ws = new WebSocket(WEBSOCKET_URL);

        ws.onopen = handleWebSocketOpen;
        ws.onmessage = handleWebSocketMessage;
        ws.onerror = handleWebSocketError;
        ws.onclose = handleWebSocketClose;
    } catch (error) {
        console.error('WebSocket connection error:', error);
        updateConnectionStatus(false);
        scheduleReconnect();
    }
}

function handleWebSocketOpen(event) {
    console.log('WebSocket connected successfully');
    isConnected = true;
    updateConnectionStatus(true);

    // Clear reconnect interval if exists
    if (reconnectInterval) {
        clearInterval(reconnectInterval);
        reconnectInterval = null;
    }
}

function handleWebSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        console.log('Received event:', data);

        // Handle connection established message
        if (data.event_type === 'connection_established') {
            console.log('Connection established:', data.message);
            return;
        }

        // Process event
        processEvent(data);
    } catch (error) {
        console.error('Error processing WebSocket message:', error);
    }
}

function handleWebSocketError(error) {
    console.error('WebSocket error:', error);
    updateConnectionStatus(false);
}

function handleWebSocketClose(event) {
    console.log('WebSocket connection closed:', event.code, event.reason);
    isConnected = false;
    updateConnectionStatus(false);
    scheduleReconnect();
}

function scheduleReconnect() {
    if (reconnectInterval) return;

    console.log('Scheduling reconnection in 3 seconds...');
    reconnectInterval = setInterval(() => {
        if (!isConnected) {
            console.log('Attempting to reconnect...');
            connectWebSocket();
        } else {
            clearInterval(reconnectInterval);
            reconnectInterval = null;
        }
    }, 3000);
}

function updateConnectionStatus(connected) {
    const indicator = document.getElementById('ws-status');
    const statusText = document.getElementById('ws-status-text');

    if (connected) {
        indicator.classList.add('connected');
        statusText.textContent = 'Connected';
    } else {
        indicator.classList.remove('connected');
        statusText.textContent = 'Disconnected';
    }
}

// Event Processing
function processEvent(event) {
    const eventType = event.event_type;
    const payload = event.payload;
    const timestamp = event.timestamp;

    // Add to events timeline
    addEventToTimeline(event);

    // Process based on event type
    switch (eventType) {
        case 'task_queued':
            handleTaskQueued(payload, timestamp);
            break;
        case 'agent_started':
            handleAgentStarted(payload, timestamp);
            break;
        case 'agent_completed':
            handleAgentCompleted(payload, timestamp);
            break;
        case 'validation_complete':
            handleValidationComplete(payload, timestamp);
            break;
        case 'hitl_escalated':
            handleHITLEscalated(payload, timestamp);
            break;
        case 'budget_warning':
        case 'budget_exceeded':
            handleBudgetAlert(payload, timestamp);
            break;
    }

    // Update displays
    updateCostDisplay();
    updateAgentDisplay();
    updateActiveTasksDisplay();
}

function handleTaskQueued(payload, timestamp) {
    const taskId = payload.task_id;
    const feature = payload.feature || 'Unknown';
    const estCost = payload.est_cost || 0;

    // Add to active tasks
    state.activeTasks.set(taskId, {
        id: taskId,
        feature: feature,
        status: 'queued',
        startTime: timestamp,
        agent: null,
        cost: 0,
        estCost: estCost
    });

    updateActiveTasksDisplay();
}

function handleAgentStarted(payload, timestamp) {
    const agent = payload.agent;
    const taskId = payload.task_id;

    // Update agent state
    if (state.agents[agent]) {
        state.agents[agent].active = true;
    }

    // Update task
    if (state.activeTasks.has(taskId)) {
        const task = state.activeTasks.get(taskId);
        task.status = 'running';
        task.agent = agent;
    }

    updateAgentDisplay();
    updateActiveTasksDisplay();
}

function handleAgentCompleted(payload, timestamp) {
    const agent = payload.agent;
    const taskId = payload.task_id;
    const cost = payload.cost_usd || 0;
    const status = payload.status;

    // Update agent state
    if (state.agents[agent]) {
        state.agents[agent].active = false;
        state.agents[agent].tasks += 1;
        state.agents[agent].cost += cost;
    }

    // Update costs
    state.costs.current += cost;
    state.costs.remaining = state.costs.budget - state.costs.current;

    // Update or remove task
    if (state.activeTasks.has(taskId)) {
        const task = state.activeTasks.get(taskId);
        task.cost += cost;

        if (status === 'success' || status === 'completed') {
            // Remove from active tasks after a delay
            setTimeout(() => {
                state.activeTasks.delete(taskId);
                updateActiveTasksDisplay();
            }, 2000);
        } else {
            task.status = status;
        }
    }

    updateCostDisplay();
    updateAgentDisplay();
    updateActiveTasksDisplay();
}

function handleValidationComplete(payload, timestamp) {
    const taskId = payload.task_id;
    const result = payload.result || {};
    const cost = payload.cost || 0;

    // Update costs
    state.costs.current += cost;
    state.costs.remaining = state.costs.budget - state.costs.current;

    // Update task
    if (state.activeTasks.has(taskId)) {
        const task = state.activeTasks.get(taskId);
        task.cost += cost;
        task.status = result.test_passed ? 'passed' : 'failed';
    }

    // Update metrics (simple estimation)
    // In production, these would come from Redis metrics
    updateMetricsEstimate('validation', result.test_passed);

    updateCostDisplay();
    updateActiveTasksDisplay();
}

function handleHITLEscalated(payload, timestamp) {
    const taskId = payload.task_id;

    // Update task
    if (state.activeTasks.has(taskId)) {
        const task = state.activeTasks.get(taskId);
        task.status = 'escalated';
    }

    // Update HITL queue depth
    state.metrics.hitlQueueDepth += 1;

    updateActiveTasksDisplay();
    updateMetricsDisplay();
}

function handleBudgetAlert(payload, timestamp) {
    state.costs.current = payload.current_spend || state.costs.current;
    state.costs.budget = payload.limit || state.costs.budget;
    state.costs.remaining = payload.remaining || state.costs.remaining;

    updateCostDisplay();
}

// Metrics Refresh
function startMetricsRefresh() {
    metricsInterval = setInterval(() => {
        // In production, fetch metrics from Redis via API
        // For now, we use estimated values from events
        updateMetricsDisplay();
    }, METRICS_REFRESH_INTERVAL);
}

function updateMetricsEstimate(type, success) {
    // Simple client-side estimation
    // In production, fetch from server API
    if (type === 'validation') {
        // Track validation success rate
        const current = state.metrics.testPassRate;
        state.metrics.testPassRate = success ?
            Math.min(100, current + 1) :
            Math.max(0, current - 1);
    }
}

// Display Updates
function updateCostDisplay() {
    const current = state.costs.current;
    const budget = state.costs.budget;
    const remaining = Math.max(0, state.costs.remaining);
    const percentUsed = Math.min(100, (current / budget) * 100);

    document.getElementById('current-spend').textContent = `$${current.toFixed(2)}`;
    document.getElementById('budget').textContent = `$${budget.toFixed(2)}`;
    document.getElementById('remaining').textContent = `$${remaining.toFixed(2)}`;
    document.getElementById('percent-used').textContent = `${percentUsed.toFixed(0)}%`;

    // Update progress bar
    const progressBar = document.getElementById('cost-bar-fill');
    progressBar.style.width = `${percentUsed}%`;
}

function updateAgentDisplay() {
    const agents = ['kaya', 'scribe', 'runner', 'medic', 'critic', 'gemini'];

    agents.forEach(agentName => {
        const agent = state.agents[agentName];
        const card = document.querySelector(`.agent-card[data-agent="${agentName}"]`);

        if (!card || !agent) return;

        // Update status badge
        const badge = card.querySelector('.agent-badge');
        if (agent.active) {
            badge.classList.remove('idle');
            badge.classList.add('active');
            badge.textContent = 'Active';
        } else {
            badge.classList.remove('active');
            badge.classList.add('idle');
            badge.textContent = 'Idle';
        }

        // Update stats
        card.querySelector(`#${agentName}-tasks`).textContent = agent.tasks;
        card.querySelector(`#${agentName}-cost`).textContent = `$${agent.cost.toFixed(2)}`;
    });
}

function updateActiveTasksDisplay() {
    const container = document.getElementById('active-tasks-container');

    if (state.activeTasks.size === 0) {
        container.innerHTML = '<div class="empty-state">No active tasks</div>';
        return;
    }

    let html = '';
    state.activeTasks.forEach((task, taskId) => {
        const statusColor = getStatusColor(task.status);
        html += `
            <div class="task-item" style="border-left-color: ${statusColor}">
                <div class="task-header">
                    <div>
                        <div class="task-id">${escapeHtml(task.id)}</div>
                        <div class="task-feature">${escapeHtml(task.feature)}</div>
                    </div>
                    <span class="agent-badge ${task.agent ? 'active' : 'idle'}">${task.status}</span>
                </div>
                <div class="task-meta">
                    ${task.agent ? `<span><strong>Agent:</strong> ${escapeHtml(task.agent)}</span>` : ''}
                    <span><strong>Cost:</strong> $${task.cost.toFixed(2)}</span>
                    <span><strong>Est. Cost:</strong> $${task.estCost.toFixed(2)}</span>
                    <span><strong>Duration:</strong> ${getDuration(task.startTime)}s</span>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function updateMetricsDisplay() {
    document.getElementById('test-pass-rate').textContent =
        `${state.metrics.testPassRate.toFixed(0)}%`;
    document.getElementById('critic-rejection-rate').textContent =
        `${state.metrics.criticRejectionRate.toFixed(0)}%`;
    document.getElementById('avg-completion-time').textContent =
        `${state.metrics.avgCompletionTime.toFixed(0)}s`;
    document.getElementById('avg-retry-count').textContent =
        state.metrics.avgRetryCount.toFixed(1);
    document.getElementById('hitl-queue-depth').textContent =
        state.metrics.hitlQueueDepth;
    document.getElementById('agent-utilization').textContent =
        `${state.metrics.agentUtilization.toFixed(0)}%`;
}

// Events Timeline
function addEventToTimeline(event) {
    // Add to state
    state.events.unshift(event);

    // Keep only last MAX_EVENTS_DISPLAY events
    if (state.events.length > MAX_EVENTS_DISPLAY) {
        state.events = state.events.slice(0, MAX_EVENTS_DISPLAY);
    }

    // Update display
    renderEventsTimeline();
}

function renderEventsTimeline() {
    const container = document.getElementById('events-timeline');

    if (state.events.length === 0) {
        container.innerHTML = '<div class="empty-state">No events yet</div>';
        return;
    }

    let html = '';
    state.events.forEach(event => {
        html += createEventHTML(event);
    });

    container.innerHTML = html;
}

function createEventHTML(event) {
    const eventType = event.event_type;
    const payload = event.payload;
    const timestamp = new Date(event.timestamp * 1000);
    const timeStr = timestamp.toLocaleTimeString();

    let detailsHTML = '';
    Object.entries(payload).forEach(([key, value]) => {
        if (key === 'timestamp') return; // Skip timestamp in payload

        // Handle nested objects
        let displayValue = value;
        if (typeof value === 'object' && value !== null) {
            displayValue = JSON.stringify(value, null, 2);
        }

        detailsHTML += `
            <div class="event-detail">
                <div class="detail-label">${escapeHtml(key)}</div>
                <div class="detail-value">${escapeHtml(String(displayValue))}</div>
            </div>
        `;
    });

    return `
        <div class="event-item ${eventType}">
            <div class="event-header">
                <span class="event-type">${formatEventType(eventType)}</span>
                <span class="event-timestamp">${timeStr}</span>
            </div>
            <div class="event-details">
                ${detailsHTML}
            </div>
        </div>
    `;
}

function clearEvents() {
    state.events = [];
    renderEventsTimeline();
}

// Utility Functions
function getStatusColor(status) {
    const colors = {
        'queued': '#1890ff',
        'running': '#52c41a',
        'passed': '#52c41a',
        'failed': '#f5222d',
        'escalated': '#faad14',
        'completed': '#4a90e2'
    };
    return colors[status] || '#7f8c8d';
}

function getDuration(startTime) {
    const now = Date.now() / 1000;
    return Math.floor(now - startTime);
}

function formatEventType(eventType) {
    return eventType
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (ws) {
        ws.close();
    }
    if (reconnectInterval) {
        clearInterval(reconnectInterval);
    }
    if (metricsInterval) {
        clearInterval(metricsInterval);
    }
});

// Export for debugging
window.dashboardState = state;
window.dashboardWS = () => ws;
