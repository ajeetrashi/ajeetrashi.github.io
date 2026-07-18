/* ============================================
   Health Automation Scheduler - Core App
   ============================================ */

(function () {
    'use strict';

    // ── Storage helpers ──
    const Store = {
        get(key, fallback = null) {
            try {
                const v = localStorage.getItem('has_' + key);
                return v ? JSON.parse(v) : fallback;
            } catch { return fallback; }
        },
        set(key, val) {
            localStorage.setItem('has_' + key, JSON.stringify(val));
        },
        remove(key) {
            localStorage.removeItem('has_' + key);
        },
        clear() {
            Object.keys(localStorage)
                .filter(k => k.startsWith('has_'))
                .forEach(k => localStorage.removeItem(k));
        }
    };

    // ── Date helpers ──
    function todayStr() {
        return new Date().toISOString().slice(0, 10);
    }

    function formatDate(d) {
        return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function dayName(d) {
        return new Date(d).toLocaleDateString('en-US', { weekday: 'short' });
    }

    function minutesToHM(m) {
        const h = Math.floor(m / 60);
        const min = m % 60;
        return h > 0 ? `${h}h ${min}m` : `${min}m`;
    }

    function uid() {
        return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
    }

    // ── Biomarker reference ranges ──
    const BIOMARKER_REF = {
        glucose:             { unit: 'mg/dL',  low: 70,  high: 100, name: 'Glucose' },
        hba1c:               { unit: '%',      low: 4,   high: 5.6, name: 'HbA1c' },
        'total-cholesterol': { unit: 'mg/dL',  low: 0,   high: 200, name: 'Total Cholesterol' },
        ldl:                 { unit: 'mg/dL',  low: 0,   high: 100, name: 'LDL' },
        hdl:                 { unit: 'mg/dL',  low: 40,  high: 999, name: 'HDL' },
        triglycerides:       { unit: 'mg/dL',  low: 0,   high: 150, name: 'Triglycerides' },
        crp:                 { unit: 'mg/L',   low: 0,   high: 1,   name: 'CRP' },
        'vitamin-d':         { unit: 'ng/mL',  low: 30,  high: 100, name: 'Vitamin D' },
        testosterone:        { unit: 'ng/dL',  low: 300, high: 1000,name: 'Testosterone' },
        tsh:                 { unit: 'mIU/L',  low: 0.4, high: 4,   name: 'TSH' },
        weight:              { unit: 'kg',     low: 0,   high: 999, name: 'Weight' },
        'body-fat':          { unit: '%',      low: 5,   high: 25,  name: 'Body Fat' },
        bmi:                 { unit: '',       low: 18.5,high: 25,  name: 'BMI' },
        waist:               { unit: 'cm',     low: 0,   high: 102, name: 'Waist' },
        'bp-systolic':       { unit: 'mmHg',   low: 90,  high: 120, name: 'BP Systolic' },
        'bp-diastolic':      { unit: 'mmHg',   low: 60,  high: 80,  name: 'BP Diastolic' },
        'resting-hr':        { unit: 'bpm',    low: 40,  high: 80,  name: 'Resting HR' },
        hrv:                 { unit: 'ms',     low: 20,  high: 999, name: 'HRV' },
        spo2:                { unit: '%',      low: 95,  high: 100, name: 'SpO2' },
    };

    // ── Preset protocols ──
    const PRESETS = {
        blueprint: {
            name: 'Bryan Johnson Blueprint',
            desc: 'Simplified version of the Blueprint longevity protocol.',
            category: 'longevity',
            items: [
                { name: 'Extra Virgin Olive Oil (30ml)', time: '06:00', category: 'nutrition' },
                { name: 'Blueprint Nutty Pudding', time: '06:15', category: 'nutrition' },
                { name: 'Collagen Peptides (20g)', time: '06:15', category: 'supplement' },
                { name: 'Cocoa Flavanols', time: '06:30', category: 'supplement' },
                { name: 'Vitamin D3 (2000 IU)', time: '06:30', category: 'supplement' },
                { name: 'Omega-3 (EPA/DHA)', time: '06:30', category: 'supplement' },
                { name: 'Creatine (5g)', time: '06:30', category: 'supplement' },
                { name: 'Exercise (45 min)', time: '07:00', category: 'exercise' },
                { name: 'Super Veggie Lunch', time: '11:00', category: 'nutrition' },
                { name: 'Last meal by 11am', time: '11:30', category: 'nutrition' },
                { name: 'Red Light Therapy (10 min)', time: '19:00', category: 'mindfulness' },
                { name: 'Wind down - no screens', time: '20:30', category: 'sleep' },
                { name: 'Sleep by 8:30pm', time: '20:30', category: 'sleep' },
            ]
        },
        huberman: {
            name: 'Huberman Essentials',
            desc: 'Key daily practices from Andrew Huberman.',
            category: 'longevity',
            items: [
                { name: 'Morning sunlight (10 min)', time: '06:30', category: 'mindfulness' },
                { name: 'Delay caffeine 90 min', time: '06:30', category: 'nutrition' },
                { name: 'AG1 / Greens drink', time: '07:00', category: 'supplement' },
                { name: 'Omega-3 (EPA 2g)', time: '07:00', category: 'supplement' },
                { name: 'Vitamin D3 + K2', time: '07:00', category: 'supplement' },
                { name: 'Tongkat Ali (400mg)', time: '07:00', category: 'supplement' },
                { name: 'Focused work block', time: '08:00', category: 'mindfulness' },
                { name: 'Resistance training', time: '10:00', category: 'exercise' },
                { name: 'Cold exposure (3 min)', time: '10:45', category: 'exercise' },
                { name: 'NSDR / Yoga Nidra (20 min)', time: '14:00', category: 'mindfulness' },
                { name: 'Magnesium Threonate', time: '21:00', category: 'supplement' },
                { name: 'Dim lights after sunset', time: '21:00', category: 'sleep' },
            ]
        },
        longevity: {
            name: 'Basic Longevity Stack',
            desc: 'Essential daily supplements and habits for longevity.',
            category: 'longevity',
            items: [
                { name: 'Vitamin D3 (5000 IU)', time: '07:00', category: 'supplement' },
                { name: 'Omega-3 Fish Oil', time: '07:00', category: 'supplement' },
                { name: 'Magnesium Glycinate (200mg)', time: '07:00', category: 'supplement' },
                { name: 'NMN (500mg)', time: '07:00', category: 'supplement' },
                { name: 'Resveratrol (500mg)', time: '07:00', category: 'supplement' },
                { name: 'Zone 2 Cardio (30 min)', time: '08:00', category: 'exercise' },
                { name: 'High protein meal', time: '12:00', category: 'nutrition' },
                { name: '10k steps', time: '17:00', category: 'exercise' },
                { name: 'Meditation (10 min)', time: '20:00', category: 'mindfulness' },
                { name: 'Sleep 7-8 hours', time: '22:00', category: 'sleep' },
            ]
        }
    };

    // ── State ──
    let tasks = Store.get('tasks', []);
    let completedToday = Store.get('completed_' + todayStr(), {});
    let protocols = Store.get('protocols', []);
    let biomarkers = Store.get('biomarkers', []);
    let preferences = Store.get('preferences', {
        wakeTime: '05:00',
        sleepTime: '22:00',
        notifications: true,
        autoReset: true
    });

    // ── DOM references ──
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ── Init ──
    function init() {
        setupDate();
        setupTabs();
        renderTasks();
        renderProtocols();
        renderBiomarkers();
        setupOura();
        setupSettings();
        setupQuickAdd();
        setupModals();
        checkDayReset();
        requestNotificationPermission();
        scheduleNotifications();
    }

    // ── Date display ──
    function setupDate() {
        const now = new Date();
        $('#current-date').textContent = now.toLocaleDateString('en-US', {
            weekday: 'long', month: 'long', day: 'numeric'
        });
    }

    // ── Tabs ──
    function setupTabs() {
        $$('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                $$('.tab-btn').forEach(b => b.classList.remove('active'));
                $$('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                $(`#tab-${btn.dataset.tab}`).classList.add('active');
            });
        });
    }

    // ── Day reset ──
    function checkDayReset() {
        const lastDate = Store.get('lastDate');
        if (lastDate !== todayStr()) {
            if (preferences.autoReset) {
                completedToday = {};
                Store.set('completed_' + todayStr(), completedToday);
            }
            Store.set('lastDate', todayStr());
            renderTasks();
        }
    }

    // ── Tasks / Daily Checklist ──
    function getTimeBlock(time) {
        const h = parseInt(time.split(':')[0], 10);
        if (h < 12) return 'morning';
        if (h < 17) return 'afternoon';
        return 'evening';
    }

    function renderTasks() {
        const morning = [];
        const afternoon = [];
        const evening = [];

        const sorted = [...tasks].sort((a, b) => a.time.localeCompare(b.time));
        sorted.forEach(t => {
            const block = getTimeBlock(t.time);
            if (block === 'morning') morning.push(t);
            else if (block === 'afternoon') afternoon.push(t);
            else evening.push(t);
        });

        renderTaskList('morning-tasks', morning);
        renderTaskList('afternoon-tasks', afternoon);
        renderTaskList('evening-tasks', evening);
        updateProgress();
    }

    function renderTaskList(containerId, items) {
        const ul = $(`#${containerId}`);
        if (!items.length) {
            ul.innerHTML = '<li class="empty-state" style="padding:0.75rem;font-size:0.85rem;">No tasks in this block</li>';
            return;
        }
        ul.innerHTML = items.map(t => {
            const done = completedToday[t.id] || false;
            return `
                <li class="task-item ${done ? 'completed' : ''}" data-id="${t.id}">
                    <div class="task-checkbox"></div>
                    <span class="task-time">${t.time}</span>
                    <span class="task-name">${escapeHtml(t.name)}</span>
                    <span class="task-category cat-${t.category}">${t.category}</span>
                    <button class="task-delete" data-id="${t.id}" title="Delete">&times;</button>
                </li>`;
        }).join('');

        ul.querySelectorAll('.task-item').forEach(li => {
            li.addEventListener('click', (e) => {
                if (e.target.classList.contains('task-delete')) return;
                toggleTask(li.dataset.id);
            });
        });

        ul.querySelectorAll('.task-delete').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteTask(btn.dataset.id);
            });
        });
    }

    function toggleTask(id) {
        completedToday[id] = !completedToday[id];
        Store.set('completed_' + todayStr(), completedToday);
        renderTasks();
    }

    function deleteTask(id) {
        tasks = tasks.filter(t => t.id !== id);
        delete completedToday[id];
        Store.set('tasks', tasks);
        Store.set('completed_' + todayStr(), completedToday);
        renderTasks();
    }

    function addTask(name, time, category) {
        const task = { id: uid(), name, time, category };
        tasks.push(task);
        Store.set('tasks', tasks);
        renderTasks();
    }

    function updateProgress() {
        const total = tasks.length;
        const done = total ? tasks.filter(t => completedToday[t.id]).length : 0;
        const pct = total ? Math.round((done / total) * 100) : 0;

        $('#daily-progress-text').textContent = `${pct}%`;
        const ring = $('#daily-progress-ring');
        const circumference = 2 * Math.PI * 26;
        ring.style.strokeDasharray = circumference;
        ring.style.strokeDashoffset = circumference - (pct / 100) * circumference;

        if (pct >= 80) {
            ring.style.stroke = 'var(--success)';
        } else if (pct >= 50) {
            ring.style.stroke = 'var(--accent)';
        } else {
            ring.style.stroke = 'var(--accent)';
        }
    }

    // ── Quick Add ──
    function setupQuickAdd() {
        $('#quick-add-form').addEventListener('submit', (e) => {
            e.preventDefault();
            const name = $('#quick-task-name').value.trim();
            const time = $('#quick-task-time').value;
            const category = $('#quick-task-category').value;
            if (name && time) {
                addTask(name, time, category);
                $('#quick-task-name').value = '';
                $('#quick-task-time').value = '';
            }
        });
    }

    // ── Protocols ──
    function renderProtocols() {
        const list = $('#protocol-list');
        if (!protocols.length) {
            list.innerHTML = '<div class="empty-state"><h3>No Protocols Yet</h3><p>Create a custom protocol or load a preset from Settings.</p></div>';
            return;
        }

        list.innerHTML = protocols.map(p => `
            <div class="protocol-card" data-id="${p.id}">
                <div class="protocol-header">
                    <div>
                        <h3>${escapeHtml(p.name)}</h3>
                        <span class="badge badge-${p.category}">${p.category}</span>
                    </div>
                    <div class="protocol-actions">
                        <button class="activate-btn" data-id="${p.id}" title="Load into daily schedule">Activate</button>
                        <button class="edit-btn" data-id="${p.id}" title="Edit">Edit</button>
                        <button class="delete-btn" data-id="${p.id}" title="Delete">Delete</button>
                    </div>
                </div>
                ${p.desc ? `<p class="protocol-desc">${escapeHtml(p.desc)}</p>` : ''}
                <p class="protocol-meta">${p.items.length} items</p>
            </div>
        `).join('');

        list.querySelectorAll('.activate-btn').forEach(btn => {
            btn.addEventListener('click', () => activateProtocol(btn.dataset.id));
        });
        list.querySelectorAll('.edit-btn').forEach(btn => {
            btn.addEventListener('click', () => editProtocol(btn.dataset.id));
        });
        list.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', () => deleteProtocol(btn.dataset.id));
        });
    }

    function activateProtocol(id) {
        const proto = protocols.find(p => p.id === id);
        if (!proto) return;
        const existingNames = new Set(tasks.map(t => t.name));
        let added = 0;
        proto.items.forEach(item => {
            if (!existingNames.has(item.name)) {
                addTask(item.name, item.time, item.category);
                added++;
            }
        });
        alert(`Activated "${proto.name}": ${added} new tasks added to your daily schedule.`);
        document.querySelector('[data-tab="today"]').click();
    }

    function editProtocol(id) {
        const proto = protocols.find(p => p.id === id);
        if (!proto) return;
        openProtocolModal(proto);
    }

    function deleteProtocol(id) {
        if (!confirm('Delete this protocol?')) return;
        protocols = protocols.filter(p => p.id !== id);
        Store.set('protocols', protocols);
        renderProtocols();
    }

    function openProtocolModal(existing = null) {
        const modal = $('#protocol-modal');
        const form = $('#protocol-form');
        const title = $('#protocol-modal-title');

        title.textContent = existing ? 'Edit Protocol' : 'New Protocol';
        $('#proto-name').value = existing ? existing.name : '';
        $('#proto-desc').value = existing ? (existing.desc || '') : '';
        $('#proto-category').value = existing ? existing.category : 'longevity';

        const itemsList = $('#proto-items-list');
        itemsList.innerHTML = '';
        if (existing && existing.items.length) {
            existing.items.forEach(item => addProtoItemRow(item));
        } else {
            addProtoItemRow();
        }

        form.onsubmit = (e) => {
            e.preventDefault();
            const data = {
                id: existing ? existing.id : uid(),
                name: $('#proto-name').value.trim(),
                desc: $('#proto-desc').value.trim(),
                category: $('#proto-category').value,
                items: getProtoItems()
            };
            if (!data.name) return;

            if (existing) {
                const idx = protocols.findIndex(p => p.id === existing.id);
                if (idx >= 0) protocols[idx] = data;
            } else {
                protocols.push(data);
            }
            Store.set('protocols', protocols);
            modal.classList.add('hidden');
            renderProtocols();
        };

        modal.classList.remove('hidden');
    }

    function addProtoItemRow(item = {}) {
        const row = document.createElement('div');
        row.className = 'proto-item-row';
        row.innerHTML = `
            <input type="text" placeholder="Item name" value="${escapeHtml(item.name || '')}" class="proto-item-name" required>
            <input type="time" value="${item.time || '07:00'}" class="proto-item-time">
            <select class="proto-item-cat">
                <option value="supplement" ${item.category === 'supplement' ? 'selected' : ''}>Supplement</option>
                <option value="exercise" ${item.category === 'exercise' ? 'selected' : ''}>Exercise</option>
                <option value="nutrition" ${item.category === 'nutrition' ? 'selected' : ''}>Nutrition</option>
                <option value="mindfulness" ${item.category === 'mindfulness' ? 'selected' : ''}>Mindfulness</option>
                <option value="sleep" ${item.category === 'sleep' ? 'selected' : ''}>Sleep</option>
                <option value="custom" ${item.category === 'custom' ? 'selected' : ''}>Custom</option>
            </select>
            <button type="button" class="proto-item-remove" title="Remove">&times;</button>
        `;
        row.querySelector('.proto-item-remove').addEventListener('click', () => row.remove());
        $('#proto-items-list').appendChild(row);
    }

    function getProtoItems() {
        return Array.from($$('.proto-item-row')).map(row => ({
            name: row.querySelector('.proto-item-name').value.trim(),
            time: row.querySelector('.proto-item-time').value,
            category: row.querySelector('.proto-item-cat').value
        })).filter(i => i.name);
    }

    $('#add-protocol-btn').addEventListener('click', () => openProtocolModal());
    $('#add-proto-item').addEventListener('click', () => addProtoItemRow());

    // ── Biomarkers ──
    function renderBiomarkers() {
        renderBiomarkerSummary();
        renderBiomarkerTable();
    }

    function renderBiomarkerSummary() {
        const summary = $('#biomarker-summary');
        const latest = {};
        biomarkers.forEach(b => {
            if (!latest[b.marker] || b.date >= latest[b.marker].date) {
                latest[b.marker] = b;
            }
        });

        const keys = Object.keys(latest);
        if (!keys.length) {
            summary.innerHTML = '';
            return;
        }

        summary.innerHTML = keys.slice(0, 8).map(key => {
            const b = latest[key];
            const ref = BIOMARKER_REF[b.marker] || {};
            const status = getMarkerStatus(b.value, ref);
            const name = ref.name || b.customName || b.marker;
            return `
                <div class="bio-stat ${status}">
                    <div class="bio-stat-label">${escapeHtml(name)}</div>
                    <div class="bio-stat-value">${b.value}${ref.unit ? ' ' + ref.unit : ''}</div>
                    <div class="bio-stat-date">${formatDate(b.date)}</div>
                </div>`;
        }).join('');
    }

    function renderBiomarkerTable() {
        const tbody = $('#biomarker-tbody');
        const empty = $('#biomarker-empty');
        const sorted = [...biomarkers].sort((a, b) => b.date.localeCompare(a.date));

        if (!sorted.length) {
            tbody.innerHTML = '';
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        tbody.innerHTML = sorted.slice(0, 50).map(b => {
            const ref = BIOMARKER_REF[b.marker] || {};
            const name = ref.name || b.customName || b.marker;
            const status = getMarkerStatus(b.value, ref);
            const statusLabel = status === 'optimal' ? 'Optimal' : status === 'warning' ? 'Borderline' : status === 'danger' ? 'High' : 'Logged';
            return `
                <tr>
                    <td>${formatDate(b.date)}</td>
                    <td>${escapeHtml(name)}</td>
                    <td>${b.value}</td>
                    <td>${ref.unit || '-'}</td>
                    <td class="status-${status}">${statusLabel}</td>
                </tr>`;
        }).join('');
    }

    function getMarkerStatus(value, ref) {
        if (!ref || ref.high === undefined) return 'normal';
        if (value >= ref.low && value <= ref.high) return 'optimal';
        const margin = (ref.high - ref.low) * 0.15;
        if (value < ref.low - margin || value > ref.high + margin) return 'danger';
        return 'warning';
    }

    // Biomarker modal
    $('#add-biomarker-btn').addEventListener('click', () => {
        $('#biomarker-modal').classList.remove('hidden');
        $('#bio-date').value = todayStr();
        $('#bio-value').value = '';
        $('#bio-notes').value = '';
        $('#bio-marker').value = 'glucose';
        $('#custom-marker-group').classList.add('hidden');
    });

    $('#bio-marker').addEventListener('change', (e) => {
        $('#custom-marker-group').classList.toggle('hidden', e.target.value !== 'custom');
    });

    $('#biomarker-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const marker = $('#bio-marker').value;
        const entry = {
            id: uid(),
            marker,
            customName: marker === 'custom' ? $('#bio-custom-name').value.trim() : null,
            value: parseFloat($('#bio-value').value),
            date: $('#bio-date').value || todayStr(),
            notes: $('#bio-notes').value.trim()
        };
        if (isNaN(entry.value)) return;
        biomarkers.push(entry);
        Store.set('biomarkers', biomarkers);
        $('#biomarker-modal').classList.add('hidden');
        renderBiomarkers();
    });

    // ── Oura Ring Integration ──
    const OURA_API = 'https://api.ouraring.com/v2/usercollection';

    function getOuraToken() {
        return Store.get('ouraToken', '');
    }

    function setupOura() {
        const token = getOuraToken();
        if (token) {
            $('#oura-not-connected').classList.add('hidden');
            $('#oura-connected').classList.remove('hidden');
            fetchOuraData();
        }

        $('#sync-oura-btn').addEventListener('click', () => {
            if (getOuraToken()) fetchOuraData();
            else document.querySelector('[data-tab="settings"]').click();
        });

        $('#refresh-oura-btn').addEventListener('click', () => fetchOuraData());
    }

    async function fetchOuraData() {
        const token = getOuraToken();
        if (!token) return;

        const today = todayStr();
        const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);

        try {
            const [sleepRes, readinessRes, activityRes] = await Promise.all([
                ouraFetch(`/daily_sleep?start_date=${weekAgo}&end_date=${today}`, token),
                ouraFetch(`/daily_readiness?start_date=${weekAgo}&end_date=${today}`, token),
                ouraFetch(`/daily_activity?start_date=${weekAgo}&end_date=${today}`, token),
            ]);

            if (sleepRes.data && sleepRes.data.length) {
                const latest = sleepRes.data[sleepRes.data.length - 1];
                setOuraValue('oura-sleep-score', latest.score, 'oura-sleep-bar');
                const contributors = latest.contributors || {};
                setDetail('oura-total-sleep', latest.contributors?.total_sleep !== undefined ? minutesToHM(latest.contributors.total_sleep) : '--');
                setDetail('oura-deep-sleep', contributors.deep_sleep !== undefined ? `${contributors.deep_sleep}` : '--');
                setDetail('oura-rem-sleep', contributors.rem_sleep !== undefined ? `${contributors.rem_sleep}` : '--');
                setDetail('oura-efficiency', contributors.efficiency !== undefined ? `${contributors.efficiency}%` : '--');
            }

            if (readinessRes.data && readinessRes.data.length) {
                const latest = readinessRes.data[readinessRes.data.length - 1];
                setOuraValue('oura-readiness', latest.score, 'oura-readiness-bar');
                const contributors = latest.contributors || {};
                setDetail('oura-rhr', contributors.resting_heart_rate !== undefined ? `${contributors.resting_heart_rate} bpm` : '--');
                setDetail('oura-hrv', contributors.hrv_balance !== undefined ? `${contributors.hrv_balance}` : '--');
                setDetail('oura-temp', latest.temperature_deviation !== undefined ? `${latest.temperature_deviation > 0 ? '+' : ''}${latest.temperature_deviation.toFixed(1)}°` : '--');
            }

            if (activityRes.data && activityRes.data.length) {
                const latest = activityRes.data[activityRes.data.length - 1];
                setOuraValue('oura-activity-score', latest.score, 'oura-activity-bar');
                setDetail('oura-steps', latest.steps !== undefined ? latest.steps.toLocaleString() : '--');
                setDetail('oura-calories', latest.active_calories !== undefined ? `${latest.active_calories} kcal` : '--');
                setDetail('oura-move-min', latest.high_activity_time !== undefined ? minutesToHM(latest.high_activity_time) : '--');
            }

            renderOuraTrend(readinessRes.data || []);

            Store.set('ouraLastSync', new Date().toISOString());
        } catch (err) {
            console.error('Oura fetch error:', err);
        }
    }

    async function ouraFetch(path, token) {
        const res = await fetch(OURA_API + path, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (!res.ok) throw new Error(`Oura API ${res.status}`);
        return res.json();
    }

    function setOuraValue(elId, score, barId) {
        const el = $(`#${elId}`);
        const bar = $(`#${barId}`);
        if (score != null) {
            el.textContent = score;
            bar.style.width = `${Math.min(score, 100)}%`;
            if (score >= 85) bar.style.background = 'var(--success)';
            else if (score >= 70) bar.style.background = 'var(--warning)';
            else bar.style.background = 'var(--danger)';
        }
    }

    function setDetail(elId, value) {
        const el = $(`#${elId}`);
        if (el) el.textContent = value;
    }

    function renderOuraTrend(data) {
        const chart = $('#oura-trend-chart');
        if (!data.length) {
            chart.innerHTML = '<p class="empty-state" style="padding:1rem;">No trend data available</p>';
            return;
        }
        const last7 = data.slice(-7);
        const maxScore = Math.max(...last7.map(d => d.score || 0), 1);

        chart.innerHTML = last7.map(d => {
            const pct = ((d.score || 0) / maxScore) * 100;
            return `
                <div class="trend-bar" style="height:${Math.max(pct, 8)}%;">
                    <span class="trend-value">${d.score || '--'}</span>
                    <span class="trend-label">${dayName(d.day)}</span>
                </div>`;
        }).join('');
    }

    // ── Settings ──
    function setupSettings() {
        // Load saved values
        $('#pref-wake').value = preferences.wakeTime;
        $('#pref-sleep').value = preferences.sleepTime;
        $('#pref-notifications').checked = preferences.notifications;
        $('#pref-auto-reset').checked = preferences.autoReset;

        const savedToken = getOuraToken();
        if (savedToken) {
            $('#oura-token').value = savedToken;
            $('#oura-status').textContent = 'Connected';
            $('#oura-status').className = 'connection-status connected';
        }

        // Save Oura token
        $('#save-oura-token').addEventListener('click', () => {
            const token = $('#oura-token').value.trim();
            if (token) {
                Store.set('ouraToken', token);
                $('#oura-status').textContent = 'Token saved. Syncing...';
                $('#oura-status').className = 'connection-status connected';
                $('#oura-not-connected').classList.add('hidden');
                $('#oura-connected').classList.remove('hidden');
                fetchOuraData();
            } else {
                Store.remove('ouraToken');
                $('#oura-status').textContent = 'Token removed';
                $('#oura-status').className = 'connection-status error';
                $('#oura-not-connected').classList.remove('hidden');
                $('#oura-connected').classList.add('hidden');
            }
        });

        // Save preferences
        $('#save-prefs-btn').addEventListener('click', () => {
            preferences = {
                wakeTime: $('#pref-wake').value,
                sleepTime: $('#pref-sleep').value,
                notifications: $('#pref-notifications').checked,
                autoReset: $('#pref-auto-reset').checked
            };
            Store.set('preferences', preferences);
            alert('Preferences saved!');
        });

        // Export
        $('#export-data-btn').addEventListener('click', () => {
            const data = {
                tasks,
                protocols,
                biomarkers,
                preferences,
                exportDate: new Date().toISOString()
            };
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `health-data-${todayStr()}.json`;
            a.click();
            URL.revokeObjectURL(url);
        });

        // Import
        $('#import-data-input').addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (ev) => {
                try {
                    const data = JSON.parse(ev.target.result);
                    if (data.tasks) { tasks = data.tasks; Store.set('tasks', tasks); }
                    if (data.protocols) { protocols = data.protocols; Store.set('protocols', protocols); }
                    if (data.biomarkers) { biomarkers = data.biomarkers; Store.set('biomarkers', biomarkers); }
                    if (data.preferences) { preferences = data.preferences; Store.set('preferences', preferences); }
                    renderTasks();
                    renderProtocols();
                    renderBiomarkers();
                    alert('Data imported successfully!');
                } catch {
                    alert('Invalid file format.');
                }
            };
            reader.readAsText(file);
        });

        // Reset today
        $('#clear-today-btn').addEventListener('click', () => {
            if (!confirm('Reset today\'s progress? Tasks will remain but all checkmarks will be cleared.')) return;
            completedToday = {};
            Store.set('completed_' + todayStr(), completedToday);
            renderTasks();
        });

        // Clear all
        $('#clear-all-btn').addEventListener('click', () => {
            if (!confirm('Delete ALL data? This cannot be undone.')) return;
            Store.clear();
            tasks = [];
            protocols = [];
            biomarkers = [];
            completedToday = {};
            renderTasks();
            renderProtocols();
            renderBiomarkers();
            alert('All data cleared.');
        });

        // Preset loaders
        $$('.load-preset').forEach(btn => {
            btn.addEventListener('click', () => {
                const key = btn.dataset.preset;
                const preset = PRESETS[key];
                if (!preset) return;
                if (protocols.find(p => p.name === preset.name)) {
                    alert(`"${preset.name}" is already in your protocols.`);
                    return;
                }
                protocols.push({
                    id: uid(),
                    name: preset.name,
                    desc: preset.desc,
                    category: preset.category,
                    items: [...preset.items]
                });
                Store.set('protocols', protocols);
                renderProtocols();
                alert(`"${preset.name}" added to your protocols. Go to Protocols tab to activate it.`);
            });
        });
    }

    // ── Modals ──
    function setupModals() {
        $$('[data-close-modal]').forEach(btn => {
            btn.addEventListener('click', () => {
                $(`#${btn.dataset.closeModal}`).classList.add('hidden');
            });
        });

        $$('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.classList.add('hidden');
            });
        });
    }

    // ── Notifications ──
    function requestNotificationPermission() {
        if (preferences.notifications && 'Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    function scheduleNotifications() {
        if (!preferences.notifications || !('Notification' in window) || Notification.permission !== 'granted') return;

        setInterval(() => {
            const now = new Date();
            const currentTime = now.toTimeString().slice(0, 5);
            tasks.forEach(t => {
                if (t.time === currentTime && !completedToday[t.id]) {
                    new Notification('Health Scheduler', {
                        body: `Time for: ${t.name}`,
                        icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">💊</text></svg>'
                    });
                }
            });
        }, 60000);
    }

    // ── Utility ──
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ── Boot ──
    document.addEventListener('DOMContentLoaded', init);
})();
