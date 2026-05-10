/**
 * Bot Busca Vagas — Frontend Logic
 * Handles navigation, API calls, charts, and real-time terminal.
 */

const API = '';  // Same origin

// ═══════════════════════════════════════════════════════════════════
//  NAVIGATION
// ═══════════════════════════════════════════════════════════════════

const navButtons = document.querySelectorAll('.nav-item');
const pages = document.querySelectorAll('.page');

navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const target = btn.dataset.page;
        navButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        pages.forEach(p => {
            p.classList.remove('active');
            if (p.id === `page-${target}`) {
                p.classList.add('active');
            }
        });

        // Refresh data on page switch
        if (target === 'dashboard') loadDashboard();
        if (target === 'jobs') loadJobs();
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
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}


// ═══════════════════════════════════════════════════════════════════
//  DASHBOARD
// ═══════════════════════════════════════════════════════════════════

let chartDaily = null;
let chartCompanies = null;

async function loadDashboard() {
    // Set date
    document.getElementById('dashboard-date').textContent =
        new Date().toLocaleDateString('pt-BR', {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });

    try {
        const res = await fetch(`${API}/api/stats`);
        const data = await res.json();

        // KPIs
        animateNumber('kpi-emails', data.emails_enviados || 0);
        animateNumber('kpi-total', data.total || 0);
        animateNumber('kpi-today', data.hoje || 0);
        animateNumber('kpi-api', data.metrics?.gemini_calls || 0);

        // Daily chart
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
                    backgroundColor: 'rgba(99, 102, 241, 0.6)',
                    borderColor: '#6366f1',
                    borderWidth: 1,
                    borderRadius: 6,
                    maxBarThickness: 32,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.04)' },
                        ticks: { color: '#64748b', font: { size: 11 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.04)' },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11 },
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
                        '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899',
                        '#14b8a6', '#f97316'
                    ],
                    borderWidth: 0,
                    hoverOffset: 6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                cutout: '65%',
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
        console.error('Dashboard error:', err);
    }
}

function animateNumber(elementId, target) {
    const el = document.getElementById(elementId);
    const current = parseInt(el.textContent) || 0;
    if (current === target) return;

    const duration = 600;
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
//  BOT CONTROL
// ═══════════════════════════════════════════════════════════════════

const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const terminalOutput = document.getElementById('terminal-output');
let logPollInterval = null;

btnStart.addEventListener('click', async () => {
    const mode = document.querySelector('input[name="bot-mode"]:checked').value;
    try {
        const res = await fetch(`${API}/api/start`, {
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
    } catch (err) {
        showToast('Erro ao iniciar o bot', 'error');
    }
});

btnStop.addEventListener('click', async () => {
    try {
        await fetch(`${API}/api/stop`, { method: 'POST' });
        showToast('Bot parado.', 'info');
        setBotRunning(false);
        stopLogPolling();
    } catch (err) {
        showToast('Erro ao parar o bot', 'error');
    }
});

function setBotRunning(running) {
    btnStart.disabled = running;
    btnStop.disabled = !running;

    const indicator = document.getElementById('bot-status-indicator');
    const dot = indicator.querySelector('.status-dot');
    if (running) {
        dot.className = 'status-dot running';
        indicator.querySelector('span:last-child').textContent = 'Bot Em Execução';
    } else {
        dot.className = 'status-dot idle';
        indicator.querySelector('span:last-child').textContent = 'Bot Inativo';
    }
}

function startLogPolling() {
    // Clear previous
    terminalOutput.textContent = '';
    if (logPollInterval) clearInterval(logPollInterval);

    logPollInterval = setInterval(async () => {
        try {
            const [logRes, statusRes] = await Promise.all([
                fetch(`${API}/api/logs`),
                fetch(`${API}/api/bot-status`)
            ]);
            const logData = await logRes.json();
            const statusData = await statusRes.json();

            // Strip ANSI escape codes for clean display
            const cleanLog = (logData.log || '')
                .replace(/\x1b\[[0-9;]*m/g, '')
                .replace(/\[[\w\s\/]*\]/g, match => match);
            terminalOutput.textContent = cleanLog || 'Aguardando saída do bot...';
            terminalOutput.scrollTop = terminalOutput.scrollHeight;

            if (!statusData.running) {
                setBotRunning(false);
                stopLogPolling();
                showToast('Bot finalizou a execução.', 'success');
                loadDashboard();  // Refresh stats
            }
        } catch (err) {
            // Silent fail on poll
        }
    }, 1500);
}

function stopLogPolling() {
    if (logPollInterval) {
        clearInterval(logPollInterval);
        logPollInterval = null;
    }
}


// ═══════════════════════════════════════════════════════════════════
//  JOBS TABLE
// ═══════════════════════════════════════════════════════════════════

async function loadJobs() {
    try {
        const res = await fetch(`${API}/api/jobs`);
        const data = await res.json();
        const jobs = data.jobs || [];

        document.getElementById('jobs-count').textContent = `${jobs.length} registros`;
        const tbody = document.getElementById('jobs-tbody');

        if (jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Nenhuma candidatura registrada ainda.</td></tr>';
            return;
        }

        tbody.innerHTML = jobs.map(j => {
            const status = j.email_enviado
                ? '<span class="status-badge success">Enviado</span>'
                : '<span class="status-badge failed">Falhou</span>';
            const email = j.email_destino || '—';
            return `<tr>
                <td>${(j.data || '').substring(0, 16)}</td>
                <td style="color: var(--text-primary); font-weight: 500;">${j.empresa || ''}</td>
                <td>${j.vaga || ''}</td>
                <td style="font-size: 0.78rem; color: var(--text-muted);">${email}</td>
                <td>${status}</td>
            </tr>`;
        }).join('');
    } catch (err) {
        console.error('Jobs error:', err);
    }
}


// ═══════════════════════════════════════════════════════════════════
//  SETTINGS
// ═══════════════════════════════════════════════════════════════════

async function loadConfig() {
    try {
        const res = await fetch(`${API}/api/config`);
        const cfg = await res.json();

        document.getElementById('cfg-api-key').value = cfg.gemini_api_key || '';
        document.getElementById('cfg-email').value = cfg.email_address || '';
        document.getElementById('cfg-password').value = cfg.email_app_password || '';
        document.getElementById('cfg-cc').value = cfg.email_cc || '';
        document.getElementById('cfg-name').value = cfg.candidate_name || '';
        document.getElementById('cfg-max-jobs').value = cfg.max_jobs_per_category || 10;
        document.getElementById('cfg-presencial').checked = cfg.search_presencial;
        document.getElementById('cfg-portugal').checked = cfg.search_portugal;
        document.getElementById('cfg-delay-min').value = cfg.request_delay_min || 2;
        document.getElementById('cfg-delay-max').value = cfg.request_delay_max || 5;

        // Show current resume name
        if (cfg.resume_pdf) {
            document.getElementById('upload-text').textContent = `📎 ${cfg.resume_pdf}`;
            document.getElementById('upload-zone').classList.add('uploaded');
        }
    } catch (err) {
        console.error('Config error:', err);
    }
}

document.getElementById('btn-save-config').addEventListener('click', async () => {
    const payload = {
        gemini_api_key: document.getElementById('cfg-api-key').value,
        email_address: document.getElementById('cfg-email').value,
        email_app_password: document.getElementById('cfg-password').value,
        email_cc: document.getElementById('cfg-cc').value,
        candidate_name: document.getElementById('cfg-name').value,
        resume_pdf: document.getElementById('upload-text').textContent.replace('📎 ', '').trim(),
        max_jobs_per_category: parseInt(document.getElementById('cfg-max-jobs').value) || 10,
        search_presencial: document.getElementById('cfg-presencial').checked,
        search_portugal: document.getElementById('cfg-portugal').checked,
        request_delay_min: parseFloat(document.getElementById('cfg-delay-min').value) || 2,
        request_delay_max: parseFloat(document.getElementById('cfg-delay-max').value) || 5,
    };

    try {
        const res = await fetch(`${API}/api/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        const feedback = document.getElementById('save-feedback');
        feedback.textContent = '✅ ' + data.message;
        feedback.classList.add('visible');
        showToast(data.message, 'success');
        setTimeout(() => feedback.classList.remove('visible'), 3000);
    } catch (err) {
        showToast('Erro ao salvar configurações', 'error');
    }
});


// ═══════════════════════════════════════════════════════════════════
//  FILE UPLOAD (Drag & Drop + Click)
// ═══════════════════════════════════════════════════════════════════

const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('resume-file');

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) uploadFile(files[0]);
});

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) uploadFile(fileInput.files[0]);
});

async function uploadFile(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showToast('Apenas arquivos PDF são aceitos!', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API}/api/upload-resume`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.status === 'ok') {
            document.getElementById('upload-text').textContent = `📎 ${data.filename}`;
            uploadZone.classList.add('uploaded');
            showToast(data.message, 'success');
        } else {
            showToast(data.detail || 'Erro no upload', 'error');
        }
    } catch (err) {
        showToast('Erro ao fazer upload do currículo', 'error');
    }
}


// ═══════════════════════════════════════════════════════════════════
//  PASSWORD TOGGLE
// ═══════════════════════════════════════════════════════════════════

function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🔒';
    } else {
        input.type = 'password';
        btn.textContent = '👁';
    }
}


// ═══════════════════════════════════════════════════════════════════
//  INITIAL LOAD
// ═══════════════════════════════════════════════════════════════════

async function checkBotStatus() {
    try {
        const res = await fetch(`${API}/api/bot-status`);
        const data = await res.json();
        if (data.running) {
            setBotRunning(true);
            startLogPolling();
        }
    } catch (err) {
        // Server not ready yet
    }
}

// Boot
loadDashboard();
checkBotStatus();
