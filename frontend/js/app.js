/**
 * Refactoring Workbench - Frontend Application v2.0
 * Handles all UI logic, API interactions, and state management.
 */

const API = '';  // Same origin

// ============== State ==============
let state = {
    projects: [],
    rules: [],
    scanResults: null,
    history: [],
};

// ============== Toast Notifications ==============
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const colors = {
        success: 'bg-emerald-500', error: 'bg-red-500',
        info: 'bg-blue-500', warning: 'bg-amber-500'
    };
    const el = document.createElement('div');
    el.className = `${colors[type] || colors.info} text-white px-4 py-3 rounded-xl shadow-lg text-sm font-medium animate-slideUp max-w-sm`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

// ============== Tab Navigation ==============
function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const isActive = btn.dataset.tab === name;
        btn.classList.toggle('border-blue-500', isActive);
        btn.classList.toggle('text-blue-600', isActive);
        btn.classList.toggle('border-transparent', !isActive);
        btn.classList.toggle('text-slate-500', !isActive);
    });
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(`tab-${name}`);
    if (target) target.classList.add('active');

    // Load data for the active tab
    switch (name) {
        case 'dashboard': loadDashboard(); break;
        case 'projects': loadProjects(); loadConfig(); break;
        case 'rules': loadRules(); break;
        case 'execute': loadExecuteOptions(); break;
        case 'tracking': loadTrackingFilters(); break;
        case 'history': loadHistory(); break;
    }
}

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ============== Modal Helpers ==============
function openModal(id) { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

// ============== API Helper ==============
async function api(path, opts = {}) {
    const url = `${API}${path}`;
    opts.headers = opts.headers || {};
    if (opts.body && typeof opts.body === 'object') {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || JSON.stringify(err));
    }
    if (res.status === 204) return null;
    return res.json();
}

// ============== Dashboard ==============
async function loadDashboard() {
    try {
        const data = await api('/api/dashboard');
        renderDashboardStats(data);
        renderDashboardRecent(data.recent_executions);
    } catch (err) {
        showToast('Failed to load dashboard: ' + err.message, 'error');
    }
}

function renderDashboardStats(stats) {
    const cards = [
        { label: 'Projects', value: stats.active_projects, total: stats.total_projects, color: 'from-blue-500 to-blue-600', icon: '📁' },
        { label: 'Active Rules', value: stats.active_rules, total: stats.total_rules, color: 'from-violet-500 to-purple-600', icon: '📋' },
        { label: 'Executions', value: stats.total_executions, color: 'from-emerald-500 to-green-600', icon: '🚀' },
        { label: 'Replacements', value: stats.total_replacements, color: 'from-amber-500 to-orange-600', icon: '🔄' },
    ];

    document.getElementById('dashboard-stats').innerHTML = cards.map(c => `
        <div class="stat-card bg-white rounded-2xl shadow-sm border border-slate-200 p-6 relative overflow-hidden">
            <div class="flex items-start justify-between">
                <div>
                    <p class="text-sm font-medium text-slate-500">${c.label}</p>
                    <p class="text-3xl font-bold mt-1 bg-gradient-to-r ${c.color} bg-clip-text text-transparent">${c.value.toLocaleString()}</p>
                    ${c.total !== undefined ? `<p class="text-xs text-slate-400 mt-1">${c.total} total</p>` : ''}
                </div>
                <span class="text-2xl">${c.icon}</span>
            </div>
            <div class="absolute bottom-0 right-0 w-32 h-32 bg-gradient-to-br ${c.color} opacity-5 rounded-tl-full"></div>
        </div>
    `).join('');
}

function renderDashboardRecent(executions) {
    const el = document.getElementById('dashboard-recent');
    if (!executions.length) {
        el.innerHTML = '<p class="text-sm text-slate-400 italic">No executions yet</p>';
        return;
    }
    el.innerHTML = executions.map(ex => `
        <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
            <div>
                <span class="text-sm font-medium text-slate-700">${ex.rule_name || `Rule #${ex.rule_id}`}</span>
                <span class="text-xs text-slate-400 ml-2">${new Date(ex.executed_at).toLocaleString()}</span>
            </div>
            <div class="flex items-center gap-2">
                <span class="text-xs px-2 py-0.5 rounded-full ${ex.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}">${ex.total_replacements} changes</span>
            </div>
        </div>
    `).join('');
}

// ============== Projects ==============
async function loadProjects() {
    try {
        state.projects = await api('/api/projects');
        renderProjects();
    } catch (err) {
        showToast('Failed to load projects: ' + err.message, 'error');
    }
}

function renderProjects() {
    document.getElementById('project-list').innerHTML = state.projects.map(p => `
        <div class="bg-white rounded-xl border border-slate-200 p-4 transition-all hover:shadow-md ${!p.is_active ? 'opacity-50' : ''}">
            <div class="flex items-start justify-between">
                <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                        <h4 class="text-sm font-semibold text-slate-800 truncate">${p.name}</h4>
                        ${p.is_active ? '<span class="px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-emerald-100 text-emerald-700">Active</span>' : '<span class="px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-slate-100 text-slate-500">Inactive</span>'}
                    </div>
                    <p class="text-xs text-slate-400 mt-0.5 font-mono truncate">${p.root_path}</p>
                    ${p.description ? `<p class="text-xs text-slate-500 mt-1">${p.description}</p>` : ''}
                </div>
                <div class="flex items-center gap-1 ml-2">
                    <button onclick="gitStatus(${p.id})" title="Git Status" class="p-1.5 rounded-lg hover:bg-blue-50 text-blue-500 hover:text-blue-700">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/></svg>
                    </button>
                    <button onclick="editProject(${p.id})" title="Edit" class="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
                    </button>
                    <button onclick="deleteProject(${p.id})" title="Delete" class="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-600">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                    </button>
                </div>
            </div>
        </div>
    `).join('') || '<p class="text-sm text-slate-400">No projects configured</p>';
}

function openProjectModal(project = null) {
    const isEdit = !!project;
    document.getElementById('project-modal-title').textContent = isEdit ? 'Edit Project' : 'Add Project';
    document.getElementById('project-id').value = isEdit ? project.id : '';
    document.getElementById('project-name').value = isEdit ? project.name : '';
    document.getElementById('project-path').value = isEdit ? project.root_path : '';
    document.getElementById('project-desc').value = isEdit ? (project.description || '') : '';
    document.getElementById('project-active').checked = isEdit ? project.is_active : true;
    openModal('project-modal');
}

async function browseFolder() {
    try {
        const result = await api('/api/utils/browse');
        if (result.path) {
            document.getElementById('project-path').value = result.path;
        } else if (result.error) {
            showToast('Browse error: ' + result.error, 'error');
        }
    } catch (err) {
        showToast('Browse failed: ' + err.message, 'error');
    }
}

function editProject(id) {
    const project = state.projects.find(p => p.id === id);
    if (project) openProjectModal(project);
}

async function saveProject(event) {
    event.preventDefault();
    const id = document.getElementById('project-id').value;
    const data = {
        name: document.getElementById('project-name').value,
        root_path: document.getElementById('project-path').value,
        description: document.getElementById('project-desc').value || null,
        is_active: document.getElementById('project-active').checked,
    };

    try {
        if (id) {
            await api(`/api/projects/${id}`, { method: 'PUT', body: data });
            showToast('Project updated', 'success');
        } else {
            await api('/api/projects', { method: 'POST', body: data });
            showToast('Project created', 'success');
        }
        closeModal('project-modal');
        loadProjects();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function deleteProject(id) {
    if (!confirm('Are you sure you want to delete this project?')) return;
    try {
        await api(`/api/projects/${id}`, { method: 'DELETE' });
        showToast('Project deleted', 'success');
        loadProjects();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ============== Git Operations ==============
async function gitStatus(projectId) {
    try {
        const data = await api(`/api/git/status/${projectId}`, { method: 'POST' });
        if (!data.is_repo) {
            showToast('Not a Git repository', 'warning');
            return;
        }
        const msg = `Branch: ${data.branch || 'unknown'}\nModified: ${data.modified_count} files${data.ahead ? `\nAhead: ${data.ahead}` : ''}${data.behind ? `\nBehind: ${data.behind}` : ''}`;
        alert(msg);
    } catch (err) {
        showToast('Git status failed: ' + err.message, 'error');
    }
}

async function gitPull(projectId) {
    try {
        const data = await api(`/api/git/pull/${projectId}`, { method: 'POST' });
        showToast(data.message, data.success ? 'success' : 'error');
    } catch (err) {
        showToast('Git pull failed: ' + err.message, 'error');
    }
}

async function autoMerge() {
    if (!confirm('This will pull all projects and re-apply active rules. Continue?')) return;
    showToast('Auto-merge started...', 'info');
    try {
        const data = await api('/api/git/auto-merge', { method: 'POST' });
        let msg = `Auto-Merge Complete\n\n`;
        msg += `Projects: ${data.total_projects}\n`;
        msg += `Successful pulls: ${data.successful_pulls}\n`;
        msg += `Total replacements: ${data.total_replacements}\n\n`;
        data.results.forEach(r => {
            msg += `• ${r.project_name}: ${r.pull_message} (${r.replacements_made} replacements)\n`;
        });
        alert(msg);
        showToast('Auto-merge completed', 'success');
    } catch (err) {
        showToast('Auto-merge failed: ' + err.message, 'error');
    }
}

// ============== Scan Configuration ==============
async function loadConfig() {
    try {
        const config = await api('/api/config');
        document.getElementById('cfg-include').value = config.include_extensions || '';
        document.getElementById('cfg-exclude').value = config.exclude_extensions || '';
        document.getElementById('cfg-folders').value = config.exclude_folders || '';
    } catch (err) {
        showToast('Failed to load config', 'error');
    }
}

async function saveConfig(event) {
    event.preventDefault();
    try {
        await api('/api/config', {
            method: 'PUT',
            body: {
                include_extensions: document.getElementById('cfg-include').value,
                exclude_extensions: document.getElementById('cfg-exclude').value,
                exclude_folders: document.getElementById('cfg-folders').value,
            }
        });
        showToast('Configuration saved', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ============== Rules ==============
async function loadRules() {
    try {
        state.rules = await api('/api/rules');
        renderRules();
    } catch (err) {
        showToast('Failed to load rules: ' + err.message, 'error');
    }
}

function renderRules() {
    document.getElementById('rule-list').innerHTML = state.rules.map(r => `
        <div class="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md transition-all ${!r.is_active ? 'opacity-50' : ''}">
            <div class="flex items-start justify-between">
                <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                        <h4 class="text-sm font-semibold text-slate-800">${r.name}</h4>
                        ${r.is_regex ? '<span class="px-1.5 py-0.5 text-[10px] rounded bg-violet-100 text-violet-700">Regex</span>' : ''}
                        ${!r.case_sensitive ? '<span class="px-1.5 py-0.5 text-[10px] rounded bg-amber-100 text-amber-700">Case-insensitive</span>' : ''}
                    </div>
                    <div class="flex items-center gap-2 mt-1.5">
                        <code class="text-xs text-red-600 bg-red-50 px-1.5 py-0.5 rounded">${escHtml(r.search_pattern)}</code>
                        <span class="text-xs text-slate-400">→</span>
                        <code class="text-xs text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">${escHtml(r.replacement_text)}</code>
                    </div>
                    ${r.description ? `<p class="text-xs text-slate-500 mt-1">${r.description}</p>` : ''}
                    ${r.target_extensions ? `<p class="text-[10px] text-slate-400 mt-0.5">Files: ${r.target_extensions}</p>` : ''}
                </div>
                <div class="flex items-center gap-1 ml-2">
                    <button onclick="editRule(${r.id})" title="Edit" class="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
                    </button>
                    <button onclick="deleteRule(${r.id})" title="Delete" class="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-600">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                    </button>
                </div>
            </div>
        </div>
    `).join('') || '<p class="text-sm text-slate-400">No rules defined yet</p>';
}

function openRuleModal(rule = null) {
    const isEdit = !!rule;
    document.getElementById('rule-modal-title').textContent = isEdit ? 'Edit Rule' : 'Add Rule';
    document.getElementById('rule-id').value = isEdit ? rule.id : '';
    document.getElementById('rule-name').value = isEdit ? rule.name : '';
    document.getElementById('rule-search').value = isEdit ? rule.search_pattern : '';
    document.getElementById('rule-replace').value = isEdit ? rule.replacement_text : '';
    document.getElementById('rule-exts').value = isEdit ? (rule.target_extensions || '') : '';
    document.getElementById('rule-desc').value = isEdit ? (rule.description || '') : '';
    document.getElementById('rule-regex').checked = isEdit ? rule.is_regex : false;
    document.getElementById('rule-case').checked = isEdit ? rule.case_sensitive : true;
    document.getElementById('rule-active').checked = isEdit ? rule.is_active : true;
    openModal('rule-modal');
}

function editRule(id) {
    const rule = state.rules.find(r => r.id === id);
    if (rule) openRuleModal(rule);
}

async function saveRule(event) {
    event.preventDefault();
    const id = document.getElementById('rule-id').value;
    const data = {
        name: document.getElementById('rule-name').value,
        search_pattern: document.getElementById('rule-search').value,
        replacement_text: document.getElementById('rule-replace').value,
        target_extensions: document.getElementById('rule-exts').value || null,
        description: document.getElementById('rule-desc').value || null,
        is_regex: document.getElementById('rule-regex').checked,
        case_sensitive: document.getElementById('rule-case').checked,
        is_active: document.getElementById('rule-active').checked,
    };

    try {
        if (id) {
            await api(`/api/rules/${id}`, { method: 'PUT', body: data });
            showToast('Rule updated', 'success');
        } else {
            await api('/api/rules', { method: 'POST', body: data });
            showToast('Rule created', 'success');
        }
        closeModal('rule-modal');
        loadRules();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function deleteRule(id) {
    if (!confirm('Delete this rule?')) return;
    try {
        await api(`/api/rules/${id}`, { method: 'DELETE' });
        showToast('Rule deleted', 'success');
        loadRules();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ============== Rule Import / Export ==============
async function exportRules() {
    try {
        const data = await api('/api/rules/export');
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `refactor-rules-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        showToast(`Exported ${data.count} rules`, 'success');
    } catch (err) {
        showToast('Export failed: ' + err.message, 'error');
    }
}

function triggerImportRules() {
    document.getElementById('import-file').click();
}

async function importRules(event) {
    const file = event.target.files[0];
    if (!file) return;
    try {
        const text = await file.text();
        const data = JSON.parse(text);
        const result = await api('/api/rules/import', { method: 'POST', body: data });
        showToast(`Imported ${result.imported} rules`, 'success');
        loadRules();
    } catch (err) {
        showToast('Import failed: ' + err.message, 'error');
    }
    event.target.value = '';
}

// ============== Execute Tab ==============
async function loadExecuteOptions() {
    try {
        const [rules, projects] = await Promise.all([
            api('/api/rules'),
            api('/api/projects')
        ]);
        state.rules = rules;
        state.projects = projects;

        document.getElementById('execute-rules').innerHTML = rules.filter(r => r.is_active).map(r => `
            <label class="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                <input type="checkbox" class="exec-rule-cb rounded border-slate-300 text-blue-600" value="${r.id}" checked>
                <span class="text-sm text-slate-700">${r.name}</span>
            </label>
        `).join('') || '<p class="text-xs text-slate-400">No active rules</p>';

        document.getElementById('execute-projects').innerHTML = projects.filter(p => p.is_active).map(p => `
            <label class="flex items-center gap-2 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                <input type="checkbox" class="exec-proj-cb rounded border-slate-300 text-blue-600" value="${p.id}" checked>
                <span class="text-sm text-slate-700">${p.name}</span>
            </label>
        `).join('') || '<p class="text-xs text-slate-400">No active projects</p>';
    } catch (err) {
        showToast('Failed to load options: ' + err.message, 'error');
    }
}

// Global variable to store raw scan results for filtering/sorting
let rawScanMatches = [];

async function runDryScan() {
    const ruleIds = [...document.querySelectorAll('.exec-rule-cb:checked')].map(cb => parseInt(cb.value));
    const projectIds = [...document.querySelectorAll('.exec-proj-cb:checked')].map(cb => parseInt(cb.value));

    if (!ruleIds.length) { showToast('Select at least one rule', 'warning'); return; }
    if (!projectIds.length) { showToast('Select at least one project', 'warning'); return; }

    const statusEl = document.getElementById('scan-status');
    const resultsContainer = document.getElementById('scan-results');
    statusEl.textContent = 'Initializing scan...';
    resultsContainer.innerHTML = '';
    document.getElementById('execute-actions').classList.add('hidden');

    // Reset state
    rawScanMatches = [];
    state.scanResults = { files: [] };
    state._selectedRuleIds = ruleIds;

    try {
        const response = await fetch(`${API}/api/scan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rule_ids: ruleIds, project_ids: projectIds })
        });

        if (!response.ok) throw new Error(response.statusText);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let totalScanned = 0;
        let totalFiles = 0;

        // Process stream
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const event = JSON.parse(line);

                    if (event.type === 'progress') {
                        totalScanned = event.scanned;
                        totalFiles = event.total;
                        statusEl.innerHTML = `
                            <span class="inline-flex items-center gap-2">
                                <svg class="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                Scanning: ${event.current_file} (${Math.round((event.scanned / event.total) * 100)}%)
                            </span>
                        `;
                    } else if (event.type === 'match') {
                        rawScanMatches.push(event);
                        // Add to state for execution
                        state.scanResults.files.push(event);
                        // Render immediately (or debounced for performance if needed)
                        renderScanResultsWithOptions();
                    } else if (event.type === 'error') {
                        showToast('Scan error: ' + event.message, 'error');
                    }
                } catch (e) {
                    console.error('Error parsing stream line:', line, e);
                }
            }
        }

        statusEl.textContent = `Completed: Scanned ${totalScanned} files. Found matches in ${rawScanMatches.length} files.`;
        if (rawScanMatches.length > 0) {
            document.getElementById('execute-actions').classList.remove('hidden');
            renderScanResultsWithOptions(); // Final render
        } else {
            resultsContainer.innerHTML = '<p class="text-slate-500 italic p-4">No matches found.</p>';
        }

    } catch (err) {
        statusEl.textContent = 'Scan failed';
        showToast('Scan failed: ' + err.message, 'error');
    }
}

// Store current view options
let scanViewOptions = {
    sortBy: 'path', // 'path', 'project', 'matches'
    groupBy: 'none' // 'none', 'project', 'extension'
};

function renderScanResultsWithOptions() {
    const container = document.getElementById('scan-results');

    // Header with controls (only add if not existing)
    if (!document.getElementById('scan-controls')) {
        const controls = document.createElement('div');
        controls.id = 'scan-controls';
        controls.className = 'flex flex-wrap items-center gap-4 mb-4 bg-slate-50 p-3 rounded-lg border border-slate-200';
        controls.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="text-xs font-semibold text-slate-500 uppercase">Sort by:</span>
                <select onchange="updateScanView('sortBy', this.value)" class="text-xs border-slate-300 rounded focus:ring-blue-500">
                    <option value="path" ${scanViewOptions.sortBy === 'path' ? 'selected' : ''}>File Path</option>
                    <option value="project" ${scanViewOptions.sortBy === 'project' ? 'selected' : ''}>Project</option>
                    <option value="matches" ${scanViewOptions.sortBy === 'matches' ? 'selected' : ''}>Match Count</option>
                </select>
            </div>
            <div class="flex items-center gap-2">
                <span class="text-xs font-semibold text-slate-500 uppercase">Group by:</span>
                <select onchange="updateScanView('groupBy', this.value)" class="text-xs border-slate-300 rounded focus:ring-blue-500">
                    <option value="none" ${scanViewOptions.groupBy === 'none' ? 'selected' : ''}>None</option>
                    <option value="project" ${scanViewOptions.groupBy === 'project' ? 'selected' : ''}>Project</option>
                    <option value="extension" ${scanViewOptions.groupBy === 'extension' ? 'selected' : ''}>File Type</option>
                </select>
            </div>
            <div class="ml-auto text-xs text-slate-400 font-mono">
                ${rawScanMatches.length} files matched
            </div>
        `;
        // Insert controls before the results list container, but we need a wrapper if we want to clear list only
        // Since resultsContainer is cleared, we should structure this differently.
        // Let's prepend controls to the container if we are re-rendering full list
    }

    // Sorting
    let displayFiles = [...rawScanMatches];
    displayFiles.sort((a, b) => {
        if (scanViewOptions.sortBy === 'project') return a.project_root.localeCompare(b.project_root);
        if (scanViewOptions.sortBy === 'matches') return b.match_count - a.match_count;
        return a.relative_path.localeCompare(b.relative_path);
    });

    // Grouping
    let html = `
        <div id="scan-controls-wrapper" class="sticky top-0 z-10 bg-white pb-2 border-b border-white">
            <div class="flex flex-wrap items-center gap-4 mb-2 bg-slate-50 p-2 rounded-lg border border-slate-200">
                <div class="flex items-center gap-2">
                    <span class="text-xs font-semibold text-slate-500 uppercase">Sort:</span>
                    <select onchange="updateScanView('sortBy', this.value)" class="text-xs py-1 border-slate-300 rounded focus:ring-blue-500">
                        <option value="path" ${scanViewOptions.sortBy === 'path' ? 'selected' : ''}>Path</option>
                        <option value="project" ${scanViewOptions.sortBy === 'project' ? 'selected' : ''}>Project</option>
                        <option value="matches" ${scanViewOptions.sortBy === 'matches' ? 'selected' : ''}>Most Matches</option>
                    </select>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-xs font-semibold text-slate-500 uppercase">Group:</span>
                    <select onchange="updateScanView('groupBy', this.value)" class="text-xs py-1 border-slate-300 rounded focus:ring-blue-500">
                        <option value="none" ${scanViewOptions.groupBy === 'none' ? 'selected' : ''}>None</option>
                        <option value="project" ${scanViewOptions.groupBy === 'project' ? 'selected' : ''}>Project</option>
                        <option value="extension" ${scanViewOptions.groupBy === 'extension' ? 'selected' : ''}>Type</option>
                    </select>
                </div>
            </div>
        </div>
        <div class="space-y-4 pt-2">
    `;

    if (scanViewOptions.groupBy === 'none') {
        html += displayFiles.map((f, i) => renderFileCard(f, i)).join('');
    } else {
        const groups = {};
        displayFiles.forEach(f => {
            let key = scanViewOptions.groupBy === 'project' ? f.project_root : f.extension;
            if (!key) key = 'Unknown';
            if (!groups[key]) groups[key] = [];
            groups[key].push(f);
        });

        // Sort groups keys
        Object.keys(groups).sort().forEach(groupKey => {
            const files = groups[groupKey];
            const label = scanViewOptions.groupBy === 'project' ?
                (state.projects.find(p => p.root_path === groupKey)?.name || truncatePath(groupKey)) :
                (groupKey.toUpperCase() || 'NO EXT');

            html += `
                <div class="border border-slate-200 rounded-xl overflow-hidden mb-4">
                    <div class="bg-slate-100 px-4 py-2 font-semibold text-sm text-slate-700 flex justify-between">
                        <span>${label}</span>
                        <span class="bg-white px-2 py-0.5 rounded-full text-xs border border-slate-200">${files.length}</span>
                    </div>
                    <div class="divide-y divide-slate-100">
                        ${files.map((f, i) => renderFileCard(f, i, true)).join('')}
                    </div>
                </div>
            `;
        });
    }

    html += '</div>';
    container.innerHTML = html;
}

function updateScanView(key, value) {
    scanViewOptions[key] = value;
    renderScanResultsWithOptions();
}

function renderFileCard(f, i, compact = false) {
    // We need to find the correct index in rawScanMatches to ensure checkbox works for global state selection
    // But for simplicity in this implementation, we map based on file_path since indexes might shift with sorting
    // Actually, `state.scanResults.files` must match `rawScanMatches` exactly/reference same objects for simplicity.
    const realIndex = rawScanMatches.findIndex(x => x.file_path === f.file_path);

    return `
        <div class="bg-white ${compact ? '' : 'rounded-xl border border-slate-200'} overflow-hidden">
            <div class="flex items-center gap-3 px-4 py-3 ${compact ? 'hover:bg-slate-50' : 'bg-slate-50 border-b border-slate-200'}">
                <input type="checkbox" class="scan-file-cb rounded border-slate-300 text-blue-600" data-idx="${realIndex}" ${f.selected ? 'checked' : ''} onchange="toggleFileSelection(${realIndex}, this.checked)">
                <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium text-slate-700 truncate font-mono">${f.relative_path}</p>
                    ${!compact ? `<p class="text-[10px] text-slate-400 truncate">${f.project_root}</p>` : ''}
                </div>
                <span class="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 whitespace-nowrap">${f.match_count} matches</span>
                <button onclick="toggleDiffPanel(this)" class="text-xs text-blue-600 hover:text-blue-800 font-medium whitespace-nowrap ml-2">Show Diff</button>
            </div>
            <div class="diff-panel hidden p-0 border-t border-slate-100">
                <div class="p-3 max-h-60 overflow-auto text-xs font-mono bg-slate-900 text-slate-100">
                   ${f.diff_html}
                </div>
            </div>
        </div>
    `;
}

function toggleDiffPanel(btn) {
    const panels = btn.closest('.bg-white').querySelectorAll('.diff-panel');
    panels.forEach(p => p.classList.toggle('hidden'));
    btn.textContent = btn.textContent === 'Show Diff' ? 'Hide Diff' : 'Show Diff';
}

function toggleFileSelection(idx, isChecked) {
    if (rawScanMatches[idx]) {
        rawScanMatches[idx].selected = isChecked;
    }
}

function selectAllFiles() {
    rawScanMatches.forEach(f => f.selected = true);
    document.querySelectorAll('.scan-file-cb').forEach(cb => cb.checked = true);
}
function deselectAllFiles() {
    rawScanMatches.forEach(f => f.selected = false);
    document.querySelectorAll('.scan-file-cb').forEach(cb => cb.checked = false);
}

async function executeRefactor() {
    if (!rawScanMatches.length) return;
    const filePaths = rawScanMatches.filter(f => f.selected).map(f => f.file_path);

    if (!filePaths.length) { showToast('No files selected', 'warning'); return; }
    if (!confirm(`Apply changes to ${filePaths.length} file(s)? Backups will be created.`)) return;

    try {
        const result = await api('/api/execute', {
            method: 'POST',
            body: { rule_ids: state._selectedRuleIds, file_paths: filePaths }
        });
        showToast(`${result.total_replacements} replacements in ${result.total_files_modified} files`, 'success');
        document.getElementById('execute-actions').classList.add('hidden');
        document.getElementById('scan-results').innerHTML = `
            <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-6 text-center">
                <p class="text-lg font-semibold text-emerald-800">✅ Execution Complete</p>
                <p class="text-sm text-emerald-600 mt-1">${result.total_replacements} replacements across ${result.total_files_modified} files</p>
                <p class="text-xs text-slate-500 mt-2">Execution ID: ${result.execution_id}</p>
            </div>
        `;
    } catch (err) {
        showToast('Execution failed: ' + err.message, 'error');
    }
}

// ============== Tracking ==============
async function loadTrackingFilters() {
    try {
        const rules = await api('/api/rules');
        const select = document.getElementById('tracking-rule-filter');
        select.innerHTML = '<option value="">All Rules</option>' +
            rules.map(r => `<option value="${r.id}">${r.name}</option>`).join('');
    } catch (err) { }
}

async function loadTracking() {
    const ruleId = document.getElementById('tracking-rule-filter').value;
    const filePath = document.getElementById('tracking-file-filter').value;

    let qs = '?limit=200';
    if (ruleId) qs += '&rule_id=' + ruleId;
    if (filePath) qs += '&file_path=' + encodeURIComponent(filePath);

    try {
        const data = await api('/api/tracking' + qs);
        renderTracking(data);
    } catch (err) {
        showToast('Failed to load tracking: ' + err.message, 'error');
    }
}

function renderTracking(data) {
    const el = document.getElementById('tracking-results');
    if (!data.entries.length) {
        el.innerHTML = '<p class="p-6 text-sm text-slate-400 italic">No tracking entries found</p>';
        return;
    }

    el.innerHTML = `
        <div class="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
            <span class="text-sm font-medium text-slate-700">${data.total} entries</span>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="border-b border-slate-200 text-left text-xs text-slate-500 uppercase tracking-wider">
                        <th class="px-4 py-2">Rule</th>
                        <th class="px-4 py-2">File</th>
                        <th class="px-4 py-2">Line</th>
                        <th class="px-4 py-2">Original</th>
                        <th class="px-4 py-2">Replacement</th>
                        <th class="px-4 py-2">Date</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.entries.map(e => `
                        <tr class="border-b border-slate-100 hover:bg-slate-50">
                            <td class="px-4 py-2 text-slate-700 font-medium">${e.rule_name || e.rule_id}</td>
                            <td class="px-4 py-2 font-mono text-xs text-slate-600 truncate max-w-xs">${truncatePath(e.file_path)}</td>
                            <td class="px-4 py-2 text-slate-500">${e.line_number}</td>
                            <td class="px-4 py-2"><code class="text-xs text-red-600 bg-red-50 px-1 rounded">${escHtml(e.original_text)}</code></td>
                            <td class="px-4 py-2"><code class="text-xs text-emerald-600 bg-emerald-50 px-1 rounded">${escHtml(e.replacement_text)}</code></td>
                            <td class="px-4 py-2 text-xs text-slate-400">${new Date(e.created_at).toLocaleDateString()}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

async function exportTracking() {
    try {
        const ruleId = document.getElementById('tracking-rule-filter').value;
        let qs = '';
        if (ruleId) qs = '?rule_id=' + ruleId;
        const data = await api('/api/tracking/export' + qs);
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `tracking-report-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('Report exported', 'success');
    } catch (err) {
        showToast('Export failed: ' + err.message, 'error');
    }
}

// ============== History ==============
async function loadHistory() {
    try {
        state.history = await api('/api/history');
        renderHistory();
    } catch (err) {
        showToast('Failed to load history: ' + err.message, 'error');
    }
}

function renderHistory() {
    document.getElementById('history-list').innerHTML = state.history.map(h => `
        <div class="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md transition-all">
            <div class="flex items-center justify-between">
                <div>
                    <div class="flex items-center gap-2">
                        <span class="text-sm font-semibold text-slate-800">${h.rule_name || `Rule #${h.rule_id}`}</span>
                        <span class="px-1.5 py-0.5 text-[10px] font-medium rounded-full ${h.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}">${h.status}</span>
                    </div>
                    <p class="text-xs text-slate-400 mt-0.5">${new Date(h.executed_at).toLocaleString()} — ${h.total_files_modified} files, ${h.total_replacements} replacements</p>
                </div>
                <div class="flex items-center gap-1">
                    <button onclick="viewHistoryDetail(${h.id})" class="px-3 py-1 text-xs bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100">Details</button>
                    <button onclick="rollback(${h.id})" class="px-3 py-1 text-xs bg-red-50 text-red-700 rounded-lg hover:bg-red-100">Rollback</button>
                </div>
            </div>
        </div>
    `).join('') || '<p class="text-sm text-slate-400">No execution history</p>';
}

async function viewHistoryDetail(executionId) {
    try {
        const detail = await api(`/api/history/${executionId}`);
        const el = document.getElementById('history-detail');
        el.classList.remove('hidden');
        el.innerHTML = `
            <h3 class="text-lg font-semibold text-slate-800 mb-3">Execution #${detail.id}</h3>
            <div class="grid grid-cols-3 gap-4 mb-4">
                <div class="bg-slate-50 rounded-lg p-3">
                    <p class="text-xs text-slate-500">Files Scanned</p>
                    <p class="text-xl font-bold text-slate-800">${detail.total_files_scanned}</p>
                </div>
                <div class="bg-slate-50 rounded-lg p-3">
                    <p class="text-xs text-slate-500">Files Modified</p>
                    <p class="text-xl font-bold text-slate-800">${detail.total_files_modified}</p>
                </div>
                <div class="bg-slate-50 rounded-lg p-3">
                    <p class="text-xs text-slate-500">Total Replacements</p>
                    <p class="text-xl font-bold text-slate-800">${detail.total_replacements}</p>
                </div>
            </div>
            ${detail.modified_files.length ? `
                <h4 class="text-sm font-medium text-slate-700 mb-2">Modified Files</h4>
                <div class="space-y-1 max-h-60 overflow-y-auto">
                    ${detail.modified_files.map(f => `
                        <div class="flex items-center justify-between py-1.5 px-3 bg-slate-50 rounded-lg">
                            <span class="text-xs font-mono text-slate-600 truncate">${truncatePath(f.file_path)}</span>
                            <span class="text-xs text-slate-400">${f.replacements_count} changes</span>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        `;
    } catch (err) {
        showToast('Failed to load details: ' + err.message, 'error');
    }
}

async function rollback(executionId) {
    if (!confirm(`Rollback execution #${executionId}? This will restore files from backups.`)) return;
    try {
        const result = await api(`/api/rollback/${executionId}`, { method: 'POST' });
        showToast(`Restored ${result.files_restored} files${result.files_failed ? `, ${result.files_failed} failed` : ''}`, result.files_failed ? 'warning' : 'success');
        if (result.errors.length) {
            console.error('Rollback errors:', result.errors);
        }
    } catch (err) {
        showToast('Rollback failed: ' + err.message, 'error');
    }
}

// ============== Utilities ==============
function escHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function truncatePath(path, maxLen = 60) {
    if (path.length <= maxLen) return path;
    return '...' + path.slice(path.length - maxLen + 3);
}

// ============== Initialize ==============
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
});
