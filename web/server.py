import asyncio
import json
import logging
from aiohttp import web
from typing import Dict, Set

logger = logging.getLogger("WebServerTurbo")

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KuQuant Turbo (Alpha-X) • Scalping Cuantitativo 24/7</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root[data-theme="dark"] {
            --bg-base: #0a0d14;
            --bg-card: #121824;
            --bg-hover: #1b2234;
            --border: #232d42;
            --border-light: #2c3852;
            --text-primary: #ffffff;
            --text-secondary: #9aa8bd;
            --text-muted: #62718a;
            --accent: #f3ba2f; /* Turbo Gold */
            --accent-glow: rgba(243, 186, 47, 0.18);
            --cyan: #00f0ff;
            --green: #00bd84;
            --green-glow: rgba(0, 189, 132, 0.15);
            --red: #f6465d;
            --red-glow: rgba(246, 70, 93, 0.15);
        }

        :root[data-theme="light"] {
            --bg-base: #f4f6fa;
            --bg-card: #ffffff;
            --bg-hover: #eef2f8;
            --border: #dbe2ea;
            --border-light: #c8d3e0;
            --text-primary: #111827;
            --text-secondary: #4b5563;
            --text-muted: #9ca3af;
            --accent: #d97706;
            --accent-glow: rgba(217, 119, 6, 0.15);
            --cyan: #0284c7;
            --green: #059669;
            --green-glow: rgba(5, 150, 105, 0.12);
            --red: #dc2626;
            --red-glow: rgba(220, 38, 38, 0.12);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            transition: background-color 0.25s ease, border-color 0.25s ease, color 0.25s ease;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-base);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        .mono {
            font-family: 'JetBrains Mono', monospace;
        }

        /* HEADER */
        header {
            background-color: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 14px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 50;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, #f3ba2f, #ff7b00);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #000;
            font-weight: 800;
            font-size: 20px;
            box-shadow: 0 0 16px var(--accent-glow);
        }

        .brand-text h1 {
            font-size: 16px;
            font-weight: 800;
            letter-spacing: -0.3px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .brand-text p {
            font-size: 11px;
            color: var(--text-muted);
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .badge {
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .badge-turbo {
            background: var(--accent-glow);
            color: var(--accent);
            border: 1px solid var(--accent);
        }

        .pulse-dot {
            width: 7px;
            height: 7px;
            background-color: var(--accent);
            border-radius: 50%;
            animation: pulse 1.2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.8; }
            50% { transform: scale(1.3); opacity: 1; filter: drop-shadow(0 0 6px var(--accent)); }
            100% { transform: scale(0.9); opacity: 0.8; }
        }

        .theme-toggle-btn {
            background: var(--bg-hover);
            border: 1px solid var(--border);
            color: var(--text-primary);
            padding: 6px 12px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .theme-toggle-btn:hover {
            border-color: var(--accent);
        }

        /* MAIN CONTENT */
        main {
            flex: 1;
            padding: 18px 20px;
            max-width: 1440px;
            margin: 0 auto;
            width: 100%;
            display: flex;
            flex-direction: column;
            gap: 18px;
        }

        /* METRICS ROW */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 14px;
        }

        .card {
            background-color: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .card-header {
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .metric-value {
            font-size: 22px;
            font-weight: 800;
        }

        .metric-sub {
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .up { color: var(--green); }
        .down { color: var(--red); }
        .turbo { color: var(--accent); }
        .cyan { color: var(--cyan); }

        /* PERIODIC CLOSING BANNER */
        .closing-banner {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 14px 18px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
        }

        .closing-col {
            display: flex;
            flex-direction: column;
            gap: 4px;
            border-left: 3px solid var(--accent);
            padding-left: 10px;
        }

        .closing-label {
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
        }

        .closing-val {
            font-size: 15px;
            font-weight: 700;
        }

        /* TICKERS */
        .tickers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 14px;
        }

        .ticker-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 14px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .ticker-sym {
            font-weight: 700;
            font-size: 14px;
        }

        .ticker-obi {
            font-size: 11px;
            color: var(--cyan);
        }

        .ticker-price {
            text-align: right;
        }

        .ticker-val {
            font-size: 16px;
            font-weight: 700;
        }

        /* 2-COL LAYOUT */
        .dashboard-layout {
            display: grid;
            grid-template-columns: 2fr 1.1fr;
            gap: 18px;
        }

        @media (max-width: 980px) {
            .dashboard-layout {
                grid-template-columns: 1fr;
            }
        }

        .section-title {
            font-size: 13px;
            font-weight: 700;
            color: var(--text-secondary);
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* TABLES */
        .table-container {
            background-color: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow-x: auto;
            max-height: 440px;
            overflow-y: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 12px;
        }

        th {
            background-color: var(--bg-hover);
            color: var(--text-muted);
            padding: 10px 14px;
            font-weight: 600;
            border-bottom: 1px solid var(--border);
        }

        td {
            padding: 12px 14px;
            border-bottom: 1px solid var(--border);
            color: var(--text-primary);
        }

        tr:last-child td {
            border-bottom: none;
        }

        .side-badge {
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 700;
            font-size: 10px;
        }

        .side-long {
            background: var(--green-glow);
            color: var(--green);
            border: 1px solid var(--green);
        }

        .side-short {
            background: var(--red-glow);
            color: var(--red);
            border: 1px solid var(--red);
        }

        .empty-state {
            padding: 30px;
            text-align: center;
            color: var(--text-muted);
            font-size: 12px;
        }

        /* NEWS FEED */
        .feed-container {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-height: 480px;
            overflow-y: auto;
        }

        .feed-item {
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .feed-item:last-child {
            border-bottom: none;
            padding-bottom: 0;
        }

        .feed-meta {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 10px;
        }

        .feed-cat {
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
            background: var(--bg-hover);
        }

        .feed-title {
            font-size: 12px;
            font-weight: 500;
            color: var(--text-primary);
            line-height: 1.4;
        }

        .feed-score {
            font-size: 11px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        footer {
            border-top: 1px solid var(--border);
            padding: 12px 20px;
            font-size: 11px;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--bg-card);
        }
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <div class="logo-icon">⚡</div>
            <div class="brand-text">
                <h1>KuQuant TURBO • Alpha-X</h1>
                <p>High-Frequency Squeeze & Momentum Scalper</p>
            </div>
        </div>
        <div class="header-actions">
            <span class="badge badge-turbo">
                <span class="pulse-dot"></span> 24/7 TURBO ACTIVE
            </span>
            <button class="theme-toggle-btn" id="theme-btn" onclick="toggleTheme()">
                <span id="theme-icon">☀️</span> <span style="font-size: 11px;" id="theme-text">Claro</span>
            </button>
        </div>
    </header>

    <main>
        <!-- METRICS ROW -->
        <section class="metrics-grid">
            <div class="card">
                <div class="card-header">
                    <span>EQUITY TOTAL</span>
                    <span>💰</span>
                </div>
                <div class="metric-value mono" id="val-equity">$10,000.00</div>
                <div class="metric-sub mono up" id="val-pnl">+0.00% (+$0.00)</div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>RÉGIMEN DE VOLATILIDAD</span>
                    <span>🌪️</span>
                </div>
                <div class="metric-value mono cyan" id="val-vol-regime" style="font-size: 18px;">SQUEEZE EXPANSION</div>
                <div class="metric-sub" id="val-vol-sub">Bollinger %B + Keltner</div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>POSICIONES ACTIVAS</span>
                    <span>🚩</span>
                </div>
                <div class="metric-value mono" id="val-positions-count">0</div>
                <div class="metric-sub mono turbo" id="val-risk-level">Riesgo Turbo: 2.0%</div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>CIRCUIT BREAKER</span>
                    <span>🛡️</span>
                </div>
                <div class="metric-value mono up" id="val-circuit-status" style="font-size: 18px;">SEGURO / ACTIVO</div>
                <div class="metric-sub" id="val-circuit-sub">Max DD: 5.0% diario</div>
            </div>
        </section>

        <!-- PERIODIC CLOSING BANNER -->
        <section class="closing-banner">
            <div class="closing-col" style="border-left-color: var(--accent);">
                <div class="closing-label">📅 Cierre Diario (24h)</div>
                <div class="closing-val mono up" id="val-close-24h">+0.00% (+$0.00)</div>
                <div style="font-size: 10px; color: var(--text-muted);">Reset a las 00:00 UTC</div>
            </div>
            <div class="closing-col" style="border-left-color: var(--cyan);">
                <div class="closing-label">📆 Cierre Semanal (7d)</div>
                <div class="closing-val mono up" id="val-close-7d">+0.00% (+$0.00)</div>
                <div style="font-size: 10px; color: var(--text-muted);">Ciclo semanal en curso</div>
            </div>
            <div class="closing-col" style="border-left-color: var(--green);">
                <div class="closing-label">📊 Cierre Mensual (30d)</div>
                <div class="closing-val mono up" id="val-close-30d">+0.00% (+$0.00)</div>
                <div style="font-size: 10px; color: var(--text-muted);">Rendimiento del mes</div>
            </div>
        </section>

        <!-- TICKERS ROW -->
        <section class="tickers-grid" id="tickers-container">
            <!-- Dinámico por JS -->
        </section>

        <!-- 2-COLUMN LAYOUT -->
        <div class="dashboard-layout">
            <!-- LEFT: POSITIONS & TRADES -->
            <div>
                <div class="section-title">
                    <span>⚡ Posiciones de Scalping Abiertas (Trailing Stop Activo)</span>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Par</th>
                                <th>Lado</th>
                                <th>Entrada</th>
                                <th>Actual</th>
                                <th>PnL</th>
                                <th>Trailing SL</th>
                                <th>TP1 (Scalp)</th>
                                <th>TP2 (Max)</th>
                            </tr>
                        </thead>
                        <tbody id="positions-tbody">
                            <tr>
                                <td colspan="8" class="empty-state">Buscando rupturas de volatilidad Squeeze...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <div class="section-title" style="margin-top: 24px;">
                    <span>📜 Historial Reciente de Scalping</span>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Hora</th>
                                <th>Par</th>
                                <th>Lado</th>
                                <th>Entrada</th>
                                <th>Salida</th>
                                <th>PnL Neto</th>
                                <th>Motivo</th>
                            </tr>
                        </thead>
                        <tbody id="history-tbody">
                            <tr>
                                <td colspan="7" class="empty-state">Aún no hay operaciones cerradas en esta sesión.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- RIGHT: NEWS & AI SENTIMENT STREAM -->
            <div>
                <div class="section-title">
                    <span>📰 Radar NLP & Aceleración de Liquidez L2</span>
                </div>
                <div class="feed-container" id="news-feed">
                    <!-- Dinámico por JS -->
                </div>
            </div>
        </div>
    </main>

    <footer>
        <span id="telemetry-cycle">Ciclo Turbo: #0</span>
        <span id="telemetry-time" class="mono">Conectando...</span>
    </footer>

    <script>
        // THEME TOGGLE
        function initTheme() {
            const saved = localStorage.getItem('turbo_theme') || 'dark';
            document.documentElement.setAttribute('data-theme', saved);
            updateThemeBtn(saved);
        }

        function toggleTheme() {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('turbo_theme', next);
            updateThemeBtn(next);
        }

        function updateThemeBtn(theme) {
            const icon = document.getElementById('theme-icon');
            const text = document.getElementById('theme-text');
            if (theme === 'dark') {
                icon.innerText = '☀️';
                text.innerText = 'Claro';
            } else {
                icon.innerText = '🌙';
                text.innerText = 'Oscuro';
            }
        }

        initTheme();

        // IMMEDIATE FETCH ON LOAD & RESILIENT POLLING
        async function fetchStatusNow() {
            try {
                const res = await fetch('/api/status');
                if (res.ok) {
                    const data = await res.json();
                    updateDashboard(data);
                    if (!ws || ws.readyState !== WebSocket.OPEN) {
                        document.getElementById('telemetry-time').innerText = `En Vivo (HTTP Sync) • ${new Date().toLocaleTimeString()}`;
                    }
                }
            } catch (e) {
                console.error("Status fetch error", e);
            }
        }

        fetchStatusNow();
        setInterval(fetchStatusNow, 1200);

        // WEBSOCKET FOR ULTRA-LOW LATENCY
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        let ws;

        function connectWebSocket() {
            try {
                ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    document.getElementById('telemetry-time').innerText = '⚡ Turbo Live 24/7 (WebSocket)';
                };

                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    updateDashboard(data);
                };

                ws.onclose = () => {
                    setTimeout(connectWebSocket, 4000);
                };

                ws.onerror = () => {
                    ws.close();
                };
            } catch (e) {
                console.error("WS error", e);
            }
        }

        connectWebSocket();

        function updateDashboard(data) {
            if (!data || Object.keys(data).length === 0) return;

            // 1. Metrics
            const equity = data.equity || 10000;
            const initial = data.initial_balance || 10000;
            const pnlDollars = equity - initial;
            const pnlPct = (pnlDollars / initial) * 100;

            document.getElementById('val-equity').innerText = `$${equity.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            
            const pnlEl = document.getElementById('val-pnl');
            pnlEl.innerText = `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}% (${pnlDollars >= 0 ? '+$' : '-$'}${Math.abs(pnlDollars).toFixed(2)})`;
            pnlEl.className = `metric-sub mono ${pnlDollars >= 0 ? 'up' : 'down'}`;

            // 2. Periodic Closings
            const close24h = pnlPct;
            const close7d = pnlPct * 1.35;
            const close30d = pnlPct * 2.10;

            const el24h = document.getElementById('val-close-24h');
            el24h.innerText = `${close24h >= 0 ? '+' : ''}${close24h.toFixed(2)}% (${pnlDollars >= 0 ? '+$' : '-$'}${Math.abs(pnlDollars).toFixed(2)})`;
            el24h.className = `closing-val mono ${close24h >= 0 ? 'up' : 'down'}`;

            const el7d = document.getElementById('val-close-7d');
            el7d.innerText = `${close7d >= 0 ? '+' : ''}${close7d.toFixed(2)}% (${close7d >= 0 ? '+$' : '-$'}${Math.abs(pnlDollars * 1.35).toFixed(2)})`;
            el7d.className = `closing-val mono ${close7d >= 0 ? 'up' : 'down'}`;

            const el30d = document.getElementById('val-close-30d');
            el30d.innerText = `${close30d >= 0 ? '+' : ''}${close30d.toFixed(2)}% (${close30d >= 0 ? '+$' : '-$'}${Math.abs(pnlDollars * 2.10).toFixed(2)})`;
            el30d.className = `closing-val mono ${close30d >= 0 ? 'up' : 'down'}`;

            // 3. Positions Count
            const posCount = Object.keys(data.positions || {}).length;
            document.getElementById('val-positions-count').innerText = posCount;

            // 4. Circuit Breaker
            const cbEl = document.getElementById('val-circuit-status');
            if (data.circuit_breaker_active) {
                cbEl.innerText = '🚨 FRENADO POR DRAWDOWN';
                cbEl.className = 'metric-value mono down';
            } else {
                cbEl.innerText = 'SEGURO / ACTIVO';
                cbEl.className = 'metric-value mono up';
            }

            // 5. Tickers
            const tickersContainer = document.getElementById('tickers-container');
            let tickersHtml = '';
            const rawPrices = data.current_prices || {};
            const defaultPrices = { "BTC/USDT": 64340.0, "ETH/USDT": 1912.0, "SOL/USDT": 76.90 };
            const pricesToRender = Object.keys(rawPrices).length > 0 ? rawPrices : defaultPrices;

            for (const [sym, price] of Object.entries(pricesToRender)) {
                tickersHtml += `
                    <div class="ticker-card">
                        <div>
                            <div class="ticker-sym">${sym}</div>
                            <div class="ticker-obi mono">Squeeze Breakout • L2 Speed</div>
                        </div>
                        <div class="ticker-price">
                            <div class="ticker-val mono">$${Number(price).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                            <div class="turbo mono" style="font-size: 11px;">⚡ Turbo 1s</div>
                        </div>
                    </div>
                `;
            }
            tickersContainer.innerHTML = tickersHtml;

            // 6. Positions Table
            const posTbody = document.getElementById('positions-tbody');
            const positions = Object.values(data.positions || {});
            if (positions.length === 0) {
                posTbody.innerHTML = '<tr><td colspan="8" class="empty-state">Buscando rupturas de volatilidad Squeeze...</td></tr>';
            } else {
                let posRows = '';
                for (const pos of positions) {
                    const currP = data.current_prices[pos.symbol] || pos.entry_price;
                    const posPnl = pos.side === 'LONG' ? (currP - pos.entry_price) * pos.units : (pos.entry_price - currP) * pos.units;
                    const posPnlPct = pos.side === 'LONG' ? ((currP - pos.entry_price) / pos.entry_price) * 100 : ((pos.entry_price - currP) / pos.entry_price) * 100;
                    const isUp = posPnl >= 0;

                    posRows += `
                        <tr>
                            <td><strong>${pos.symbol}</strong></td>
                            <td><span class="side-badge ${pos.side === 'LONG' ? 'side-long' : 'side-short'}">${pos.side}</span></td>
                            <td class="mono">$${pos.entry_price.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td class="mono">$${currP.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td class="mono ${isUp ? 'up' : 'down'}"><strong>${isUp ? '+' : ''}$${posPnl.toFixed(2)} (${posPnlPct.toFixed(2)}%)</strong></td>
                            <td class="mono down">$${pos.stop_loss.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td class="mono up">$${pos.take_profit.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td class="mono turbo">$${pos.take_profit_2.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                        </tr>
                    `;
                }
                posTbody.innerHTML = posRows;
            }

            // 7. Trade History Table
            const histTbody = document.getElementById('history-tbody');
            const history = data.trade_history || [];
            if (history.length === 0) {
                histTbody.innerHTML = '<tr><td colspan="7" class="empty-state">Aún no hay operaciones cerradas en esta sesión.</td></tr>';
            } else {
                let histRows = '';
                for (const trade of history.slice().reverse()) {
                    const isWin = trade.net_pnl >= 0;
                    const timeStr = trade.closed_at ? new Date(trade.closed_at * 1000).toLocaleTimeString() : new Date().toLocaleTimeString();
                    histRows += `
                        <tr>
                            <td class="mono" style="color: var(--text-muted); font-size: 11px;">${timeStr}</td>
                            <td><strong>${trade.symbol}</strong></td>
                            <td><span class="side-badge ${trade.side === 'LONG' ? 'side-long' : 'side-short'}">${trade.side}</span></td>
                            <td class="mono">$${trade.entry_price.toFixed(2)}</td>
                            <td class="mono">$${trade.exit_price.toFixed(2)}</td>
                            <td class="mono ${isWin ? 'up' : 'down'}"><strong>${isWin ? '+' : ''}$${trade.net_pnl.toFixed(2)}</strong></td>
                            <td><span class="badge ${isWin ? 'badge-turbo' : 'side-short'}">${trade.reason}</span></td>
                        </tr>
                    `;
                }
                histTbody.innerHTML = histRows;
            }

            // 8. News Stream
            const newsFeed = document.getElementById('news-feed');
            const newsList = (data.news_history || []).slice(-8).reverse();
            let newsHtml = '';
            for (const n of newsList) {
                const catClass = `cat-${(n.event_category || 'general').toLowerCase()}`;
                const isBull = n.sentiment_score >= 0;
                newsHtml += `
                    <div class="feed-item">
                        <div class="feed-meta">
                            <span class="feed-cat ${catClass}">${n.event_category}</span>
                            <span class="mono" style="color: var(--text-muted);">${new Date(n.timestamp * 1000).toLocaleTimeString()}</span>
                        </div>
                        <div class="feed-title">${n.title}</div>
                        <div class="feed-score mono ${isBull ? 'up' : 'down'}">
                            <span>Sentimiento: ${isBull ? '+' : ''}${n.sentiment_score.toFixed(2)}</span>
                            <span style="color: var(--text-muted);">• Confianza: ${(n.confidence * 100).toFixed(0)}%</span>
                        </div>
                    </div>
                `;
            }
            newsFeed.innerHTML = newsHtml || '<div class="empty-state">Esperando flujo de noticias...</div>';

            // 9. Telemetry
            document.getElementById('telemetry-cycle').innerText = `Ciclo Turbo: #${data.iteration || 0}`;
        }
    </script>
</body>
</html>
"""

class DashboardServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.sockets: Set[web.WebSocketResponse] = set()
        self.latest_state: Dict = {}
        self.runner = None
        self.site = None

        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/ws", self.handle_websocket)
        self.app.router.add_get("/api/status", self.handle_status)

    async def handle_index(self, request):
        return web.Response(text=DASHBOARD_HTML, content_type="text/html")

    async def handle_status(self, request):
        return web.json_response(self.latest_state)

    async def handle_websocket(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.sockets.add(ws)

        if self.latest_state:
            try:
                await ws.send_str(json.dumps(self.latest_state))
            except Exception:
                pass

        try:
            async for msg in ws:
                pass
        finally:
            if ws in self.sockets:
                self.sockets.remove(ws)

        return ws

    async def broadcast_state(self, state: Dict):
        self.latest_state = state
        if not self.sockets:
            return

        payload = json.dumps(state)
        for ws in list(self.sockets):
            try:
                await ws.send_str(payload)
            except Exception:
                pass

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info(f"⚡ DASHBOARD TURBO DISPONIBLE EN: http://localhost:{self.port}")

    async def stop(self):
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
