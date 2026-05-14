/**
 * Bot Busca Vagas Premium — Frontend Logic
 * Auth, Tailwind UI, API Integration, Charts, Real-time logs.
 */

const API = '';  // Same origin

// ═══════════════════════════════════════════════════════════════════
//  STATE & AUTHENTICATION
// ═══════════════════════════════════════════════════════════════════

let authToken = localStorage.getItem('bot_auth_token') || null;

const loginView = document.getElementById('login-view');
const appView = document.getElementById('app-view');

function setToken(token) {
    authToken = token;
    if (token) {
        localStorage.setItem('bot_auth_token', token);
    } else {
        localStorage.removeItem('bot_auth_token');
    }
}

// Wrapper for fetch that auto-injects Bearer token
async function apiFetch(endpoint, options = {}) {
    if (!options.headers) options.headers = {};
    if (authToken) {
        options.headers['Authorization'] = `Bearer ${authToken}`;
    }
    const res = await fetch(`${API}${endpoint}`, options);
    
    // If Unauthorized, force logout
    if (res.status === 401) {
        handleLogout();
        throw new Error("Unauthorized");
    }
    return res;
}

function showLoginScreen() {
    loginView.classList.remove('hidden', 'opacity-0');
    appView.classList.add('hidden');
    setTimeout(() => {
        document.getElementById('login-box').classList.remove('scale-95', 'opacity-0');
        document.getElementById('login-box').classList.add('scale-100', 'opacity-100');
    }, 50);
}

function showDashboardScreen() {
    document.getElementById('login-box').classList.remove('scale-100');
    document.getElementById('login-box').classList.add('scale-95', 'opacity-0');
    loginView.classList.add('opacity-0');
    setTimeout(() => {
        loginView.classList.add('hidden');
        appView.classList.remove('hidden');
        // Initial Loads
        loadDashboard();
        checkBotStatus();
        checkHunterStatus();
        loadHunterLeads();
    }, 400);
}

function handleLogout() {
    setToken(null);
    showLoginScreen();
    showToast('Sessão encerrada.', 'info');
}

document.getElementById('btn-logout').addEventListener('click', handleLogout);

// ═══════════════════════════════════════════════════════════════════
//  LOGIN LOGIC & CPF MASK
// ═══════════════════════════════════════════════════════════════════

const cpfInput = document.getElementById('login-cpf');
cpfInput.addEventListener('input', (e) => {
    let val = e.target.value.replace(/\D/g, '');
    if (val.length > 3) val = val.substring(0,3) + '.' + val.substring(3);
    if (val.length > 7) val = val.substring(0,7) + '.' + val.substring(7);
    if (val.length > 11) val = val.substring(0,11) + '-' + val.substring(11,13);
    e.target.value = val;
});

const togglePasswordBtn = document.getElementById('toggle-password');
const pwdInput = document.getElementById('login-password');
togglePasswordBtn.addEventListener('click', () => {
    if (pwdInput.type === 'password') {
        pwdInput.type = 'text';
        togglePasswordBtn.innerHTML = '<i data-lucide="eye-off" class="w-5 h-5"></i>';
    } else {
        pwdInput.type = 'password';
        togglePasswordBtn.innerHTML = '<i data-lucide="eye" class="w-5 h-5"></i>';
    }
    lucide.createIcons();
});

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const cpf = cpfInput.value;
    const password = pwdInput.value;
    const btn = e.target.querySelector('button');
    const originalContent = btn.innerHTML;
    
    btn.innerHTML = '<div class="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div> Entrando...';
    btn.disabled = true;

    try {
        const res = await fetch(`${API}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cpf, password })
        });
        
        const data = await res.json();
        
        if (res.ok && data.token) {
            setToken(data.token);
            showToast(data.message, 'success');
            showDashboardScreen();
        } else {
            showToast(data.detail || 'Erro ao fazer login', 'error');
        }
    } catch (err) {
        showToast('Erro de conexão com o servidor', 'error');
    } finally {
        btn.innerHTML = originalContent;
        btn.disabled = false;
        lucide.createIcons();
    }
});


// ═══════════════════════════════════════════════════════════════════
//  NAVIGATION (TAILWIND STYLED)
// ═══════════════════════════════════════════════════════════════════

const navButtons = document.querySelectorAll('.nav-btn');
const pages = document.querySelectorAll('.page');
const pageTitle = document.getElementById('page-title');

const pageTitles = {
    'dashboard': 'Visão Geral',
    'control': 'Controle do Bot',
    'hunter': 'Email Hunter',
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
        if (target === 'hunter') loadHunterLeads();
        if (target === 'settings') loadConfig();
        if (target === 'auto') checkAutoStatus();
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

        // Daily chart with tailwind styling
        const dailyCtx = document.getElementById('chart-daily').getContext('2d');
        if (chartDaily) chartDaily.destroy();
        
        // Configurações Globais Chart.js
        Chart.defaults.color = '#94a3b8';
        Chart.defaults.font.family = 'Inter, sans-serif';

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

        // Companies chart
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
    const mode = document.querySelector('input[name="bot-mode"]:checked').value;
    try {
        const res = await apiFetch(`/api/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode })
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

let autoStatusTimer = null;

async function checkAutoStatus() {
    try {
        const res = await apiFetch(`/api/auto/status`);
        const data = await res.json();
        
        if (data.running) {
            btnStartAuto.classList.add('hidden');
            btnStopAuto.classList.remove('hidden');
            autoTerminalWrap.classList.add('ring-1', 'ring-emerald-500/50', 'shadow-[0_0_20px_rgba(16,185,129,0.1)]');
            autoTerminalWrap.classList.remove('border-slate-800');
            
            // Poll logs
            if (!autoStatusTimer) {
                autoStatusTimer = setInterval(updateAutoLogs, 1000);
            }
        } else {
            btnStartAuto.classList.remove('hidden');
            btnStopAuto.classList.add('hidden');
            autoTerminalWrap.classList.remove('ring-1', 'ring-emerald-500/50', 'shadow-[0_0_20px_rgba(16,185,129,0.1)]');
            autoTerminalWrap.classList.add('border-slate-800');
            
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
            tbody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-slate-500">Nenhuma candidatura registrada.</td></tr>';
            return;
        }

        tbody.innerHTML = jobs.map(j => {
            const statusHtml = j.email_enviado
                ? '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><i data-lucide="check" class="w-3 h-3"></i> Enviado</span>'
                : '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20"><i data-lucide="x" class="w-3 h-3"></i> Falhou</span>';
            const email = j.email_destino || '—';
            return `<tr class="hover:bg-slate-800/30 transition-colors">
                <td class="p-4 text-slate-400">${(j.data || '').substring(0, 16)}</td>
                <td class="p-4 text-white font-medium">${j.empresa || ''}</td>
                <td class="p-4 text-slate-300">${j.vaga || ''}</td>
                <td class="p-4 text-indigo-300 text-xs font-mono">${email}</td>
                <td class="p-4">${statusHtml}</td>
            </tr>`;
        }).join('');
        lucide.createIcons();
    } catch (err) {}
}


const btnStartHunter = document.getElementById('btn-start-hunter');
const btnStopHunter = document.getElementById('btn-stop-hunter');
const hunterTerminal = document.getElementById('hunter-terminal-output');
const hunterTerminalWrap = document.getElementById('hunter-terminal-wrap');

let hunterLogPollInterval = null;

if (btnStartHunter) {
    btnStartHunter.addEventListener('click', async () => {
        try {
            const res = await apiFetch(`/api/hunter/start`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'running') {
                showToast('O Hunter já está rodando!', 'info');
                return;
            }
            showToast('Email Hunter iniciado! 🎯', 'success');
            setHunterRunning(true);
            startHunterLogPolling();
        } catch (err) {}
    });
}

if (btnStopHunter) {
    btnStopHunter.addEventListener('click', async () => {
        try {
            await apiFetch(`/api/hunter/stop`, { method: 'POST' });
            showToast('Email Hunter parado.', 'info');
            setHunterRunning(false);
            stopHunterLogPolling();
        } catch (err) {}
    });
}

function setHunterRunning(running) {
    if (btnStartHunter) {
        btnStartHunter.disabled = running;
        if(running) btnStartHunter.classList.add('hidden');
        else btnStartHunter.classList.remove('hidden');
    }
    if (btnStopHunter) {
        btnStopHunter.disabled = !running;
        if(running) btnStopHunter.classList.remove('hidden');
        else btnStopHunter.classList.add('hidden');
    }
    if(running) hunterTerminalWrap.classList.remove('hidden');
}

function startHunterLogPolling() {
    if (hunterTerminal) hunterTerminal.textContent = '';
    if (hunterLogPollInterval) clearInterval(hunterLogPollInterval);

    hunterLogPollInterval = setInterval(async () => {
        try {
            const [logRes, statusRes] = await Promise.all([
                apiFetch(`/api/hunter/logs`),
                apiFetch(`/api/hunter/status`)
            ]);
            const logData = await logRes.json();
            const statusData = await statusRes.json();

            const cleanLog = (logData.log || '').replace(/\x1b\[[0-9;]*m/g, '');
            if (hunterTerminal) {
                hunterTerminal.textContent = cleanLog || 'Aguardando saída do bot hunter...';
                hunterTerminal.parentElement.scrollTop = hunterTerminal.parentElement.scrollHeight;
            }

            if (!statusData.running) {
                setHunterRunning(false);
                stopHunterLogPolling();
                showToast('Caçada concluída.', 'success');
                loadHunterLeads();
            }
        } catch (err) {}
    }, 1500);
}

function stopHunterLogPolling() {
    if (hunterLogPollInterval) {
        clearInterval(hunterLogPollInterval);
        hunterLogPollInterval = null;
    }
}

async function loadHunterLeads() {
    try {
        const res = await apiFetch(`/api/hunter/leads`);
        const data = await res.json();
        const leads = data.leads || [];

        const countEl = document.getElementById('hunter-leads-count');
        if (countEl) countEl.textContent = leads.length;
        
        const tbody = document.getElementById('hunter-tbody');
        if (!tbody) return;

        if (leads.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="p-8 text-center text-slate-500">Nenhum lead capturado.</td></tr>';
            return;
        }

        tbody.innerHTML = leads.map(lead => {
            const email = lead.email_contato || lead.email || '—';
            const statusHtml = lead.status === 'applied' 
                ? '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Enviado</span>' 
                : lead.status === 'failed' 
                ? '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">Falhou</span>' 
                : '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">Pendente</span>';
                
            const isApi = (lead.fonte || '').toLowerCase().includes('api');
            const badge = isApi ? '<span class="inline-flex ml-2 items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">API</span>' 
                                : '<span class="inline-flex ml-2 items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">Web Scrape</span>';
            return `<tr class="hover:bg-slate-800/30 transition-colors">
                <td class="p-4 text-white font-medium">${lead.empresa || ''}</td>
                <td class="p-4 text-indigo-300 text-xs font-mono">${email}</td>
                <td class="p-4 text-slate-400 text-sm">${lead.cargo_da_vaga || lead.vaga || '—'}</td>
                <td class="p-4 flex items-center">${statusHtml} ${badge}</td>
            </tr>`;
        }).join('');
    } catch (err) {}
}

const btnApplyLeads = document.getElementById('btn-apply-leads');
if (btnApplyLeads) {
    btnApplyLeads.addEventListener('click', async () => {
        try {
            const res = await apiFetch(`/api/leads/apply`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'running') {
                showToast(data.message, 'info');
                return;
            }
            showToast(data.message, 'success');
            document.querySelector('[data-target="control"]').click();
            checkBotStatus();
        } catch (err) {
            showToast('Erro ao iniciar disparos', 'error');
        }
    });
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

        if (cfg.resume_pdf) {
            document.getElementById('upload-text').textContent = `📎 ${cfg.resume_pdf}`;
            document.getElementById('upload-zone').classList.add('border-indigo-500', 'bg-indigo-500/5');
        }
    } catch (err) {}
}

document.getElementById('btn-save-config').addEventListener('click', async () => {
    const payload = {
        gemini_api_key: document.getElementById('cfg-api-key').value,
        email_address: document.getElementById('cfg-email').value,
        email_app_password: document.getElementById('cfg-password').value,
        dashboard_password: document.getElementById('cfg-dashboard-password').value,
        email_cc: document.getElementById('cfg-cc').value,
        candidate_name: document.getElementById('cfg-name').value,
        resume_pdf: document.getElementById('upload-text').textContent.replace('📎 ', '').trim(),
        personalize_only_emails: document.getElementById('cfg-personalize-emails').checked,
    };

    try {
        const res = await apiFetch(`/api/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        const feedback = document.getElementById('save-feedback');
        feedback.classList.remove('opacity-0');
        showToast(data.message, 'success');
        setTimeout(() => feedback.classList.add('opacity-0'), 3000);
    } catch (err) {}
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

async function checkHunterStatus() {
    try {
        const res = await apiFetch(`/api/hunter/status`);
        const data = await res.json();
        if (data.running) {
            setHunterRunning(true);
            startHunterLogPolling();
        }
    } catch (err) {}
}

// Start
if (authToken) {
    // Validate token visually
    apiFetch('/api/bot-status').then(() => {
        showDashboardScreen();
    }).catch(() => {
        showLoginScreen();
    });
} else {
    showLoginScreen();
}
