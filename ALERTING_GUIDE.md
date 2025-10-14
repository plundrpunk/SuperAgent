# SuperAgent Alert System Configuration Guide

## Overview

The SuperAgent Alert System monitors key metrics and sends notifications when thresholds are exceeded. This helps detect and respond to system health issues proactively.

## Features

- **Configurable Thresholds**: Define alert conditions in YAML
- **Multiple Notification Channels**: Console, webhook, and email
- **Rate Limiting**: Prevents alert fatigue (max 1 alert per condition per 10 minutes)
- **Alert History**: Track and query triggered alerts
- **Integration**: Works seamlessly with MetricsAggregator

## Architecture

```
MetricsAggregator → AlertManager → Notification Channels
     (metrics)         (checks)      (console/webhook/email)
```

## Configuration

### Alert Conditions

Alert conditions are defined in `.claude/observability.yaml`:

```yaml
alerts:
  - condition: "critic_rejection_rate > 0.50"
    action: "notify_admin"
    message: "Critic rejecting >50% of tests - check test quality"

  - condition: "validation_pass_rate < 0.70"
    action: "notify_admin"
    message: "Validation pass rate <70% - investigate failures"

  - condition: "cost_per_feature > 1.00"
    action: "warn_user"
    message: "Cost per feature exceeding $1.00 - review complexity"

  - condition: "average_retry_count > 2.0"
    action: "notify_admin"
    message: "High retry rate - check medic effectiveness"
```

### Condition Syntax

Format: `<metric> <operator> <threshold>`

**Supported Operators:**
- `>` - Greater than
- `<` - Less than
- `>=` - Greater than or equal
- `<=` - Less than or equal
- `==` - Equal to
- `!=` - Not equal to

**Available Metrics:**
- `critic_rejection_rate` - Percentage of tests rejected by Critic (0.0-1.0)
- `validation_pass_rate` - Percentage of validations that pass (0.0-1.0)
- `cost_per_feature` - Average cost per completed feature (USD)
- `average_retry_count` - Average number of retries per task
- `agent_utilization` - Percentage of time agents are active (0.0-1.0)
- `time_to_completion` - Average time from queue to completion (seconds)

### Actions

- `notify_admin` - High-priority alert (red console output, admin webhook/email)
- `warn_user` - Lower-priority warning (yellow console output, user notification)

## Notification Channels

### Console (Always Enabled)

Console notifications are color-coded:
- **Red** - `notify_admin` alerts
- **Yellow** - `warn_user` alerts

Example output:
```
[ALERT] 2025-10-14 10:30:00
Metric: critic_rejection_rate
Condition: > 0.5
Current Value: 0.6000
Action: notify_admin
Message: Critic rejecting >50% of tests - check test quality
```

### Webhook

Enable webhook notifications via environment variables:

```bash
ALERT_WEBHOOK_URL=https://your-webhook-endpoint.com/alerts
```

Or programmatically:

```python
from agent_system.observability import AlertManager

manager = AlertManager(
    webhook_enabled=True,
    webhook_url='https://your-webhook-endpoint.com/alerts'
)
```

**Webhook Payload:**

```json
{
  "metric": "critic_rejection_rate",
  "operator": ">",
  "threshold": 0.5,
  "current_value": 0.6,
  "action": "notify_admin",
  "message": "Critic rejecting >50% of tests - check test quality",
  "timestamp": 1760461637.42,
  "timestamp_iso": "2025-10-14T10:30:37.420000"
}
```

### Email (SMTP)

Configure email notifications via environment variables:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_EMAIL_FROM=alerts@example.com
ALERT_EMAIL_TO=admin@example.com,team@example.com
```

Or programmatically:

```python
manager = AlertManager(
    email_enabled=True,
    smtp_host='smtp.gmail.com',
    smtp_port=587,
    smtp_username='your-email@gmail.com',
    smtp_password='your-app-password',
    email_from='alerts@example.com',
    email_to=['admin@example.com', 'team@example.com']
)
```

## Usage

### Basic Usage

```python
from agent_system.observability import EventEmitter, AlertManager

# Create emitter (with metrics aggregation)
emitter = EventEmitter()

# Create alert manager
alert_manager = AlertManager()

# Get current metrics
metrics = emitter.get_metrics()

# Check for alerts
triggered_alerts = alert_manager.check_alerts(metrics)

if triggered_alerts:
    print(f"⚠ {len(triggered_alerts)} alerts triggered!")
    for alert in triggered_alerts:
        print(f"  - {alert.condition.metric}: {alert.metric_value}")
```

### Integration with Event Stream

```python
import time
from agent_system.observability import emit_event, get_emitter, AlertManager

# Get global emitter
emitter = get_emitter()

# Create alert manager
alert_manager = AlertManager()

# Emit some events (these update metrics)
emit_event('task_queued', {
    'task_id': 't_001',
    'feature': 'login_test',
    'est_cost': 0.50,
    'timestamp': time.time()
})

emit_event('agent_completed', {
    'agent': 'scribe',
    'task_id': 't_001',
    'status': 'success',
    'duration_ms': 2000,
    'cost_usd': 0.15
})

# Periodically check metrics and trigger alerts
metrics = emitter.get_metrics()
alert_manager.check_alerts(metrics)
```

### Alert History

```python
# Get all alerts
all_alerts = alert_manager.alert_history

# Filter by metric
critic_alerts = alert_manager.get_alert_history(
    metric='critic_rejection_rate'
)

# Filter by time
import time
one_hour_ago = time.time() - 3600
recent_alerts = alert_manager.get_alert_history(
    since=one_hour_ago
)

# Limit results
last_5_alerts = alert_manager.get_alert_history(limit=5)
```

### Alert Statistics

```python
stats = alert_manager.get_stats()

print(f"Total alerts: {stats['total_alerts']}")
print(f"Alerts by metric: {stats['alerts_by_metric']}")
print(f"Alerts by action: {stats['alerts_by_action']}")

if stats['most_recent']:
    print(f"Most recent: {stats['most_recent']['metric']} at {stats['most_recent']['timestamp_iso']}")
```

## Rate Limiting

Alerts are rate-limited to prevent notification spam:

- **Default**: 1 alert per condition per 10 minutes
- **Configurable**: Set `rate_limit_seconds` parameter

```python
# Custom rate limit (5 minutes)
manager = AlertManager(rate_limit_seconds=300)
```

Rate limiting is per-condition, so different alerts can still fire:

```python
# First check - triggers critic alert
metrics = {'critic_rejection_rate': 0.60}
manager.check_alerts(metrics)  # Alert sent

# Second check immediately - rate limited
manager.check_alerts(metrics)  # No alert (rate limited)

# Third check with different condition - not rate limited
metrics = {'validation_pass_rate': 0.65}
manager.check_alerts(metrics)  # Alert sent (different condition)
```

### Reset Rate Limits

For testing or emergency situations:

```python
manager.reset_rate_limits()
```

## Recommended Alert Thresholds

Based on SuperAgent's target metrics:

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| `critic_rejection_rate` | > 0.50 | Critic should reject 15-30% normally |
| `validation_pass_rate` | < 0.70 | Target 95%+ pass rate |
| `cost_per_feature` | > 1.00 | Target $0.50 per feature |
| `average_retry_count` | > 2.0 | Target ≤1.5 retries per failure |

## Example: Automated Monitoring

```python
#!/usr/bin/env python3
"""
Automated alert monitoring script.
Run periodically (e.g., via cron) to check system health.
"""
import time
from agent_system.observability import get_emitter, AlertManager

def monitor_alerts():
    """Check metrics and send alerts."""
    emitter = get_emitter()
    alert_manager = AlertManager(
        console_enabled=True,
        webhook_enabled=True,
        webhook_url='https://your-webhook-endpoint.com/alerts'
    )

    # Get current metrics
    metrics = emitter.get_metrics()

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking metrics...")
    print(f"  critic_rejection_rate: {metrics.get('critic_rejection_rate', 0):.2%}")
    print(f"  validation_pass_rate: {metrics.get('validation_pass_rate', 0):.2%}")
    print(f"  cost_per_feature: ${metrics.get('cost_per_feature', 0):.2f}")
    print(f"  average_retry_count: {metrics.get('average_retry_count', 0):.2f}")

    # Check for alerts
    triggered = alert_manager.check_alerts(metrics)

    if triggered:
        print(f"\n⚠ {len(triggered)} alerts triggered!")
        for alert in triggered:
            print(f"  - {alert.condition.message}")
    else:
        print("\n✓ All metrics within normal bounds")

    return len(triggered)

if __name__ == '__main__':
    alert_count = monitor_alerts()
    exit(alert_count)  # Exit with alert count (0 = success)
```

Run via cron:

```bash
# Check every 15 minutes
*/15 * * * * cd /path/to/SuperAgent && ./monitor_alerts.py >> /var/log/superagent-alerts.log 2>&1
```

## Testing

Run the test suite:

```bash
# Activate virtual environment
source venv/bin/activate

# Run alerting tests
pytest tests/unit/test_alerting.py -v

# With coverage
pytest tests/unit/test_alerting.py --cov=agent_system.observability.alerting --cov-report=html
```

## Troubleshooting

### Alerts Not Triggering

1. **Check config file**: Ensure `.claude/observability.yaml` exists and is valid YAML
2. **Verify metrics**: Print metrics to ensure they're being calculated correctly
3. **Check thresholds**: Verify metric values actually exceed thresholds
4. **Rate limiting**: Check if alerts are rate-limited (call `reset_rate_limits()`)

```python
# Debug mode
manager = AlertManager(console_enabled=True)
metrics = emitter.get_metrics()

print("Current metrics:", metrics)
print("Alert conditions:", [(c.metric, c.operator, c.threshold) for c in manager.conditions])

triggered = manager.check_alerts(metrics)
print(f"Triggered: {len(triggered)} alerts")
```

### Webhook Not Working

1. **Check URL**: Verify webhook URL is correct
2. **Test connectivity**: Use curl to test endpoint
3. **Check logs**: Look for error messages in console output
4. **Verify payload**: Check webhook expects JSON payload

```bash
# Test webhook endpoint
curl -X POST https://your-webhook-endpoint.com/alerts \
  -H "Content-Type: application/json" \
  -d '{"metric": "test", "value": 1.0}'
```

### Email Not Sending

1. **Check SMTP credentials**: Verify username/password are correct
2. **Port/TLS**: Most SMTP servers use port 587 with STARTTLS
3. **App passwords**: For Gmail, use app-specific passwords, not account password
4. **Firewall**: Ensure port 587 is not blocked

```python
# Test email configuration
import smtplib

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('your-email@gmail.com', 'your-app-password')
    print("✓ SMTP connection successful")
    server.quit()
except Exception as e:
    print(f"✗ SMTP connection failed: {e}")
```

## Best Practices

1. **Set appropriate thresholds**: Too sensitive = alert fatigue, too lenient = missed issues
2. **Use rate limiting**: Prevents notification spam during incidents
3. **Monitor alert history**: Review trends to tune thresholds
4. **Test notifications**: Verify webhooks and emails work before relying on them
5. **Combine channels**: Use console for development, webhook/email for production
6. **Document responses**: Create runbooks for each alert type

## Related Documentation

- **Event Streaming**: See `OBSERVABILITY_IMPLEMENTATION_SUMMARY.md`
- **Metrics**: See `agent_system/observability/event_stream.py`
- **Configuration**: See `.claude/observability.yaml`

## Support

For issues or questions:
- Check test files: `tests/unit/test_alerting.py`
- Review example: `examples/alerting_example.py`
- Read source: `agent_system/observability/alerting.py`
