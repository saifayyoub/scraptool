const API = ''; // same origin: works locally on 127.0.0.1:8002 and on any deployed URL
let feeds = [];
let articles = [];
let selectedArticle = null;
let currentFilter = 'all';
let folders = [];

const DOT_COLORS = ['orange','red','teal','purple','green','darkblue','gray','brown','marine','pink'];

(async function init() {
    if (localStorage.getItem('dark') === 'true') document.documentElement.classList.add('dark');
    document.getElementById('dark-mode-toggle').addEventListener('click', () => {
        document.documentElement.classList.toggle('dark');
        localStorage.setItem('dark', document.documentElement.classList.contains('dark'));
    });
    await Promise.all([loadFeeds(), loadArticles()]);
    setupResize();
    setupSearch();
    setupSyncBtn();
    setupAddFeed();
    setupAddFolder();
    setupSettings();
    setupFeedContextMenu();
    document.getElementById('btn-done').addEventListener('click', () => updateStatus('done'));
    document.getElementById('btn-posted').addEventListener('click', publishToBlogger);
    document.getElementById('btn-copy-html').addEventListener('click', copyHTML);
    document.getElementById('btn-fulltext').addEventListener('click', fetchFullText);
    document.getElementById('btn-star-toggle').addEventListener('click', () => starArticle(selectedArticle?.id));
    document.getElementById('btn-unread').addEventListener('click', () => updateStatus('unread'));
    document.getElementById('btn-delete-article').addEventListener('click', deleteCurrentArticle);
})();

function clearNavSelection() {
    document.querySelectorAll('.nav-item, .feed-item').forEach(el => el.classList.remove('selected'));
}

async function loadFeeds() {
    try {
        const r = await fetch(`${API}/feeds/`);
        feeds = await r.json();
        renderFeeds();
        document.getElementById('feed-count').textContent = `${feeds.length} feeds`;
    } catch (e) { console.error('feeds error', e); }
}

function feedDomain(url) {
    try { return new URL(url).hostname; } catch { return ''; }
}

function renderFeeds() {
    const el = document.getElementById('feed-list');
    el.innerHTML = feeds.map((f, i) => {
        const uc = f.unread_count || 0;
        const dot = DOT_COLORS[i % DOT_COLORS.length];
        const domain = feedDomain(f.url);
        return `<div class="feed-item" data-id="${f.id}" onclick="filterFeed(${f.id})">
            <div class="favicon-dot ${dot}" style="position:relative;overflow:hidden;">
                ${domain ? `<img src="https://${domain}/favicon.ico" width="14" height="14" style="position:absolute;inset:0;border-radius:50%;" onerror="this.remove()" />` : ''}
            </div>
            <span class="feed-label">${f.title}</span>
            ${uc > 0 ? `<span class="feed-badge">${uc}</span>` : ''}
        </div>`;
    }).join('');
}

function filterAll() {
    currentFilter = 'all';
    selectedArticle = null;
    clearNavSelection();
    document.getElementById('nav-all')?.classList.add('selected');
    loadArticles();
}

function filterStarred() {
    currentFilter = 'starred';
    selectedArticle = null;
    clearNavSelection();
    document.getElementById('nav-starred')?.classList.add('selected');
    loadArticles();
}

function filterDone() {
    currentFilter = 'done';
    selectedArticle = null;
    clearNavSelection();
    document.getElementById('nav-done')?.classList.add('selected');
    loadArticles();
}

function filterFeed(id) {
    currentFilter = id;
    selectedArticle = null;
    clearNavSelection();
    document.querySelector(`.feed-item[data-id="${id}"]`)?.classList.add('selected');
    loadArticles();
}

function setupSearch() {
    let timer;
    document.getElementById('search-input').addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(loadArticles, 300);
    });
}

async function loadArticles() {
    try {
        let url = `${API}/articles/?`;
        if (currentFilter === 'starred') url += 'status_filter=starred';
        else if (currentFilter === 'done') url += 'status_filter=done';
        else if (currentFilter === 'all') url += 'status_filter=all';
        else url += `status_filter=undone&feed_id=${currentFilter}`;
        const q = document.getElementById('search-input').value.trim();
        if (q) url += `&search=${encodeURIComponent(q)}`;
        const r = await fetch(url);
        articles = await r.json();
        renderArticles(articles);
    } catch (e) { console.error('articles error', e); }
}

function renderArticles(articles) {
    const container = document.getElementById('article-rows');
    if (!articles || articles.length === 0) {
        container.innerHTML = '<div class="empty-state">No articles</div>';
        return;
    }
    articles = [...articles].sort((a, b) => {
        const da = parseDate(a.published_date) || parseDate(a.added_at) || 0;
        const db = parseDate(b.published_date) || parseDate(b.added_at) || 0;
        return db - da;
    });
    const groups = groupByDay(articles);
    let html = '';
    function articleTag(a) {
        const added = a.added_at ? (parseDate(a.added_at) || new Date(0)).getTime() : 0;
        const updated = a.updated_at ? (parseDate(a.updated_at) || new Date(0)).getTime() : 0;
        const diff = updated - added;
        if (a.is_done) return '';
        if (diff > 60000) return '<span class="tag-updated">UPDATED</span>';
        if (added > Date.now() - 86400000) return '<span class="tag-new">NEW</span>';
        return '';
    }
    for (const [label, items] of Object.entries(groups)) {
        html += `<div class="day-header">${label}</div>`;
        for (const a of items) {
            const title = a.edited_title || a.title || 'Untitled';
            const isUnread = !a.is_read && !a.is_done;
            const feed = feeds.find(f => f.id === a.feed_id);
            const feedName = feed ? feed.title : '';
            const time = a.published_date || a.added_at || '';
            const timeStr = time ? formatTime(time) : '';
            const isActive = selectedArticle && selectedArticle.id === a.id;
            const tag = articleTag(a);
            html += `<div class="article-row ${isActive ? 'selected' : ''}" data-id="${a.id}">
                <div class="title">${title}</div>
                <div class="meta">
                    <div class="dot ${isUnread ? 'unread' : ''}"></div>
                    <span class="feed-name">${feedName}</span>
                    ${tag ? tag : ''}
                    <span class="time">${timeStr}</span>
                </div>
            </div>`;
        }
    }
    container.innerHTML = html;
    container.querySelectorAll('.article-row').forEach(el => {
        el.addEventListener('click', () => {
            const id = parseInt(el.dataset.id);
            openArticle(articles.find(a => a.id === id));
        });
    });
}

function parseDate(s) {
    if (!s) return null;
    const str = /^\d{4}-\d{2}-\d{2} /.test(s) ? s.replace(' ', 'T') : s;
    const d = new Date(str);
    return isNaN(d.getTime()) ? null : d;
}
function utcDay(date) {
    return date.getUTCFullYear() * 10000 + (date.getUTCMonth() + 1) * 100 + date.getUTCDate();
}
function groupByDay(articles) {
    const groups = {};
    const now = new Date();
    const todayKey = utcDay(now);
    const yestKey = utcDay(new Date(now - 86400000));
    for (const a of articles) {
        const date = parseDate(a.published_date) || parseDate(a.added_at);
        let label;
        if (date) {
            const k = utcDay(date);
            if (k === todayKey) label = 'Today';
            else if (k === yestKey) label = 'Yesterday';
            else label = date.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
        } else label = 'Unknown';
        if (!groups[label]) groups[label] = [];
        groups[label].push(a);
    }
    return groups;
}

function formatTime(dateStr) {
    const d = parseDate(dateStr);
    if (!d) return '';
    const now = new Date();
    const diff = now - d;
    if (diff < 3600000) return `${Math.round(diff / 60000)}m`;
    if (diff < 86400000) return `${Math.round(diff / 3600000)}h`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function openArticle(article) {
    if (!article) return;
    selectedArticle = article;
    if (!article.is_read) {
        article.is_read = 1;
        fetch(`${API}/articles/${article.id}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status_type: 'read', value: true })
        }).catch(() => {});
        const row = document.querySelector(`.article-row[data-id="${article.id}"]`);
        if (row) {
            const dot = row.querySelector('.dot');
            if (dot) dot.classList.remove('unread');
        }
        loadFeeds();
    }
    document.querySelectorAll('.article-row').forEach(el => {
        el.classList.toggle('selected', parseInt(el.dataset.id) === article.id);
    });
    const title = article.edited_title || article.title || 'Untitled';
    const desc = article.edited_description || article.description || '';
    const content = article.edited_content || article.content || desc || 'No content.';
    const feed = feeds.find(f => f.id === article.feed_id);
    const feedName = feed ? feed.title : '';
    const date = article.published_date || article.added_at || '';
    const dateStr = date ? new Date(date).toLocaleString() : '';
    const visible = content.replace(/<[^>]*>/g, '').trim();
    const isShort = visible.length > 0 && visible.length < 200;
    const hint = (isShort && !article.fulltext_attempted && article.link && !article.link.startsWith('urn:')) ? `
        <div style="background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:10px 14px;font-size:13px;color:var(--fg2);margin-bottom:14px;display:flex;align-items:center;gap:8px;">
            <i class="fas fa-info-circle" style="color:var(--accent);"></i>
            This is only a short summary. <span id="hint-fetch" style="cursor:pointer;color:var(--accent);text-decoration:underline;">Fetch full text</span>
        </div>` : '';
    const pane = document.getElementById('article-content');
    pane.innerHTML = `
        <div class="article-headline" dir="rtl">${title}</div>
        <div class="source-line">
            from ${feedName} &nbsp; ${dateStr}
            ${article.link ? `&nbsp; <a href="${article.link}" target="_blank" style="color:var(--accent);text-decoration:none;">Source</a>` : ''}
        </div>
        ${hint}
        <div class="article-body" dir="rtl">${content}</div>
    `;
    const hintEl = document.getElementById('hint-fetch');
    if (hintEl) hintEl.addEventListener('click', fetchFullText);
    document.getElementById('pane-inner').scrollTop = 0;
    updateToolbar();
}

function updateToolbar() {
    const a = selectedArticle;
    if (!a) return;
    document.getElementById('btn-star-toggle').innerHTML = a.is_starred
        ? '<i class="fas fa-star" style="color:#f59e0b;"></i> Starred'
        : '<i class="far fa-star"></i> Star';
    document.getElementById('btn-posted').innerHTML = a.is_posted
        ? '<i class="fas fa-check" style="color:#2e9e3f;"></i> Posted'
        : '<i class="fas fa-share-nodes" style="color:#ff5722;"></i> Blogger';
    document.getElementById('btn-unread').innerHTML = a.is_read
        ? '<i class="far fa-envelope-open"></i>'
        : '<i class="far fa-envelope"></i>';
}

async function starArticle(id) {
    if (!id) return;
    try {
        const r = await fetch(`${API}/articles/${id}/star`, { method: 'POST' });
        const data = await r.json();
        const art = articles.find(a => a.id === id);
        if (art) art.is_starred = data.is_starred ? 1 : 0;
        if (selectedArticle?.id === id) selectedArticle.is_starred = data.is_starred ? 1 : 0;
        updateToolbar();
        showToast(data.is_starred ? 'Starred' : 'Unstarred');
        if (currentFilter === 'starred' && !data.is_starred) {
            articles = articles.filter(a => a.id !== id);
            renderArticles(articles);
        }
    } catch (e) { showToast('Failed', 'error'); }
}

async function publishToBlogger() {
    if (!selectedArticle) return;
    if (selectedArticle.is_posted) { showToast('Already posted', 'error'); return; }
    try {
        const r = await fetch(`${API}/articles/${selectedArticle.id}/publish-blogger`, { method: 'POST' });
        const data = await r.json();
        if (data.success) {
            selectedArticle.is_posted = 1;
            updateToolbar();
            loadFeeds();
            showToast('Posted to Blogger!');
        } else {
            showToast(data.error || 'Publish failed', 'error');
        }
    } catch (e) { showToast('Network error', 'error'); }
}

async function updateStatus(type) {
    if (!selectedArticle) return;
    let statusType = type;
    let value = true;
    if (type === 'unread') { statusType = 'read'; value = !selectedArticle.is_read; }
    else if (type === 'done') value = !selectedArticle.is_done;
    try {
        const r = await fetch(`${API}/articles/${selectedArticle.id}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status_type: statusType, value })
        });
        if (r.ok) {
            showToast(`${type}: ${value ? 'on' : 'off'}`);
            if (type === 'done') {
                selectedArticle.is_done = value ? 1 : 0;
                if (value && currentFilter !== 'done') {
                    articles = articles.filter(a => a.id !== selectedArticle.id);
                    renderArticles(articles);
                    document.getElementById('article-content').innerHTML = '<div class="empty-state">Select an article to read</div>';
                    selectedArticle = null;
                    loadFeeds();
                    return;
                }
            }
            if (type === 'unread') {
                selectedArticle.is_read = value ? 1 : 0;
                updateToolbar();
                renderArticles(articles);
            }
            loadFeeds();
        }
    } catch (e) { showToast('Failed', 'error'); }
}

function copyHTML() {
    if (!selectedArticle) return;
    const body = document.querySelector('.article-body');
    if (body) navigator.clipboard.writeText(body.innerHTML).then(() => showToast('HTML copied!')).catch(() => showToast('Failed', 'error'));
}

async function fetchFullText() {
    if (!selectedArticle) return;
    if (!selectedArticle.link || selectedArticle.link.startsWith('urn:')) { showToast('No source URL available', 'error'); return; }
    const btn = document.getElementById('btn-fulltext');
    const orig = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    try {
        const r = await fetch(`${API}/articles/${selectedArticle.id}/fulltext`, { method: 'POST' });
        const data = await r.json();
        if (r.ok && data.success) {
            selectedArticle.description = data.description;
            selectedArticle.fulltext_attempted = 1;
            openArticle(selectedArticle);
            showToast(data.upgraded ? `Full text fetched (${data.length} chars)` : 'Content unchanged');
        } else {
            showToast(data.detail || 'Extraction failed', 'error');
        }
    } catch (e) { showToast('Network error', 'error'); }
    btn.innerHTML = orig;
}

async function deleteCurrentArticle() {
    if (!selectedArticle || !confirm('Delete this article?')) return;
    try {
        const r = await fetch(`${API}/articles/${selectedArticle.id}`, { method: 'DELETE' });
        if (r.ok) {
            showToast('Deleted');
            articles = articles.filter(a => a.id !== selectedArticle.id);
            renderArticles(articles);
            document.getElementById('article-content').innerHTML = '<div class="empty-state">Select an article to read</div>';
            selectedArticle = null;
            loadFeeds();
        }
    } catch (e) { showToast('Failed', 'error'); }
}

function setupSyncBtn() {
    document.getElementById('sync-btn').addEventListener('click', async () => {
        const btn = document.getElementById('sync-btn');
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        try {
            const r = await fetch(`${API}/sync/`, { method: 'POST' });
            if (r.ok) {
                const data = await r.json();
                const msg = data.new_articles_count || data.updated_articles_count
                    ? `${data.new_articles_count || 0} new, ${data.updated_articles_count || 0} updated`
                    : 'No new articles';
                showToast(msg);
            } else showToast('Sync failed', 'error');
        } catch (e) { showToast('Network error', 'error'); }
        btn.innerHTML = '<i class="fas fa-sync-alt"></i>';
        await Promise.all([loadFeeds(), loadArticles()]);
    });
}

function setupAddFeed() {
    document.getElementById('btn-add-feed').addEventListener('click', () => {
        showAddFeedProperties('', '');
    });
}

function setupAddFolder() {
    document.getElementById('btn-add-folder').addEventListener('click', () => {
        const name = prompt('Folder name:');
        if (!name) return;
        fetch(`${API}/folders/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
            .then(r => r.ok ? (showToast('Folder created!'), loadFolders()) : r.json().then(e => showToast(e.detail || 'Failed', 'error')))
            .catch(() => showToast('Network error', 'error'));
    });
}

async function loadFolders() {
    try { const r = await fetch(`${API}/folders/`); folders = await r.json(); } catch (e) { folders = []; }
}

function setupResize() {
    const handle = document.getElementById('resize-handle');
    const list = document.getElementById('article-list-pane');
    const saved = localStorage.getItem('listWidth');
    if (saved) list.style.width = saved + 'px';
    handle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        handle.classList.add('active');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        const startX = e.clientX;
        const startW = list.offsetWidth;
        function onMove(ev) {
            const w = Math.max(180, Math.min(700, startW + ev.clientX - startX));
            list.style.width = w + 'px';
        }
        function onUp() {
            handle.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            localStorage.setItem('listWidth', list.offsetWidth);
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
        }
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    });
}

function setupSettings() {
    const modal = document.getElementById('settings-modal');
    const openBtn = document.getElementById('btn-settings');
    const closeBtn = document.getElementById('modal-close');
    const saveBtn = document.getElementById('btn-save-blogger');
    const connectBtn = document.getElementById('btn-connect-blogger');

    openBtn.addEventListener('click', () => {
        modal.style.display = 'flex';
        fetch(`${API}/blogger-config`).then(r => r.json()).then(cfg => {
            document.getElementById('b-client-id').value = cfg.client_id || '';
            document.getElementById('b-client-secret').value = '';
            document.getElementById('b-blog-id').value = cfg.blog_id || '';
            const status = document.getElementById('blogger-status');
            if (cfg.connected) status.innerHTML = '<span style="color:#16a34a;">Connected</span>';
            else status.textContent = 'Not connected';
        });
    });
    closeBtn.addEventListener('click', () => modal.style.display = 'none');
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });

    saveBtn.addEventListener('click', async () => {
        const payload = {
            client_id: document.getElementById('b-client-id').value.trim(),
            client_secret: document.getElementById('b-client-secret').value.trim(),
            blog_id: document.getElementById('b-blog-id').value.trim(),
            access_token: '', refresh_token: ''
        };
        await fetch(`${API}/blogger-config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        showToast('Blogger settings saved');
    });

    connectBtn.addEventListener('click', async () => {
        const resp = await fetch(`${API}/blogger/auth-url`);
        if (!resp.ok) { showToast('Save Client ID first', 'error'); return; }
        const data = await resp.json();
        window.open(data.auth_url, '_blank', 'width=600,height=700');
    });
}

function setupFeedContextMenu() {
    const menu = document.getElementById('context-menu');
    document.addEventListener('contextmenu', (e) => {
        const item = e.target.closest('.feed-item');
        if (!item) { menu.style.display = 'none'; return; }
        e.preventDefault();
        const id = parseInt(item.dataset.id);
        const feed = feeds.find(f => f.id === id);
        if (!feed) return;
        menu.innerHTML = `
            <div class="cm-item" data-action="mark-read">Mark all items as read</div>
            <div class="cm-item" data-action="rename">Rename</div>
            <div class="cm-item" data-action="delete">Delete</div>
            <div class="cm-item" data-action="sync">Update feed</div>
            <hr class="cm-sep">
            <div class="cm-item" data-action="properties">Properties</div>
        `;
        menu.style.display = 'block';
        menu.style.left = Math.min(e.clientX, window.innerWidth - 190) + 'px';
        menu.style.top = Math.min(e.clientY, window.innerHeight - 220) + 'px';
        menu._feedId = id;
    });
    menu.addEventListener('click', async (e) => {
        const action = e.target.dataset.action;
        if (!action) return;
        const id = menu._feedId;
        menu.style.display = 'none';
        if (action === 'mark-read') {
            await fetch(`${API}/feeds/${id}/mark-read`, { method: 'POST' });
            showToast('All marked as read');
            await Promise.all([loadFeeds(), loadArticles()]);
        } else if (action === 'delete') {
            if (!confirm('Delete this feed and its articles?')) return;
            await fetch(`${API}/feeds/${id}`, { method: 'DELETE' });
            showToast('Feed deleted');
            document.getElementById('article-rows').innerHTML = '<div class="empty-state">No articles</div>';
            document.getElementById('article-content').innerHTML = '<div class="empty-state">Select an article to read</div>';
            selectedArticle = null;
            await Promise.all([loadFeeds(), loadArticles()]);
        } else if (action === 'rename') {
            const feed = feeds.find(f => f.id === id);
            const name = prompt('New name:', feed ? feed.title : '');
            if (name && name.trim()) {
                await fetch(`${API}/feeds/${id}/rename`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: name.trim() })
                });
                showToast('Feed renamed');
    await Promise.all([loadFeeds(), loadArticles(), loadFolders()]);
            }
        } else if (action === 'sync') {
            const r = await fetch(`${API}/feeds/${id}/sync`, { method: 'POST' });
            if (r.ok) {
                const data = await r.json();
                const msg = data.new_articles_count || data.updated_articles_count
                    ? `${data.new_articles_count || 0} new, ${data.updated_articles_count || 0} updated`
                    : 'No new articles';
                showToast(msg);
            } else showToast('Sync failed', 'error');
            await Promise.all([loadFeeds(), loadArticles()]);
            filterFeed(id);
        } else if (action === 'properties') {
            showFeedProperties(id);
        }
    });
    document.addEventListener('click', () => { menu.style.display = 'none'; });
}

function showFeedProperties(id) {
    const feed = feeds.find(f => f.id === id);
    if (!feed) return;
    showPropsModal(feed, false, id);
}

async function showAddFeedProperties(url, title) {
    await loadFolders();
    const feed = { url: url || '', title: title || '', max_entries: 20, scan_interval: 0, folder_id: null, proxy: '', username: '', password: '', full_text: 1 };
    showPropsModal(feed, true, null);
}

function showPropsModal(feed, isNew, editId) {
    const modal = document.getElementById('props-modal');
    const body = document.getElementById('props-body');
    const latestStr = isNew ? '—' : (() => {
        const published = articles.filter(a => a.feed_id === editId && a.published_date).sort((a, b) => (parseDate(b.published_date) || 0) - (parseDate(a.published_date) || 0));
        const latest = published[0];
        if (!latest) return 'N/A';
        const diff = Date.now() - new Date(latest.published_date).getTime();
        const m = Math.round(diff / 60000);
        return m < 1 ? 'just now' : m + ' minutes';
    })();
    const entryOptions = [1,5,10,20,50,100,200,500,1000];
    const intervalOptions = [0,1,2,3,4,5,10,15,20,30,45,60];
    const folderOpts = [{id:null, name:'Root'}, ...folders];
    body.innerHTML = `
        <div class="props-row"><span class="props-label">Feed URL</span><span class="props-value" style="display:flex;gap:6px;flex-wrap:wrap;"><input class="settings-input" id="prop-url" value="${(feed.url||'').replace(/"/g,'&quot;')}" style="flex:1;min-width:150px;" /><button class="settings-btn" id="prop-load">Load</button></span></div>
        <div id="prop-results-wrap"></div>
        <div class="props-row"><span class="props-label">Title</span><span class="props-value"><input class="settings-input" id="prop-title" value="${(feed.title||'').replace(/"/g,'&quot;')}" /></span></div>
        <div class="props-row"><span class="props-label">Latest entry posted</span><span class="props-value">${latestStr}</span></div>
        <div class="props-row"><span class="props-label">Status</span><span class="props-value" style="color:#16a34a;">OK</span></div>
        <div class="props-row"><span class="props-label">Maximum entries to save</span><span class="props-value"><select class="settings-input" id="prop-entries">${entryOptions.map(v => `<option value="${v}" ${(feed.max_entries||20)==v?'selected':''}>${v}</option>`).join('')}</select></span></div>
        <div class="props-row"><span class="props-label">Scan interval</span><span class="props-value"><select class="settings-input" id="prop-interval">${intervalOptions.map(v => `<option value="${v}" ${(feed.scan_interval||0)==v?'selected':''}>${v===0?'Manual':v+' min'}</option>`).join('')}</select></span></div>
        <div class="props-row"><span class="props-label">Auto full text</span><span class="props-value"><label style="display:flex;align-items:center;gap:6px;cursor:pointer;"><input type="checkbox" id="prop-fulltext" ${(feed.full_text===undefined || feed.full_text) ? 'checked' : ''} /> Fetch full article text when the summary is short</label></span></div>
        <div class="props-row"><span class="props-label">Folder</span><span class="props-value"><select class="settings-input" id="prop-folder">${folderOpts.map(fo => `<option value="${fo.id===null?'':fo.id}" ${(feed.folder_id||'')==(fo.id||'')?'selected':''}>${fo.name}</option>`).join('')}</select></span></div>
        <div class="props-row"><span class="props-label">Proxy</span><span class="props-value"><select class="settings-input" id="prop-proxy"><option value="" ${!feed.proxy?'selected':''}>None</option><option value="feedly" ${feed.proxy==='feedly'?'selected':''}>Feedly</option></select></span></div>
        <div class="props-row"><span class="props-label">Username</span><span class="props-value"><input class="settings-input" id="prop-username" value="${(feed.username||'').replace(/"/g,'&quot;')}" /></span></div>
        <div class="props-row"><span class="props-label">Password</span><span class="props-value"><input class="settings-input" id="prop-password" type="password" value="${(feed.password||'').replace(/"/g,'&quot;')}" /></span></div>
        <div style="text-align:right;margin-top:12px;"><button class="settings-btn" id="prop-save" style="background:var(--accent);color:#fff;">${isNew ? 'Add Feed' : 'Save'}</button></div>
    `;
    modal.style.display = 'flex';
    document.getElementById('props-close').onclick = () => modal.style.display = 'none';
    modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
    document.getElementById('prop-load').addEventListener('click', async () => {
        const url = document.getElementById('prop-url').value.trim();
        if (!url) return;
        try {
            const r = await fetch(`${API}/discover-feeds?url=${encodeURIComponent(url)}`);
            if (!r.ok) { showToast('No feeds found', 'error'); return; }
            const discovered = await r.json();
            const wrap = document.getElementById('prop-results-wrap');
            if (discovered.length === 1) {
                wrap.innerHTML = '';
                document.getElementById('prop-url').value = discovered[0].url;
                document.getElementById('prop-title').value = discovered[0].title;
            } else {
                wrap.innerHTML = '<div class="prop-results">' + discovered.map((f, i) =>
                    `<div class="pr-item" data-idx="${i}">${f.title || f.url}</div>`
                ).join('') + '</div>';
                wrap.querySelectorAll('.pr-item').forEach(el => {
                    el.addEventListener('click', () => {
                        const f = discovered[parseInt(el.dataset.idx)];
                        document.getElementById('prop-url').value = f.url;
                        document.getElementById('prop-title').value = f.title || f.url;
                        wrap.innerHTML = '';
                    });
                });
            }
        } catch (e) { showToast('Discovery failed', 'error'); }
    });
    document.getElementById('prop-save').addEventListener('click', async () => {
        const payload = {
            url: document.getElementById('prop-url').value.trim(),
            title: document.getElementById('prop-title').value.trim(),
            max_entries: parseInt(document.getElementById('prop-entries').value) || 20,
            scan_interval: parseInt(document.getElementById('prop-interval').value) || 0,
            folder_id: document.getElementById('prop-folder').value || null,
            proxy: document.getElementById('prop-proxy').value,
            username: document.getElementById('prop-username').value,
            password: document.getElementById('prop-password').value,
            full_text: document.getElementById('prop-fulltext').checked ? 1 : 0
        };
        if (isNew) {
            const r = await fetch(`${API}/feeds/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (r.ok) {
                const data = await r.json();
                showToast(`Feed added! ${data.imported || 0}/${data.entries_found || 0} articles`);
            } else {
                const err = await r.json();
                showToast(err.detail || 'Failed', 'error');
                return;
            }
        } else {
            await fetch(`${API}/feeds/${editId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            showToast('Properties saved');
        }
        modal.style.display = 'none';
        await Promise.all([loadFeeds(), loadArticles()]);
    });
}

function showToast(msg, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.3s'; setTimeout(() => toast.remove(), 300); }, 2500);
}
