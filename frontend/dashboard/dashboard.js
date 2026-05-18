document.addEventListener('DOMContentLoaded', () => {
    // Theme Logic
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    
    function initTheme() {
        const isDark = localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches);
        if (isDark) {
            document.documentElement.classList.add('dark');
            themeIcon.classList.replace('fa-moon', 'fa-sun');
        } else {
            document.documentElement.classList.remove('dark');
            themeIcon.classList.replace('fa-sun', 'fa-moon');
        }
    }

    themeToggle.addEventListener('click', () => {
        const isDark = document.documentElement.classList.toggle('dark');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        if (isDark) {
            themeIcon.classList.replace('fa-moon', 'fa-sun');
        } else {
            themeIcon.classList.replace('fa-sun', 'fa-moon');
        }
        // Redraw chart if exists to update colors
        if (lastChartData) initChart(lastChartData);
    });

    initTheme();

    // Search Logic
    const searchForm = document.getElementById('search-form');
    searchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = document.getElementById('dashboard-search').value;
        if (query) {
            window.location.href = `../index.html?search=${encodeURIComponent(query)}`;
        }
    });

    // Sidebar Toggle for Mobile
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('active');
        });
    }

    let lastChartData = null;

    // Function to fetch stats and update UI
    async function updateDashboardData() {
        const statusBadge = document.getElementById('connection-status');
        try {
            const response = await fetch('http://127.0.0.1:8000/stats/');
            if (!response.ok) throw new Error('Backend not responding');
            const data = await response.json();

            // Update Status Badge
            statusBadge.innerHTML = `<i class="fas fa-circle" style="color: var(--accent-success); margin-right: 5px; font-size: 0.6rem;"></i> Backend Online`;

            // Update Stats Cards
            document.getElementById('total-feeds').textContent = data.total_feeds;
            document.getElementById('feeds-delta').textContent = `${data.feeds_this_week} added this week`;
            
            document.getElementById('undone-posts').textContent = data.undone_posts;
            document.getElementById('articles-delta').textContent = `${data.new_articles_today} new today`;
            
            document.getElementById('completion-rate').textContent = `${data.completion_rate}%`;
            document.getElementById('done-posts-count').textContent = `${data.done_posts} done articles`;
            
            // Distribution
            document.getElementById('whatsapped-count').textContent = data.whatsapped;
            document.getElementById('posted-count').textContent = data.posted;

            // Update Chart
            lastChartData = data.weekly_data;
            initChart(data.weekly_data);
            initDistributionChart(data.weekly_data);
            
            // Social Imports Chart & Stats
            const socialData = [data.linkedin_imports, data.facebook_imports, data.instagram_imports];
            initSocialImportsChart(socialData);
            
            const socialStatsContainer = document.getElementById('social-imports-stats');
            socialStatsContainer.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <i class="fab fa-linkedin" style="color: #0a66c2; font-size: 1.2rem;"></i>
                        <span style="font-weight: 500; font-size: 0.9rem;">LinkedIn</span>
                    </div>
                    <span style="font-weight: 600;">${data.linkedin_imports}</span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <i class="fab fa-facebook-square" style="color: #1877f2; font-size: 1.2rem;"></i>
                        <span style="font-weight: 500; font-size: 0.9rem;">Facebook</span>
                        <span style="background: rgba(239, 68, 68, 0.1); color: var(--accent-danger); font-size: 0.6rem; padding: 2px 6px; border-radius: 4px; font-weight: 600;">Scraper Blocked</span>
                    </div>
                    <span style="font-weight: 600;">${data.facebook_imports}</span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <i class="fab fa-instagram" style="color: #e1306c; font-size: 1.2rem;"></i>
                        <span style="font-weight: 500; font-size: 0.9rem;">Instagram</span>
                        <span style="background: rgba(239, 68, 68, 0.1); color: var(--accent-danger); font-size: 0.6rem; padding: 2px 6px; border-radius: 4px; font-weight: 600;">Scraper Blocked</span>
                    </div>
                    <span style="font-weight: 600;">${data.instagram_imports}</span>
                </div>
            `;

            // Update Activity Feed
            updateActivityFeed(data.recent_activity);

        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            statusBadge.innerHTML = `<i class="fas fa-circle" style="color: var(--accent-danger); margin-right: 5px; font-size: 0.6rem;"></i> Backend Offline`;
        }
    }

    // Initialize Chart
    let curationChart = null;
    function initChart(chartData) {
        const ctx = document.getElementById('curationChart').getContext('2d');
        const isDark = document.documentElement.classList.contains('dark');
        const textColor = isDark ? '#94a3b8' : '#64748b';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';
        
        if (curationChart) {
            curationChart.destroy();
        }

        curationChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [
                    {
                        label: 'Done',
                        data: chartData.done,
                        backgroundColor: '#8b5cf6',
                        borderRadius: 6,
                    },
                    {
                        label: 'Undone',
                        data: chartData.undone,
                        backgroundColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                        borderRadius: 6,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: textColor,
                            font: { family: 'Outfit', size: 12 }
                        }
                    }
                },
                scales: {
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        grid: { color: gridColor },
                        ticks: { color: textColor }
                    },
                    x: {
                        stacked: true,
                        grid: { display: false },
                        ticks: { color: textColor }
                    }
                }
            }
        });
    }

    let socialImportsChart = null;
    function initSocialImportsChart(dataCounts) {
        const ctx = document.getElementById('socialImportsChart').getContext('2d');
        const isDark = document.documentElement.classList.contains('dark');
        const textColor = isDark ? '#94a3b8' : '#64748b';
        
        if (socialImportsChart) socialImportsChart.destroy();

        socialImportsChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['LinkedIn', 'Facebook', 'Instagram'],
                datasets: [{
                    data: dataCounts,
                    backgroundColor: ['#0a66c2', '#1877f2', '#e1306c'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    let distributionChart = null;
    function initDistributionChart(chartData) {
        const ctx = document.getElementById('distributionChart').getContext('2d');
        const isDark = document.documentElement.classList.contains('dark');
        const textColor = isDark ? '#94a3b8' : '#64748b';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';
        
        if (distributionChart) distributionChart.destroy();

        distributionChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.labels,
                datasets: [
                    {
                        label: 'WhatsApp Alone',
                        data: chartData.whatsapped,
                        borderColor: '#25D366',
                        backgroundColor: 'rgba(37, 211, 102, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: 'Posted Alone',
                        data: chartData.posted,
                        borderColor: '#ff5722',
                        backgroundColor: 'rgba(255, 87, 34, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: textColor, font: { family: 'Outfit', size: 12 } }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: gridColor },
                        ticks: { color: textColor }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: textColor }
                    }
                }
            }
        });
    }

    // Update Activity Feed UI
    function updateActivityFeed(activities) {
        const feedContainer = document.getElementById('activity-feed-container');
        if (!feedContainer) return;
        feedContainer.innerHTML = ''; // Clear current

        if (!activities || activities.length === 0) {
            feedContainer.innerHTML = '<p style="text-align: center; color: var(--text-muted); font-size: 0.8rem; padding: 2rem;">No recent curation activity.</p>';
            return;
        }

        activities.forEach(item => {
            let iconClass = 'fa-check';
            let iconBg = 'rgba(16, 185, 129, 0.2)';
            let iconColor = '#10b981';
            let actionText = 'Article Curation';

            if (item.is_whatsapped) {
                iconClass = 'fa-whatsapp';
                iconBg = 'rgba(37, 211, 102, 0.2)';
                iconColor = '#25D366';
                actionText = 'Shared via WhatsApp';
            } else if (item.is_posted) {
                iconClass = 'fa-share-nodes';
                iconBg = 'rgba(6, 182, 212, 0.2)';
                iconColor = '#06b6d4';
                actionText = 'Posted to LinkedIn';
            } else if (item.is_done) {
                actionText = 'Marked as DONE';
            }

            const activityItem = `
                <div style="display: flex; gap: 15px; margin-bottom: 1.2rem;">
                    <div style="width: 35px; height: 35px; border-radius: 8px; background: ${iconBg}; display: flex; align-items: center; justify-content: center; color: ${iconColor};">
                        <i class="fas ${iconClass}"></i>
                    </div>
                    <div>
                        <p style="font-size: 0.9rem; font-weight: 500;">${actionText}</p>
                        <p style="font-size: 0.75rem; color: var(--text-muted);">${item.title.substring(0, 45)}...</p>
                    </div>
                </div>
            `;
            feedContainer.insertAdjacentHTML('beforeend', activityItem);
        });
    }

    // Initial load
    updateDashboardData();

    // Auto-refresh every 60 seconds
    setInterval(updateDashboardData, 60000);

    console.log('EduFeed Dashboard Connected.');
});
