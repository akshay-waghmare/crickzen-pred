# Scraper Performance Monitoring Guide (Async)

## 🎯 Purpose

This monitoring system tracks the health, performance, and reliability of the async scraper service. It uses Prometheus metrics and a `/status` endpoint for real-time observability.

---

## 📊 Monitoring Endpoints

### **GET /status**

Returns service health, state, and key metrics.

**Usage:**
```bash
curl http://localhost:5000/status
```

**Example Response:**
```json
{
  "status": "success",
  "data": {
    "state": "healthy",
    "score": 100,
    "uptime_seconds": 3600,
    "pids_count": 12,
    "memory_usage_mb": 450.5,
    "last_scrape_timestamp": 1715000000.0,
    "details": {
      "freshness": {
        "p50": 2.5,
        "p90": 5.1,
        "p99": 12.0
      },
      "consecutive_failures": 0,
      "reconciliation_warnings": []
    }
  }
}
```

### **GET /metrics**

Prometheus exposition format.

**Key Metrics:**
- `scraper_freshness_seconds`: Time since last successful scrape per match.
- `scraper_queue_depth`: Number of tasks waiting in scheduler.
- `scraper_active_tasks`: Number of tasks currently processing.
- `scraper_scrapes_total`: Counter of scrape attempts (success/failure).
- `scraper_browser_restarts_total`: Counter of browser recycles (stall recovery).
- `scraper_health_score`: Current health score (0-100).

---

## 🚨 Alerting Rules

### **1. Freshness Lag (Critical)**
Trigger if p90 freshness exceeds 60 seconds.
```yaml
- alert: ScraperFreshnessLag
  expr: scraper_freshness_seconds{quantile="0.9"} > 60
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Scraper data is stale (>60s)"
```

### **2. Stall Detected (Critical)**
Trigger if health score drops below 40 (FAILING state).
```yaml
- alert: ScraperStalled
  expr: scraper_health_score < 40
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Scraper service is stalled or failing"
```

### **3. High Queue Depth (Warning)**
Trigger if queue depth exceeds 100 tasks.
```yaml
- alert: ScraperHighQueue
  expr: scraper_queue_depth > 100
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Scraper queue backing up"
```

---

## 🚦 Health States

| State | Score | Description | Action |
|-------|-------|-------------|--------|
| **HEALTHY** | 100 | Normal operation | None |
| **DEGRADED** | 70 | High latency or minor errors | Monitor closely |
| **RECOVERING** | 50 | Automated recovery in progress | Wait for stabilization |
| **FAILING** | 30 | Stalled or critical errors | Manual intervention if persists |

---

## 🔍 Troubleshooting

### **Stall Recovery**
The service automatically attempts to recycle the browser pool if no successful scrapes occur for `STALENESS_THRESHOLD_SECONDS` (default 180s).
- Check logs for `Triggering automated recovery...`
- Check `scraper_browser_restarts_total` metric.

### **High Memory Usage**
- Check `memory_usage_mb` in `/status`.
- If > 2GB, consider restarting container or reducing `CONCURRENCY_CAP`.


#### **2. Memory Usage**
- ✅ **< 4 GB**: Healthy
- ⚠️ **4-8 GB**: Elevated
- 🔴 **> 8 GB**: Critical

#### **3. Concurrent Matches**
- ✅ **< 10 matches**: Normal load
- ⚠️ **10-20 matches**: High load
- 🔴 **> 20 matches**: Very high load

---

## 📈 Monitoring Commands

### **Quick Health Check**
```powershell
# Check if batching is needed (returns true/false)
curl http://localhost:5000/monitoring/performance | ConvertFrom-Json | Select-Object -ExpandProperty batching_recommendation | Select-Object should_enable_batching

# Get readiness score
curl http://localhost:5000/monitoring/performance | ConvertFrom-Json | Select-Object -ExpandProperty batching_recommendation | Select-Object readiness_score, score_interpretation
```

### **Monitor Current Load**
```powershell
# Watch key metrics every 30 seconds
while ($true) {
    $perf = curl http://localhost:5000/monitoring/performance | ConvertFrom-Json
    Write-Host "`n=== Performance Snapshot $(Get-Date -Format 'HH:mm:ss') ==="
    Write-Host "Active Matches: $($perf.current_performance.active_matches)"
    Write-Host "API Calls/Min: $($perf.current_performance.estimated_api_calls_per_minute)"
    Write-Host "Memory (MB): $($perf.current_performance.total_memory_mb)"
    Write-Host "Batching Needed: $($perf.batching_recommendation.should_enable_batching)"
    Write-Host "Score: $($perf.batching_recommendation.readiness_score)/100"
    Start-Sleep -Seconds 30
}
```

### **Track Performance Over Time**
```powershell
# Log performance metrics to file
$logFile = "performance_log_$(Get-Date -Format 'yyyyMMdd').json"
while ($true) {
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $perf = curl http://localhost:5000/monitoring/performance | ConvertFrom-Json
    
    $entry = @{
        timestamp = $timestamp
        active_matches = $perf.current_performance.active_matches
        api_calls_per_min = $perf.current_performance.estimated_api_calls_per_minute
        memory_mb = $perf.current_performance.total_memory_mb
        batching_score = $perf.batching_recommendation.readiness_score
    }
    
    $entry | ConvertTo-Json -Compress | Out-File -Append $logFile
    Write-Host "$timestamp - Logged: $($entry.active_matches) matches, $($entry.api_calls_per_min) calls/min, Score: $($entry.batching_score)"
    Start-Sleep -Seconds 300  # Log every 5 minutes
}
```

---

## 🎨 Dashboard View (Browser)

Create a simple HTML dashboard:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Scraper Performance Monitor</title>
    <script>
        async function refreshMetrics() {
            const response = await fetch('http://localhost:5000/monitoring/performance');
            const data = await response.json();
            
            document.getElementById('status').innerHTML = data.batching_recommendation.score_interpretation;
            document.getElementById('score').innerHTML = data.batching_recommendation.readiness_score + '/100';
            document.getElementById('matches').innerHTML = data.current_performance.active_matches;
            document.getElementById('api_calls').innerHTML = data.current_performance.estimated_api_calls_per_minute + '/min';
            document.getElementById('memory').innerHTML = data.current_performance.total_memory_mb + ' MB';
            
            document.getElementById('reasons').innerHTML = data.batching_recommendation.reasons
                .map(r => `<li>${r}</li>`).join('');
        }
        
        setInterval(refreshMetrics, 10000);  // Refresh every 10 seconds
        refreshMetrics();  // Initial load
    </script>
</head>
<body>
    <h1>Scraper Performance Monitor</h1>
    <div>
        <h2>Status: <span id="status">Loading...</span></h2>
        <p>Readiness Score: <strong id="score">-</strong></p>
    </div>
    <div>
        <h3>Current Metrics</h3>
        <ul>
            <li>Active Matches: <strong id="matches">-</strong></li>
            <li>API Calls: <strong id="api_calls">-</strong></li>
            <li>Memory Usage: <strong id="memory">-</strong></li>
        </ul>
    </div>
    <div>
        <h3>Analysis</h3>
        <ul id="reasons"></ul>
    </div>
</body>
</html>
```

Save as `performance_dashboard.html` and open in browser.

---

## 🔧 Troubleshooting

### **Issue: Endpoint returns 404**
**Cause:** Server not restarted after adding endpoint  
**Fix:** Restart scraper: `python crex_scraper_python/run_server.py`

### **Issue: Metrics seem inaccurate**
**Cause:** Estimation based on active scrapers  
**Fix:** For production, implement actual request counter in `cricket_data_service.py`

### **Issue: Memory values are 0**
**Cause:** Scrapers haven't updated resource usage yet  
**Fix:** Wait 30 seconds for first resource check, or trigger manually

---

## 📁 Batching Implementation (When Ready)

When monitoring shows batching is needed (`readiness_score >= 70`):

### **1. Activate Batching (5 minutes)**

```powershell
# 1. Switch to batched service
cd apps/scraper/crex_scraper_python/src
(Get-Content crex_scraper.py) -replace 'import cricket_data_service', 'import cricket_data_service_batched as cricket_data_service' | Set-Content crex_scraper.py

# 2. Set batch configuration (optional)
$env:BATCH_SIZE = "10"
$env:BATCH_FLUSH_INTERVAL = "5.0"

# 3. Restart scraper
cd ../..
python crex_scraper_python/run_server.py
```

### **2. Update Backend (2.5 hours)**

Follow the complete guide in:
- `BACKEND_BATCH_SUPPORT_PLAN.md` - Full implementation
- `IMPLEMENTATION_CHECKLIST.md` - Step-by-step tasks

### **3. Verify Performance Improvement**

After enabling batching, metrics should show:
- 📉 API calls reduced by ~90% (e.g., 1200/min → 120/min)
- 📉 Readiness score drops below 40
- ✅ Status changes to "🟢 No batching needed"

---

## 📊 Performance Baselines

Record your baseline metrics when system is healthy:

```powershell
# Create baseline snapshot
$baseline = curl http://localhost:5000/monitoring/performance | ConvertFrom-Json
$baseline | ConvertTo-Json -Depth 5 | Out-File "baseline_$(Get-Date -Format 'yyyyMMdd').json"

Write-Host "Baseline saved:"
Write-Host "  - Active Matches: $($baseline.current_performance.active_matches)"
Write-Host "  - API Calls/Min: $($baseline.current_performance.estimated_api_calls_per_minute)"
Write-Host "  - Memory: $($baseline.current_performance.total_memory_mb) MB"
Write-Host "  - Readiness Score: $($baseline.batching_recommendation.readiness_score)"
```

Compare future snapshots against this baseline to track degradation.

---

## ✅ Monitoring Checklist

**Daily:**
- [ ] Check `/monitoring/performance` endpoint
- [ ] Verify readiness score < 40
- [ ] Confirm no critical warnings

**Weekly:**
- [ ] Review performance logs
- [ ] Compare against baseline
- [ ] Check for trending issues

**When scaling up:**
- [ ] Monitor before adding matches
- [ ] Watch readiness score closely
- [ ] Have batching plan ready

**If score > 70:**
- [ ] Review BACKEND_BATCH_SUPPORT_PLAN.md
- [ ] Schedule implementation window
- [ ] Prepare rollback plan
- [ ] Implement batching

---

## 🎯 Summary

**Current State:**
- ✅ Monitoring endpoint active at `/monitoring/performance`
- ✅ Automatic batching recommendations
- ✅ Batching code ready (not active)
- ✅ Low-risk, high-visibility monitoring

**When to Act:**
- 🟢 Score 0-39: You're good, keep monitoring
- 🟡 Score 40-69: Watch closely, be ready
- 🔴 Score 70-100: Implement batching now

**Implementation Time When Needed:**
- Scraper batching: 5 minutes (just change import)
- Backend changes: 2.5 hours (follow plan)
- Testing: 1 hour
- **Total: ~3.5 hours**

The system will tell you exactly when optimization is needed!
