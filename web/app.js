/**
 * Bot Busca Vagas Premium — Frontend Logic
 * Auth, Tailwind UI, API Integration, Charts, Real-time logs.
 */

const API = '';  // Same origin

// ═══════════════════════════════════════════════════════════════════
//  STATE & AUTHENTICATION
// ═══════════════════════════════════════════════════════════════════

async function apiFetch(endpoint, options = {}) {
    if (!options.headers) options.headers = {};
    const token = localStorage.getItem('dashboard_token');
    if (token) {
        options.headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(`${API}${endpoint}`, options);
    return res;
}

async function bootDashboard() {
    await loadDashboard();
    await checkBotStatus();
    await checkAutoStatus();
    lucide.createIcons();
}

async function handleLogin() {
    const cpfInput = document.getElementById('login-cpf');
    const passwordInput = document.getElementById('login-password');
    const cpf = cpfInput.value.trim();
    const password = passwordInput.value.trim();
    
    if (!cpf || !password) {
        showToast('CPF e senha são obrigatórios!', 'error');
        return;
    }
    
    try {
        const res = await fetch(`/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cpf, password })
        });
        
        const data = await res.json();
        
        if (res.ok && data.status === 'ok') {
            localStorage.setItem('dashboard_token', data.token);
            showToast('Acesso concedido! 🔒', 'success');
            await bootDashboard();
            hideLoginScreen();
        } else {
            showToast(data.detail || 'Senha ou CPF incorretos!', 'error');
        }
    } catch (err) {
        showToast('Erro ao conectar com o servidor.', 'error');
    }
}

function handleLogout() {
    localStorage.removeItem('dashboard_token');
    showToast('Sessão encerrada.', 'info');
    showLoginScreen();
}

function showAuthLoader() {
    document.getElementById('auth-loader').classList.remove('hidden');
    document.getElementById('login-view').classList.add('hidden');
    document.getElementById('app-view').classList.add('hidden');
}

function hideAuthLoader() {
    document.getElementById('auth-loader').classList.add('hidden');
}

function showLoginScreen() {
    hideAuthLoader();
    document.getElementById('app-view').classList.add('hidden');
    document.getElementById('login-view').classList.remove('hidden');
}

function hideLoginScreen() {
    document.getElementById('app-view').classList.remove('hidden');
    document.getElementById('login-view').classList.add('hidden');
}

async function initSession() {
    showAuthLoader();

    const token = localStorage.getItem('dashboard_token');
    if (!token) {
        hideAuthLoader();
        showLoginScreen();
        return;
    }

    try {
        const res = await fetch(`/api/bot-status`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (res.status === 200) {
            await bootDashboard();
            hideAuthLoader();
            hideLoginScreen();
            return;
        }

        if (res.status === 401) {
            localStorage.removeItem('dashboard_token');
        }
    } catch (e) {
        showToast('Não foi possível conectar ao servidor. Verifique sua rede.', 'error');
    }

    hideAuthLoader();
    showLoginScreen();
}


// ═══════════════════════════════════════════════════════════════════
//  NAVIGATION (TAILWIND STYLED)
// ═══════════════════════════════════════════════════════════════════

const navButtons = document.querySelectorAll('.nav-btn');
const pages = document.querySelectorAll('.page');
const pageTitle = document.getElementById('page-title');

const pageTitles = {
    'dashboard': 'Visão Geral',
    'control': 'Controle do Bot',
    'jobs': 'Histórico de Candidaturas',
    'settings': 'Configurações'
};

navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const target = btn.dataset.target;
        
        // Reset styles for all
        navButtons.forEach(b => {
            b.classList.remove('active', 'text-indigo-400', 'bg-indigo-500/10');
            b.classList.add('text-slate-400', 'hover:text-slate-200', 'hover:bg-slate-800/50');
        });
        
        // Active style
        btn.classList.add('active', 'text-indigo-400', 'bg-indigo-500/10');
        btn.classList.remove('text-slate-400', 'hover:text-slate-200', 'hover:bg-slate-800/50');
        
        pageTitle.textContent = pageTitles[target];

        pages.forEach(p => {
            p.classList.add('hidden');
            p.classList.remove('fade-enter-active');
        });
        
        const activePage = document.getElementById(`page-${target}`);
        activePage.classList.remove('hidden');
        
        // Trigger reflow for animation
        void activePage.offsetWidth;
        activePage.classList.add('fade-enter-active');

        // Load data specific to page
        if (target === 'dashboard') loadDashboard();
        if (target === 'jobs') loadJobs();
        if (target === 'control') {
            loadHunterLeads();
            checkAutoStatus();
        }
        if (target === 'settings') loadConfig();
    });
});


// ═══════════════════════════════════════════════════════════════════
//  TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════════

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = '';
    if(type==='success') icon = '<i data-lucide="check-circle" class="w-5 h-5 text-white/80"></i>';
    if(type==='error') icon = '<i data-lucide="alert-circle" class="w-5 h-5 text-white/80"></i>';
    if(type==='info') icon = '<i data-lucide="info" class="w-5 h-5 text-white/80"></i>';
    
    toast.innerHTML = `${icon} <span>${message}</span>`;
    container.appendChild(toast);
    lucide.createIcons();
    setTimeout(() => toast.remove(), 4000);
}


// ═══════════════════════════════════════════════════════════════════
//  DASHBOARD & CHARTS
// ═══════════════════════════════════════════════════════════════════

let chartDaily = null;
let chartSources = null;
let chartFunnel = null;
let chartCompanies = null;

async function loadDashboard() {
    document.getElementById('dashboard-date').textContent =
        new Date().toLocaleDateString('pt-BR', {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });

    try {
        const res = await apiFetch(`/api/stats`);
        const data = await res.json();

        animateNumber('kpi-emails', data.emails_enviados || 0);
        animateNumber('kpi-total', data.total || 0);
        animateNumber('kpi-today', data.hoje || 0);
        animateNumber('kpi-api', data.metrics?.gemini_calls || 0);

        // Configurações Globais Chart.js
        Chart.defaults.color = '#94a3b8';
        Chart.defaults.font.family = 'Inter, sans-serif';

        // 1. Daily activity bar chart
        const dailyCtx = document.getElementById('chart-daily').getContext('2d');
        if (chartDaily) chartDaily.destroy();
        chartDaily = new Chart(dailyCtx, {
            type: 'bar',
            data: {
                labels: (data.chart_days?.labels || []).map(d => {
                    const parts = d.split('-');
                    return `${parts[2]}/${parts[1]}`;
                }),
                datasets: [{
                    label: 'Candidaturas',
                    data: data.chart_days?.values || [],
                    backgroundColor: 'rgba(99, 102, 241, 0.8)',
                    borderColor: '#6366f1',
                    borderWidth: 0,
                    borderRadius: 6,
                    maxBarThickness: 32,
                    hoverBackgroundColor: 'rgba(99, 102, 241, 1)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#64748b' }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
                        ticks: {
                            color: '#64748b',
                            stepSize: 1,
                        }
                    }
                }
            }
        });

        // 2. Sources doughnut chart
        const sourcesCtx = document.getElementById('chart-sources').getContext('2d');
        if (chartSources) chartSources.destroy();
        const sourcesLabels = Object.keys(data.leads_sources || {});
        const sourcesValues = Object.values(data.leads_sources || {});
        chartSources = new Chart(sourcesCtx, {
            type: 'doughnut',
            data: {
                labels: sourcesLabels,
                datasets: [{
                    data: sourcesValues,
                    backgroundColor: [
                        '#6366f1', '#10b981', '#f59e0b', '#3b82f6', '#ec4899', '#8b5cf6'
                    ],
                    borderWidth: 0,
                    hoverOffset: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#94a3b8',
                            font: { size: 11 },
                            padding: 12,
                            usePointStyle: true,
                            pointStyleWidth: 8,
                        }
                    }
                }
            }
        });

        // 3. Funnel horizontal bar chart
        const funnelCtx = document.getElementById('chart-funnel').getContext('2d');
        if (chartFunnel) chartFunnel.destroy();
        chartFunnel = new Chart(funnelCtx, {
            type: 'bar',
            data: {
                labels: data.funnel?.labels || ["Vagas Encontradas", "Vagas Qualificadas", "Currículos Gerados", "E-mails Enviados"],
                datasets: [{
                    label: 'Total',
                    data: data.funnel?.values || [0, 0, 0, 0],
                    backgroundColor: [
                        'rgba(99, 102, 241, 0.8)', // Indigo
                        'rgba(59, 130, 246, 0.8)', // Blue
                        'rgba(139, 92, 246, 0.8)', // Purple
                        'rgba(16, 185, 129, 0.8)'  // Emerald
                    ],
                    borderColor: [
                        '#6366f1', '#3b82f6', '#8b5cf6', '#10b981'
                    ],
                    borderWidth: 1,
                    borderRadius: 6,
                    barThickness: 28,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#64748b', precision: 0 }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#e2e8f0', font: { weight: '500' } }
                    }
                }
            }
        });

        // 4. Companies chart
        const compCtx = document.getElementById('chart-companies').getContext('2d');
        if (chartCompanies) chartCompanies.destroy();
        const compLabels = (data.top_empresas?.labels || []).map(l =>
            l.length > 20 ? l.substring(0, 18) + '…' : l
        );
        chartCompanies = new Chart(compCtx, {
            type: 'doughnut',
            data: {
                labels: compLabels,
                datasets: [{
                    data: data.top_empresas?.values || [],
                    backgroundColor: [
                        '#6366f1', '#3b82f6', '#06b6d4', '#10b981',
                        '#f59e0b', '#f43f5e', '#8b5cf6', '#ec4899',
                        '#14b8a6', '#f97316'
                    ],
                    borderWidth: 0,
                    hoverOffset: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#94a3b8',
                            font: { size: 11 },
                            padding: 12,
                            usePointStyle: true,
                            pointStyleWidth: 8,
                        }
                    }
                }
            }
        });
    } catch (err) {
        // Handle error gracefully silently if it's unauthorized, it will auto-redirect
    }
}

function animateNumber(elementId, target) {
    const el = document.getElementById(elementId);
    if(!el) return;
    const current = parseInt(el.textContent) || 0;
    if (current === target) return;

    const duration = 800;
    const steps = 30;
    const increment = (target - current) / steps;
    let step = 0;

    const timer = setInterval(() => {
        step++;
        el.textContent = Math.round(current + increment * step);
        if (step >= steps) {
            el.textContent = target;
            clearInterval(timer);
        }
    }, duration / steps);
}


// ═══════════════════════════════════════════════════════════════════
//  BOT CONTROL & TERMINAL
// ═══════════════════════════════════════════════════════════════════

const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const terminalOutput = document.getElementById('terminal-output');
const termLoader = document.getElementById('term-loader');
let logPollInterval = null;

btnStart.addEventListener('click', async () => {
    const mode = document.getElementById('cfg-test-mode')?.checked ? 'teste' : 'full';
    const hunt_leads_first = document.getElementById('cfg-hunt-leads')?.checked ?? false;
    try {
        const res = await apiFetch(`/api/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode, hunt_leads_first })
        });
        const data = await res.json();

        if (data.status === 'running') {
            showToast('O bot já está em execução!', 'info');
            return;
        }

        showToast('Bot iniciado! 🚀', 'success');
        setBotRunning(true);
        startLogPolling();
    } catch (err) {}
});

btnStop.addEventListener('click', async () => {
    try {
        await apiFetch(`/api/stop`, { method: 'POST' });
        showToast('Bot interrompido.', 'info');
        setBotRunning(false);
        stopLogPolling();
    } catch (err) {}
});

function setBotRunning(running) {
    btnStart.disabled = running;
    btnStop.disabled = !running;
    
    if(running){
        btnStart.classList.add('opacity-50', 'cursor-not-allowed');
        btnStop.classList.remove('opacity-50', 'cursor-not-allowed');
    } else {
        btnStart.classList.remove('opacity-50', 'cursor-not-allowed');
        btnStop.classList.add('opacity-50', 'cursor-not-allowed');
    }

    const dot = document.getElementById('bot-dot');
    const text = document.getElementById('bot-status-text');
    if (running) {
        dot.className = 'w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse';
        text.textContent = 'Em Execução';
        text.classList.add('text-emerald-400');
        termLoader.classList.remove('hidden');
    } else {
        dot.className = 'w-2 h-2 rounded-full bg-slate-500 shadow-[0_0_8px_rgba(100,116,139,0.5)]';
        text.textContent = 'Inativo';
        text.classList.remove('text-emerald-400');
        termLoader.classList.add('hidden');
    }
}

function startLogPolling() {
    terminalOutput.textContent = '';
    if (logPollInterval) clearInterval(logPollInterval);

    logPollInterval = setInterval(async () => {
        try {
            const [logRes, statusRes] = await Promise.all([
                apiFetch(`/api/logs`),
                apiFetch(`/api/bot-status`)
            ]);
            const logData = await logRes.json();
            const statusData = await statusRes.json();

            const cleanLog = (logData.log || '')
                .replace(/\x1b\[[0-9;]*m/g, '')
                .replace(/\[[\w\s\/]*\]/g, match => match);
            terminalOutput.textContent = cleanLog || 'Aguardando saída do bot...';
            terminalOutput.parentElement.scrollTop = terminalOutput.parentElement.scrollHeight;

            if (!statusData.running) {
                setBotRunning(false);
                stopLogPolling();
                showToast('A execução finalizou.', 'success');
                loadDashboard();
                loadHunterLeads();
            }
        } catch (err) {}
    }, 1500);
}

function stopLogPolling() {
    if (logPollInterval) {
        clearInterval(logPollInterval);
        logPollInterval = null;
        termLoader.classList.add('hidden');
    }
}


//  AUTO 24/7 (ORCHESTRATOR)
// ═══════════════════════════════════════════════════════════════════

const btnStartAuto = document.getElementById('btn-start-auto');
const btnStopAuto = document.getElementById('btn-stop-auto');
const autoTerminal = document.getElementById('auto-terminal-output');
const autoTerminalWrap = document.getElementById('auto-terminal-wrap');
const autoLogSection = autoTerminalWrap;

let autoStatusTimer = null;

async function checkAutoStatus() {
    try {
        const res = await apiFetch(`/api/auto/status`);
        const data = await res.json();
        
        if (data.running) {
            btnStartAuto.classList.add('hidden');
            btnStopAuto.classList.remove('hidden');
            if (autoLogSection) autoLogSection.classList.remove('hidden');
            
            // Poll logs
            if (!autoStatusTimer) {
                autoStatusTimer = setInterval(updateAutoLogs, 1000);
            }
        } else {
            btnStartAuto.classList.remove('hidden');
            btnStopAuto.classList.add('hidden');
            if (autoLogSection) autoLogSection.classList.add('hidden');
            
            if (autoStatusTimer) {
                clearInterval(autoStatusTimer);
                autoStatusTimer = null;
                updateAutoLogs(); // final fetch
            }
        }
    } catch (err) { }
}

async function updateAutoLogs() {
    try {
        const res = await apiFetch(`/api/auto/logs`);
        const data = await res.json();
        const oldLog = autoTerminal.textContent;
        const newLog = data.log || 'Nenhuma saída recebida.';
        
        if (oldLog !== newLog) {
            autoTerminal.textContent = newLog;
            autoTerminal.scrollTop = autoTerminal.scrollHeight;
        }
    } catch (err) { }
}

btnStartAuto.addEventListener('click', async () => {
    autoTerminal.textContent = 'Iniciando Piloto Automático...';
    try {
        await apiFetch(`/api/auto/start`, { method: 'POST' });
        checkAutoStatus();
        showToast('Modo Autônomo iniciado!', 'success');
    } catch (err) { }
});

btnStopAuto.addEventListener('click', async () => {
    try {
        await apiFetch(`/api/auto/stop`, { method: 'POST' });
        checkAutoStatus();
        showToast('Modo Autônomo interrompido.', 'info');
    } catch (err) { }
});


// ═══════════════════════════════════════════════════════════════════
//  JOBS & SETTINGS TABLES
// ═══════════════════════════════════════════════════════════════════

async function loadJobs() {
    try {
        const res = await apiFetch(`/api/jobs`);
        const data = await res.json();
        const jobs = data.jobs || [];

        const tbody = document.getElementById('jobs-tbody');

        if (jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="p-8 text-center text-slate-500">Nenhuma candidatura registrada.</td></tr>';
            return;
        }

        tbody.innerHTML = jobs.map(j => {
            const statusHtml = j.email_enviado
                ? '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><i data-lucide="check" class="w-3 h-3"></i> Enviado</span>'
                : '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20"><i data-lucide="x" class="w-3 h-3"></i> Falhou</span>';
            const email = j.email_destino || '—';
            
            let cvActionHtml = '<span class="text-slate-600 font-medium text-xs">—</span>';
            if (j.curriculo_path) {
                const filename = j.curriculo_path.split(/[/\\]/).pop();
                cvActionHtml = `<button onclick="openPdfPreview('${filename.replace(/'/g, "\\'")}')" class="text-indigo-400 hover:text-indigo-300 p-1.5 rounded-lg hover:bg-slate-800/60 transition-colors inline-flex items-center gap-1 text-xs font-semibold" title="Visualizar PDF">
                    <i data-lucide="eye" class="w-4 h-4"></i> Ver CV
                </button>`;
            }

            return `<tr class="hover:bg-slate-800/30 transition-colors">
                <td class="p-4 text-slate-400">${(j.data || '').substring(0, 16)}</td>
                <td class="p-4 text-white font-medium">${j.empresa || ''}</td>
                <td class="p-4 text-slate-300">${j.vaga || ''}</td>
                <td class="p-4 text-indigo-300 text-xs font-mono">${email}</td>
                <td class="p-4">${statusHtml}</td>
                <td class="p-4 text-right">${cvActionHtml}</td>
            </tr>`;
        }).join('');
        lucide.createIcons();
    } catch (err) {}
}


async function loadHunterLeads() {
    try {
        const res = await apiFetch(`/api/hunter/leads`);
        const data = await res.json();
        const leads = data.leads || [];

        window.currentLeads = leads;

        const countEl = document.getElementById('hunter-leads-count');
        if (countEl) countEl.textContent = leads.length;
        
        const tbody = document.getElementById('hunter-tbody');
        if (!tbody) return;

        if (leads.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="p-8 text-center text-slate-500">Nenhum lead capturado.</td></tr>';
            return;
        }

        tbody.innerHTML = leads.map(lead => {
            const email = lead.email_contato || lead.email || '—';
            const statusHtml = lead.status === 'applied' 
                ? '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><i data-lucide="check" class="w-3 h-3"></i> Enviado</span>' 
                : lead.status === 'failed' 
                ? '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20"><i data-lucide="x" class="w-3 h-3"></i> Falhou</span>' 
                : '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20"><i data-lucide="clock" class="w-3 h-3"></i> Pendente</span>';
                
            const isApi = (lead.fonte || '').toLowerCase().includes('api');
            const isManual = (lead.fonte || '').toLowerCase().includes('manual');
            const badge = isApi ? '<span class="inline-flex ml-2 items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">API</span>' 
                        : isManual ? '<span class="inline-flex ml-2 items-center px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">Manual</span>'
                        : '<span class="inline-flex ml-2 items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">Web Scrape</span>';
            
            return `<tr class="hover:bg-slate-800/30 transition-colors">
                <td class="p-4 text-white font-medium">${lead.empresa || ''}</td>
                <td class="p-4 text-indigo-300 text-xs font-mono">${email}</td>
                <td class="p-4 text-slate-400 text-sm">${lead.cargo_da_vaga || lead.vaga || '—'}</td>
                <td class="p-4 text-slate-400 text-xs font-semibold">${lead.fonte || 'Manual'}</td>
                <td class="p-4 flex items-center">${statusHtml} ${badge}</td>
                <td class="p-4 text-right">
                    <div class="flex justify-end gap-1.5">
                        <button onclick="openLeadModal(${lead.id})" class="text-indigo-400 hover:text-indigo-300 p-1.5 rounded-lg hover:bg-slate-800/60 transition-colors" title="Editar Lead">
                            <i data-lucide="edit-2" class="w-4 h-4"></i>
                        </button>
                        <button onclick="deleteLead(${lead.id})" class="text-rose-400 hover:text-rose-300 p-1.5 rounded-lg hover:bg-slate-800/60 transition-colors" title="Excluir Lead">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>
                </td>
            </tr>`;
        }).join('');
        lucide.createIcons();
    } catch (err) {}
}

// ═══════════════════════════════════════════════════════════════════
//  SETTINGS & FILE UPLOAD
// ═══════════════════════════════════════════════════════════════════

async function loadConfig() {
    try {
        const res = await apiFetch(`/api/config`);
        const cfg = await res.json();

        document.getElementById('cfg-api-key').value = cfg.gemini_api_key || '';
        document.getElementById('cfg-email').value = cfg.email_address || '';
        document.getElementById('cfg-password').value = cfg.email_app_password || '';
        document.getElementById('cfg-dashboard-password').value = cfg.dashboard_password || '';
        document.getElementById('cfg-cc').value = cfg.email_cc || '';
        document.getElementById('cfg-name').value = cfg.candidate_name || '';
        document.getElementById('cfg-personalize-emails').checked = cfg.personalize_only_emails;
        document.getElementById('cfg-use-base-resume-only').checked = cfg.use_base_resume_only;

        if (cfg.resume_pdf) {
            document.getElementById('upload-text').textContent = `📎 ${cfg.resume_pdf}`;
            document.getElementById('upload-zone').classList.add('border-indigo-500', 'bg-indigo-500/5');
        }

        window.currentKeywords = (cfg.job_categories || '')
            .split(',')
            .map(k => k.trim())
            .filter(k => k.length > 0);

        window.currentCities = (cfg.presencial_cities || '')
            .split(',')
            .map(c => c.trim())
            .filter(c => c.length > 0);

        window.renderTags('keyword');
        window.renderTags('city');
    } catch (err) {}
}

document.getElementById('btn-save-config').addEventListener('click', async () => {
    const confirmPassword = prompt('Por segurança, digite a sua Senha do Dashboard para confirmar as alterações:');
    if (!confirmPassword) {
        showToast('Cancelado. A senha de confirmação é obrigatória.', 'error');
        return;
    }

    const payload = {
        gemini_api_key: document.getElementById('cfg-api-key').value,
        email_address: document.getElementById('cfg-email').value,
        email_app_password: document.getElementById('cfg-password').value,
        dashboard_password: document.getElementById('cfg-dashboard-password').value,
        confirm_password: confirmPassword,
        email_cc: document.getElementById('cfg-cc').value,
        candidate_name: document.getElementById('cfg-name').value,
        resume_pdf: document.getElementById('upload-text').textContent.replace('📎 ', '').trim(),
        personalize_only_emails: document.getElementById('cfg-personalize-emails').checked,
        use_base_resume_only: document.getElementById('cfg-use-base-resume-only').checked,
        job_categories: window.currentKeywords.join(', '),
        presencial_cities: window.currentCities.join(', '),
    };

    try {
        const res = await apiFetch(`/api/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (res.ok) {
            const feedback = document.getElementById('save-feedback');
            feedback.classList.remove('opacity-0');
            showToast(data.message, 'success');
            setTimeout(() => feedback.classList.add('opacity-0'), 3000);
            loadConfig();
        } else {
            showToast(data.detail || 'Senha de confirmação incorreta!', 'error');
        }
    } catch (err) {
        showToast('Erro ao salvar as configurações', 'error');
    }
});


const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('resume-file');

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('border-indigo-500', 'bg-indigo-500/10');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('border-indigo-500', 'bg-indigo-500/10');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('border-indigo-500', 'bg-indigo-500/10');
    const files = e.dataTransfer.files;
    if (files.length > 0) uploadFile(files[0]);
});

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) uploadFile(fileInput.files[0]);
});

async function uploadFile(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showToast('Apenas PDF é aceito.', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await apiFetch(`/api/upload-resume`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (res.ok) {
            document.getElementById('upload-text').textContent = `📎 ${data.filename}`;
            uploadZone.classList.add('border-indigo-500', 'bg-indigo-500/5');
            showToast(data.message, 'success');
        } else {
            showToast(data.detail || 'Erro no upload', 'error');
        }
    } catch (err) {
        showToast('Erro ao fazer upload', 'error');
    }
}


// ═══════════════════════════════════════════════════════════════════
//  INITIAL BOOT
// ═══════════════════════════════════════════════════════════════════

async function checkBotStatus() {
    try {
        const res = await apiFetch(`/api/bot-status`);
        const data = await res.json();
        if (data.running) {
            setBotRunning(true);
            startLogPolling();
        }
    } catch (err) {}
}

// ═══════════════════════════════════════════════════════════════════
//  CRM LEAD MODAL & OPERATIONS
// ═══════════════════════════════════════════════════════════════════

window.openLeadModal = function(leadId = null) {
    const modal = document.getElementById('lead-modal');
    const title = document.getElementById('lead-modal-title');
    const form = document.getElementById('lead-form');
    
    if (leadId) {
        title.innerHTML = '<i data-lucide="edit-3" class="w-5 h-5 text-indigo-400"></i> Editar Lead';
        const lead = window.currentLeads.find(l => l.id === leadId);
        if (lead) {
            document.getElementById('lead-id').value = lead.id;
            document.getElementById('lead-empresa').value = lead.empresa || '';
            document.getElementById('lead-email').value = lead.email_contato || lead.email || '';
            document.getElementById('lead-cargo').value = lead.cargo_da_vaga || lead.vaga || '';
            document.getElementById('lead-site').value = lead.site || '';
            document.getElementById('lead-status').value = lead.status || 'pending';
            document.getElementById('lead-fonte').value = lead.fonte || 'Manual';
        }
    } else {
        title.innerHTML = '<i data-lucide="plus" class="w-5 h-5 text-indigo-400"></i> Adicionar Lead';
        form.reset();
        document.getElementById('lead-id').value = '';
        document.getElementById('lead-status').value = 'pending';
        document.getElementById('lead-fonte').value = 'Manual';
    }
    
    modal.classList.remove('hidden');
    void modal.offsetWidth; // Force reflow
    modal.classList.remove('opacity-0');
    modal.querySelector('.glass').classList.remove('scale-95');
    lucide.createIcons();
}

window.closeLeadModal = function() {
    const modal = document.getElementById('lead-modal');
    modal.classList.add('opacity-0');
    modal.querySelector('.glass').classList.add('scale-95');
    setTimeout(() => {
        modal.classList.add('hidden');
        document.getElementById('lead-form').reset();
        document.getElementById('lead-id').value = '';
    }, 300);
}

window.saveLead = async function() {
    const id = document.getElementById('lead-id').value;
    const empresa = document.getElementById('lead-empresa').value.trim();
    const email = document.getElementById('lead-email').value.trim();
    const cargo_da_vaga = document.getElementById('lead-cargo').value.trim();
    const site = document.getElementById('lead-site').value.trim();
    const status = document.getElementById('lead-status').value;
    const fonte = document.getElementById('lead-fonte').value;
    
    if (!empresa || !email || !cargo_da_vaga) {
        showToast('Preencha todos os campos obrigatórios (*).', 'error');
        return;
    }
    
    const payload = { empresa, email, cargo_da_vaga, site, status, fonte };
    
    try {
        let res;
        if (id) {
            res = await apiFetch(`/api/leads/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            res = await apiFetch(`/api/leads`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }
        
        const data = await res.json();
        if (res.ok && data.status !== 'error') {
            showToast(data.message || 'Lead salvo com sucesso!', 'success');
            closeLeadModal();
            loadHunterLeads();
            loadDashboard(); // Refresh stats/charts
        } else {
            showToast(data.message || 'Erro ao salvar o lead.', 'error');
        }
    } catch (err) {
        showToast('Erro de comunicação com o servidor.', 'error');
    }
}

window.deleteLead = async function(leadId) {
    if (!confirm('Deseja realmente excluir este lead permanentemente?')) return;
    
    try {
        const res = await apiFetch(`/api/leads/${leadId}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        
        if (res.ok && data.status !== 'error') {
            showToast(data.message || 'Lead excluído com sucesso!', 'success');
            loadHunterLeads();
            loadDashboard(); // Refresh stats/charts
        } else {
            showToast(data.message || 'Erro ao excluir o lead.', 'error');
        }
    } catch (err) {
        showToast('Erro ao remover lead.', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════
//  PDF LIVE PREVIEWER
// ═══════════════════════════════════════════════════════════════════

window.openPdfPreview = function(filename) {
    if (!filename) {
        showToast('Currículo não disponível para este registro.', 'info');
        return;
    }
    const modal = document.getElementById('pdf-modal');
    const iframe = document.getElementById('pdf-viewer-frame');
    iframe.src = `/cvs/${encodeURIComponent(filename)}`;
    
    modal.classList.remove('hidden');
    void modal.offsetWidth; // Force reflow
    modal.classList.remove('opacity-0');
    modal.querySelector('.glass').classList.remove('scale-95');
    lucide.createIcons();
}

window.closePdfPreview = function() {
    const modal = document.getElementById('pdf-modal');
    const iframe = document.getElementById('pdf-viewer-frame');
    modal.classList.add('opacity-0');
    modal.querySelector('.glass').classList.add('scale-95');
    setTimeout(() => {
        modal.classList.add('hidden');
        iframe.src = '';
    }, 300);
}

// ═══════════════════════════════════════════════════════════════════
//  DYNAMIC SEARCH FILTERS & KEYWORDS (TAG MANAGER)
// ═══════════════════════════════════════════════════════════════════

window.currentKeywords = [];
window.currentCities = [];

window.renderTags = function(type) {
    if (type === 'keyword') {
        const container = document.getElementById('keywords-tags-container');
        if (!container) return;
        if (window.currentKeywords.length === 0) {
            container.innerHTML = '<span class="text-xs text-slate-500 italic p-1">Nenhuma palavra-chave cadastrada.</span>';
            return;
        }
        container.innerHTML = window.currentKeywords.map((kw, index) => {
            return `<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/25 transition-all hover:bg-indigo-500/20">
                ${kw}
                <button type="button" onclick="removeSearchTag('keyword', ${index})" class="text-indigo-400 hover:text-indigo-200 transition-colors focus:outline-none">
                    <i data-lucide="x" class="w-3.5 h-3.5"></i>
                </button>
            </span>`;
        }).join('');
    } else if (type === 'city') {
        const container = document.getElementById('cities-tags-container');
        if (!container) return;
        if (window.currentCities.length === 0) {
            container.innerHTML = '<span class="text-xs text-slate-500 italic p-1">Nenhuma cidade cadastrada.</span>';
            return;
        }
        container.innerHTML = window.currentCities.map((city, index) => {
            return `<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/25 transition-all hover:bg-emerald-500/20">
                ${city}
                <button type="button" onclick="removeSearchTag('city', ${index})" class="text-emerald-400 hover:text-emerald-200 transition-colors focus:outline-none">
                    <i data-lucide="x" class="w-3.5 h-3.5"></i>
                </button>
            </span>`;
        }).join('');
    }
    lucide.createIcons();
}

window.addSearchTag = function(type) {
    if (type === 'keyword') {
        const input = document.getElementById('new-tag-keyword');
        if (!input) return;
        const val = input.value.trim();
        if (!val) return;
        
        const parts = val.split(',').map(p => p.trim()).filter(p => p.length > 0);
        parts.forEach(part => {
            if (!window.currentKeywords.includes(part)) {
                window.currentKeywords.push(part);
            }
        });
        
        input.value = '';
        window.renderTags('keyword');
    } else if (type === 'city') {
        const input = document.getElementById('new-tag-city');
        if (!input) return;
        const val = input.value.trim();
        if (!val) return;
        
        const parts = val.split(',').map(p => p.trim()).filter(p => p.length > 0);
        parts.forEach(part => {
            if (!window.currentCities.includes(part)) {
                window.currentCities.push(part);
            }
        });
        
        input.value = '';
        window.renderTags('city');
    }
}

window.removeSearchTag = function(type, index) {
    if (type === 'keyword') {
        window.currentKeywords.splice(index, 1);
        window.renderTags('keyword');
    } else if (type === 'city') {
        window.currentCities.splice(index, 1);
        window.renderTags('city');
    }
}

// Hook keydown events for Enter key
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('new-tag-keyword')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            window.addSearchTag('keyword');
        }
    });
    document.getElementById('new-tag-city')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            window.addSearchTag('city');
        }
    });

    initSession();
});
