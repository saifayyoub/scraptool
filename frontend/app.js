const API_BASE = 'http://127.0.0.1:8000';

let currentFeeds = [];
let currentFilter = 'undone';
let currentSearch = '';
let selectedArticle = null;
let isEditMode = false;
let debounceTimer;
let quill;

let isDarkMode = false;
let currentImportPlatform = 'linkedin';

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    init();
});

function initTheme() {
    isDarkMode = localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches);
    updateThemeDOM();
}

function updateThemeDOM() {
    if (isDarkMode) {
        document.documentElement.classList.add('dark');
        document.getElementById('dark-mode-indicator')?.classList.add('translate-x-5');
    } else {
        document.documentElement.classList.remove('dark');
        document.getElementById('dark-mode-indicator')?.classList.remove('translate-x-5');
    }
}

function toggleDarkMode() {
    isDarkMode = !isDarkMode;
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
    updateThemeDOM();
}

async function init() {
    quill = new Quill('#quill-container', {
        theme: 'snow',
        modules: {
            table: true,
            toolbar: [
                [{ 'header': [1, 2, 3, false] }],
                ['bold', 'italic', 'underline', 'strike'],
                [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                [{ 'direction': 'rtl' }, { 'align': [] }],
                ['link', 'image', 'video'],
                ['table'],
                ['clean']
            ]
        }
    });
    
    // Handle URL parameters for deep linking (e.g. from Dashboard)
    const urlParams = new URLSearchParams(window.location.search);
    const searchParam = urlParams.get('search');
    const filterParam = urlParams.get('filter');
    
    if (searchParam) {
        currentSearch = searchParam;
        document.getElementById('search-input').value = searchParam;
    }
    if (filterParam) {
        currentFilter = filterParam;
        // setFilter handles UI update and loadArticles
        setFilter(filterParam);
    } else {
        setupEventListeners();
        setupMarkdownPaste();
        await loadFeeds();
        await loadArticles();
    }

    if (filterParam) {
        // If we didn't call the default setup above
        setupEventListeners();
        setupMarkdownPaste();
        await loadFeeds();
    }
}

function setupMarkdownPaste() {
    const editor = document.querySelector('#quill-container .ql-editor');
    if (!editor) return;

    editor.addEventListener('paste', (e) => {
        // Allow default if it's already HTML (e.g. copied from a website)
        if (e.clipboardData.types.includes('text/html')) return;

        const text = e.clipboardData.getData('text/plain');
        
        // Detection for markdown patterns (headers, tables, bold, links)
        const isMd = /^#+\s|\|.*\||\[.*\]\(.*\)|^\s*[\*\+-]\s|^\d+\.\s/m.test(text);
        
        if (isMd) {
            e.preventDefault();
            const html = marked.parse(text);
            const range = quill.getSelection();
            quill.clipboard.dangerouslyPasteHTML(range ? range.index : 0, html);
            showToast('Formatted as Markdown');
        }
    });
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    const bg = type === 'success' ? 'bg-green-600' : (type === 'error' ? 'bg-red-600' : 'bg-marine-600');
    toast.className = `${bg} text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 transform transition-all duration-300 translate-y-10 opacity-0 pointer-events-auto`;
    toast.innerHTML = `
        <span class="text-sm font-medium">${message}</span>
        <button onclick="this.parentElement.remove()" class="text-white opacity-70 hover:opacity-100">×</button>
    `;
    container.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.classList.remove('translate-y-10', 'opacity-0');
    }, 10);
    
    // Auto remove
    setTimeout(() => {
        toast.classList.add('translate-y-10', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function setupEventListeners() {
    // Add Feed
    const addFeedForm = document.getElementById('add-feed-form');
    addFeedForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = document.getElementById('feed-url-input');
        const url = input.value;
        if (!url) return;
        
        try {
            const btn = addFeedForm.querySelector('button');
            btn.innerHTML = '<span class="animate-spin w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full inline-block"></span>';
            const res = await fetch(`${API_BASE}/feeds/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url})
            });
            if (res.ok) {
                input.value = '';
                showToast('Feed added successfully! Fetching articles...');
                await loadFeeds();
                // Trigger a sync for the new feed
                await fetch(`${API_BASE}/sync/`, {method: 'POST'});
                await loadArticles();
            } else {
                const errData = await res.json();
                showToast(errData.detail || 'Failed to add feed.', 'error');
            }
        } catch (err) {
            console.error(err);
            showToast('Network error: Is the backend server running?', 'error');
        } finally {
            const btn = addFeedForm.querySelector('button');
            btn.innerHTML = '+';
        }
    });

    // Update Feeds
    const syncBtn = document.getElementById('sync-btn');
    syncBtn.addEventListener('click', async () => {
        const originalText = syncBtn.innerHTML;
        syncBtn.innerHTML = '<span class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full inline-block"></span> Updating...';
        try {
            const res = await fetch(`${API_BASE}/sync/`, {method: 'POST'});
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to update feeds.');
            }
            const data = await res.json();
            showToast(`Feeds updated. ${data.new_articles_count} new articles.`);
            await loadArticles();
        } catch (err) {
            console.error(err);
            showToast(err.message || 'Failed to update feeds.', 'error');
        }
        syncBtn.innerHTML = originalText;
    });
    
    // Unified Social Importer Tabs
    const importTabs = document.querySelectorAll('.social-tab-btn');
    const importForm = document.getElementById('social-import-form');
    const importInput = document.getElementById('social-url-input');
    const importBtn = document.getElementById('social-import-submit-btn');

    importTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const platform = tab.dataset.platform;
            currentImportPlatform = platform;

            // Reset tabs UI styling
            importTabs.forEach(t => {
                t.className = "social-tab-btn flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold rounded-md transition-all text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200";
            });

            // Set active tab styling
            if (platform === 'linkedin') {
                tab.className = "social-tab-btn flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold rounded-md transition-all text-[#0a66c2] bg-white dark:bg-slate-600 shadow-sm";
                importInput.placeholder = "LinkedIn Post URL";
                importInput.className = "w-full bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-md px-3 py-1.5 text-sm dark:text-white focus:ring-2 focus:ring-[#0a66c2] outline-none transition-all";
                importBtn.className = "w-full bg-[#0a66c2] hover:bg-[#084f97] text-white font-medium py-1.5 px-3 rounded-md text-sm transition-colors shadow-sm flex items-center justify-center gap-2";
            } else if (platform === 'facebook') {
                tab.className = "social-tab-btn flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold rounded-md transition-all text-[#1877f2] bg-white dark:bg-slate-600 shadow-sm";
                importInput.placeholder = "Facebook Post URL";
                importInput.className = "w-full bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-md px-3 py-1.5 text-sm dark:text-white focus:ring-2 focus:ring-[#1877f2] outline-none transition-all";
                importBtn.className = "w-full bg-[#1877f2] hover:bg-[#156bec] text-white font-medium py-1.5 px-3 rounded-md text-sm transition-colors shadow-sm flex items-center justify-center gap-2";
            } else if (platform === 'instagram') {
                tab.className = "social-tab-btn flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold rounded-md transition-all text-[#e1306c] bg-white dark:bg-slate-600 shadow-sm";
                importInput.placeholder = "Instagram Post/Reel URL";
                importInput.className = "w-full bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-md px-3 py-1.5 text-sm dark:text-white focus:ring-2 focus:ring-[#e1306c] outline-none transition-all";
                importBtn.className = "w-full bg-[#e1306c] hover:bg-[#c1245c] text-white font-medium py-1.5 px-3 rounded-md text-sm transition-colors shadow-sm flex items-center justify-center gap-2";
            }
        });
    });

    // Unified Social Import Form Submit
    importForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = importInput.value;
        if (!url) return;
        
        const origText = importBtn.innerHTML;
        importBtn.disabled = true;
        importBtn.innerHTML = '<span class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full inline-block"></span> Importing...';
        
        try {
            const res = await fetch(`${API_BASE}/${currentImportPlatform}/import`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url})
            });
            if (res.ok) {
                importInput.value = '';
                const platformName = currentImportPlatform.charAt(0).toUpperCase() + currentImportPlatform.slice(1);
                showToast(`${platformName} post imported!`);
                if (currentFilter !== 'undone') {
                    setFilter('undone');
                } else {
                    await loadArticles();
                }
            } else {
                const data = await res.json();
                showToast(data.detail || 'Failed to import.', 'error');
            }
        } catch (err) {
            showToast('Network error.', 'error');
        } finally {
            importBtn.disabled = false;
            importBtn.innerHTML = origText;
        }
    });

    // Filters
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            setFilter(e.target.dataset.filter);
        });
    });

    // Search
    const searchInput = document.getElementById('search-input');
    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            currentSearch = e.target.value;
            loadArticles();
        }, 300);
    });

    // Article Status & Action Buttons
    document.getElementById('btn-unread').addEventListener('click', () => updateArticleStatus('unread'));
    document.getElementById('btn-posted').addEventListener('click', () => updateArticleStatus('posted'));
    document.getElementById('btn-whatsapped').addEventListener('click', () => updateArticleStatus('whatsapped'));
    document.getElementById('btn-done').addEventListener('click', () => updateArticleStatus('done'));
    document.getElementById('btn-copy-html').addEventListener('click', copyArticleHtml);
    
    // Edit Toggle
    document.getElementById('btn-edit-toggle').addEventListener('click', toggleEditMode);
    
    // Save Edit
    document.getElementById('btn-save').addEventListener('click', saveArticleEdit);
    
    // Delete Article
    document.getElementById('btn-delete-article').addEventListener('click', deleteArticle);
    
    // Dark Mode
    document.getElementById('dark-mode-toggle').addEventListener('click', toggleDarkMode);
    
    // Seamless Edit Mode: Click viewer area to edit
    document.getElementById('viewer-mode').addEventListener('click', () => {
        if (!isEditMode) toggleEditMode();
    });

    // Sidebar Accordion Toggle
    const accordionHeader = document.getElementById('accordion-header');
    const accordionContent = document.getElementById('accordion-content');
    const accordionChevron = document.getElementById('accordion-chevron');
    if (accordionHeader && accordionContent) {
        accordionHeader.addEventListener('click', () => {
            accordionContent.classList.toggle('hidden');
            accordionChevron.classList.toggle('rotate-180');
        });
    }

    // Toolbar Dropdowns
    const shareDropdownBtn = document.getElementById('btn-share-dropdown');
    const shareDropdownMenu = document.getElementById('share-dropdown-menu');
    const moreDropdownBtn = document.getElementById('btn-more-dropdown');
    const moreDropdownMenu = document.getElementById('more-dropdown-menu');

    if (shareDropdownBtn && shareDropdownMenu) {
        shareDropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            shareDropdownMenu.classList.toggle('hidden');
            if(moreDropdownMenu) moreDropdownMenu.classList.add('hidden');
        });
    }

    if (moreDropdownBtn && moreDropdownMenu) {
        moreDropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            moreDropdownMenu.classList.toggle('hidden');
            if(shareDropdownMenu) shareDropdownMenu.classList.add('hidden');
        });
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (shareDropdownMenu && !shareDropdownBtn.contains(e.target) && !shareDropdownMenu.contains(e.target)) {
            shareDropdownMenu.classList.add('hidden');
        }
        if (moreDropdownMenu && !moreDropdownBtn.contains(e.target) && !moreDropdownMenu.contains(e.target)) {
            moreDropdownMenu.classList.add('hidden');
        }
    });
}

function setFilter(filter) {
    currentFilter = filter;
    
    // Update active UI
    document.querySelectorAll('.filter-btn').forEach(btn => {
        if (btn.dataset.filter === filter) {
            btn.classList.add('text-marine-600', 'border-marine-600');
            btn.classList.remove('text-slate-500', 'border-transparent');
        } else {
            btn.classList.remove('text-marine-600', 'border-marine-600');
            btn.classList.add('text-slate-500', 'border-transparent');
        }
    });
    
    loadArticles();
}

async function loadFeeds() {
    try {
        const res = await fetch(`${API_BASE}/feeds/`);
        currentFeeds = await res.json();
        renderFeeds(currentFeeds);
    } catch (err) {
        console.error("Error loading feeds", err);
    }
}

function renderFeeds(feeds) {
    const list = document.getElementById('feed-list');
    list.innerHTML = `
        <div class="py-2 px-3 my-1 cursor-pointer rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors flex items-center gap-2 text-sm font-medium ${currentFeedId === 'all' ? 'bg-slate-100 dark:bg-slate-800 font-semibold text-marine-700 dark:text-marine-300' : ''}" onclick="filterByFeed('all')">
            <i class="fas fa-list text-slate-400 w-4 text-center text-xs"></i> All Feeds
        </div>
        <div class="py-2 px-3 my-1 cursor-pointer rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors flex items-center gap-2 text-sm font-medium ${currentFeedId === 'linkedin' ? 'bg-slate-100 dark:bg-slate-800 font-semibold text-[#0a66c2]' : ''}" onclick="filterByFeed('linkedin')">
            <i class="fab fa-linkedin text-[#0a66c2] w-4 text-center"></i> LinkedIn
        </div>
        <div class="py-2 px-3 my-1 cursor-pointer rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors flex items-center gap-2 text-sm font-medium ${currentFeedId === 'facebook' ? 'bg-slate-100 dark:bg-slate-800 font-semibold text-[#1877f2]' : ''}" onclick="filterByFeed('facebook')">
            <i class="fab fa-facebook text-[#1877f2] w-4 text-center"></i> Facebook
        </div>
        <div class="py-2 px-3 my-1 cursor-pointer rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors flex items-center gap-2 text-sm font-medium ${currentFeedId === 'instagram' ? 'bg-slate-100 dark:bg-slate-800 font-semibold text-[#e1306c]' : ''}" onclick="filterByFeed('instagram')">
            <i class="fab fa-instagram text-[#e1306c] w-4 text-center"></i> Instagram
        </div>
    `;
    
    feeds.forEach(feed => {
        const domain = new URL(feed.url).hostname;
        const faviconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
        
        const el = document.createElement('div');
        const isActive = currentFeedId === feed.id;
        el.className = `group py-2 px-3 my-1 cursor-pointer rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors flex items-center justify-between text-sm ${isActive ? 'bg-slate-100 dark:bg-slate-800 font-semibold text-marine-600 dark:text-marine-400' : ''}`;
        el.innerHTML = `
            <div class="flex items-center gap-2 truncate" onclick="filterByFeed(${feed.id})">
                <img src="${faviconUrl}" class="w-4 h-4 rounded-sm" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><circle cx=%2250%22 cy=%2250%22 r=%2240%22 fill=%22%23cbd5e1%22/></svg>'"> 
                <span class="truncate" title="${feed.title}">${feed.title}</span>
            </div>
            <button onclick="deleteFeed(event, ${feed.id})" class="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500 transition-all p-1" title="Delete Feed">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
            </button>
        `;
        list.appendChild(el);
    });
}

async function deleteFeed(event, feedId) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to delete this feed? All UNDONE articles will be removed. DONE articles will be kept.')) return;
    
    try {
        const res = await fetch(`${API_BASE}/feeds/${feedId}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('Feed deleted.');
            if (currentFeedId === feedId) currentFeedId = 'all';
            await loadFeeds();
            await loadArticles();
        } else {
            showToast('Failed to delete feed.', 'error');
        }
    } catch (err) {
        showToast('Network error.', 'error');
    }
}

let currentFeedId = 'all';
function filterByFeed(id) {
    currentFeedId = id;
    renderFeeds(currentFeeds);
    loadArticles();
}

async function loadArticles() {
    try {
        let url = `${API_BASE}/articles/?status_filter=${currentFilter}`;
        if (currentFeedId && currentFeedId !== 'all') url += `&feed_id=${currentFeedId}`;
        if (currentSearch) url += `&search=${encodeURIComponent(currentSearch)}`;
        
        const res = await fetch(url);
        const articles = await res.json();
        renderArticles(articles);
    } catch (err) {
        console.error("Error loading articles", err);
    }
}

function renderArticles(articles) {
    const list = document.getElementById('article-list');
    list.innerHTML = '';
    
    if (articles.length === 0) {
        list.innerHTML = '<div class="p-8 text-center text-slate-500 text-sm">No articles found.</div>';
        return;
    }

    articles.forEach(article => {
        const el = document.createElement('div');
        const isRead = article.is_read;
        el.className = `p-4 border-b border-slate-200 dark:border-slate-700 cursor-pointer transition-colors hover:bg-slate-100 dark:hover:bg-slate-700/50 ${isRead ? 'bg-slate-50 dark:bg-slate-800/80 opacity-80' : 'bg-white dark:bg-slate-800'}`;
        if (selectedArticle && selectedArticle.id === article.id) {
            el.classList.add('ring-2', 'ring-inset', 'ring-marine-500', 'bg-marine-50', 'dark:bg-marine-900/40');
        }
        
        const date = new Date(article.published_date || article.added_at).toLocaleDateString(undefined, {month: 'short', day: 'numeric'});
        
        const displayTitle = article.edited_title || article.title;
        const displayDesc = stripHtml(article.edited_description || article.description || '');
        
        // Badges
        let badges = '';
        if (!isRead) badges += '<span class="inline-block px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-[10px] uppercase font-bold mr-1">Unread</span>';
        else badges += '<span class="inline-block px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 text-[10px] uppercase font-bold mr-1">Read</span>';
        
        if (article.is_posted) badges += '<span class="inline-block px-1.5 py-0.5 rounded bg-[#ff5722] text-white text-[10px] uppercase font-bold mr-1">Posted</span>';
        if (article.is_whatsapped) badges += '<span class="inline-block px-1.5 py-0.5 rounded bg-green-100 text-green-700 text-[10px] uppercase font-bold mr-1">WA</span>';
        if (article.is_done) badges += '<span class="inline-block px-1.5 py-0.5 rounded bg-marine-100 text-marine-700 text-[10px] uppercase font-bold mr-1">Done</span>';

        let faviconImg = '';
        if (article.feed_id) {
            const feed = currentFeeds.find(f => f.id === article.feed_id);
            if (feed) {
                const domain = new URL(feed.url).hostname;
                faviconImg = `<img src="https://www.google.com/s2/favicons?domain=${domain}&sz=32" class="w-3.5 h-3.5 rounded-sm" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><circle cx=%2250%22 cy=%2250%22 r=%2240%22 fill=%22%23cbd5e1%22/></svg>'">`;
            } else {
                faviconImg = '<div class="w-2 h-2 rounded-full bg-slate-400"></div>';
            }
        } else {
            // Social / Manual import brand icon
            const link = article.link || '';
            if (link.includes('linkedin.com')) {
                faviconImg = '<i class="fab fa-linkedin text-[#0a66c2] text-xs w-3.5 text-center"></i>';
            } else if (link.includes('facebook.com') || link.includes('fb.watch') || link.includes('fb.com')) {
                faviconImg = '<i class="fab fa-facebook text-[#1877f2] text-xs w-3.5 text-center"></i>';
            } else if (link.includes('instagram.com') || link.includes('instagr.am')) {
                faviconImg = '<i class="fab fa-instagram text-[#e1306c] text-xs w-3.5 text-center"></i>';
            } else {
                faviconImg = '<i class="fas fa-link text-slate-400 text-xs w-3.5 text-center"></i>';
            }
        }

        el.innerHTML = `
            <div class="flex justify-between items-baseline mb-1">
                <div class="flex items-center gap-1.5 truncate mr-2">
                    ${faviconImg}
                    <span class="text-xs font-semibold text-marine-600 dark:text-marine-400 truncate">${getFeedTitle(article.feed_id, article.link)}</span>
                </div>
                <span class="text-xs text-slate-400 whitespace-nowrap">${date}</span>
            </div>
            <h3 class="text-slate-800 dark:text-slate-200 font-semibold leading-snug mb-1 text-sm ${!isRead ? 'text-black dark:text-white' : ''}">${displayTitle}</h3>
            <div class="mb-1">${badges}</div>
        `;
        
        el.onclick = () => openArticle(article);
        list.appendChild(el);
    });
}

function getFeedTitle(id, link) {
    if (!id) {
        if (link && link.includes('linkedin.com')) return 'LinkedIn';
        if (link && (link.includes('facebook.com') || link.includes('fb.watch') || link.includes('fb.com'))) return 'Facebook';
        if (link && (link.includes('instagram.com') || link.includes('instagr.am'))) return 'Instagram';
        return 'Manual Import';
    }
    const feed = currentFeeds.find(f => f.id === id);
    return feed ? feed.title : 'Unknown';
}

function stripHtml(html) {
    const tmp = document.createElement("DIV");
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || "";
}

async function openArticle(article) {
    selectedArticle = article;
    isEditMode = false;
    
    // Refresh list to highlight selected
    loadArticles();
    
    const pane = document.getElementById('article-content-pane');
    const toolbar = document.getElementById('article-toolbar');
    
    pane.classList.remove('hidden');
    toolbar.classList.remove('hidden');
    
    updateToolbar();
    renderArticleView();
    
    if (!article.is_read) {
        try {
            await fetch(`${API_BASE}/articles/${article.id}/status`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({status_type: 'read', value: true})
            });
            article.is_read = 1;
        } catch (e) { console.error(e); }
    }
}

function renderArticleView() {
    const article = selectedArticle;
    if (!article) return;
    
    document.getElementById('article-link').href = article.link;
    document.getElementById('article-date').innerText = new Date(article.published_date || article.added_at).toLocaleString();
    
    const title = article.edited_title || article.title;
    const desc = article.edited_description || article.description || '';
    const content = article.edited_content || article.content || desc || 'No content available.';
    
    if (isEditMode) {
        document.getElementById('viewer-mode').classList.add('hidden');
        document.getElementById('editor-mode').classList.remove('hidden');
        
        document.getElementById('edit-title').value = title;
        document.getElementById('edit-date-display').innerText = new Date(article.published_date || article.added_at).toLocaleString();
        quill.setContents([]); // Clear first
        quill.clipboard.dangerouslyPasteHTML(0, content);
    } else {
        document.getElementById('editor-mode').classList.add('hidden');
        document.getElementById('viewer-mode').classList.remove('hidden');
        
        document.getElementById('article-title').innerText = title;
        document.getElementById('article-body').innerHTML = content;
    }
    updateToolbar();
}

function updateToolbar() {
    const article = selectedArticle;
    if (!article) return;

    // 1. Source Tag
    const sourceTag = document.getElementById('article-source-tag');
    let sourceHtml = '';
    const isLinkedIn = !article.feed_id && article.link && article.link.includes('linkedin.com');
    const isFacebook = !article.feed_id && article.link && (article.link.includes('facebook.com') || article.link.includes('fb.watch') || article.link.includes('fb.com'));
    const isInstagram = !article.feed_id && article.link && (article.link.includes('instagram.com') || article.link.includes('instagr.am'));
    
    if (isLinkedIn) {
        sourceHtml = '<i class="fab fa-linkedin-in text-[#0a66c2]"></i> LinkedIn Post';
    } else if (isFacebook) {
        sourceHtml = '<i class="fab fa-facebook-f text-[#1877f2]"></i> Facebook Post';
    } else if (isInstagram) {
        sourceHtml = '<i class="fab fa-instagram text-[#e1306c]"></i> Instagram Post';
    } else if (!article.feed_id) {
        sourceHtml = '<i class="fas fa-pen-nib text-slate-500"></i> Manual Entry';
    } else {
        sourceHtml = '<i class="fas fa-rss text-marine-500"></i> RSS Feed';
    }
    sourceTag.innerHTML = sourceHtml;

    // Done articles hide the Unread toggle to maintain stability
    const unreadBtn = document.getElementById('btn-unread');
    if (article.is_done) {
        unreadBtn.classList.add('hidden');
    } else {
        unreadBtn.classList.remove('hidden');
        const unreadText = document.getElementById('btn-unread-text');
        if(unreadText) unreadText.innerText = article.is_read ? 'Mark Unread' : 'Mark Read';
    }
    
    // Posted (Dropdown Item)
    const postedBtn = document.getElementById('btn-posted');
    const postedSpan = postedBtn.querySelector('span');
    if (article.is_posted) {
        postedBtn.classList.add('bg-slate-100', 'dark:bg-slate-700');
        if(postedSpan) postedSpan.innerHTML = 'Posted to Blogger <i class="fas fa-check text-[#ff5722] ml-1"></i>';
    } else {
        postedBtn.classList.remove('bg-slate-100', 'dark:bg-slate-700');
        if(postedSpan) postedSpan.innerText = 'Mark Posted (Blogger)';
    }

    // Whatsapped (Dropdown Item)
    const waBtn = document.getElementById('btn-whatsapped');
    const waSpan = waBtn.querySelector('span');
    if (article.is_whatsapped) {
        waBtn.classList.add('bg-slate-100', 'dark:bg-slate-700');
        if(waSpan) waSpan.innerHTML = 'Shared to WhatsApp <i class="fas fa-check text-green-600 ml-1"></i>';
    } else {
        waBtn.classList.remove('bg-slate-100', 'dark:bg-slate-700');
        if(waSpan) waSpan.innerText = 'Mark Shared (WA)';
    }

    // Edit Toggle
    const editBtn = document.getElementById('btn-edit-toggle');
    const editBtnText = editBtn.querySelector('span');
    if (isEditMode) {
        if(editBtnText) editBtnText.innerText = 'Cancel Edit';
        editBtn.classList.add('bg-slate-100', 'text-slate-700', 'dark:bg-slate-700', 'dark:text-slate-300');
        editBtn.classList.remove('bg-marine-50', 'text-marine-700');
    } else {
        if(editBtnText) editBtnText.innerText = 'Edit Mode';
        editBtn.classList.remove('bg-slate-100', 'text-slate-700', 'dark:bg-slate-700', 'dark:text-slate-300');
        editBtn.classList.add('bg-marine-50', 'text-marine-700');
    }

    // Delete button logic: Show for Done articles AND social posts
    const deleteBtn = document.getElementById('btn-delete-article');
    const isSocial = !article.feed_id;
    if (article.is_done || currentFilter === 'done' || isSocial) {
        deleteBtn.classList.remove('hidden');
    } else {
        deleteBtn.classList.add('hidden');
    }
}

function toggleEditMode() {
    isEditMode = !isEditMode;
    renderArticleView();
}

async function updateArticleStatus(type) {
    if (!selectedArticle) return;
    
    let targetValue = true;
    let statusType = type;
    
    if (type === 'unread') {
        statusType = 'read';
        targetValue = !selectedArticle.is_read;
    } else if (type === 'posted') {
        targetValue = !selectedArticle.is_posted;
    } else if (type === 'whatsapped') {
        targetValue = !selectedArticle.is_whatsapped;
    } else if (type === 'done') {
        targetValue = !selectedArticle.is_done;
    }
    
    try {
        const res = await fetch(`${API_BASE}/articles/${selectedArticle.id}/status`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({status_type: statusType, value: targetValue})
        });
        
        if (res.ok) {
            showToast(`Status updated: ${type} ${targetValue ? 'set' : 'removed'}`);
            if (type === 'unread') selectedArticle.is_read = targetValue ? 1 : 0;
            if (type === 'posted') selectedArticle.is_posted = targetValue ? 1 : 0;
            if (type === 'whatsapped') selectedArticle.is_whatsapped = targetValue ? 1 : 0;
            if (type === 'done') selectedArticle.is_done = targetValue ? 1 : 0;
            
            // UI Button Text Update for Unread/Read
            if (type === 'unread') {
                const unreadText = document.getElementById('btn-unread-text');
                if (unreadText) unreadText.innerText = selectedArticle.is_read ? 'Mark Unread' : 'Mark Read';
            }
            
            // Refresh current list depending on filter
            if ((currentFilter === 'undone' && type === 'done') || 
                (currentFilter === 'unread' && type === 'read') ||
                (currentFilter === 'read' && type === 'unread')) {
                // Remove from view
                document.getElementById('article-content-pane').classList.add('hidden');
                document.getElementById('article-toolbar').classList.add('hidden');
                selectedArticle = null;
            } else {
                updateToolbar();
            }
            loadArticles();
        }
    } catch (e) {
        showToast('Failed to update status', 'error');
    }
}

async function saveArticleEdit() {
    if (!selectedArticle) return;
    
    const title = document.getElementById('edit-title').value;
    const desc = selectedArticle.edited_description || selectedArticle.description || '';
    const content = quill.root.innerHTML;
    
    const btn = document.getElementById('btn-save');
    const orig = btn.innerHTML;
    btn.innerHTML = 'Saving...';
    
    try {
        const res = await fetch(`${API_BASE}/articles/${selectedArticle.id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title, description: desc, content})
        });
        
        if (res.ok) {
            showToast('Modifications saved!');
            selectedArticle.edited_title = title;
            selectedArticle.edited_description = desc;
            selectedArticle.edited_content = content;
            // No longer moving to Done automatically
            
            isEditMode = false;
            renderArticleView();
            loadArticles();
        } else {
             showToast('Failed to save.', 'error');
        }
    } catch (e) {
        showToast('Network error.', 'error');
    } finally {
        btn.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg> Save Modifications`;
    }
}

function copyArticleHtml() {
    if (!selectedArticle) return;
    
    let content = '';
    if (isEditMode) {
        content = quill.root.innerHTML;
    } else {
        content = document.getElementById('article-body').innerHTML;
    }
    
    navigator.clipboard.writeText(content).then(() => {
        showToast('HTML content copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy: ', err);
        showToast('Failed to copy HTML.', 'error');
    });
}

async function deleteArticle() {
    if (!selectedArticle) return;
    if (!confirm('Are you sure you want to permanently delete this article?')) return;
    
    try {
        const res = await fetch(`${API_BASE}/articles/${selectedArticle.id}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('Article deleted.');
            document.getElementById('article-content-pane').classList.add('hidden');
            document.getElementById('article-toolbar').classList.add('hidden');
            selectedArticle = null;
            await loadArticles();
        } else {
            showToast('Failed to delete article.', 'error');
        }
    } catch (err) {
        showToast('Network error.', 'error');
    }
}
