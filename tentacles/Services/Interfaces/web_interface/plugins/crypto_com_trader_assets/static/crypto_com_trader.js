(() => {
  "use strict";

  const root = document.getElementById("crypto-trader");
  if (!root) return;

  // Endpoint URLs
  const URLS = {
    status: root.dataset.statusUrl,
    mode: root.dataset.modeUrl,
    credentials: root.dataset.credentialsUrl,
    portfolio: root.dataset.portfolioUrl,
    market: root.dataset.marketUrl,
    candles: root.dataset.candlesUrl,
    orderCreate: root.dataset.orderCreateUrl,
    orderCancel: root.dataset.orderCancelUrl,
    orderCancelAll: root.dataset.orderCancelAllUrl,
    openOrders: root.dataset.openOrdersUrl,
    orderHistory: root.dataset.orderHistoryUrl,
    paperReset: root.dataset.paperResetUrl,
    strategies: root.dataset.strategiesUrl,
    gridStart: root.dataset.gridStartUrl,
    gridStop: root.dataset.gridStopUrl,
    dcaStart: root.dataset.dcaStartUrl,
    dcaStop: root.dataset.dcaStopUrl,
    radarStart: root.dataset.radarStartUrl,
    radarStop: root.dataset.radarStopUrl,
    aiCopilot: root.dataset.aiCopilotUrl,
    aiRadar: root.dataset.aiRadarUrl,
    aiExecute: root.dataset.aiExecuteUrl,
    secondsAdvice: "/crypto-com/api/seconds/advice",
    secondsTrade: "/crypto-com/api/seconds/trade",
    secondsActive: "/crypto-com/api/seconds/active",
    secondsCashout: "/crypto-com/api/seconds/cashout",
    secondsHistory: "/crypto-com/api/seconds/history",
    secondsAutopilotStatus: "/crypto-com/api/seconds/autopilot/status",
    secondsAutopilotToggle: "/crypto-com/api/seconds/autopilot/toggle",
  };

  // State
  const state = {
    pair: "BTC_USDT",
    timeframe: "1h",
    orderSide: "BUY",
    orderType: "MARKET",
    mode: "paper",
    lastPrice: 0,
    bestBid: 0,
    bestAsk: 0,
    balances: { USDT: 10000 },
    candles: [],
    strategies: {},
    secondsPair: "BTC_USDT",
    secondsDuration: 30,
    secondsStake: 10,
    secondsAiEngine: "antigravity", // 'antigravity', 'codex', 'consensus'
    tvInterval: "1",
    autopilotEnabled: false,
    autopilotConfidence: 72,
  };

  const $ = (id) => document.getElementById(id);

  function toast(msg, type = "info") {
    const container = $("toast-container");
    if (!container) return;
    const div = document.createElement("div");
    div.className = "trader-toast";
    const icon = type === "error" ? "fa-triangle-exclamation text-danger" : (type === "success" ? "fa-circle-check text-success" : "fa-circle-info text-info");
    div.innerHTML = `<i class="fas ${icon}"></i> <span>${msg}</span>`;
    container.appendChild(div);
    setTimeout(() => {
      div.style.opacity = "0";
      setTimeout(() => div.remove(), 300);
    }, 4000);
  }

  // --- Initial Data Load ---
  async function init() {
    setupTabs();
    setupPairChips();
    setupOrderForm();
    setupCanvas();
    setupStrategies();
    setupSettingsModal();
    setupCopilot();
    setupRadarTab();
    setupSecondsScalper();

    await fetchStatus();
    await refreshMarket();
    await refreshPortfolio();
    await refreshOrders();
    await refreshStrategies();
    await refreshRadar();
    await refreshSecondsAdvice();
    await refreshSecondsActive();
    await refreshSecondsHistory();
    await refreshAutopilotStatus();
    renderTradingViewSecondsChart(state.secondsPair, state.tvInterval);

    // Start polling intervals
    setInterval(refreshMarket, 3500);
    setInterval(refreshPortfolio, 7000);
    setInterval(refreshOrders, 6000);
    setInterval(refreshStrategies, 10000);
    setInterval(() => refreshRadar(state.radarPair || "BTC_USDT"), 15000);
    setInterval(() => refreshSecondsAdvice(state.secondsPair || "BTC_USDT"), 4500);
    setInterval(refreshSecondsActive, 1000);
    setInterval(refreshSecondsHistory, 5000);
    setInterval(refreshAutopilotStatus, 3500);
  }

  // --- Tabs Navigation ---
  function setupTabs() {
    function activateTab(tabName) {
      console.log("[CryptoCom] Switching to tab:", tabName);
      document.querySelectorAll(".tab-link").forEach((b) => {
        if (b.dataset.tab === tabName) {
          b.classList.add("active");
        } else {
          b.classList.remove("active");
        }
      });
      document.querySelectorAll(".tab-pane").forEach((p) => {
        p.classList.remove("active");
        p.style.display = "none";
      });
      const target = $(`tab-${tabName}`);
      if (target) {
        target.classList.add("active");
        target.style.display = "block";
        if (tabName === "terminal") drawChart();
        if (tabName === "seconds") {
          renderTradingViewSecondsChart(state.secondsPair, state.tvInterval);
          refreshAutopilotStatus();
          refreshSecondsAdvice();
          refreshSecondsActive();
          refreshSecondsHistory();
        }
      } else {
        console.error("[CryptoCom] Target tab not found: tab-" + tabName);
      }
    }
    window.switchCryptoTraderTab = activateTab;

    document.querySelectorAll(".tab-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        activateTab(btn.dataset.tab);
      });
    });

    // Orders subtabs
    function switchOrderSubtab(sub) {
      document.querySelectorAll("#order-table-tabs .nav-link").forEach((l) => {
        if (l.dataset.subtab === sub) {
          l.classList.add("active");
        } else {
          l.classList.remove("active");
        }
      });
      const openWrap = $("table-open-orders-wrap");
      const histWrap = $("table-order-history-wrap");
      if (openWrap) openWrap.style.display = sub === "open-orders" ? "block" : "none";
      if (histWrap) histWrap.style.display = sub === "order-history" ? "block" : "none";
    }
    window.switchOrderSubtab = switchOrderSubtab;

    document.querySelectorAll("#order-table-tabs .nav-link").forEach((link) => {
      link.addEventListener("click", () => {
        switchOrderSubtab(link.dataset.subtab);
      });
    });
  }

  // --- Pair Selector ---
  function setupPairChips() {
    document.querySelectorAll(".pair-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        document.querySelectorAll(".pair-chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        state.pair = chip.dataset.pair;
        updatePairLabels();
        refreshMarket();
      });
    });

    // Timeframe selector
    document.querySelectorAll("#timeframe-group button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#timeframe-group button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.timeframe = btn.dataset.tf;
        fetchCandles();
      });
    });
  }

  function updatePairLabels() {
    const [base, quote] = state.pair.split("_");
    $("chart-symbol").textContent = state.pair;
    $("base-symbol").textContent = base;
    $("submit-symbol").textContent = base;
    updateAvailableBalance();
  }

  function updateAvailableBalance() {
    const [base, quote] = state.pair.split("_");
    if (state.orderSide === "BUY") {
      const avail = state.balances[quote] || 0;
      $("avail-balance").textContent = `${avail.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${quote}`;
    } else {
      const avail = state.balances[base] || 0;
      $("avail-balance").textContent = `${avail.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 6 })} ${base}`;
    }
  }

  // --- Status & Mode ---
  async function fetchStatus() {
    try {
      const res = await fetch(URLS.status);
      const data = await res.json();
      state.mode = data.mode || "paper";
      renderMode();
    } catch (e) {
      console.error("Status check failed", e);
    }
  }

  function renderMode() {
    const badge = $("mode-badge");
    const text = $("mode-text");
    const toggle = $("mode-toggle-text");
    const tag = $("order-mode-tag");
    if (state.mode === "live") {
      badge.className = "mode-pill live";
      text.textContent = "LIVE EXCHANGE";
      toggle.textContent = "Switch to Paper";
      tag.textContent = "LIVE";
      tag.className = "badge badge-danger";
    } else {
      badge.className = "mode-pill paper";
      text.textContent = "PAPER TRADING";
      toggle.textContent = "Switch to Live";
      tag.textContent = "PAPER";
      tag.className = "badge badge-success";
    }
  }

  $("btn-toggle-mode")?.addEventListener("click", async () => {
    const newMode = state.mode === "paper" ? "live" : "paper";
    try {
      const res = await fetch(URLS.mode, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: newMode }),
      });
      const data = await res.json();
      if (res.ok) {
        state.mode = data.mode;
        renderMode();
        toast(`Switched to ${state.mode.toUpperCase()} mode`, "success");
        refreshPortfolio();
        refreshOrders();
      } else {
        toast(data.error || "Failed to switch mode. Ensure API keys are set for live mode.", "error");
      }
    } catch (e) {
      toast("Error toggling mode: " + e.message, "error");
    }
  });

  // --- Market Overview & Candlestick ---
  async function refreshMarket() {
    try {
      const url = URLS.market.replace("__INSTRUMENT__", state.pair);
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();

      renderTicker(data.ticker);
      renderOrderBook(data.book);
      if (!state.candles.length) {
        fetchCandles();
      }
    } catch (e) {
      console.error("Market fetch error", e);
    }
  }

  function renderTicker(ticker) {
    if (!ticker) return;
    const last = parseFloat(ticker.a || ticker.b || 0);
    const change = parseFloat(ticker.c || 0) * 100;
    const high = parseFloat(ticker.h || 0);
    const low = parseFloat(ticker.l || 0);
    const vol = parseFloat(ticker.vv || 0);

    state.lastPrice = last;
    $("stat-last").textContent = last.toLocaleString(undefined, { minimumFractionDigits: 2 });
    const changeEl = $("stat-change");
    changeEl.textContent = `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`;
    changeEl.className = change >= 0 ? "text-success" : "text-danger";

    $("stat-high").textContent = high.toLocaleString(undefined, { minimumFractionDigits: 2 });
    $("stat-low").textContent = low.toLocaleString(undefined, { minimumFractionDigits: 2 });
    $("stat-vol").textContent = `$${Math.round(vol).toLocaleString()}`;

    // Update chip price
    const chip = $(`chip-${state.pair}`);
    if (chip) chip.textContent = `$${last.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

    recalcOrderSummary();
  }

  function renderOrderBook(book) {
    if (!book) return;
    const asks = (book.asks || []).slice(0, 6).reverse();
    const bids = (book.bids || []).slice(0, 6);

    state.bestAsk = asks.length ? parseFloat(asks[asks.length - 1][0]) : state.lastPrice;
    state.bestBid = bids.length ? parseFloat(bids[0][0]) : state.lastPrice;

    // Asks
    const maxAskVol = Math.max(...asks.map((a) => parseFloat(a[1])), 1);
    const asksEl = $("book-asks");
    asksEl.innerHTML = asks
      .map(([px, qty]) => {
        const pct = Math.min(100, Math.round((parseFloat(qty) / maxAskVol) * 100));
        return `<div class="book-row" onclick="window.setPrice(${px})">
          <div class="depth-bar" style="width:${pct}%"></div>
          <span>${parseFloat(px).toFixed(2)}</span>
          <span>${parseFloat(qty).toFixed(4)}</span>
        </div>`;
      })
      .join("");

    // Mid price and spread
    const mid = (state.bestAsk + state.bestBid) / 2;
    $("mid-price").textContent = mid.toFixed(2);
    const spreadBps = state.bestBid > 0 ? (((state.bestAsk - state.bestBid) / state.bestBid) * 10000).toFixed(1) : 0;
    $("book-spread").textContent = `Spread: ${spreadBps} bps`;

    // Bids
    const maxBidVol = Math.max(...bids.map((b) => parseFloat(b[1])), 1);
    const bidsEl = $("book-bids");
    bidsEl.innerHTML = bids
      .map(([px, qty]) => {
        const pct = Math.min(100, Math.round((parseFloat(qty) / maxBidVol) * 100));
        return `<div class="book-row" onclick="window.setPrice(${px})">
          <div class="depth-bar" style="width:${pct}%"></div>
          <span>${parseFloat(px).toFixed(2)}</span>
          <span>${parseFloat(qty).toFixed(4)}</span>
        </div>`;
      })
      .join("");
  }

  window.setPrice = function (px) {
    if (state.orderType !== "MARKET") {
      $("order-price").value = px;
      recalcOrderSummary();
    }
  };

  async function fetchCandles() {
    try {
      const url = URLS.candles.replace("__INSTRUMENT__", state.pair) + `?timeframe=${state.timeframe}&count=70`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      state.candles = data.candles || [];
      drawChart();
    } catch (e) {
      console.error("Candles fetch error", e);
    }
  }

  // --- Interactive Canvas Candlestick Chart ---
  function setupCanvas() {
    const canvas = $("candleCanvas");
    if (!canvas) return;

    window.addEventListener("resize", () => {
      canvas.width = canvas.parentElement.clientWidth;
      drawChart();
    });
    setTimeout(() => {
      canvas.width = canvas.parentElement.clientWidth;
      drawChart();
    }, 100);
  }

  function drawChart() {
    const canvas = $("candleCanvas");
    if (!canvas || !state.candles.length) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    const candles = state.candles;
    let minP = Infinity, maxP = -Infinity;
    candles.forEach((c) => {
      const high = parseFloat(c.h);
      const low = parseFloat(c.l);
      if (high > maxP) maxP = high;
      if (low < minP) minP = low;
    });

    const padP = (maxP - minP) * 0.08 || 1;
    minP -= padP;
    maxP += padP;

    const chartH = h - 60; // Leave 60px for volume
    const n = candles.length;
    const candleW = Math.max(3, Math.floor((w - 70) / n) - 3);
    const step = (w - 70) / n;

    // Draw Price Grid Lines
    ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
    ctx.lineWidth = 1;
    ctx.font = "10px JetBrains Mono";
    ctx.fillStyle = "#6c727f";

    for (let i = 0; i <= 4; i++) {
      const y = 20 + (chartH / 4) * i;
      const priceVal = maxP - ((maxP - minP) / 4) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w - 60, y);
      ctx.stroke();
      ctx.fillText(priceVal.toFixed(2), w - 55, y + 3);
    }

    // Draw Candlesticks
    candles.forEach((c, i) => {
      const o = parseFloat(c.o);
      const high = parseFloat(c.h);
      const low = parseFloat(c.l);
      const close = parseFloat(c.c);

      const x = i * step + 10;
      const yO = chartH - ((o - minP) / (maxP - minP)) * chartH + 10;
      const yC = chartH - ((close - minP) / (maxP - minP)) * chartH + 10;
      const yH = chartH - ((high - minP) / (maxP - minP)) * chartH + 10;
      const yL = chartH - ((low - minP) / (maxP - minP)) * chartH + 10;

      const isUp = close >= o;
      const color = isUp ? "#00e676" : "#ff334b";

      // Wick
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(x + candleW / 2, yH);
      ctx.lineTo(x + candleW / 2, yL);
      ctx.stroke();

      // Body
      ctx.fillStyle = color;
      const bodyY = Math.min(yO, yC);
      const bodyH = Math.max(2, Math.abs(yO - yC));
      ctx.fillRect(x, bodyY, candleW, bodyH);
    });

    const last = candles[candles.length - 1];
    if (last) {
      $("chart-ohlc").textContent = `O: ${parseFloat(last.o).toFixed(2)} H: ${parseFloat(last.h).toFixed(2)} L: ${parseFloat(last.l).toFixed(2)} C: ${parseFloat(last.c).toFixed(2)}`;
    }
  }

  // --- Order Form Setup ---
  function setupOrderForm() {
    $("btn-side-buy")?.addEventListener("click", () => {
      state.orderSide = "BUY";
      $("btn-side-buy").classList.add("active");
      $("btn-side-sell").classList.remove("active");
      const btn = $("btn-execute-order");
      btn.className = "btn btn-submit-order buy mt-3";
      btn.innerHTML = `<i class="fas fa-check-circle mr-1"></i> Buy <span id="submit-symbol">${state.pair.split("_")[0]}</span>`;
      updateAvailableBalance();
      recalcOrderSummary();
    });

    $("btn-side-sell")?.addEventListener("click", () => {
      state.orderSide = "SELL";
      $("btn-side-sell").classList.add("active");
      $("btn-side-buy").classList.remove("active");
      const btn = $("btn-execute-order");
      btn.className = "btn btn-submit-order sell mt-3";
      btn.innerHTML = `<i class="fas fa-arrow-down mr-1"></i> Sell <span id="submit-symbol">${state.pair.split("_")[0]}</span>`;
      updateAvailableBalance();
      recalcOrderSummary();
    });

    document.querySelectorAll(".order-type-group .btn-type").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".order-type-group .btn-type").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.orderType = btn.dataset.type;
        $("group-price").style.display = state.orderType === "MARKET" ? "none" : "block";
        if (state.orderType !== "MARKET" && !$("order-price").value) {
          $("order-price").value = state.lastPrice || "";
        }
        recalcOrderSummary();
      });
    });

    $("order-qty")?.addEventListener("input", recalcOrderSummary);
    $("order-price")?.addEventListener("input", recalcOrderSummary);

    // Percentage slider
    document.querySelectorAll(".btn-pct").forEach((btn) => {
      btn.addEventListener("click", () => {
        const pct = parseInt(btn.dataset.pct, 10) / 100;
        const [base, quote] = state.pair.split("_");
        const px = state.orderType === "MARKET" ? (state.orderSide === "BUY" ? state.bestAsk : state.bestBid) : (parseFloat($("order-price").value) || state.lastPrice);
        if (state.orderSide === "BUY") {
          const availUsdt = (state.balances[quote] || 0) * pct;
          if (px > 0) {
            $("order-qty").value = ((availUsdt * 0.999) / px).toFixed(5);
          }
        } else {
          const availBase = (state.balances[base] || 0) * pct;
          $("order-qty").value = availBase.toFixed(5);
        }
        recalcOrderSummary();
      });
    });

    // Execute order
    $("form-order")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const qty = parseFloat($("order-qty").value);
      if (!qty || qty <= 0) {
        toast("Please enter a valid quantity", "error");
        return;
      }
      const price = state.orderType === "MARKET" ? null : parseFloat($("order-price").value);
      if (state.orderType !== "MARKET" && (!price || price <= 0)) {
        toast("Please enter a valid limit price", "error");
        return;
      }

      const payload = {
        instrument: state.pair,
        side: state.orderSide,
        type: state.orderType,
        quantity: qty,
        price: price,
      };

      try {
        const res = await fetch(URLS.orderCreate, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.ok) {
          const isFilled = data.order && data.order.status === "FILLED";
          if (isFilled) {
            toast(`⚡ ${state.orderSide} ${state.pair} MARKET order filled instantly at $${data.order.price || state.lastPrice}! Showing in Execution History.`, "success");
            switchOrderSubtab("order-history");
          } else {
            toast(`📋 ${state.orderSide} ${state.pair} LIMIT order placed! It is now active in Open Orders.`, "success");
            switchOrderSubtab("open-orders");
          }
          $("order-qty").value = "";
          recalcOrderSummary();
          refreshPortfolio();
          refreshOrders();
        } else {
          toast(data.error || "Order execution failed", "error");
        }
      } catch (err) {
        toast("Failed to submit order: " + err.message, "error");
      }
    });

    // Cancel all button
    $("btn-cancel-all")?.addEventListener("click", async () => {
      if (!confirm("Are you sure you want to cancel all open orders?")) return;
      try {
        const res = await fetch(URLS.orderCancelAll, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ instrument: state.pair }),
        });
        if (res.ok) {
          toast("Canceled all open orders", "success");
          refreshOrders();
          refreshPortfolio();
        }
      } catch (err) {
        toast("Error canceling orders: " + err.message, "error");
      }
    });
  }

  function recalcOrderSummary() {
    const qty = parseFloat($("order-qty")?.value) || 0;
    const px = state.orderType === "MARKET" ? (state.orderSide === "BUY" ? state.bestAsk : state.bestBid) : (parseFloat($("order-price")?.value) || state.lastPrice);
    const notional = qty * (px || 0);
    const fee = notional * 0.00075;

    $("order-notional").textContent = `${notional.toFixed(2)} USDT`;
    $("order-fee").textContent = `${fee.toFixed(2)} USDT`;
  }

  // --- Portfolio Ledger ---
  async function refreshPortfolio() {
    try {
      const res = await fetch(URLS.portfolio);
      if (!res.ok) return;
      const data = await res.json();
      state.balances = data.balances || {};

      $("total-equity").innerHTML = `$${data.total_equity_usdt.toLocaleString(undefined, { minimumFractionDigits: 2 })} <small>USDT</small>`;

      const pnlEl = $("unrealized-pnl");
      if (data.unrealized_pnl_pct !== undefined) {
        const isPos = data.unrealized_pnl_usdt >= 0;
        pnlEl.textContent = `${isPos ? "+" : ""}${data.unrealized_pnl_pct}% ($${data.unrealized_pnl_usdt.toFixed(2)})`;
        pnlEl.className = isPos ? "pnl-tag text-success" : "pnl-tag text-danger";
      }

      updateAvailableBalance();

      // Render breakdown table
      const tbody = $("portfolio-tbody");
      if (tbody && data.breakdown) {
        tbody.innerHTML = data.breakdown
          .map((item) => {
            const alloc = data.total_equity_usdt > 0 ? ((item.value_usdt / data.total_equity_usdt) * 100).toFixed(1) : 0;
            return `<tr>
              <td><strong>${item.asset}</strong></td>
              <td>${item.quantity.toFixed(4)}</td>
              <td>$${item.price.toFixed(2)}</td>
              <td><strong>$${item.value_usdt.toFixed(2)}</strong></td>
              <td class="text-right"><span class="badge badge-dark">${alloc}%</span></td>
            </tr>`;
          })
          .join("");
      }
    } catch (e) {
      console.error("Portfolio fetch error", e);
    }
  }

  $("btn-reset-paper")?.addEventListener("click", async () => {
    if (!confirm("Reset paper balance to initial $10,000 USDT?")) return;
    try {
      const res = await fetch(URLS.paperReset, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount: 10000 }),
      });
      if (res.ok) {
        toast("Paper balance reset to $10,000 USDT", "success");
        refreshPortfolio();
        refreshOrders();
      }
    } catch (e) {
      toast("Reset failed: " + e.message, "error");
    }
  });

  // --- Orders Management ---
  async function refreshOrders() {
    try {
      // Open orders
      const resOpen = await fetch(URLS.openOrders);
      if (resOpen.ok) {
        const data = await resOpen.json();
        renderOpenOrders(data.open_orders || []);
      }

      // History
      const resHist = await fetch(URLS.orderHistory);
      if (resHist.ok) {
        const data = await resHist.json();
        renderOrderHistory(data.history || []);
      }
    } catch (e) {
      console.error("Orders fetch error", e);
    }
  }

  function renderOpenOrders(orders) {
    const countEl = $("count-open-orders");
    if (countEl) countEl.textContent = orders.length;
    const tbody = $("open-orders-tbody");
    if (!orders.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">
        <div class="mb-2"><i class="fas fa-inbox fa-2x text-muted" style="opacity:0.4;"></i></div>
        <div class="font-weight-bold text-light">No Active Open Orders</div>
        <small class="text-muted d-block mt-1">
          Market orders execute instantly and appear under 
          <a href="javascript:void(0)" onclick="window.switchOrderSubtab('order-history')" class="text-warning font-weight-bold" style="text-decoration: underline;">
            Execution History
          </a>.
          Pending Limit orders will stay here until price reaches their trigger.
        </small>
      </td></tr>`;
      return;
    }

    tbody.innerHTML = orders
      .map((o) => {
        const sideBadge = o.side === "BUY" ? "badge-success" : "badge-danger";
        const date = new Date((o.created_at || Date.now() / 1000) * 1000).toLocaleTimeString();
        return `<tr>
          <td>${date}</td>
          <td><strong>${o.instrument}</strong></td>
          <td>${o.type}</td>
          <td><span class="badge ${sideBadge}">${o.side}</span></td>
          <td>$${o.price ? o.price.toFixed(2) : "Market"}</td>
          <td>${o.quantity.toFixed(4)}</td>
          <td><span class="badge badge-info">${o.status}</span></td>
          <td class="text-right">
            <button class="btn btn-sm btn-outline-danger py-0" onclick="window.cancelOrder('${o.instrument}', '${o.order_id}')">
              Cancel
            </button>
          </td>
        </tr>`;
      })
      .join("");
  }

  window.cancelOrder = async function (inst, id) {
    try {
      const res = await fetch(URLS.orderCancel, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instrument: inst, order_id: id }),
      });
      if (res.ok) {
        toast("Order canceled", "info");
        refreshOrders();
        refreshPortfolio();
      }
    } catch (e) {
      toast("Cancel error: " + e.message, "error");
    }
  };

  function renderOrderHistory(history) {
    const countEl = $("count-order-history");
    if (countEl) countEl.textContent = history.length;
    const tbody = $("order-history-tbody");
    if (!history.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">No trade history yet</td></tr>`;
      return;
    }

    tbody.innerHTML = history
      .slice(0, 30)
      .map((h) => {
        const sideBadge = h.side === "BUY" ? "text-success" : "text-danger";
        const date = new Date((h.filled_at || h.created_at || Date.now() / 1000) * 1000).toLocaleTimeString();
        const notional = h.notional || (h.quantity * (h.price || 0));
        return `<tr>
          <td>${date}</td>
          <td><strong>${h.instrument}</strong></td>
          <td>${h.type || "MARKET"}</td>
          <td class="${sideBadge} font-weight-bold">${h.side}</td>
          <td>$${h.price ? h.price.toFixed(2) : "—"}</td>
          <td>${h.quantity.toFixed(4)}</td>
          <td>$${notional.toFixed(2)}</td>
          <td>${h.fee ? `$${h.fee.toFixed(2)}` : "—"}</td>
          <td><span class="badge ${h.status === 'FILLED' ? 'badge-success' : 'badge-secondary'}">${h.status}</span></td>
        </tr>`;
      })
      .join("");
  }

  // --- Strategy Management ---
  async function refreshStrategies() {
    try {
      const res = await fetch(URLS.strategies);
      if (!res.ok) return;
      const data = await res.json();
      state.strategies = data;

      // Update badges and buttons
      renderStrategyStatus("grid", data.grid);
      renderStrategyStatus("dca", data.dca);
      renderStrategyStatus("radar", data.radar);
    } catch (e) {
      console.error("Strategies fetch error", e);
    }
  }

  function renderStrategyStatus(name, strat) {
    const badge = $(`${name}-bot-badge`);
    const startBtn = $(`btn-start-${name}`);
    const stopBtn = $(`btn-stop-${name}`);
    if (!strat || !badge) return;

    if (strat.status === "RUNNING") {
      badge.className = "bot-badge running";
      badge.textContent = "RUNNING";
      if (startBtn) startBtn.disabled = true;
      if (stopBtn) stopBtn.disabled = false;
    } else {
      badge.className = "bot-badge";
      badge.textContent = "STOPPED";
      if (startBtn) startBtn.disabled = false;
      if (stopBtn) stopBtn.disabled = true;
    }

    // Specific strategy data
    if (name === "dca" && strat.state) {
      $("dca-total-invested").textContent = `$${strat.state.total_invested_usdt || "0.00"}`;
      $("dca-total-tokens").textContent = strat.state.total_accumulated_tokens ? strat.state.total_accumulated_tokens.toFixed(4) : "0.0000";
      $("dca-avg-price").textContent = `$${strat.state.average_price || "0.00"}`;
      $("dca-exec-count").textContent = `${strat.state.executions_count || 0} executions`;
      if (strat.state.last_execution) {
        $("dca-last-exec").textContent = new Date(strat.state.last_execution * 1000).toLocaleTimeString();
      }
    }
  }

  function setupStrategies() {
    // Grid Launch / Stop
    $("btn-start-grid")?.addEventListener("click", async () => {
      const lower = parseFloat($("grid-lower").value);
      const upper = parseFloat($("grid-upper").value);
      const grids = parseInt($("grid-count").value, 10);
      const inv = parseFloat($("grid-investment").value);
      const inst = $("grid-instrument").value;

      if (!lower || !upper || lower >= upper) {
        toast("Please enter valid lower and upper grid bounds", "error");
        return;
      }

      try {
        const res = await fetch(URLS.gridStart, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            instrument: inst,
            lower_price: lower,
            upper_price: upper,
            grids: grids,
            total_investment: inv,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          toast("Grid Trading Bot launched!", "success");
          refreshStrategies();
        } else {
          toast(data.error || "Failed to start grid", "error");
        }
      } catch (e) {
        toast("Grid launch error: " + e.message, "error");
      }
    });

    $("btn-stop-grid")?.addEventListener("click", async () => {
      try {
        const res = await fetch(URLS.gridStop, { method: "POST" });
        if (res.ok) {
          toast("Grid Bot stopped", "info");
          refreshStrategies();
        }
      } catch (e) {
        toast("Error stopping grid: " + e.message, "error");
      }
    });

    // DCA Launch / Stop
    $("btn-start-dca")?.addEventListener("click", async () => {
      const inst = $("dca-instrument").value;
      const amt = parseFloat($("dca-amount").value);
      const interval = parseInt($("dca-interval").value, 10);
      const dip = $("dca-dip-switch").checked;

      try {
        const res = await fetch(URLS.dcaStart, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            instrument: inst,
            amount_usdt: amt,
            interval_minutes: interval,
            dip_multiplier_enabled: dip,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          toast("DCA Accumulator started!", "success");
          refreshStrategies();
        } else {
          toast(data.error || "Failed to start DCA", "error");
        }
      } catch (e) {
        toast("DCA error: " + e.message, "error");
      }
    });

    $("btn-stop-dca")?.addEventListener("click", async () => {
      try {
        const res = await fetch(URLS.dcaStop, { method: "POST" });
        if (res.ok) {
          toast("DCA Bot stopped", "info");
          refreshStrategies();
        }
      } catch (e) {
        toast("Error stopping DCA: " + e.message, "error");
      }
    });

    // Radar Launch / Stop
    $("btn-start-radar")?.addEventListener("click", async () => {
      const buyScore = parseFloat($("radar-buy-score").value);
      const sellScore = parseFloat($("radar-sell-score").value);
      const size = parseFloat($("radar-order-size").value);
      const univ = $("radar-universe").value.split(",").map((s) => s.trim());

      try {
        const res = await fetch(URLS.radarStart, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            instruments: univ,
            min_buy_score: buyScore,
            max_sell_score: sellScore,
            order_size_usdt: size,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          toast("Radar Momentum Bot activated!", "success");
          refreshStrategies();
        } else {
          toast(data.error || "Failed to start Radar bot", "error");
        }
      } catch (e) {
        toast("Radar bot error: " + e.message, "error");
      }
    });

    $("btn-stop-radar")?.addEventListener("click", async () => {
      try {
        const res = await fetch(URLS.radarStop, { method: "POST" });
        if (res.ok) {
          toast("Radar Bot stopped", "info");
          refreshStrategies();
        }
      } catch (e) {
        toast("Error stopping Radar bot: " + e.message, "error");
      }
    });
  }

  // --- AI Copilot ("Talk to Trade") ---
  function setupCopilot() {
    const trigger = $("btn-toggle-copilot");
    const drawer = $("copilot-drawer");
    const closeBtn = $("btn-close-copilot");
    const form = $("copilot-form");
    const input = $("copilot-input");

    trigger?.addEventListener("click", () => {
      drawer.classList.toggle("active");
      if (drawer.classList.contains("active")) {
        input?.focus();
      }
    });

    closeBtn?.addEventListener("click", () => {
      drawer.classList.remove("active");
    });

    // Quick chip buttons
    document.querySelectorAll(".copilot-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const prompt = chip.dataset.prompt;
        if (!prompt) return;
        input.value = prompt;
        form.dispatchEvent(new Event("submit"));
      });
    });

    // Form submit
    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const prompt = input.value.trim();
      if (!prompt) return;
      input.value = "";

      // Append User message
      appendCopilotMessage("user", prompt);

      // Append Thinking bubble
      const thinkingEl = appendCopilotMessage("assistant", `<em><i class="fas fa-spinner fa-spin text-gold mr-1"></i> Analyzing market & compiling response…</em>`);

      try {
        const res = await fetch(URLS.aiCopilot, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt, instrument: state.pair }),
        });
        const data = await res.json();
        thinkingEl.remove();

        if (res.ok) {
          appendCopilotAssistantResponse(data.reply, data.action_card);
          if (data.provider) {
            const provTag = $("copilot-provider-tag");
            if (provTag) provTag.textContent = data.provider === "openai" ? "Codex / OpenAI" : (data.provider === "gemini" ? "Antigravity AI" : "AI Ready");
          }
        } else {
          appendCopilotMessage("assistant", `<span class="text-danger"><i class="fas fa-exclamation-circle mr-1"></i> ${data.error || "Copilot encountered an issue processing request."}</span>`);
        }
      } catch (err) {
        thinkingEl.remove();
        appendCopilotMessage("assistant", `<span class="text-danger"><i class="fas fa-triangle-exclamation mr-1"></i> Failed to connect: ${err.message}</span>`);
      }
    });
  }

  function appendCopilotMessage(sender, htmlContent) {
    const body = $("copilot-chat-body");
    if (!body) return null;
    const msg = document.createElement("div");
    msg.className = `copilot-msg ${sender}`;
    msg.innerHTML = `<div class="msg-bubble">${htmlContent}</div>`;
    body.appendChild(msg);
    body.scrollTop = body.scrollHeight;
    return msg;
  }

  function appendCopilotAssistantResponse(markdownReply, actionCard) {
    const body = $("copilot-chat-body");
    if (!body) return;

    // Basic markdown conversion
    let formatted = (markdownReply || "")
      .replace(/^### (.*$)/gim, '<strong class="text-gold d-block mb-1">$1</strong>')
      .replace(/^## (.*$)/gim, '<strong class="text-gold d-block mb-1">$1</strong>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n\n/g, '<p class="mb-2"></p>')
      .replace(/\n/g, '<br>');

    let actionCardHtml = "";
    const actionId = "action-" + Date.now();
    if (actionCard && actionCard.type === "TRADE") {
      const sideBadge = actionCard.side === "BUY" ? "badge-success" : "badge-danger";
      const priceDisplay = actionCard.order_type === "LIMIT" && actionCard.price ? `$${actionCard.price.toLocaleString()}` : "Best Market Ask/Bid";

      actionCardHtml = `
        <div class="copilot-action-card mt-2">
          <div class="action-card-header">
            <div>
              <span class="badge ${sideBadge} mr-1 font-weight-bold">${actionCard.side}</span>
              <span class="badge badge-dark">${actionCard.order_type}</span>
            </div>
            <strong class="text-white">${actionCard.instrument}</strong>
          </div>
          <div class="action-param-grid">
            <div class="action-param">Quantity: <strong>${actionCard.quantity}</strong></div>
            <div class="action-param">Price: <strong>${priceDisplay}</strong></div>
            <div class="action-param">Total Value: <strong>$${actionCard.notional_usdt.toLocaleString()} USDT</strong></div>
            <div class="action-param">Mode: <strong class="text-gold">${state.mode.toUpperCase()}</strong></div>
          </div>
          <button class="btn-confirm-action" id="${actionId}">
            <i class="fas fa-bolt"></i> Confirm & Execute Trade
          </button>
        </div>
      `;
    }

    const msg = document.createElement("div");
    msg.className = "copilot-msg assistant";
    msg.innerHTML = `<div class="msg-bubble">${formatted}${actionCardHtml}</div>`;
    body.appendChild(msg);
    body.scrollTop = body.scrollHeight;

    // Attach click handler to Action Card execution button
    if (actionCard && $(actionId)) {
      $(actionId).addEventListener("click", async () => {
        const btn = $(actionId);
        btn.disabled = true;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Submitting to Crypto.com…`;

        try {
          const res = await fetch(URLS.aiExecute, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(actionCard),
          });
          const data = await res.json();
          if (res.ok) {
            btn.className = "btn-confirm-action bg-success text-white";
            btn.innerHTML = `<i class="fas fa-check-circle"></i> Executed Successfully!`;
            toast(`⚡ ${actionCard.side} order executed via Copilot!`, "success");
            refreshPortfolio();
            refreshOrders();
          } else {
            btn.disabled = false;
            btn.innerHTML = `<i class="fas fa-triangle-exclamation"></i> Retry Execution`;
            toast(data.error || "Execution failed", "error");
          }
        } catch (e) {
          btn.disabled = false;
          btn.innerHTML = `<i class="fas fa-triangle-exclamation"></i> Error - Retry`;
          toast("Action execution error: " + e.message, "error");
        }
      });
    }
  }

  // --- AI Radar & Technical Analyst ---
  function setupRadarTab() {
    state.radarPair = "BTC_USDT";

    // Pair selection chips
    document.querySelectorAll("#radar-pair-selector button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#radar-pair-selector button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.radarPair = btn.dataset.pair;
        refreshRadar(state.radarPair);
      });
    });

    // Manual Refresh button
    $("btn-refresh-radar")?.addEventListener("click", () => {
      refreshRadar(state.radarPair);
    });

    // Apply Setup to Order Form
    $("btn-apply-radar-setup")?.addEventListener("click", () => {
      if (!state.currentRadarSetup) return;
      const setup = state.currentRadarSetup;

      // Switch to Terminal tab
      document.querySelectorAll(".tab-link").forEach((b) => {
        if (b.dataset.tab === "terminal") b.click();
      });

      // Switch pair if different
      const pairChip = $(`chip-${setup.instrument}`) || document.querySelector(`.pair-chip[data-pair="${setup.instrument}"]`);
      if (pairChip) pairChip.click();

      // Set side to BUY (or SELL depending on signal)
      if (setup.signal === "DEFENSIVE" || setup.signal === "TAKE PROFIT") {
        $("btn-side-sell")?.click();
      } else {
        $("btn-side-buy")?.click();
      }

      // Select Limit
      document.querySelectorAll(".order-type-group .btn-type").forEach((b) => {
        if (b.dataset.type === "LIMIT") b.click();
      });

      // Set price
      if ($("order-price")) {
        $("order-price").value = setup.levels.recommended_entry || setup.last_price;
      }

      // Set 15% quantity
      const avail = state.balances["USDT"] || 1000;
      const entryPx = setup.levels.recommended_entry || setup.last_price;
      if (entryPx > 0 && $("order-qty")) {
        $("order-qty").value = ((avail * 0.15) / entryPx).toFixed(5);
      }

      recalcOrderSummary();
      toast(`🎯 Applied AI Radar setup (${setup.instrument} @ $${entryPx.toLocaleString()}) to Order Form!`, "success");
    });
  }

  async function refreshRadar(pair = state.radarPair || "BTC_USDT") {
    try {
      const url = `${URLS.aiRadar}?instrument=${encodeURIComponent(pair)}`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      state.currentRadarSetup = data;

      // Render Symbol & Badge
      const symEl = $("radar-symbol");
      if (symEl) symEl.textContent = data.instrument;

      const badge = $("radar-signal-badge");
      if (badge) {
        badge.className = "radar-signal-pill " + (data.signal.toLowerCase().replace(" ", "-"));
        badge.textContent = data.signal;
      }

      // Confidence
      const confVal = $("radar-confidence-val");
      const confBar = $("radar-confidence-bar");
      if (confVal) confVal.textContent = `${data.confidence}%`;
      if (confBar) confBar.style.width = `${data.confidence}%`;

      const lastScan = $("radar-last-scan-time");
      if (lastScan) lastScan.textContent = "Scanned " + new Date(data.timestamp * 1000).toLocaleTimeString();

      // Liquidity / Depth
      const depthRatio = $("radar-depth-ratio");
      if (depthRatio) depthRatio.textContent = `${data.depth_ratio.toFixed(2)}x`;
      const depthStatus = $("radar-depth-status");
      if (depthStatus) depthStatus.textContent = data.depth_ratio >= 1.0 ? "Buyer Dominated" : "Seller Dominated";

      const bidPct = Math.min(85, Math.max(15, (data.depth_ratio / (data.depth_ratio + 1)) * 100));
      const bidsBar = $("radar-depth-bids");
      const asksBar = $("radar-depth-asks");
      if (bidsBar) bidsBar.style.width = `${bidPct}%`;
      if (asksBar) asksBar.style.width = `${100 - bidPct}%`;

      const spreadVal = $("radar-spread-val");
      if (spreadVal) spreadVal.textContent = data.indicators.spread.value;

      // Indicators
      const rsiVal = $("radar-rsi-val");
      if (rsiVal) rsiVal.textContent = `${data.rsi_14} (${data.indicators.rsi.status})`;
      const atrVal = $("radar-atr-val");
      if (atrVal) atrVal.textContent = data.indicators.volatility_range.value;
      const chgVal = $("radar-change-val");
      if (chgVal) {
        chgVal.textContent = `${data.change_24h >= 0 ? "+" : ""}${data.change_24h.toFixed(2)}%`;
        chgVal.className = data.change_24h >= 0 ? "font-weight-bold text-success" : "font-weight-bold text-danger";
      }
      const pxVal = $("radar-price-val");
      if (pxVal) pxVal.textContent = `$${data.last_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

      // Targets
      const r2 = $("target-r2");
      const r1 = $("target-r1");
      const entry = $("target-entry");
      const s1 = $("target-s1");
      const s2 = $("target-s2");
      const sl = $("target-sl");

      if (r2) r2.textContent = `$${data.levels.resistance_2.toLocaleString()}`;
      if (r1) r1.textContent = `$${data.levels.resistance_1.toLocaleString()}`;
      if (entry) entry.textContent = `$${data.levels.recommended_entry.toLocaleString()}`;
      if (s1) s1.textContent = `$${data.levels.support_1.toLocaleString()}`;
      if (s2) s2.textContent = `$${data.levels.support_2.toLocaleString()}`;
      if (sl) sl.textContent = `$${data.levels.stop_loss.toLocaleString()}`;

      // Narrative
      const narr = $("radar-narrative-text");
      if (narr) {
        narr.innerHTML = data.narrative.replace(/\*\*(.*?)\*\*/g, '<strong class="text-gold">$1</strong>');
      }
    } catch (e) {
      console.error("AI Radar fetch error", e);
    }
  }

  // --- Seconds Scalper (AI Fast-Cycle Trading & TradingView & Auto-Pilot) ---
  function renderTradingViewSecondsChart(pair = state.secondsPair || "BTC_USDT", interval = state.tvInterval || "1") {
    const container = $("tradingview_seconds_chart");
    if (!container) return;

    const cleanPair = pair.replace("_", "");
    const tvSymbol = `BINANCE:${cleanPair}`;
    const lbl = $("tv-seconds-symbol-lbl");
    if (lbl) lbl.textContent = `${tvSymbol} • ${interval}m`;

    container.innerHTML = "";
    if (typeof TradingView !== "undefined") {
      try {
        new TradingView.widget({
          autosize: true,
          symbol: tvSymbol,
          interval: interval,
          timezone: "Etc/UTC",
          theme: "dark",
          style: "1",
          locale: "en",
          toolbar_bg: "#070709",
          enable_publishing: false,
          hide_side_toolbar: false,
          allow_symbol_change: true,
          container_id: "tradingview_seconds_chart",
        });
        return;
      } catch (e) {
        console.warn("TradingView widget init error:", e);
      }
    }

    const iframe = document.createElement("iframe");
    iframe.style.width = "100%";
    iframe.style.height = "100%";
    iframe.style.border = "none";
    iframe.src = `https://s.tradingview.com/widgetembed/?symbol=${encodeURIComponent(tvSymbol)}&interval=${interval}&theme=dark&style=1&locale=en`;
    container.appendChild(iframe);
  }
  window.renderTradingViewSecondsChart = renderTradingViewSecondsChart;

  async function refreshAutopilotStatus() {
    try {
      const res = await fetch(URLS.secondsAutopilotStatus);
      if (!res.ok) return;
      const data = await res.json();
      state.autopilotEnabled = Boolean(data.enabled);

      const badge = $("sec-autopilot-badge");
      if (badge) {
        if (data.enabled) {
          badge.textContent = `ACTIVE (${(data.engine || 'antigravity').toUpperCase()})`;
          badge.className = "badge badge-autopilot-active ml-2";
        } else {
          badge.textContent = "STANDBY (OFF)";
          badge.className = "badge badge-secondary ml-2";
        }
      }

      const btnLabel = $("autopilot-toggle-label");
      const btnToggle = $("btn-toggle-autopilot");
      if (btnLabel && btnToggle) {
        btnLabel.textContent = data.enabled ? "Stop Auto-Pilot" : "Start Auto-Pilot";
        btnToggle.className = data.enabled ? "btn btn-sm btn-danger" : "btn btn-sm btn-outline-warning";
      }

      const narr = $("autopilot-status-narrative");
      if (narr) {
        const icon = data.enabled ? '<i class="fas fa-satellite-dish text-success mr-1"></i>' : '<i class="fas fa-pause text-muted mr-1"></i>';
        narr.innerHTML = `${icon} ${data.last_action || 'Standby'}`;
      }

      const countEl = $("autopilot-total-trades");
      if (countEl) countEl.textContent = data.total_auto_trades || 0;
    } catch (e) {
      console.debug("Autopilot status error:", e);
    }
  }

  function setupSecondsScalper() {
    // Pair selector buttons
    document.querySelectorAll("#seconds-pair-selector button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#seconds-pair-selector button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.secondsPair = btn.dataset.pair || "BTC_USDT";
        const sym = $("sec-active-symbol");
        if (sym) sym.textContent = state.secondsPair;
        renderTradingViewSecondsChart(state.secondsPair, state.tvInterval);
        refreshSecondsAdvice(state.secondsPair, state.secondsAiEngine);
      });
    });

    // TradingView Interval Selector
    document.querySelectorAll("#tv-timeframe-selector button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#tv-timeframe-selector button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.tvInterval = btn.dataset.tf || "1";
        renderTradingViewSecondsChart(state.secondsPair, state.tvInterval);
      });
    });

    // AI Engine Selector
    document.querySelectorAll("#seconds-ai-engine-selector button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#seconds-ai-engine-selector button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.secondsAiEngine = btn.dataset.engine || "antigravity";
        const lbl = $("sec-model-lbl");
        if (lbl) {
          lbl.textContent = state.secondsAiEngine === "codex" ? "Codex AI" : (state.secondsAiEngine === "consensus" ? "Dual Consensus" : "Antigravity AI");
        }
        refreshSecondsAdvice(state.secondsPair, state.secondsAiEngine);
      });
    });

    // Duration selector pills
    document.querySelectorAll("#seconds-duration-group button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#seconds-duration-group button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.secondsDuration = parseInt(btn.dataset.duration) || 30;
      });
    });

    // Quick Stake Chips
    document.querySelectorAll(".sec-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        document.querySelectorAll(".sec-chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        const val = parseFloat(chip.dataset.stake) || 10;
        state.secondsStake = val;
        const input = $("seconds-stake-input");
        if (input) input.value = val;
        recalcSecondsPotential();
      });
    });

    // Stake custom input
    const stakeInput = $("seconds-stake-input");
    if (stakeInput) {
      stakeInput.addEventListener("input", () => {
        const val = parseFloat(stakeInput.value) || 0;
        state.secondsStake = val;
        document.querySelectorAll(".sec-chip").forEach((c) => {
          if (parseFloat(c.dataset.stake) === val) {
            c.classList.add("active");
          } else {
            c.classList.remove("active");
          }
        });
        recalcSecondsPotential();
      });
    }

    function recalcSecondsPotential() {
      const profitEl = $("sec-potential-profit");
      if (profitEl) {
        const stake = parseFloat($("seconds-stake-input")?.value) || 0;
        const profit = stake * 0.85;
        profitEl.textContent = `+$${profit.toFixed(2)} USDT`;
      }
    }

    // Refresh advice manually
    $("btn-refresh-seconds-advice")?.addEventListener("click", () => {
      refreshSecondsAdvice(state.secondsPair, state.secondsAiEngine);
      toast(`Scanned live market tape with ${state.secondsAiEngine.toUpperCase()}`, "info");
    });

    // FLASH CALL button
    $("btn-flash-call")?.addEventListener("click", () => {
      submitSecondsTrade("CALL");
    });

    // FLASH PUT button
    $("btn-flash-put")?.addEventListener("click", () => {
      submitSecondsTrade("PUT");
    });

    // Auto-Pilot Controls
    $("btn-toggle-autopilot")?.addEventListener("click", async () => {
      const willEnable = !state.autopilotEnabled;
      const eng = $("autopilot-engine-select")?.value || state.secondsAiEngine;
      const conf = state.autopilotConfidence || 72;
      const stake = state.secondsStake || 10;
      const dur = state.secondsDuration || 30;

      try {
        const res = await fetch(URLS.secondsAutopilotToggle, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            enabled: willEnable,
            engine: eng,
            min_confidence: conf,
            stake_usdt: stake,
            duration_seconds: dur,
            instrument: state.secondsPair,
          }),
        });
        const data = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || "Failed to toggle Auto-Pilot");

        state.autopilotEnabled = willEnable;
        toast(willEnable ? "🤖 Autonomous AI Scalper ACTIVE!" : "⏸️ Auto-Pilot stopped.", willEnable ? "success" : "info");
        await refreshAutopilotStatus();
      } catch (err) {
        toast(err.message, "error");
      }
    });

    $("autopilot-engine-select")?.addEventListener("change", async (e) => {
      if (state.autopilotEnabled) {
        await fetch(URLS.secondsAutopilotToggle, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: true, engine: e.target.value }),
        });
        refreshAutopilotStatus();
      }
    });

    document.querySelectorAll("#autopilot-conf-selector button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        document.querySelectorAll("#autopilot-conf-selector button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.autopilotConfidence = parseInt(btn.dataset.conf) || 72;
        if (state.autopilotEnabled) {
          await fetch(URLS.secondsAutopilotToggle, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: true, min_confidence: state.autopilotConfidence }),
          });
          refreshAutopilotStatus();
        }
      });
    });
  }

  async function refreshSecondsAdvice(pair = state.secondsPair || "BTC_USDT", engine = state.secondsAiEngine || "antigravity") {
    try {
      const url = `${URLS.secondsAdvice}?instrument=${encodeURIComponent(pair)}&provider=${encodeURIComponent(engine)}`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();

      const sym = $("sec-active-symbol");
      if (sym) sym.textContent = data.instrument;

      const modelLbl = $("sec-model-lbl");
      if (modelLbl) {
        const prov = (data.provider || engine).toLowerCase();
        modelLbl.textContent = prov === "codex" ? "Codex AI" : (prov === "consensus" ? "Dual Consensus" : "Antigravity AI");
      }

      const dirPill = $("sec-signal-direction");
      if (dirPill) {
        if (data.direction === "CALL") {
          dirPill.className = "seconds-signal-pill signal-call";
          dirPill.textContent = "CALL / LONG 🚀";
        } else {
          dirPill.className = "seconds-signal-pill signal-put";
          dirPill.textContent = "PUT / SHORT 🔻";
        }
      }

      const probText = $("sec-prob-text");
      const probBar = $("sec-prob-bar");
      if (probText) probText.textContent = `${data.probability}%`;
      if (probBar) {
        probBar.style.width = `${data.probability}%`;
        probBar.className = data.direction === "CALL" ? "progress-bar bg-gradient-success" : "progress-bar bg-danger";
      }

      const depthMetric = $("sec-metric-depth");
      if (depthMetric) {
        const d = data.depth_ratio || 1.0;
        depthMetric.textContent = `${d.toFixed(2)}x ${d >= 1.0 ? "Bid" : "Ask"}`;
      }

      const takerMetric = $("sec-metric-taker");
      if (takerMetric) {
        const t = data.taker_ratio || 0.5;
        takerMetric.textContent = `${Math.round(t * 100)}% Buy`;
      }

      const tickMetric = $("sec-metric-tick");
      if (tickMetric) {
        tickMetric.textContent = data.direction === "CALL" ? "Bullish ▲" : "Bearish ▼";
        tickMetric.className = data.direction === "CALL" ? "font-weight-bold text-success" : "font-weight-bold text-danger";
      }

      const ratBox = $("sec-rationale-text");
      if (ratBox) ratBox.textContent = data.rationale || "AI synthesizing real-time order flow…";

      // Also update available USDT
      const availEl = $("sec-avail-usdt");
      if (availEl) {
        const avail = state.balances["USDT"] || 0;
        availEl.textContent = `$${avail.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      }

      const modeBadge = $("sec-mode-badge");
      if (modeBadge) {
        modeBadge.textContent = state.mode === "live" ? "LIVE REAL TRADING" : "PAPER SIMULATION";
        modeBadge.className = state.mode === "live" ? "badge badge-danger" : "badge badge-info";
      }
    } catch (e) {
      console.error("Seconds advice fetch error:", e);
    }
  }

  async function submitSecondsTrade(direction) {
    const stakeInput = $("seconds-stake-input");
    const stake = parseFloat(stakeInput?.value) || 10;
    if (stake <= 0) {
      toast("Please enter a valid stake in USDT", "error");
      return;
    }

    const duration = state.secondsDuration || 30;
    const pair = state.secondsPair || "BTC_USDT";
    const aiLabel = state.secondsAiEngine === "codex" ? "Codex AI" : (state.secondsAiEngine === "consensus" ? "Dual Consensus" : "Antigravity AI");

    const btnCall = $("btn-flash-call");
    const btnPut = $("btn-flash-put");
    if (btnCall) btnCall.disabled = true;
    if (btnPut) btnPut.disabled = true;

    try {
      const res = await fetch(URLS.secondsTrade, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instrument: pair,
          direction: direction,
          stake_usdt: stake,
          duration_seconds: duration,
          ai_engine: aiLabel,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || "Failed to execute seconds scalp trade");
      }

      toast(`⚡ Flash ${direction} launched for ${duration}s on ${pair} (${aiLabel})!`, "success");
      await refreshSecondsActive();
      await refreshPortfolio();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      if (btnCall) btnCall.disabled = false;
      if (btnPut) btnPut.disabled = false;
    }
  }

  async function refreshSecondsActive() {
    try {
      const res = await fetch(URLS.secondsActive);
      if (!res.ok) return;
      const data = await res.json();
      const trades = data.active_trades || [];

      const countBadge = $("sec-active-count-badge");
      if (countBadge) {
        countBadge.textContent = `${trades.length} Active`;
        countBadge.className = trades.length > 0 ? "badge badge-warning ml-2" : "badge badge-dark ml-2";
      }

      const container = $("seconds-active-cards-container");
      if (!container) return;

      if (trades.length === 0) {
        container.innerHTML = `
          <div class="seconds-empty-state text-center py-4 w-100" id="seconds-empty-state">
            <i class="fas fa-stopwatch text-muted fa-3x mb-3"></i>
            <h5 class="text-white">No Active Seconds Scalps</h5>
            <p class="text-muted small mb-0">Choose your stake and duration, then click <strong>FLASH CALL</strong> or <strong>FLASH PUT</strong> to begin a micro-cycle.</p>
          </div>
        `;
        return;
      }

      container.innerHTML = trades
        .map((t) => {
          const isCall = t.direction === "CALL";
          const dirColor = isCall ? "#00e676" : "#ff334b";
          const cardClass = isCall ? "call-card" : "put-card";
          const remSec = Math.max(0, Math.ceil(t.remaining_seconds));
          const totalSec = t.duration_seconds || 30;
          const pctRemaining = Math.max(0, Math.min(1, remSec / totalSec));
          const radius = 36;
          const circum = 2 * Math.PI * radius; // ~226.19
          const strokeOffset = circum * (1 - pctRemaining);
          const isProfit = t.floating_pnl_usdt > 0;
          const pnlColorClass = isProfit ? "text-success" : "text-danger";
          const pnlSign = isProfit ? "+" : "";

          return `
            <div class="seconds-active-card ${cardClass}" id="card-${t.trade_id}">
              <div class="d-flex justify-content-between align-items-start mb-2">
                <div>
                  <span class="badge ${isCall ? "badge-success" : "badge-danger"} font-weight-bold mr-1">
                    ${isCall ? "▲ CALL (LONG)" : "▼ PUT (SHORT)"}
                  </span>
                  <strong class="text-white font-mono">${t.instrument}</strong>
                </div>
                <span class="small text-muted font-mono font-weight-bold">$${t.stake_usdt.toFixed(2)} Stake</span>
              </div>

              <div class="d-flex align-items-center justify-content-between my-3">
                <!-- Circular SVG Countdown -->
                <div class="svg-countdown-wrap">
                  <svg width="90" height="90">
                    <circle class="countdown-bg-circle" cx="45" cy="45" r="36"></circle>
                    <circle class="countdown-progress-circle" cx="45" cy="45" r="36"
                      style="stroke: ${dirColor}; stroke-dasharray: ${circum}; stroke-dashoffset: ${strokeOffset};">
                    </circle>
                  </svg>
                  <div class="countdown-number">${remSec}s</div>
                </div>

                <!-- Live Floating PnL & Tick Price -->
                <div class="text-right flex-grow-1 ml-3">
                  <div class="small text-muted mb-1">FLOATING PnL</div>
                  <div class="h4 font-weight-bold ${pnlColorClass} mb-1 font-mono">
                    ${pnlSign}$${t.floating_pnl_usdt.toFixed(2)} (${pnlSign}${t.floating_pnl_pct.toFixed(1)}%)
                  </div>
                  <div class="small font-mono text-muted">
                    Entry: <span class="text-white">$${t.entry_price.toLocaleString()}</span>
                  </div>
                  <div class="small font-mono text-muted">
                    Now: <span class="text-gold font-weight-bold">$${t.current_price.toLocaleString()}</span>
                    <span class="${t.delta_pct >= 0 ? "text-success" : "text-danger"}">(${t.delta_pct >= 0 ? "▲ +" : "▼ "}${t.delta_pct.toFixed(2)}%)</span>
                  </div>
                </div>
              </div>

              <!-- Early Cashout Action -->
              <div class="d-flex justify-content-between align-items-center mt-2 pt-2 border-top border-secondary">
                <span class="small text-muted">Auto-settles in <strong>${remSec}s</strong></span>
                <button class="btn btn-sm btn-cashout-early" onclick="window.cashoutSecondsTrade('${t.trade_id}')">
                  <i class="fas fa-hand-holding-dollar mr-1"></i> Cash Out ($${t.cashout_value_usdt.toFixed(2)})
                </button>
              </div>
            </div>
          `;
        })
        .join("");
    } catch (e) {
      console.error("Seconds active trades fetch error:", e);
    }
  }

  async function cashoutSecondsTrade(tradeId) {
    if (!tradeId) return;
    try {
      const res = await fetch(URLS.secondsCashout, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trade_id: tradeId }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || "Cashout failed");
      }
      toast(`💰 Cashed out early! Secured $${data.trade.pnl_usdt >= 0 ? '+' : ''}${data.trade.pnl_usdt.toFixed(2)} USDT`, "success");
      await refreshSecondsActive();
      await refreshSecondsHistory();
      await refreshPortfolio();
    } catch (err) {
      toast(err.message, "error");
    }
  }
  window.cashoutSecondsTrade = cashoutSecondsTrade;

  async function refreshSecondsHistory() {
    try {
      const res = await fetch(URLS.secondsHistory);
      if (!res.ok) return;
      const data = await res.json();

      const totalEl = $("sec-stat-total");
      if (totalEl) totalEl.textContent = data.total_trades || 0;

      const winrateEl = $("sec-stat-winrate");
      if (winrateEl) winrateEl.textContent = `${data.win_rate_pct || 0}%`;

      const wlEl = $("sec-stat-wl");
      if (wlEl) wlEl.textContent = `${data.wins || 0}W / ${data.losses || 0}L`;

      const pnlEl = $("sec-stat-pnl");
      if (pnlEl) {
        const p = data.total_pnl_usdt || 0;
        pnlEl.textContent = `${p >= 0 ? "+" : ""}$${p.toFixed(2)}`;
        pnlEl.className = p >= 0 ? "font-weight-bold text-success" : "font-weight-bold text-danger";
      }

      const tbody = $("seconds-history-tbody");
      if (!tbody) return;

      const trades = data.trades || [];
      if (trades.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" class="text-center text-muted py-4">No scalps executed yet in this session.</td></tr>`;
        return;
      }

      tbody.innerHTML = trades
        .map((h) => {
          const isCall = h.direction === "CALL";
          const pnl = h.pnl_usdt || 0;
          const isProfit = pnl > 0;
          const pnlColorClass = isProfit ? "text-success font-weight-bold" : (pnl < 0 ? "text-danger font-weight-bold" : "text-muted");
          const pnlSign = isProfit ? "+" : "";

          let statusBadge = `<span class="badge badge-secondary">${h.status}</span>`;
          if (h.status === "WIN") {
            statusBadge = `<span class="badge-scalp-win"><i class="fas fa-check-circle mr-1"></i>WIN (+85%)</span>`;
          } else if (h.status === "LOSS") {
            statusBadge = `<span class="badge-scalp-loss"><i class="fas fa-times-circle mr-1"></i>LOSS</span>`;
          } else if (h.status && h.status.startsWith("CASHED_OUT")) {
            statusBadge = `<span class="badge-scalp-cashed"><i class="fas fa-hand-holding-dollar mr-1"></i>CASHED OUT</span>`;
          }

          let aiBadgeClass = "badge-ai-antigravity";
          if (h.ai_engine === "Codex AI") aiBadgeClass = "badge-ai-codex";
          if (h.ai_engine === "Dual Consensus") aiBadgeClass = "badge-ai-consensus";
          const aiBadge = `<span class="badge ${aiBadgeClass}">${h.ai_engine || "Antigravity AI"}</span>`;

          const timeStr = h.closed_at ? new Date(h.closed_at * 1000).toLocaleTimeString() : "—";
          const shortId = h.trade_id.replace("sec_", "").substring(0, 8);

          return `
            <tr>
              <td class="font-mono text-muted">#${shortId}</td>
              <td class="font-mono font-weight-bold text-white">${h.instrument}</td>
              <td>${aiBadge}</td>
              <td><span class="badge ${isCall ? "badge-success" : "badge-danger"}">${isCall ? "CALL ▲" : "PUT ▼"}</span></td>
              <td class="font-mono">${h.duration_seconds}s</td>
              <td class="font-mono">$${h.stake_usdt.toFixed(2)}</td>
              <td class="font-mono text-white">$${h.entry_price ? h.entry_price.toLocaleString() : "—"}</td>
              <td class="font-mono text-gold">$${h.exit_price ? h.exit_price.toLocaleString() : "—"}</td>
              <td class="font-mono ${pnlColorClass}">${pnlSign}$${pnl.toFixed(2)} (${pnlSign}${h.pnl_pct || 0}%)</td>
              <td>${statusBadge}</td>
              <td class="text-muted small">${timeStr}</td>
            </tr>
          `;
        })
        .join("");
    } catch (e) {
      console.error("Seconds history fetch error:", e);
    }
  }

  // --- Settings Modal & API Credentials ---
  function setupSettingsModal() {
    $("btn-open-settings")?.addEventListener("click", () => {
      if (window.$ && window.$.fn && window.$.fn.modal) {
        window.$("#settingsModal").modal("show");
      } else {
        const modal = $("settingsModal");
        modal.classList.add("show");
        modal.style.display = "block";
      }
    });

    $("btn-save-credentials")?.addEventListener("click", async () => {
      const apiKey = $("input-api-key").value.trim();
      const apiSecret = $("input-api-secret").value.trim();
      const fb = $("credentials-feedback");

      if (!apiKey || !apiSecret) {
        fb.innerHTML = `<div class="alert alert-danger">Both Key and Secret are required</div>`;
        return;
      }

      fb.innerHTML = `<div class="alert alert-secondary">Validating HMAC-SHA256 signature with Crypto.com Exchange…</div>`;

      try {
        const res = await fetch(URLS.credentials, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret }),
        });
        const data = await res.json();
        if (data.valid) {
          fb.innerHTML = `<div class="alert alert-success"><i class="fas fa-check-circle"></i> Connected! Successfully authenticated with Crypto.com Pro.</div>`;
          toast("Crypto.com API credentials validated!", "success");
        } else {
          fb.innerHTML = `<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> Credentials saved, but connection returned: ${data.error || "Authentication failed"}</div>`;
        }
      } catch (e) {
        fb.innerHTML = `<div class="alert alert-danger">Error: ${e.message}</div>`;
      }
    });

    $("btn-reset-paper")?.addEventListener("click", async () => {
      try {
        const res = await fetch("/crypto-com/api/paper/reset", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ amount: 10000.0 }),
        });
        if (res.ok) {
          toast("Virtual paper balance reset to $10,000.00 USDT", "success");
          await refreshPortfolio();
          await refreshSecondsAdvice();
        }
      } catch (e) {
        toast(e.message, "error");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", init);
  if (document.readyState === "complete" || document.readyState === "interactive") {
    init();
  }
})();
