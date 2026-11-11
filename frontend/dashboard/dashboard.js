document.addEventListener('DOMContentLoaded', () => {
    // ── Theme ──
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');

    function initTheme() {
        const isDark = localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches);
        document.documentElement.classList.toggle('dark', isDark);
        if (themeIcon) themeIcon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const isDark = document.documentElement.classList.toggle('dark');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            if (themeIcon) themeIcon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
            redrawCharts();
        });
    }
    initTheme();

    // ── Search ──
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const q = document.getElementById('dashboard-search');
            if (q && q.value) window.location.href = '../index.html?search=' + encodeURIComponent(q.value);
        });
    }

    // ── Sidebar mobile toggle ──
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => sidebar.classList.toggle('active'));
    }

    // ── Period selector ──
    const periodSelect = document.getElementById('period-select');
    if (periodSelect) {
        periodSelect.addEventListener('change', () => updateDashboardData());
    }

    // ── Chart refs ──
    let curationChart = null;
    let socialImportsChart = null;
    let distributionChart = null;
    let statusChart = null;

    function isDark() { return document.documentElement.classList.contains('dark'); }
    function textColor() { return isDark() ? '#94a3b8' : '#64748b'; }
    function gridColor() { return isDark() ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'; }

    function redrawCharts() { if (lastData) renderAll(lastData); }

    let lastData = null;

    function $(id) { return document.getElementById(id); }

    // ── Fetch & update ──
    async function updateDashboardData() {
        const badge = $('connection-status');
        const period = periodSelect ? periodSelect.value : 'weekly';
        try {
            const res = await fetch('/stats/?period=' + period);
            if (!res.ok) throw new Error('Backend error');
            const d = await res.json();
            lastData = d;

            if (badge) badge.innerHTML = '<i class="fas fa-circle" style="color:var(--accent-success);margin-right:5px;font-size:0.6rem;"></i> Online';

            // ── KPI Cards ──
            setText('total-articles', d.total_articles);
            setText('total-articles-trend', (d.new_articles_today || 0) + ' new today');

            setText('done-posts', d.done_posts);
            setText('done-pct', (d.completion_rate || 0) + '%');
            if (d.done_this_week !== undefined && d.done_last_week !== undefined) {
                var trend = d.done_this_week - d.done_last_week;
                var trendIcon = trend >= 0 ? '<i class="fas fa-arrow-up" style="color:#10b981"></i>' : '<i class="fas fa-arrow-down" style="color:#ef4444"></i>';
                setHtml('done-trend', trendIcon + ' <span id="done-this-week"></span> done this week (' + (trend >= 0 ? '+' : '') + trend + ' vs last)');
            }
            setText('done-this-week', d.done_this_week || 0);

            setText('undone-posts', d.undone_posts);
            var unreadVal = d.total_articles - d.total_read;
            setText('unread-posts', unreadVal > 0 ? unreadVal : 0);
            setText('new-today', d.new_articles_today || 0);

            setText('completion-rate', (d.completion_rate || 0) + '%');

            setText('posted-count', d.posted);
            setText('posted-rate', (d.posted_rate || 0) + '%');
            setText('posted-today', d.posted_today || 0);

            setText('whatsapped-count', d.whatsapped);
            setText('whatsapped-rate', (d.whatsapped_rate || 0) + '%');
            setText('whatsapped-today', d.whatsapped_today || 0);

            setText('total-feeds', d.total_feeds);
            setText('active-feeds', d.active_feeds || 0);
            setText('avg-per-feed', d.avg_per_feed || 0);

            setText('updated-today', d.updated_recently || 0);
            setText('zero-engagement', d.zero_engagement || 0);

            // ── Charts ──
            renderAll(d);

            // ── Social imports ──
            initSocialImportsChart([d.linkedin_imports || 0]);
            var s = $('social-imports-stats');
            if (s) s.innerHTML =
                '<div style="display:flex;justify-content:space-between;align-items:center;"><div style="display:flex;align-items:center;gap:8px;"><i class="fab fa-linkedin" style="color:#0a66c2;font-size:1.2rem"></i><span style="font-weight:500;font-size:0.9rem">LinkedIn</span></div><span style="font-weight:600">' + (d.linkedin_imports || 0) + '</span></div>';

            // ── Feed table ──
            renderFeedTable(d.feed_stats);

            // ── Activity feed ──
            updateActivityFeed(d.recent_activity);

        } catch (err) {
            console.error('Dashboard error:', err);
            if (badge) badge.innerHTML = '<i class="fas fa-circle" style="color:var(--accent-danger);margin-right:5px;font-size:0.6rem;"></i> Offline';
        }
    }

    function setText(id, val) { var el = $(id); if (el) el.textContent = val || 0; }
    function setHtml(id, html) { var el = $(id); if (el) el.innerHTML = html; }

    function renderAll(data) {
        if (data.trend_data) {
            initChart(data.trend_data);
            initDistributionChart(data.trend_data);
        }
        initStatusChart(data);
    }

    // ── Curation Chart (bar) ──
    function initChart(td) {
        var ctx = $('curationChart');
        if (!ctx) return;
        if (curationChart) curationChart.destroy();
        curationChart = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: td.labels,
                datasets: [
                    { label: 'Done', data: td.done, backgroundColor: '#8b5cf6', borderRadius: 6 },
                    { label: 'Undone', data: td.undone, backgroundColor: isDark() ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)', borderRadius: 6 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { labels: { color: textColor(), font: { size: 12 } } } },
                scales: {
                    y: { stacked: true, beginAtZero: true, grid: { color: gridColor() }, ticks: { color: textColor() } },
                    x: { stacked: true, grid: { display: false }, ticks: { color: textColor() } }
                }
            }
        });
    }

    // ── Social Imports Doughnut ──
    function initSocialImportsChart(data) {
        var ctx = $('socialImportsChart');
        if (!ctx) return;
        if (socialImportsChart) socialImportsChart.destroy();
        socialImportsChart = new Chart(ctx.getContext('2d'), {
            type: 'doughnut',
            data: { labels: ['LinkedIn'], datasets: [{ data: data, backgroundColor: ['#0a66c2'], borderWidth: 0, hoverOffset: 4 }] },
            options: { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { legend: { display: false } } }
        });
    }

    // ── Distribution Timeline (line) ──
    function initDistributionChart(td) {
        var ctx = $('distributionChart');
        if (!ctx) return;
        if (distributionChart) distributionChart.destroy();
        distributionChart = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: td.labels,
                datasets: [
                    { label: 'WhatsApp', data: td.whatsapped, borderColor: '#25D366', backgroundColor: 'rgba(37,211,102,0.1)', borderWidth: 2, fill: true, tension: 0.3 },
                    { label: 'Posted', data: td.posted, borderColor: '#ff5722', backgroundColor: 'rgba(255,87,34,0.1)', borderWidth: 2, fill: true, tension: 0.3 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { labels: { color: textColor(), font: { size: 12 } } } },
                scales: {
                    y: { beginAtZero: true, grid: { color: gridColor() }, ticks: { color: textColor() } },
                    x: { grid: { display: false }, ticks: { color: textColor() } }
                }
            }
        });
    }

    // ── Status Overview (doughnut) ──
    function initStatusChart(d) {
        var ctx = $('statusChart');
        if (!ctx) return;
        if (statusChart) statusChart.destroy();
        statusChart = new Chart(ctx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Done', 'Undone', 'Posted', 'WhatsApped'],
                datasets: [{ data: [d.done_posts || 0, d.undone_posts || 0, d.posted || 0, d.whatsapped || 0], backgroundColor: ['#8b5cf6', 'rgba(0,0,0,0.15)', '#ff5722', '#25D366'], borderWidth: 0, hoverOffset: 4 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '60%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: textColor(), font: { size: 10 }, padding: 12 } }
                }
            }
        });
    }

    // ── Feed Table ──
    function renderFeedTable(stats) {
        var tbody = $('feed-table-body');
        if (!tbody) return;
        if (!stats || stats.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:2rem;color:var(--text-muted);">No feeds.</td></tr>';
            return;
        }
        tbody.innerHTML = stats.map(function(f) {
            var pct = f.total > 0 ? Math.round((f.done / f.total) * 100) : 0;
            return '<tr><td><span class="feed-name">' + esc(f.title || f.url) + '</span></td><td>' + f.total + '</td><td>' + f.done + '</td><td><span class="pct ' + (pct > 50 ? 'pct-high' : 'pct-low') + '">' + pct + '%</span></td><td>' + f.posted + '</td><td>' + f.whatsapped + '</td></tr>';
        }).join('');
    }

    function esc(s) {
        if (!s) return '';
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // ── Activity Feed ──
    function updateActivityFeed(activities) {
        var container = $('activity-feed-container');
        if (!container) return;
        container.innerHTML = '';
        if (!activities || activities.length === 0) {
            container.innerHTML = '<p style="text-align:center;color:var(--text-muted);font-size:0.8rem;padding:2rem;">No recent activity.</p>';
            return;
        }
        activities.forEach(function(item) {
            var icon = 'fa-check', bg = 'rgba(16,185,129,0.2)', color = '#10b981', text = 'Article Curation';
            if (item.is_whatsapped) { icon = 'fa-whatsapp'; bg = 'rgba(37,211,102,0.2)'; color = '#25D366'; text = 'Shared via WhatsApp'; }
            else if (item.is_posted) { icon = 'fa-share-nodes'; bg = 'rgba(6,182,212,0.2)'; color = '#06b6d4'; text = 'Posted to Blogger'; }
            else if (item.is_done) { text = 'Marked as DONE'; }
            var el = document.createElement('div');
            el.style.cssText = 'display:flex;gap:15px;margin-bottom:1.2rem;';
            el.innerHTML = '<div style="width:35px;height:35px;border-radius:8px;background:' + bg + ';display:flex;align-items:center;justify-content:center;color:' + color + ';"><i class="fas ' + icon + '"></i></div><div><p style="font-size:0.9rem;font-weight:500;">' + text + '</p><p style="font-size:0.75rem;color:var(--text-muted);">' + esc((item.title || '').substring(0, 50)) + '...</p></div>';
            container.appendChild(el);
        });
    }

    // ── Initial load ──
    updateDashboardData();
    setInterval(updateDashboardData, 60000);

    console.log('EduFeed Dashboard v3 Connected.');
});
