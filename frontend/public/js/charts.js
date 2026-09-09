/* ═══════════════════════════════════════════════════════════
   SANKET // RISKSYS  —  SVG Chart Rendering
   ═══════════════════════════════════════════════════════════ */

const Charts = (() => {
  /* ── Sparkline (mini trend line) ────────────────────── */
  function renderSparkline(containerId, data, color = '#10b981') {
    const el = document.getElementById(containerId);
    if (!el) return;
    const w = el.clientWidth || 240;
    const h = 28;
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;

    const points = data.map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      return `${x},${y}`;
    });

    const areaPoints = `0,${h} ${points.join(' ')} ${w},${h}`;

    el.innerHTML = `
      <svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
        <defs>
          <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${color}" stop-opacity=".18"/>
            <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <polygon points="${areaPoints}" fill="url(#sparkGrad)"/>
        <polyline points="${points.join(' ')}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
  }

  /* ── Trajectory Divergence Line Chart ───────────────── */
  function renderTrajectoryChart(containerId, labelsContainerId, chartData) {
    const el = document.getElementById(containerId);
    const labelsEl = document.getElementById(labelsContainerId);
    if (!el) return;

    const w = el.clientWidth || 500;
    const h = 180;
    const padL = 32;
    const padR = 16;
    const padT = 20;
    const padB = 12;
    const chartW = w - padL - padR;
    const chartH = h - padT - padB;

    const { labels, target, contractorReport, sanketTelemetry, anomalyPoint, discrepancyGap } = chartData;
    const n = target.length;

    const maxVal = Math.max(100, ...target, ...contractorReport, ...sanketTelemetry);
    const yMax = Math.ceil(maxVal / 25) * 25;

    function xPos(i) { return padL + (n > 1 ? (i / (n - 1)) * chartW : chartW / 2); }
    function yPos(v) { return padT + chartH - (v / yMax) * chartH; }

    function polyline(data, color, dash = false) {
      const pts = data.map((v, i) => `${xPos(i)},${yPos(v)}`).join(' ');
      return `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"
        ${dash ? 'stroke-dasharray="6 4"' : ''}/>`;
    }

    // Grid lines
    let gridLines = '';
    for (let pct = 0; pct <= yMax; pct += Math.max(25, Math.ceil(yMax / 4 / 25) * 25)) {
      const y = yPos(pct);
      gridLines += `<line x1="${padL}" y1="${y}" x2="${w - padR}" y2="${y}" stroke="#e5e7eb" stroke-width=".7"/>`;
      gridLines += `<text x="${padL - 4}" y="${y + 3}" fill="#9ca3af" font-size="8" text-anchor="end" font-family="'JetBrains Mono', monospace">${pct}%</text>`;
    }

    // Shaded area between contractor and sanket (discrepancy zone)
    let areaPath = `M ${xPos(0)},${yPos(contractorReport[0])}`;
    for (let i = 1; i < n; i++) areaPath += ` L ${xPos(i)},${yPos(contractorReport[i])}`;
    for (let i = n - 1; i >= 0; i--) areaPath += ` L ${xPos(i)},${yPos(sanketTelemetry[i])}`;
    areaPath += ' Z';

    let annotations = '';

    if (anomalyPoint) {
      const aIdx = anomalyPoint.index;
      const anomalyX = xPos(aIdx);
      const anomalyY = yPos(sanketTelemetry[aIdx]);
      const anomalyLines = anomalyPoint.label.split('\\n');
      annotations += `
        <!-- Anomaly marker -->
        <line x1="${anomalyX}" y1="${anomalyY - 20}" x2="${anomalyX}" y2="${anomalyY}" stroke="#ef4444" stroke-width="1" stroke-dasharray="3 2"/>
        <rect x="${anomalyX - 80}" y="${anomalyY - 52}" width="160" height="30" rx="4" fill="#0c1f37" opacity=".92"/>
        <text x="${anomalyX}" y="${anomalyY - 38}" fill="#f87171" font-size="7.5" text-anchor="middle" font-weight="700" font-family="'JetBrains Mono', monospace">${anomalyLines[0]}</text>
        <text x="${anomalyX}" y="${anomalyY - 27}" fill="#94a3b8" font-size="7" text-anchor="middle" font-family="'JetBrains Mono', monospace">${anomalyLines[1] || ''}</text>
      `;
    }

    if (discrepancyGap) {
      const dIdx = discrepancyGap.index;
      const gapTopY = yPos(contractorReport[dIdx]);
      const gapBotY = yPos(sanketTelemetry[dIdx]);
      const gapX = xPos(dIdx);
      annotations += `
        <!-- Discrepancy gap line -->
        <line x1="${gapX + 8}" y1="${gapTopY}" x2="${gapX + 8}" y2="${gapBotY}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4 2"/>
        <rect x="${gapX + 14}" y="${(gapTopY + gapBotY) / 2 - 10}" width="120" height="18" rx="3" fill="rgba(239,68,68,.12)" stroke="#ef4444" stroke-width=".7"/>
        <text x="${gapX + 74}" y="${(gapTopY + gapBotY) / 2 + 2}" fill="#ef4444" font-size="8" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono', monospace">${discrepancyGap.label}</text>
      `;
    }

    const svg = `
      <svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="overflow:visible">
        <!-- Grid -->
        ${gridLines}

        <!-- Discrepancy shaded area -->
        <path d="${areaPath}" fill="rgba(239,68,68,.07)"/>

        <!-- Lines -->
        ${polyline(target, '#d4d4d8', true)}
        ${polyline(contractorReport, '#a1a1aa', true)}
        ${polyline(sanketTelemetry, '#000000')}

        <!-- Data dots (sanket line) -->
        ${sanketTelemetry.map((v, i) => `
          <circle cx="${xPos(i)}" cy="${yPos(v)}" r="3" fill="#000000" stroke="#fff" stroke-width="1.5"/>
          <circle cx="${xPos(i)}" cy="${yPos(v)}" r="14" fill="transparent" class="hover-target" style="cursor:crosshair;"
            data-month="${labels[i]}" 
            data-target="${(target[i] || 0).toFixed(1)}" 
            data-contractor="${(contractorReport[i] || 0).toFixed(1)}" 
            data-sanket="${(v || 0).toFixed(1)}" />
        `).join('')}

        ${annotations}
      </svg>`;

    el.innerHTML = svg;

    const tooltip = document.getElementById('chartTooltip');
    if (tooltip) {
      el.querySelectorAll('.hover-target').forEach(targetEl => {
        targetEl.addEventListener('mouseenter', (e) => {
          tooltip.style.display = 'block';
          tooltip.innerHTML = `
            <div style="font-weight:bold; margin-bottom:6px; color:#f8fafc;">${e.target.dataset.month}</div>
            <div style="color:#a1a1aa;">Target: <span style="float:right;margin-left:12px">${e.target.dataset.target}%</span></div>
            <div style="color:#d4d4d8;">Reported: <span style="float:right;margin-left:12px">${e.target.dataset.contractor}%</span></div>
            <div style="color:#ffffff; font-weight:bold;">Sanket: <span style="float:right;margin-left:12px">${e.target.dataset.sanket}%</span></div>
          `;
        });
        targetEl.addEventListener('mousemove', (e) => {
          tooltip.style.left = (e.pageX + 15) + 'px';
          tooltip.style.top = (e.pageY - 15) + 'px';
        });
        targetEl.addEventListener('mouseleave', () => {
          tooltip.style.display = 'none';
        });
      });
    }

    // X-axis labels
    if (labelsEl) {
      labelsEl.innerHTML = labels.map(l =>
        `<span>${l}</span>`
      ).join('');
    }
  }

  return { renderSparkline, renderTrajectoryChart };
})();
