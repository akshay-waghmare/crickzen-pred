/**
 * CrickenZen Dashboard — Main client-side logic.
 *
 * Alpine.js store + Chart.js charts for live T20 win probability display.
 * Handles: polling, token refresh, gauges, probability timeline, run-rate chart.
 */

/* global Alpine, Chart, POLL_INTERVAL_MS */

// ── Chart.js defaults (dark theme) ──────────────────────────────────────
Chart.defaults.color = '#94a3b8';          // text-gray-400
Chart.defaults.borderColor = '#1e293b';    // surface-800
Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

// ── Centre-label plugin for half-donut gauges ──────────────────────────
const gaugeCentreLabel = {
  id: 'gaugeCentreLabel',
  afterDraw(chart) {
    const { ctx, chartArea: { left, right, bottom } } = chart;
    const pct = chart.data.datasets[0].data[0];
    if (pct == null) return;

    const cx = (left + right) / 2;
    const cy = bottom - 4;
    const label = `${Math.round(pct * 100)}%`;

    ctx.save();
    ctx.font = 'bold 18px Inter, system-ui, sans-serif';
    ctx.fillStyle = '#f1f5f9';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillText(label, cx, cy);
    ctx.restore();
  },
};

// ── Phase-boundary annotation helper ────────────────────────────────────
function phaseLines() {
  return [
    { over: 6, label: 'PP' },
    { over: 16, label: 'Death' },
  ];
}

// ── Colour helpers ──────────────────────────────────────────────────────
const TEAM_EMERALD = '#10b981';
const TEAM_ROSE    = '#f43f5e';
const GRID_COLOUR  = 'rgba(51,65,85,0.5)';  // surface-700 @ 50%

// ── Alpine store ────────────────────────────────────────────────────────
document.addEventListener('alpine:init', () => {

  Alpine.store('dashboard', {
    // ── reactive state ──
    accessToken: null,
    state: null,
    isLive: false,
    isStale: false,
    error: null,
    selectedLeague: '',
    pollIntervalMs: 1500,   // fast poll — ETag 304 is nearly free
    etag: null,
    newBall: false,         // true for 800ms after each new ball
    lastBallKey: null,      // '<innings>.<over>.<ball>.<score>' to detect changes
    ballCount: 0,           // total balls received this session

    // ── internal handles ──
    _pollTimer: null,
    _refreshTimer: null,
    _newBallTimer: null,
    _probChart: null,
    _rrChart: null,
    _gaugeHome: null,
    _gaugeAway: null,

    // ────────────────────────────────────────────────────────────────────
    // init: called from x-init on dashboard page
    // ────────────────────────────────────────────────────────────────────
    init() {
      this.accessToken = sessionStorage.getItem('access_token');
      if (!this.accessToken) {
        window.location.href = '/login';
        return;
      }
      this.scheduleRefresh();
      this.startPollLoop();
    },

    // ────────────────────────────────────────────────────────────────────
    // Polling
    // ────────────────────────────────────────────────────────────────────
    startPollLoop() {
      // First fetch immediately
      this.fetchState();
      // Then repeat on interval
      this._pollTimer = setInterval(() => this.fetchState(), this.pollIntervalMs);
    },

    stopPollLoop() {
      if (this._pollTimer) {
        clearInterval(this._pollTimer);
        this._pollTimer = null;
      }
    },

    async fetchState() {
      try {
        const headers = {
          'Authorization': `Bearer ${this.accessToken}`,
        };
        if (this.etag) {
          headers['If-None-Match'] = this.etag;
        }

        let url = '/api/live-state';
        if (this.selectedLeague) {
          url += `?league=${encodeURIComponent(this.selectedLeague)}`;
        }

        const resp = await fetch(url, { headers, credentials: 'include' });

        if (resp.status === 304) {
          // Not Modified — keep existing state
          return;
        }

        if (resp.status === 401) {
          // Token expired — try refresh once
          const refreshed = await this._tryRefresh();
          if (refreshed) {
            return this.fetchState();
          }
          this.logout();
          return;
        }

        if (resp.status === 404) {
          // No live data available
          this.state = null;
          this.isLive = false;
          this.isStale = false;
          this.error = null;
          return;
        }

        if (!resp.ok) {
          this.error = `Server error (${resp.status})`;
          return;
        }

        const data = await resp.json();
        const newEtag = resp.headers.get('ETag');
        if (newEtag) this.etag = newEtag;

        // Detect a new ball (over/ball/score changed)
        const ballKey = `${data.is_second_innings ? 2 : 1}.${data.over}.${data.ball}.${data.score}`;
        const isNewBall = this.lastBallKey !== null && ballKey !== this.lastBallKey;
        if (isNewBall) {
          this.ballCount++;
          this.newBall = true;
          if (this._newBallTimer) clearTimeout(this._newBallTimer);
          this._newBallTimer = setTimeout(() => { this.newBall = false; }, 800);
        }
        this.lastBallKey = ballKey;

        // Update state
        this.state = data;
        this.isStale = !!data.stale;
        this.isLive = !data.stale && !data.match_over;
        this.error = null;

        // Update charts on next tick (DOM needs to render canvas first)
        this.$nextTick(() => this._updateCharts(data));

      } catch (err) {
        console.error('[CrickenZen] Poll error:', err);
        this.error = 'Connection lost. Retrying…';
      }
    },

    // ────────────────────────────────────────────────────────────────────
    // Silent token refresh
    // ────────────────────────────────────────────────────────────────────
    scheduleRefresh() {
      if (this._refreshTimer) clearTimeout(this._refreshTimer);

      const issuedAt = parseInt(sessionStorage.getItem('token_issued_at') || '0', 10);
      const expiresIn = parseInt(sessionStorage.getItem('token_expires_in') || '3300', 10);
      const expiresAt = issuedAt + expiresIn * 1000;
      const refreshIn = expiresAt - Date.now() - 5 * 60 * 1000; // 5 min before expiry

      if (refreshIn <= 0) {
        // Already close to or past expiry — refresh now
        this._tryRefresh();
        return;
      }

      this._refreshTimer = setTimeout(async () => {
        await this._tryRefresh();
      }, refreshIn);
    },

    async _tryRefresh() {
      try {
        const resp = await fetch('/auth/refresh', {
          method: 'POST',
          credentials: 'include',
        });
        if (!resp.ok) return false;

        const data = await resp.json();
        this.accessToken = data.access_token;
        sessionStorage.setItem('access_token', data.access_token);
        sessionStorage.setItem('token_expires_in', data.expires_in.toString());
        sessionStorage.setItem('token_issued_at', Date.now().toString());
        this.scheduleRefresh();
        return true;
      } catch (err) {
        console.error('[CrickenZen] Refresh failed:', err);
        return false;
      }
    },

    // ────────────────────────────────────────────────────────────────────
    // Logout
    // ────────────────────────────────────────────────────────────────────
    async logout() {
      this.stopPollLoop();
      if (this._refreshTimer) clearTimeout(this._refreshTimer);

      try {
        await fetch('/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${this.accessToken}` },
          credentials: 'include',
        });
      } catch (_) { /* best-effort */ }

      sessionStorage.removeItem('access_token');
      sessionStorage.removeItem('token_expires_in');
      sessionStorage.removeItem('token_issued_at');
      this.accessToken = null;
      window.location.href = '/login';
    },

    // ────────────────────────────────────────────────────────────────────
    // Chart updates
    // ────────────────────────────────────────────────────────────────────
    _updateCharts(data) {
      this._updateGauges(data);
      this._updateProbChart(data);
      this._updateRRChart(data);
    },

    // ── Half-donut gauges ──
    _updateGauges(data) {
      // Use final calibrated prob; fall back to bat_win_prob which is the same value
      const batProb = data.calibrated_per_over_prob ?? data.bat_win_prob ?? 0.5;
      const bowlProb = 1 - batProb;

      // Home gauge (batting team)
      this._gaugeHome = this._renderGauge(
        'gauge-home', this._gaugeHome, batProb, TEAM_EMERALD
      );

      // Away gauge (bowling team)
      this._gaugeAway = this._renderGauge(
        'gauge-away', this._gaugeAway, bowlProb, TEAM_ROSE
      );
    },

    _renderGauge(canvasId, existingChart, probability, colour) {
      const canvas = document.getElementById(canvasId);
      if (!canvas) return existingChart;

      if (existingChart) {
        existingChart.data.datasets[0].data = [probability, 1 - probability];
        existingChart.update('active');
        return existingChart;
      }

      return new Chart(canvas, {
        type: 'doughnut',
        data: {
          datasets: [{
            data: [probability, 1 - probability],
            backgroundColor: [colour, 'rgba(51,65,85,0.4)'],
            borderWidth: 0,
            circumference: 180,
            rotation: -90,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '72%',
          plugins: {
            legend: { display: false },
            tooltip: { enabled: false },
          },
          animation: {
            animateRotate: true,
            duration: 600,
            easing: 'easeOutQuart',
          },
        },
        plugins: [gaugeCentreLabel],
      });
    },

    // ── Probability timeline chart ──
    _updateProbChart(data) {
      const history = data.history || [];
      if (history.length === 0) return;

      // history items use: { overs, bat_prob, bowl_prob, score, wickets, innings }
      const labels = history.map(h => {
        const o = h.overs ?? h.over ?? '';
        return o !== '' ? parseFloat(o).toFixed(1) : '';
      });
      const probs = history.map(h => h.bat_prob ?? h.bat_win_prob ?? 0.5);

      // Detect wickets by comparing successive wickets counts
      const wicketData = history
        .map((h, i) => {
          if (i === 0) return null;
          const wktDiff = (h.wickets ?? 0) - (history[i - 1].wickets ?? 0);
          return wktDiff > 0 ? { x: i, y: h.bat_prob ?? h.bat_win_prob ?? 0.5 } : null;
        })
        .filter(Boolean);

      const canvas = document.getElementById('prob-chart');
      if (!canvas) return;

      if (this._probChart) {
        // Update existing chart
        this._probChart.data.labels = labels;
        this._probChart.data.datasets[0].data = probs;
        this._probChart.data.datasets[1].data = wicketData;
        // Update phase lines
        this._probChart.options.plugins.annotation = this._phaseAnnotations(history);
        this._probChart.update('active');
        return;
      }

      // Create new chart
      this._probChart = new Chart(canvas, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Win Probability',
              data: probs,
              borderColor: TEAM_EMERALD,
              backgroundColor: 'rgba(16,185,129,0.1)',
              borderWidth: 2,
              pointRadius: 0,
              pointHitRadius: 8,
              fill: true,
              tension: 0.3,
            },
            {
              label: 'Wickets',
              data: wicketData,
              type: 'scatter',
              pointRadius: 6,
              pointStyle: 'crossRot',
              pointBorderColor: TEAM_ROSE,
              pointBackgroundColor: TEAM_ROSE,
              showLine: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: 'index',
            intersect: false,
          },
          scales: {
            x: {
              grid: { color: GRID_COLOUR },
              ticks: {
                maxTicksLimit: 12,
                font: { size: 10 },
              },
            },
            y: {
              min: 0,
              max: 1,
              grid: { color: GRID_COLOUR },
              ticks: {
                callback: v => `${Math.round(v * 100)}%`,
                stepSize: 0.25,
                font: { size: 10 },
              },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: ctx => {
                  if (ctx.dataset.label === 'Wickets') return '🏏 Wicket!';
                  return `Win: ${Math.round(ctx.parsed.y * 100)}%`;
                },
              },
            },
            annotation: this._phaseAnnotations(history),
          },
          animation: {
            duration: 400,
            easing: 'easeOutQuart',
          },
        },
      });
    },

    _phaseAnnotations(history) {
      // Find indices where over crosses phase boundaries
      const annotations = {};
      const boundaries = phaseLines();

      for (const { over, label } of boundaries) {
        // history items use 'overs' (e.g. 6.0) not 'over'
        const idx = history.findIndex(h => parseFloat(h.overs ?? h.over ?? 0) >= over);
        if (idx > 0) {
          annotations[`phase_${over}`] = {
            type: 'line',
            xMin: idx,
            xMax: idx,
            borderColor: 'rgba(148,163,184,0.3)',
            borderWidth: 1,
            borderDash: [4, 4],
            label: {
              display: true,
              content: label,
              position: 'start',
              color: '#64748b',
              font: { size: 10, weight: 'normal' },
              backgroundColor: 'transparent',
            },
          };
        }
      }

      // Innings boundary (over 20 = start of 2nd innings, but data may not label it)
      const inn2Start = history.findIndex(h => h.innings === 2);
      if (inn2Start > 0) {
        annotations.innings_break = {
          type: 'line',
          xMin: inn2Start,
          xMax: inn2Start,
          borderColor: 'rgba(250,204,21,0.5)',
          borderWidth: 2,
          borderDash: [6, 3],
          label: {
            display: true,
            content: 'Inn 2',
            position: 'start',
            color: '#fbbf24',
            font: { size: 10, weight: 'bold' },
            backgroundColor: 'transparent',
          },
        };
      }

      return { annotations };
    },

    // ── Run-rate bar chart ──
    _updateRRChart(data) {
      if (!data.is_second_innings) return;

      const crr = data.current_run_rate || 0;
      const rrr = data.required_run_rate || 0;

      const canvas = document.getElementById('rr-chart');
      if (!canvas) return;

      if (this._rrChart) {
        this._rrChart.data.datasets[0].data = [crr, rrr];
        this._rrChart.update('active');
        return;
      }

      this._rrChart = new Chart(canvas, {
        type: 'bar',
        data: {
          labels: ['CRR', 'RRR'],
          datasets: [{
            data: [crr, rrr],
            backgroundColor: [TEAM_EMERALD, TEAM_ROSE],
            borderRadius: 6,
            barPercentage: 0.5,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: GRID_COLOUR },
              ticks: {
                callback: v => v.toFixed(1),
                font: { size: 11 },
              },
            },
            y: {
              grid: { display: false },
              ticks: { font: { size: 12, weight: 'bold' } },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: ctx => `${ctx.parsed.x.toFixed(2)} runs/over`,
              },
            },
          },
          animation: {
            duration: 400,
            easing: 'easeOutQuart',
          },
        },
      });
    },

    // ── $nextTick polyfill (Alpine provides this on the store) ──
    $nextTick(fn) {
      requestAnimationFrame(() => setTimeout(fn, 0));
    },
  });
});
