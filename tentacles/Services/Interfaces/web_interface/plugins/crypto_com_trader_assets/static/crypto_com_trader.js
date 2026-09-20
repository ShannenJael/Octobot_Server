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

    await fetchStatus();
    await refreshMarket();
    await refreshPortfolio();
    await refreshOrders();
    await refreshStrategies();

    // Start polling intervals
    setInterval(refreshMarket, 3500);
    setInterval(refreshPortfolio, 7000);
    setInterval(refreshOrders, 6000);
    setInterval(refreshStrategies, 10000);
  }

  // --- Tabs Navigation ---
  function setupTabs() {
    document.querySelectorAll(".tab-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-link").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab-pane").forEach((p) => (p.style.display = "none"));
        btn.classList.add("active");
        const target = $(`tab-${btn.dataset.tab}`);
        if (target) {
          target.style.display = "block";
          if (btn.dataset.tab === "terminal") drawChart();
        }
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
  }

  document.addEventListener("DOMContentLoaded", init);
  if (document.readyState === "complete" || document.readyState === "interactive") {
    init();
  }
})();
