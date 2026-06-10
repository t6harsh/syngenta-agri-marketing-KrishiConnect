/* ══════════════════════════════════════════════════════
   KrishiConnect AI — Frontend Application
   ══════════════════════════════════════════════════════ */

const API = '';

// ─── Tab Navigation ───
document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
    });
});

// ─── Helpers ───
function $(id) { return document.getElementById(id); }
function fmt(n) { return n >= 1000 ? (n / 1000).toFixed(1) + 'K' : n; }
function pct(n) { return (n * 100).toFixed(1) + '%'; }

// Track the group_by used for the latest segment load
window._currentGroupBy = '';

function metricCard(label, value, detail, color = 'green') {
    return `<div class="metric-card"><div class="metric-label">${label}</div><div class="metric-value ${color}">${value}</div><div class="metric-detail">${detail}</div></div>`;
}

function barChart(items, maxVal, colorCycle) {
    const colors = colorCycle || ['green', 'blue', 'amber', 'purple', 'teal', 'red'];
    return '<div class="bar-chart">' + items.map((item, i) => {
        const w = Math.max(6, (item.value / maxVal) * 100);
        const c = colors[i % colors.length];
        return `<div class="bar-row"><div class="bar-label">${item.label}</div><div class="bar-track"><div class="bar-fill ${c}" style="width:${w}%"><span class="bar-value">${item.display || item.value}</span></div></div></div>`;
    }).join('') + '</div>';
}

function kvList(items) {
    return '<div class="kv-list">' + items.map(i => `<div class="kv-item"><span class="kv-key">${i.k}</span><span class="kv-value">${i.v}</span></div>`).join('') + '</div>';
}

async function api(path) {
    const r = await fetch(API + path);
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
}

function renderStoryboard(sb) {
    if (!sb || !sb.length) return 'No storyboard available.';
    return sb.map(scene =>
        `<div style="margin-bottom:8px;border-bottom:1px solid var(--border-color);padding-bottom:4px;">
            <b>Scene ${scene.scene} (${scene.duration_sec}s):</b> ${scene.visual}
            <br/><i style="color:var(--text-muted)">Voice: "${scene.narration_en}"</i>
        </div>`
    ).join('');
}

// ─── Boot ───
async function boot() {
    try {
        const data = await api('/api/data/overview');
        $('status-dot').classList.add('online');
        $('status-text').innerHTML = `<span class="blinking-dot" id="status-dot" style="background-color: var(--toxic-green)"></span>SYS.BOOT COMPLETE // ${data.growers} GROWERS LOADED`;
        renderDashboard(data);
        populateFilters(data);
    } catch (e) {
        $('status-text').textContent = 'Connection failed';
        console.error(e);
    }
}

async function renderDashboard(d) {
    try {
        const biz = await api('/api/analytics/business-overview');

        // Top business KPIs
        const stateCount = Object.keys(biz.by_state).length;
        $('overview-metrics').innerHTML =
            metricCard('Total Growers', fmt(biz.total_growers), stateCount + ' states, ' + Object.keys(biz.by_crop).length + ' crops', 'green') +
            metricCard('Active Clusters', biz.total_segments, 'Micro-segments identified', 'blue') +
            metricCard('Campaigns Sent', fmt(biz.total_campaigns_sent), 'WhatsApp messages', 'amber') +
            metricCard('Delivery Rate', pct(biz.overall_delivery_rate), 'Messages delivered', 'purple') +
            metricCard('Open Rate', pct(biz.overall_open_rate), 'Of delivered', 'teal') +
            metricCard('Campaign→Action', pct(biz.campaign_to_action_rate), 'Click → product scan', 'green');

        // Crop distribution
        const crops = Object.entries(biz.by_crop).sort((a, b) => b[1] - a[1]);
        const maxCrop = crops[0] ? crops[0][1] : 1;
        $('crop-distribution').innerHTML = barChart(crops.map(([k, v]) => ({ label: k, value: v, display: v })), maxCrop);

        // Channel utilization
        const ch = Object.entries(biz.by_channel).sort((a, b) => b[1] - a[1]);
        const maxCh = ch[0] ? ch[0][1] : 1;
        $('channel-distribution').innerHTML = barChart(ch.map(([k, v]) => ({ label: k, value: v, display: v })), maxCh, ['green', 'blue', 'purple']);

        // Top segments by grower count
        const segs = biz.top_segments || [];
        const maxSeg = segs.length ? segs[0].grower_count : 1;
        $('top-segments').innerHTML = segs.length ? barChart(segs.map(s => ({
            label: s.crop + '/' + s.stage + ' ' + s.state,
            value: s.grower_count,
            display: s.grower_count
        })), maxSeg) : '<p style="color:var(--text-dim)">No segment data</p>';

        // State distribution (real data, no random)
        const states = Object.entries(biz.by_state).sort((a, b) => b[1] - a[1]);
        const maxState = states[0] ? states[0][1] : 1;
        $('state-distribution').innerHTML = barChart(states.map(([k, v]) => ({ label: k, value: v, display: v })), maxState, ['teal', 'blue', 'green', 'amber', 'purple']);

        // Segment Engagement Rankings
        try {
            const eng = await api('/api/analytics/segment-engagement');
            renderSegmentEngagement(eng);
        } catch (e) {
            $('segment-engagement').innerHTML = '<p style="color:#ef4444">Failed to load segment engagement</p>';
        }

        // Optimal Send Times
        try {
            const ot = await api('/api/analytics/optimal-send-times');
            renderOptimalTimes(ot);
        } catch (e) {
            $('optimal-times').innerHTML = '<p style="color:#ef4444">Failed to load optimal times</p>';
        }

        // Summary metrics for TARGET_CLUSTERS tab
        $('segment-summary-metrics').innerHTML = '';
    } catch (e) {
        console.error('Dashboard render error:', e);
    }
}

function renderSegmentEngagement(data) {
    if (!data.segments || !data.segments.length) {
        $('segment-engagement').innerHTML = '<p style="color:var(--text-dim)">No WhatsApp engagement data for segmentation.</p>';
        return;
    }

    const top = data.top_performing || [];
    const bottom = data.bottom_performing || [];

    let html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:8px">';

    // -- Top Performing --
    html += '<div><h4 style="font-size:11px;color:var(--toxic-green);margin-bottom:12px">▲ TOP PERFORMING SEGMENTS</h4>';
    html += '<div class="engagement-list">';
    top.forEach(s => {
        const engPct = (s.engagement_score * 100).toFixed(1);
        const openPct = (s.open_rate * 100).toFixed(1);
        const clickPct = (s.click_rate * 100).toFixed(1);
        html += `<div class="eng-row" style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--grid-line);font-size:11px">
            <div style="flex:1">
                <span style="color:var(--text-chalk);font-weight:600">${s.crop}</span>
                <span style="color:var(--text-dim)"> / ${s.stage} / ${s.state}</span>
            </div>
            <div style="text-align:right;white-space:nowrap">
                <span style="color:var(--toxic-green);font-weight:700;font-size:12px">${engPct}%</span>
                <span style="color:var(--text-dim);margin-left:8px">⇧${openPct}% · ⇧${clickPct}%</span>
                <span style="color:var(--text-dim);margin-left:4px">(${fmt(s.grower_count)} growers)</span>
            </div>
        </div>`;
    });
    html += '</div></div>';

    // -- Bottom Performing --
    const worstClass = bottom.length > 0 && bottom[0] === bottom[bottom.length - 1] ? 'alert-critical' : '';
    html += '<div><h4 style="font-size:11px;color:#ef4444;margin-bottom:12px">▼ BOTTOM PERFORMING SEGMENTS</h4>';
    html += '<div class="engagement-list">';
    bottom.forEach(s => {
        const engPct = (s.engagement_score * 100).toFixed(1);
        const openPct = (s.open_rate * 100).toFixed(1);
        const clickPct = (s.click_rate * 100).toFixed(1);
        const isWorst5 = s.rank > data.total_segments - 5;
        html += `<div class="eng-row ${isWorst5 ? 'eng-alert' : ''}" style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--grid-line);font-size:11px${isWorst5 ? ';background:rgba(255,0,60,0.08);border-left:3px solid #ef4444;padding-left:8px' : ''}">
            <div style="flex:1">
                <span style="color:var(--text-chalk);font-weight:600">${s.crop}</span>
                <span style="color:var(--text-dim)"> / ${s.stage} / ${s.state}</span>
            </div>
            <div style="text-align:right;white-space:nowrap">
                <span style="color:#ef4444;font-weight:700;font-size:12px">${engPct}%</span>
                <span style="color:var(--text-dim);margin-left:8px">⇧${openPct}% · ⇧${clickPct}%</span>
                <span style="color:var(--text-dim);margin-left:4px">(${fmt(s.grower_count)} growers)</span>
            </div>
        </div>`;
    });
    html += '</div></div></div>';

    // Bottom line: insight callout
    if (bottom.length >= 5) {
        const worst5 = bottom.slice(0, 5);
        const totalGrowers = worst5.reduce((sum, s) => sum + s.grower_count, 0);
        const avgEng = worst5.reduce((sum, s) => sum + s.engagement_score, 0) / worst5.length;
        html += `<div style="margin-top:16px;padding:12px;background:rgba(255,0,60,0.06);border:1px solid rgba(255,0,60,0.25);border-radius:0;font-size:11px">
            <span style="color:#ef4444;font-weight:700">⚠ ALERT:</span>
            <span style="color:var(--text-dim)"> Bottom 5 segments avg ${(avgEng * 100).toFixed(1)}% engagement across ${fmt(totalGrowers)} growers. Consider reallocating budget from low-engagement clusters to top-performing ones for better ROI.</span>
        </div>`;
    }

    $('segment-engagement').innerHTML = html;
}

function renderOptimalTimes(data) {
    if (!data.segments || !data.segments.length) {
        $('optimal-times').innerHTML = '<p style="color:var(--text-dim)">No send-time data available.</p>';
        return;
    }

    // Global weekday ranking bar chart
    const globalDays = data.global_weekday_ranking || [];
    const maxGlobal = globalDays.length ? globalDays[0].open_rate : 1;

    let html = '<h4 style="font-size:11px;color:var(--sky-blue);margin-bottom:12px">GLOBAL WEEKDAY OPEN RATES</h4>';
    html += '<div style="margin-bottom:24px">' + barChart(globalDays.map(d => ({
        label: d.day.slice(0, 3),
        value: d.open_rate * 100,
        display: (d.open_rate * 100).toFixed(1) + '%'
    })), Math.max(maxGlobal * 100, 1), ['blue', 'green', 'amber', 'purple', 'teal', 'red', 'blue']) + '</div>';

    // Per-segment optimal day table (top segments by message volume)
    const topSegs = data.segments.slice(0, 20);
    html += '<h4 style="font-size:11px;color:var(--toxic-green);margin-bottom:12px">OPTIMAL DAY BY SEGMENT</h4>';
    html += '<div style="max-height:280px;overflow-y:auto;border:1px solid var(--grid-line)">';
    html += '<table class="data-table" style="width:100%;font-size:10px"><thead><tr>' +
        '<th>STATE</th><th>CROP</th><th>DEVICE</th><th>BEST DAY</th><th>OPEN RATE</th><th>AVG OPEN</th><th>LIFT</th><th>MSGS</th>' +
        '</tr></thead><tbody>';

    topSegs.forEach(s => {
        const optPct = (s.optimal_open_rate * 100).toFixed(1);
        const avgPct = (s.avg_open_rate * 100).toFixed(1);
        const liftPct = (s.uplift_vs_avg * 100).toFixed(1);
        const liftColor = s.uplift_vs_avg > 0.3 ? 'var(--toxic-green)' : s.uplift_vs_avg > 0.1 ? 'var(--phosphor-orange)' : 'var(--text-dim)';
        html += `<tr>
            <td>${s.state}</td>
            <td>${s.crop}</td>
            <td>${s.device_type === 'smartphone' ? '📱' : '📟'}</td>
            <td style="color:var(--toxic-green);font-weight:700">${s.optimal_day}</td>
            <td style="color:var(--sky-blue);font-weight:600">${optPct}%</td>
            <td style="color:var(--text-dim)">${avgPct}%</td>
            <td style="color:${liftColor};font-weight:600">+${liftPct}%</td>
            <td style="color:var(--text-dim)">${fmt(s.total_messages)}</td>
        </tr>`;
    });
    html += '</tbody></table></div>';

    // Insight callout
    const bestGlobal = globalDays[0];
    const worstGlobal = globalDays[globalDays.length - 1];
    html += `<div style="margin-top:16px;padding:12px;background:rgba(0,229,255,0.04);border:1px solid rgba(0,229,255,0.15);font-size:11px">
        <span style="color:var(--sky-blue);font-weight:700">● INSIGHT:</span>
        <span style="color:var(--text-dim)"> Best global day is <strong style="color:var(--text-chalk)">${bestGlobal ? bestGlobal.day : 'N/A'}</strong> (${bestGlobal ? (bestGlobal.open_rate * 100).toFixed(1) : 0}% open rate). Worst is <strong style="color:var(--text-chalk)">${worstGlobal ? worstGlobal.day : 'N/A'}</strong> (${worstGlobal ? (worstGlobal.open_rate * 100).toFixed(1) : 0}%). Scheduling on optimal days can lift open rates by up to <strong style="color:var(--toxic-green)">${data.segments.length ? (Math.max(...data.segments.map(s => s.uplift_vs_avg)) * 100).toFixed(0) : 0}%</strong> for individual segments.</span>
    </div>`;

    $('optimal-times').innerHTML = html;
}

function populateFilters(d) {
    const cropSel = $('seg-filter-crop');
    d.crops.forEach(c => { if (c && c !== 'unknown') cropSel.innerHTML += `<option value="${c}">${c.toUpperCase()}</option>`; });
    const stateSel = $('seg-filter-state');
    d.states.forEach(s => { stateSel.innerHTML += `<option value="${s}">${s.toUpperCase()}</option>`; });
    const langSel = $('seg-filter-language');
    d.languages.forEach(l => { if (l && l !== 'unknown') langSel.innerHTML += `<option value="${l}">${l.toUpperCase()}</option>`; });
}

// ─── Segments ───
$('seg-load-btn').addEventListener('click', async () => {
    const crop = $('seg-filter-crop').value;
    const stage = $('seg-filter-stage').value;
    const state = $('seg-filter-state').value;
    const language = $('seg-filter-language').value;
    const device = $('seg-filter-device').value;

    // Read group-by checkboxes
    const checkedDims = [...document.querySelectorAll('.gb-dim:checked')].map(cb => cb.value);
    const groupBy = checkedDims.length ? checkedDims.join(',') : 'crop';

    let url = `/api/segments/list?limit=100&group_by=${groupBy}`;
    if (crop) url += '&crop=' + crop;
    if (stage) url += '&stage=' + stage;
    if (state) url += '&state=' + state;
    if (language) url += '&language=' + language;
    if (device) url += '&device_type=' + device;

    try {
        const data = await api(url);
        // Store segments for inline generation
        window._segmentsData = {};
        data.segments.forEach(s => { window._segmentsData[s.segment_id] = s; });

        // Determine which columns to show based on group_by
        const gb = checkedDims.length ? checkedDims : ['crop'];
        const showCol = dim => gb.includes(dim);

        // Toggle thead visibility
        document.querySelectorAll('#segments-thead .th-dims').forEach(th => {
            th.style.display = showCol(th.dataset.dim) ? '' : 'none';
        });

        // Store current group_by for segment generation
        window._currentGroupBy = groupBy;

        const tbody = $('segments-tbody');
        tbody.innerHTML = data.segments.map(s => `<tr>
            <td style="color:var(--text-primary);font-weight:600;font-size:11px;word-break:break-all;max-width:180px;">
                <span title="${s.segment_id}">${gb.length <= 2 ? s.segment_id : gb.map(d => ({crop:s.crop,stage:s.stage,state:s.state,language:s.language,device_type:s.device_type}[d])).join('/')}</span>
            </td>
            ${showCol('crop') ? `<td><span class="tag tag-green">${s.crop}</span></td>` : ''}
            ${showCol('stage') ? `<td><span class="tag tag-blue">${s.stage}</span></td>` : ''}
            ${showCol('state') ? `<td>${s.state}</td>` : ''}
            ${showCol('language') ? `<td><span class="tag tag-purple">${s.language}</span></td>` : ''}
            ${showCol('device_type') ? `<td><span class="tag ${s.device_type === 'smartphone' ? 'tag-green' : 'tag-amber'}">${s.device_type}</span></td>` : ''}
            <td style="color:var(--text-primary);font-weight:700">${s.grower_count}</td>
            <td>${s.avg_farm_size} ac</td>
            <td style="font-size:11px">${s.threat || '—'}</td>
            <td style="font-size:11px">${(s.recommended_products || []).slice(0, 2).join(', ')}${(s.recommended_products || []).length > 2 ? '…' : ''}</td>
            <td><div class="seg-action-cell"><button class="btn-generate-seg" data-seg-id="${s.segment_id}">GENERATE</button></div></td>
        </tr>`).join('');

        // Attach segment generate click handlers — opens inline panel
        document.querySelectorAll('.btn-generate-seg').forEach(btn => {
            btn.addEventListener('click', () => {
                const segId = btn.dataset.segId;
                const seg = window._segmentsData[segId];
                if (!seg) return;

                // Highlight selected row
                document.querySelectorAll('#segments-tbody tr').forEach(r => r.classList.remove('row-selected'));
                btn.closest('tr').classList.add('row-selected');

                // Show inline generation panel
                $('seg-gen-selected').textContent = `[${seg.grower_count}] ${seg.crop} / ${seg.stage} / ${seg.state} / ${seg.language} ⋮ ${segId}`;
                $('seg-gen-panel').style.display = 'block';
                $('seg-gen-panel').dataset.segId = segId;
                $('seg-gen-panel').dataset.groupBy = window._currentGroupBy || '';
                $('seg-gen-meta').innerHTML = '';
                $('seg-gen-outputs').innerHTML = '';
                // Scroll to panel
                $('seg-gen-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });
    } catch (e) { console.error(e); }
});

// ─── Grower Lookup ───
$('grower-load-btn').addEventListener('click', async () => {
    const gid = $('grower-id-input').value.trim();
    if (!gid) return;
    try {
        const ctx = await api(`/api/grower/${gid}`);
        $('grower-profile-area').style.display = 'grid';

        $('grower-info').innerHTML = kvList([
            { k: 'ID', v: ctx.grower_id }, { k: 'State', v: ctx.state }, { k: 'District', v: ctx.district },
            { k: 'Tehsil', v: ctx.tehsil }, { k: 'Language', v: `<span class="tag tag-purple">${ctx.language}</span>` },
            { k: 'Device', v: `<span class="tag ${ctx.device_type === 'smartphone' ? 'tag-green' : 'tag-amber'}">${ctx.device_type}</span>` },
            { k: 'Age', v: ctx.age }, { k: 'Gender', v: ctx.gender }, { k: 'Farm Size', v: ctx.farm_size_acres + ' acres' },
        ]);

        $('grower-context').innerHTML = kvList([
            { k: 'Crop', v: `<span class="tag tag-green">${ctx.crop}</span>` },
            { k: 'Current Stage', v: `<span class="tag tag-blue">${ctx.current_stage}</span>` },
            { k: 'Active Threat', v: `<span class="tag tag-red">${ctx.threat || 'None'}</span>` },
            { k: 'Recommended Channel', v: `<span class="tag tag-green">${ctx.recommended_channel}</span>` },
            { k: 'Product Scanned', v: ctx.product_scanned ? '✅ Yes' : '❌ No' },
            { k: 'Offline Campaign', v: ctx.offline_attended ? '✅ Attended' : '❌ Not attended' },
        ]);

        $('grower-products').innerHTML = '<div class="kv-list">' + (ctx.recommended_products || []).map(p =>
            `<div class="kv-item"><span class="kv-key">${p.product}</span><span class="kv-value">${p.in_stock ? '<span class="tag tag-green">In Stock (' + p.local_stock + ')</span>' : '<span class="tag tag-red">Out of Stock</span>'}</span></div>`
        ).join('') + '</div>';

        const wa = ctx.whatsapp_history || {};
        $('grower-engagement').innerHTML = kvList([
            { k: 'Messages Sent', v: wa.total_messages || 0 }, { k: 'Delivered', v: wa.delivered || 0 },
            { k: 'Opened', v: wa.opened || 0 }, { k: 'Clicked', v: wa.clicked || 0 },
        ]);
    } catch (e) { $('grower-profile-area').style.display = 'none'; console.error(e); }
});

// ─── Content Generation ───
$('content-generate-btn').addEventListener('click', async () => {
    const gid = $('content-grower-input').value.trim();
    const fmt_type = $('content-format').value;
    if (!gid) return;
    $('content-result-card').style.display = 'block';
    $('content-meta').innerHTML = '<div class="loading-spinner">Generating content…</div>';
    $('content-outputs').innerHTML = '';

    try {
        const result = await api(`/api/generate/${gid}?format=${fmt_type}`);
        $('content-meta').innerHTML = `<div class="content-meta-grid">
            <div class="content-meta-item"><span class="label">Grower</span><span class="value">${result.grower_id}</span></div>
            <div class="content-meta-item"><span class="label">Language</span><span class="value">${result.language}</span></div>
            <div class="content-meta-item"><span class="label">Channel</span><span class="value">${result.channel}</span></div>
            <div class="content-meta-item"><span class="label">Product</span><span class="value">${result.product_recommended}</span></div>
            <div class="content-meta-item"><span class="label">Method</span><span class="value">${result.generation_method}</span></div>
        </div>`;

        const content = result.content || {};
        let html = '';

        // Dynamic Weather Triggers & Orchestration
        let orchHtml = '<div style="display:grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">';
        orchHtml += `<div class="content-block"><div class="content-block-label">🌩️ Active Weather Triggers</div><div class="content-block-text" style="font-size:12px;">`;
        if (result.weather_triggers && result.weather_triggers.length > 0) {
            orchHtml += result.weather_triggers.map(t => `<span class="tag tag-red">${t.disease}</span> (Severity: ${t.severity})`).join('<br/>');
        } else {
            orchHtml += "None detected. Using default crop schedule.";
        }
        orchHtml += `</div></div>`;

        orchHtml += `<div class="content-block"><div class="content-block-label">⏱️ Delivery Orchestration</div><div class="content-block-text" style="font-size:12px;">`;
        if (result.delivery_plan) {
            orchHtml += `<b>Sequence:</b> ${result.delivery_plan.channel_sequence.join(' → ')}<br/>`;
            orchHtml += `<b>Send Window:</b> ${result.delivery_plan.send_window.start} - ${result.delivery_plan.send_window.end}<br/>`;
            orchHtml += `<b>Reason:</b> ${result.delivery_plan.routing_reason}`;
        }
        orchHtml += `</div></div></div>`;
        html += orchHtml;

        // Content Guardrails
        if (result.guardrail_check) {
            const passed = result.guardrail_check.passed;
            html += `<div class="content-block" style="border-left: 4px solid ${passed ? 'var(--accent-green)' : 'var(--accent-red)'}">`;
            html += `<div class="content-block-label">🛡️ Content Guardrails</div><div class="content-block-text" style="font-size:12px;">`;
            html += passed ? "✅ All checks passed. No forbidden claims detected." : "❌ WARNING: Guardrail violations detected!";
            if (result.guardrail_check.issues && result.guardrail_check.issues.length > 0) {
                html += "<ul>" + result.guardrail_check.issues.map(i => `<li>${i.message}</li>`).join('') + "</ul>";
            }
            html += `</div></div>`;
        }

        // Output Delivery Blocks
        if (content.whatsapp) html += `<div class="content-block"><div class="content-block-label">📱 WhatsApp Message</div><div class="content-block-text">${content.whatsapp}</div></div>`;
        if (content.sms) html += `<div class="content-block sms"><div class="content-block-label">💬 SMS</div><div class="content-block-text">${content.sms}</div></div>`;
        
        if (content.voice_script) {
            html += `<div class="content-block voice">
                <div class="content-block-label">🎙️ Voice Call Script</div>
                <div class="content-block-text">${content.voice_script}</div>`;
        
            if (content.voice_audio_base64) {
                html += `<div style="margin-top: 12px;">
                    <audio controls style="width: 100%; height: 35px; filter: invert(90%) sepia(20%) saturate(300%) hue-rotate(350deg);">
                        <source src="${content.voice_audio_base64}" type="audio/mp3">
                    </audio>
                  </div>`;
            }
            html += `</div>`;
        }

        // Visual & Video with dedicated generate buttons
        html += `<div class="content-block visual-block">
            <div class="content-block-label">🎨 Visual Concept Prompt (For Image AI)</div>
            <div style="margin-bottom:8px;">
                <button class="btn btn-primary gen-visual-btn"
                    data-crop="${result.crop||''}" data-stage="${result.stage||''}"
                    data-threat="${result.threat||''}" data-product="${result.product_recommended||''}"
                    data-state="${result.state||''}" data-language="${result.language||''}"
                    data-target="content-outputs" style="font-size:10px;padding:4px 10px;">GENERATE VISUAL</button>
            </div>
            <div class="visual-display content-block-text" style="font-family:monospace;font-size:11px;background:var(--bg-dark);padding:8px;">
                ${content.visual_prompt || 'Click GENERATE VISUAL to create a visual concept prompt.'}
            </div>
        </div>`;
        html += `<div class="content-block video-block">
            <div class="content-block-label">🎬 Video Storyboard (For Low-Literacy Segments)</div>
            <div style="margin-bottom:8px;">
                <button class="btn btn-primary gen-video-btn"
                    data-crop="${result.crop||''}" data-stage="${result.stage||''}"
                    data-threat="${result.threat||''}" data-product="${result.product_recommended||''}"
                    data-state="${result.state||''}" data-language="${result.language||''}"
                    data-grower-count="${result.reach||0}"
                    data-target="content-outputs" style="font-size:10px;padding:4px 10px;">GENERATE VIDEO</button>
            </div>
            <div class="video-display content-block-text" style="font-size:12px;">
                ${content.video_storyboard ? renderStoryboard(content.video_storyboard) : 'Click GENERATE VIDEO to create a video storyboard.'}
            </div>
        </div>`;

        // ─── Human-in-the-Loop (RLHF) Panel ───
        if (html !== '') {
            window.lastGeneratedPayload = content; 
            
            html += `
            <div class="content-block" style="border: 1px dashed var(--border-color); margin-top: 25px; padding: 15px; background: rgba(0,0,0,0.2);">
                <div class="content-block-label">👨‍⚖️ Human-in-the-Loop Evaluation (RLHF)</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 10px;">Evaluate this AI generation for safety and tone before network dispatch.</div>
                <div style="display: flex; gap: 10px;">
                    <button onclick="submitRLHF('${result.grower_id}', '${result.generation_method}', 'thumbs_up')" style="background: var(--toxic-green); color: black; border: none; padding: 8px 16px; cursor: pointer; font-weight: bold; border-radius: 2px;">👍 APPROVED</button>
                    <button onclick="submitRLHF('${result.grower_id}', '${result.generation_method}', 'thumbs_down')" style="background: #ef4444; color: white; border: none; padding: 8px 16px; cursor: pointer; font-weight: bold; border-radius: 2px;">👎 FEEDBACK</button>
                </div>
                <div id="rlhf-status" style="margin-top: 10px; font-size: 12px; font-weight: bold;"></div>
            </div>`;
        }

        $('content-outputs').innerHTML = html || '<p>No content generated</p>';
    } catch (e) { $('content-meta').innerHTML = '<p style="color:var(--accent-red)">Error: ' + e.message + '</p>'; }
});

// ─── Inline Segment Content Generation (Target Clusters) ───
$('seg-gen-btn').addEventListener('click', async () => {
    const segId = $('seg-gen-panel').dataset.segId;
    const fmt = $('seg-gen-format').value;
    const groupBy = $('seg-gen-panel').dataset.groupBy || '';
    if (!segId) return;

    $('seg-gen-meta').innerHTML = '<div class="loading-spinner">Generating segment content…</div>';
    $('seg-gen-outputs').innerHTML = '';

    try {
        const url = `/api/segments/${segId}/generate?format=${fmt}${groupBy ? '&group_by=' + encodeURIComponent(groupBy) : ''}`;
        const result = await api(url);
        const seg = result.segment_details || {};

        $('seg-gen-meta').innerHTML = `<div class="content-meta-grid">
            <div class="content-meta-item"><span class="label">Crop/Stage</span><span class="value">${seg.crop} / ${seg.stage}</span></div>
            <div class="content-meta-item"><span class="label">Region</span><span class="value">${seg.state}</span></div>
            <div class="content-meta-item"><span class="label">Language</span><span class="value">${result.language}</span></div>
            <div class="content-meta-item"><span class="label">Channel</span><span class="value">${result.channel}</span></div>
            <div class="content-meta-item"><span class="label">Product</span><span class="value">${result.product_recommended}</span></div>
            <div class="content-meta-item"><span class="label">Reach</span><span class="value" style="color:var(--toxic-green);font-weight:700">${result.reach} growers</span></div>
            <div class="content-meta-item"><span class="label">Method</span><span class="value">${result.generation_method}</span></div>
        </div>`;

        const content = result.content || {};
        let html = '';

        // Weather triggers & delivery plan
        let orchHtml = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">';
        orchHtml += `<div class="content-block"><div class="content-block-label">🌩️ Weather Triggers</div><div class="content-block-text" style="font-size:12px;">`;
        if (result.weather_triggers && result.weather_triggers.length > 0) {
            orchHtml += result.weather_triggers.map(t => `<span class="tag tag-red">${t.disease}</span> (Severity: ${t.severity})`).join('<br/>');
        } else {
            orchHtml += "None detected.";
        }
        orchHtml += `</div></div>`;
        orchHtml += `<div class="content-block"><div class="content-block-label">⏱️ Delivery Plan</div><div class="content-block-text" style="font-size:12px;">`;
        if (result.delivery_plan) {
            orchHtml += `<b>Strategy:</b> ${result.delivery_plan.bulk_delivery?.strategy || '—'}<br/>`;
            orchHtml += `<b>ETA:</b> ${result.delivery_plan.bulk_delivery?.estimated_delivery_time || '—'}<br/>`;
            orchHtml += `<b>Sequence:</b> ${(result.delivery_plan.channel_sequence || []).join(' → ')}<br/>`;
            orchHtml += `<b>Send Window:</b> ${result.delivery_plan.send_window?.start || '—'} – ${result.delivery_plan.send_window?.end || '—'}`;
        }
        orchHtml += `</div></div></div>`;
        html += orchHtml;

        // Guardrails
        if (result.guardrail_check) {
            const passed = result.guardrail_check.passed;
            html += `<div class="content-block" style="border-left:4px solid ${passed ? 'var(--accent-green)' : 'var(--accent-red)'}">`;
            html += `<div class="content-block-label">🛡️ Content Guardrails</div><div class="content-block-text" style="font-size:12px;">`;
            html += passed ? "✅ All checks passed." : "❌ WARNING: Guardrail violations!";
            if (result.guardrail_check.issues && result.guardrail_check.issues.length > 0) {
                html += "<ul>" + result.guardrail_check.issues.map(i => `<li>${i.message}</li>`).join('') + "</ul>";
            }
            html += `</div></div>`;
        }

        // Messages
        if (content.whatsapp) html += `<div class="content-block"><div class="content-block-label">📱 WhatsApp (Segment)</div><div class="content-block-text">${content.whatsapp}</div></div>`;
        if (content.sms) html += `<div class="content-block sms"><div class="content-block-label">💬 SMS (Segment)</div><div class="content-block-text">${content.sms}</div></div>`;
        if (content.voice_script) {
            html += `<div class="content-block voice"><div class="content-block-label">🎙️ Voice Script (Segment)</div><div class="content-block-text">${content.voice_script}</div>`;
            if (content.voice_audio_base64) {
                html += `<div style="margin-top:12px;"><audio controls style="width:100%;height:35px;filter:invert(90%)"><source src="${content.voice_audio_base64}" type="audio/mp3"></audio></div>`;
            }
            html += `</div>`;
        }

        // Visual & Video with dedicated generate buttons
        html += `<div class="content-block visual-block">
            <div class="content-block-label">🎨 Visual Prompt</div>
            <div style="margin-bottom:8px;">
                <button class="btn btn-primary gen-visual-btn"
                    data-crop="${result.crop||''}" data-stage="${result.stage||''}"
                    data-threat="${result.threat||''}" data-product="${result.product_recommended||''}"
                    data-state="${result.state||''}" data-language="${result.language||''}"
                    data-target="seg-gen-outputs" style="font-size:10px;padding:4px 10px;">GENERATE VISUAL</button>
            </div>
            <div class="visual-display content-block-text" style="font-family:monospace;font-size:11px;background:var(--bg-dark);padding:8px;">
                ${content.visual_prompt || 'Click GENERATE VISUAL to create a visual concept prompt.'}
            </div>
        </div>`;
        html += `<div class="content-block video-block">
            <div class="content-block-label">🎬 Video Storyboard</div>
            <div style="margin-bottom:8px;">
                <button class="btn btn-primary gen-video-btn"
                    data-crop="${result.crop||''}" data-stage="${result.stage||''}"
                    data-threat="${result.threat||''}" data-product="${result.product_recommended||''}"
                    data-state="${result.state||''}" data-language="${result.language||''}"
                    data-grower-count="${result.reach||0}"
                    data-target="seg-gen-outputs" style="font-size:10px;padding:4px 10px;">GENERATE VIDEO</button>
            </div>
            <div class="video-display content-block-text" style="font-size:12px;">
                ${content.video_storyboard ? renderStoryboard(content.video_storyboard) : 'Click GENERATE VIDEO to create a video storyboard.'}
            </div>
        </div>`;
        // RLHF
        if (html !== '') {
            window.lastSegmentPayload = content;
            html += `
            <div class="content-block" style="border:1px dashed var(--border-color);margin-top:25px;padding:15px;background:rgba(0,0,0,0.2);">
                <div class="content-block-label">👨‍⚖️ Human-in-the-Loop Evaluation (RLHF)</div>
                <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px;">Evaluate this AI generation for safety and tone before network dispatch.</div>
                <div style="display:flex;gap:10px;">
                    <button onclick="submitRLHF('${segId}', '${result.generation_method}', 'thumbs_up')" style="background:var(--toxic-green);color:black;border:none;padding:8px 16px;cursor:pointer;font-weight:bold;border-radius:2px;">👍 APPROVED</button>
                    <button onclick="submitRLHF('${segId}', '${result.generation_method}', 'thumbs_down')" style="background:#ef4444;color:white;border:none;padding:8px 16px;cursor:pointer;font-weight:bold;border-radius:2px;">👎 FEEDBACK</button>
                </div>
                <div id="rlhf-status-seg" style="margin-top:10px;font-size:12px;font-weight:bold;"></div>
            </div>`;
        }

        $('seg-gen-outputs').innerHTML = html || '<p>No content generated</p>';
    } catch (e) {
        $('seg-gen-meta').innerHTML = '<p style="color:var(--accent-red)">Error: ' + e.message + '</p>';
    }
});

// Close segment gen panel
$('seg-gen-close').addEventListener('click', () => {
    $('seg-gen-panel').style.display = 'none';
    document.querySelectorAll('#segments-tbody tr').forEach(r => r.classList.remove('row-selected'));
});

// ─── Visual / Video Generation Buttons (delegated) ───
document.addEventListener('click', async e => {
    const btn = e.target.closest('.gen-visual-btn, .gen-video-btn');
    if (!btn) return;
    e.preventDefault();
    const isVideo = btn.classList.contains('gen-video-btn');
    const block = btn.closest('.visual-block, .video-block');
    const display = block.querySelector(isVideo ? '.video-display' : '.visual-display');
    display.innerHTML = '<div class="loading-spinner" style="padding:4px 0;">Generating…</div>';

    const params = new URLSearchParams({
        crop: btn.dataset.crop || '', stage: btn.dataset.stage || '',
        threat: btn.dataset.threat || '', product: btn.dataset.product || '',
        state: btn.dataset.state || '', language: btn.dataset.language || '',
    });
    if (isVideo) params.set('grower_count', btn.dataset.growerCount || '0');

    try {
        const type = isVideo ? 'video' : 'visual';
        const res = await api(`/api/generate/${type}?${params}`);
        if (isVideo) {
            display.innerHTML = res.video_storyboard ? renderStoryboard(res.video_storyboard) : 'No storyboard generated.';
        } else {
            display.innerHTML = res.visual_prompt || 'No visual prompt generated.';
        }
    } catch (err) {
        display.innerHTML = `<span style="color:var(--accent-red)">Error: ${err.message}</span>`;
    }
});

// ─── Analytics ───
document.querySelector('[data-tab="analytics"]').addEventListener('click', loadAnalytics);
async function loadAnalytics() {
    try {
        // Fetch all analytics data in parallel
        const [wa, conv, df, pos, inv, fa, rev] = await Promise.all([
            api('/api/analytics/whatsapp'),
            api('/api/analytics/conversion'),
            api('/api/analytics/digital-funnel'),
            api('/api/analytics/pos-trends'),
            api('/api/analytics/inventory'),
            api('/api/analytics/field-activity'),
            api('/api/analytics/revenue-impact'),
        ]);

        // Campaign revenue impact (rendered below, after field activity)
        window._revenueImpactData = rev;

        // Campaign KPI row
        $('campaign-metrics').innerHTML =
            metricCard('Total Messages', fmt(wa.total_messages), 'All campaigns', 'green') +
            metricCard('Delivery Rate', pct(wa.delivery_rate), 'Of sent messages', 'blue') +
            metricCard('Open Rate', pct(wa.open_rate), 'Of delivered', 'amber') +
            metricCard('Click Rate', pct(wa.click_rate), 'Of opened', 'purple') +
            metricCard('Campaign→Action', pct(conv.campaign_to_action_rate), 'Click → product scan', 'green') +
            metricCard('Click→Scan', pct(conv.click_to_scan_rate), 'Of clicked users', 'teal');

        // WhatsApp funnel (keep)
        const maxWa = wa.total_messages || 1;
        $('wa-funnel').innerHTML = `<div class="funnel-chart">
            <div class="funnel-step"><div class="funnel-label">Sent</div><div class="funnel-bar" style="width:100%;background:linear-gradient(90deg,#6366f1,#818cf8)">${fmt(wa.total_messages)}</div><div class="funnel-rate">100%</div></div>
            <div class="funnel-step"><div class="funnel-label">Delivered</div><div class="funnel-bar" style="width:${wa.delivery_rate * 100}%;background:linear-gradient(90deg,#3b82f6,#60a5fa)">${fmt(wa.delivered)}</div><div class="funnel-rate">${pct(wa.delivery_rate)}</div></div>
            <div class="funnel-step"><div class="funnel-label">Opened</div><div class="funnel-bar" style="width:${(wa.opened / maxWa) * 100}%;background:linear-gradient(90deg,#f59e0b,#fbbf24)">${fmt(wa.opened)}</div><div class="funnel-rate">${pct(wa.open_rate)}</div></div>
            <div class="funnel-step"><div class="funnel-label">Clicked</div><div class="funnel-bar" style="width:${(wa.clicked / maxWa) * 100}%;background:linear-gradient(90deg,#22c55e,#4ade80)">${fmt(wa.clicked)}</div><div class="funnel-rate">${pct(wa.click_rate)}</div></div>
        </div>`;

        // Conversion by crop — bar chart sorted by CTA rate
        const byCrop = Object.entries(conv.by_crop).sort((a, b) => b[1].campaign_to_action_rate - a[1].campaign_to_action_rate);
        const maxCta = byCrop.length > 0 ? byCrop[0][1].campaign_to_action_rate * 100 : 100;
        const ctaExplanation = '<p style="font-size:10px;color:var(--text-dim);margin-bottom:16px;text-transform:none;letter-spacing:0">Growers who clicked a campaign message AND scanned the promoted product within 14 days — by crop.</p>';
        $('conversion-by-crop').innerHTML = byCrop.length ? ctaExplanation + barChart(byCrop.map(([crop, d]) => ({
            label: crop,
            value: d.campaign_to_action_rate * 100,
            display: pct(d.campaign_to_action_rate)
        })), maxCta, ['green', 'blue', 'amber', 'purple', 'teal']) : '<p style="color:var(--text-dim)">No conversion data</p>';

        // POS sales trend — weekly revenue bars
        const posData = (pos.weekly_data || []).map(w => ({
            label: w.week.slice(5),
            value: w.total_revenue,
            display: '\u20B9' + fmt(w.total_revenue)
        }));
        const maxPos = posData.length ? Math.max(...posData.map(d => d.value), 1) : 1;
        $('pos-trend').innerHTML = posData.length ? barChart(posData, maxPos, ['green']) : '<p style="color:var(--text-dim)">No POS data</p>';

        // Digital campaigns (keep as is)
        const campaignEntries = Object.entries(df.campaigns || {});
        $('digital-campaigns').innerHTML = campaignEntries.length ? '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px">' +
            campaignEntries.map(([id, c]) => `<div style="background:var(--bg-panel);padding:20px;border:1px solid var(--grid-line)">
                <div style="font-weight:700;margin-bottom:8px;font-size:12px">${c.campaign_crop} — ${c.campaign_product}</div>
                ${kvList([
                { k: 'Impressions', v: fmt(c.total_impressions) },
                { k: 'Visits', v: fmt(c.total_visits) + ' (' + pct(c.impression_to_visit_rate) + ')' },
                { k: 'Leads', v: fmt(c.total_leads) + ' (' + pct(c.visit_to_lead_rate) + ')' },
            ])}
            </div>`).join('') + '</div>' : '<p style="color:var(--text-dim)">No digital campaign data</p>';

        // Inventory health — OOS rates by SKU
        const skus = Object.entries(inv.by_sku || {}).sort((a, b) => b[1].out_of_stock_rate - a[1].out_of_stock_rate);
        const invExplanation = '<p style="font-size:10px;color:var(--text-dim);margin-bottom:8px;text-transform:none;letter-spacing:0">Percentage of retailers with zero stock of each product. Higher = supply gap.</p>';
        $('inventory-health').innerHTML = '<p style="font-size:11px;color:var(--text-muted);margin-bottom:12px">Snapshot: ' + inv.snapshot_week + '</p>' +
            (skus.length ? invExplanation + barChart(skus.map(([name, d]) => ({ label: name, value: d.out_of_stock_rate * 100, display: pct(d.out_of_stock_rate) + ' OOS' })), 100, ['red', 'amber', 'amber', 'amber', 'green', 'green']) : '<p style="color:var(--text-dim)">No inventory data</p>');

        // Field activity — total + visit type summary + monthly trend bars
        const faTypes = Object.entries(fa.by_type || {});
        const faExplanation = '<p style="font-size:10px;color:var(--text-dim);margin-bottom:8px;text-transform:none;letter-spacing:0">Monthly field visit count by sales representatives. Tracks ground-level engagement.</p>';
        $('field-activity').innerHTML =
            kvList([
                { k: 'Total Visits', v: fmt(fa.total_visits) },
                ...faTypes.map(([k, v]) => ({ k: k, v: fmt(v) })),
            ]) +
            '<div style="margin-top:20px"><h4 style="font-size:11px;color:var(--text-dim);margin-bottom:12px">MONTHLY TREND</h4>' +
            faExplanation +
            barChart((fa.monthly_trend || []).map(m => ({
                label: m.month.slice(5),
                value: m.visits,
                display: m.visits
            })), Math.max(...(fa.monthly_trend || []).map(m => m.visits), 1), ['blue']) +
            '</div>';

        // Campaign revenue impact
        const revProducts = Object.entries(rev.by_product || {});
        let revHtml = '<div style="margin-bottom:20px">' + metricCard('Total Attributed Revenue', '\u20B9' + fmt(rev.total_attributed_revenue), '28-day attribution window', 'green') + '</div>';
        if (revProducts.length) {
            revHtml += revProducts.map(([name, p]) => {
                const stateEntries = Object.entries(p.states || {});
                const stateRows = stateEntries.map(([st, d]) =>
                    `<div class="kv-item"><span class="kv-key">${st}</span><span class="kv-value">${d.campaign_messages} msgs, pre \u20B9${fmt(d.pre_avg_weekly_revenue)} → post \u20B9${fmt(d.post_avg_weekly_revenue)}/wk (${d.uplift_pct > 0 ? '+' : ''}${(d.uplift_pct * 100).toFixed(1)}%)</span></div>`
                ).join('');
                const totalUplift = p.total_attributed > 0 ? '+' : '';
                return `<div style="background:var(--bg-panel);padding:20px;border:1px solid var(--grid-line);margin-bottom:16px">
                    <div style="font-weight:700;margin-bottom:8px;font-size:13px;color:var(--toxic-green)">${name} <span style="color:var(--text-chalk);font-weight:400;font-size:11px">— attributed \u20B9${fmt(p.total_attributed)}</span></div>
                    <div class="kv-list">${stateRows}</div>
                </div>`;
            }).join('');
        } else {
            revHtml += '<p style="color:var(--text-dim)">No revenue impact data (no matching POS transactions found)</p>';
        }
        $('revenue-impact').innerHTML = revHtml;

    } catch (e) { console.error('Analytics load error:', e); }
}

// ─── ML Model ───
document.querySelector('[data-tab="model"]').addEventListener('click', loadModel);
async function loadModel() {
    try {
        const info = await api('/api/model/info');
        const oi = info.open_feature_importance || {};
        const maxFI = Math.max(...Object.values(oi), 0.01);

        // Clean label mapper to turn ugly database keys into professional titles
        const featureLabels = {
    "cohort_open_propensity": "Lookalike Cluster Open Rate",
    "cohort_click_propensity": "Lookalike Cluster Click Rate",
    "predicted_open_prob": "Engineered Open Propensity Signal",
    "age_farm_ratio": "Resource Allocation Density Index",
    "days_since_sowing": "Days Since Crop Sowing",
    "grower_farm_size": "Farm Size (Acres)",
    "grower_age": "Grower Age",
    "offline_attended": "Field Day Attendance",
    "has_scanned": "Past QR Product Scans",
    "language_enc": "Regional Language Profile",
    "product_enc": "Target Chemical Profile",
    "msg_month": "Seasonal Month Signal",
    "msg_day_of_week": "Day of Week Signal",
    "gender_enc": "Demographic Gender Profile"
};

        $('model-info').innerHTML = `
            <div class="model-metrics">
                <div class="model-metric"><div class="value green">${info.open_model_auc_cv5}</div><div class="label">Open Model AUC (5-fold CV)</div></div>
                <div class="model-metric"><div class="value blue">${info.click_model_auc_cv5}</div><div class="label">Click Model AUC (5-fold CV)</div></div>
                <div class="model-metric"><div class="value amber">${fmt(info.training_samples)}</div><div class="label">Training Samples</div></div>
                <div class="model-metric"><div class="value purple">${pct(info.open_rate_actual)}</div><div class="label">Actual Open Rate</div></div>
            </div>
            <h3>Feature Importance (Open Model)</h3>
            <div class="feature-importance">${Object.entries(oi).sort((a, b) => b[1] - a[1]).map(([k, v]) => {
                const cleanName = featureLabels[k] || k; // Fallback to key if label missing
                return `<div class="fi-row"><div class="fi-name">${cleanName}</div><div class="fi-bar-track"><div class="fi-bar-fill" style="width:${(v / maxFI) * 100}%"></div></div><div class="fi-value">${v.toFixed(3)}</div></div>`;
            }).join('')}</div>`;
        loadPrioritization();
    } catch (e) { $('model-info').innerHTML = '<p style="color:var(--accent-red)">Error loading model: ' + e.message + '</p>'; }
}

async function loadPrioritization() {
    try {
        const data = await api('/api/model/grower-prioritization?limit=100');
        const growers = data.ranked_growers || [];
        const dist = data.distribution || {};
        if (!growers.length) {
            $('grower-priority').innerHTML = '<p style="color:var(--text-dim)">No prioritization data.</p>';
            return;
        }

        // Distribution summary
        const highCount = growers.filter(g => g.engagement_score > (dist.p75 || 0.5)).length;
        const lowCount = growers.filter(g => g.engagement_score < (dist.p25 || 0.1)).length;

        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px">
            <div class="model-metric"><div class="value green">${(dist.max * 100).toFixed(1)}%</div><div class="label">Top Engagement</div></div>
            <div class="model-metric"><div class="value amber">${(dist.mean * 100).toFixed(1)}%</div><div class="label">Avg Engagement (${fmt(data.total_growers)} growers)</div></div>
            <div class="model-metric"><div class="value blue">${(dist.median * 100).toFixed(1)}%</div><div class="label">Median Engagement</div></div>
            <div class="model-metric"><div class="value purple">${fmt(highCount)} high · ${fmt(lowCount)} low</div><div class="label">Top/Bottom Quartile</div></div>
        </div>`;

        // Top 20 growers table
        html += '<h4 style="font-size:11px;color:var(--toxic-green);margin-bottom:12px">▲ TOP 100 GROWERS BY PREDICTED ENGAGEMENT</h4>';
        html += '<div style="max-height:320px;overflow-y:auto;border:1px solid var(--grid-line)">';
        html += '<table class="data-table" style="width:100%;font-size:10px"><thead><tr>' +
            '<th>RANK</th><th>GROWER</th><th>CROP</th><th>STATE</th><th>DEVICE</th><th>OPEN</th><th>CLICK</th><th>SCORE</th>' +
            '</tr></thead><tbody>';
        growers.forEach(g => {
            const tier = g.engagement_score > dist.p75 ? 'green' : g.engagement_score > dist.median ? 'amber' : 'red';
            html += `<tr>
                <td style="color:var(--text-dim)">#${g.rank}</td>
                <td style="color:var(--text-chalk);font-weight:600">${g.grower_id}</td>
                <td>${g.crop}</td>
                <td>${g.state}</td>
                <td>${g.device_type === 'smartphone' ? '📱' : '📟'} ${g.device_type}</td>
                <td style="color:var(--toxic-green)">${(g.open_probability * 100).toFixed(1)}%</td>
                <td style="color:var(--sky-blue)">${(g.click_probability * 100).toFixed(1)}%</td>
                <td style="color:var(--${tier});font-weight:700">${(g.engagement_score * 100).toFixed(1)}%</td>
            </tr>`;
        });
        html += '</tbody></table></div>';

        // Actionable insight
        const top5 = growers.slice(0, 5);
        const bottom5 = growers.slice(-5);
        html += `<div style="margin-top:16px;padding:12px;background:rgba(0,255,65,0.04);border:1px solid rgba(0,255,65,0.15);font-size:11px">
            <span style="color:var(--toxic-green);font-weight:700">● INSIGHT:</span>
            <span style="color:var(--text-dim)"> Top 5 growers avg ${(top5.reduce((s, g) => s + g.engagement_score, 0) / 5 * 100).toFixed(1)}% engagement. Prioritize smartphone users in high-scoring state×crop combos. Bottom 5 avg ${(bottom5.reduce((s, g) => s + g.engagement_score, 0) / 5 * 100).toFixed(1)}% — skip or use SMS-only fallback.</span>
        </div>`;

        $('grower-priority').innerHTML = html;
    } catch (e) {
        $('grower-priority').innerHTML = '<p style="color:#ef4444">Error: ' + e.message + '</p>';
    }
}

$('model-predict-btn').addEventListener('click', async () => {
    const gid = $('model-grower-input').value.trim();
    if (!gid) return;
    try {
        const pred = await api(`/api/grower/${gid}/receptivity`);
        const tierColor = pred.engagement_tier === 'high' ? 'green' : pred.engagement_tier === 'medium' ? 'amber' : 'red';
        $('model-prediction').innerHTML = `<div class="prediction-result">
            <div class="pred-gauge"><div class="gauge-value green">${(pred.open_probability * 100).toFixed(1)}%</div><div class="gauge-label">Open Probability</div></div>
            <div class="pred-gauge"><div class="gauge-value blue">${(pred.click_probability * 100).toFixed(1)}%</div><div class="gauge-label">Click Probability</div></div>
            <div class="pred-gauge"><div class="gauge-value ${tierColor}">${pred.engagement_tier.toUpperCase()}</div><div class="gauge-label">Engagement Tier</div><div class="gauge-tier"><span class="tag tag-${tierColor}">${pred.engagement_tier}</span></div></div>
        </div>`;
    } catch (e) { $('model-prediction').innerHTML = '<p style="color:var(--accent-red)">' + e.message + '</p>'; }
});

// ─── RLHF Submission Handler (works for grower & segment panels) ───
async function submitRLHF(targetId, campaignId, status) {
    const statusDiv = document.getElementById('rlhf-status-seg') || document.getElementById('rlhf-status');
    if (!statusDiv) return;
    statusDiv.style.color = 'var(--text-muted)';
    statusDiv.innerText = "Submitting feedback to model logs...";

    let reason = "";
    if (status === 'thumbs_down') {
        reason = prompt("Why are you rejecting this? (e.g., Tone, Hallucination, Bad translation)");
        if (reason === null) { statusDiv.innerText = ""; return; }
    }

    try {
        const response = await fetch('/api/rlhf/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                grower_id: targetId,
                campaign_id: campaignId,
                status: status,
                failure_reason: reason,
                payload_snapshot: window.lastSegmentPayload || window.lastGeneratedPayload || {}
            })
        });

        if (response.ok) {
            statusDiv.style.color = status === 'thumbs_up' ? 'var(--toxic-green)' : '#ef4444';
            statusDiv.innerText = "✅ Feedback written to RLHF logs.";
        } else {
            statusDiv.style.color = '#ef4444';
            statusDiv.innerText = "❌ Failed to log feedback.";
        }
    } catch (e) {
        statusDiv.style.color = '#ef4444';
        statusDiv.innerText = "❌ Error: " + e.message;
    }
}

// ─── Collapsible Cards ───
document.querySelectorAll('.card h3').forEach(h3 => {
    h3.style.position = 'relative';
    h3.style.paddingRight = '36px';
    const indicator = document.createElement('span');
    indicator.className = 'coll-toggle';
    indicator.textContent = '[−]';
    indicator.style.cssText = 'position:absolute;right:0;top:50%;transform:translateY(-50%);font-family:var(--font-data);font-size:11px;color:var(--text-dim);font-weight:400;letter-spacing:0;pointer-events:none;';
    h3.appendChild(indicator);
    h3.style.cursor = 'pointer';
    h3.style.userSelect = 'none';
});
document.addEventListener('click', e => {
    const card = e.target.closest('.card');
    if (!card) return;
    const h3 = card.querySelector('h3');
    if (!h3 || !h3.contains(e.target)) return;
    card.classList.toggle('collapsed');
    const ind = h3.querySelector('.coll-toggle');
    if (ind) ind.textContent = card.classList.contains('collapsed') ? '[+]' : '[−]';
});

// ─── Init ───
boot();