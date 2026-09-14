(() => {
  const root = document.getElementById("market-radar");
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  let scan = null;
  let selected = null;
  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
  const number = (value, digits=2) => Number(value).toLocaleString(undefined, {maximumFractionDigits:digits});

  async function request(url, options={}) {
    const response = await fetch(url, {headers:{"Content-Type":"application/json"}, ...options});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
  }

  function updateStudio(scanData) {
    if (!scanData) return;

    // Weights display
    const weights = scanData.active_weights || {};
    const modelStatus = scanData.model_status || {};
    const keys = [
      ["trend", "Trend"],
      ["momentum", "Momentum"],
      ["liquidity", "Liquidity"],
      ["volatility", "Volatility"],
      ["relative_strength", "Rel Strength"]
    ];

    if ($("radar-weights-display") && Object.keys(weights).length > 0) {
      $("radar-weights-display").innerHTML = keys.map(([k, label]) => {
        const pct = Math.round((weights[k] || 0.2) * 100);
        return `
          <div class="weight-bar-row">
            <span>${escapeHtml(label)}</span>
            <div class="progress">
              <div class="progress-bar bg-info" role="progressbar" style="width: ${pct}%">${pct}%</div>
            </div>
          </div>`;
      }).join("");
    }

    if ($("train-status-badge")) {
      const isCustom = modelStatus.is_custom_trained;
      $("train-status-badge").textContent = isCustom ? "Trained (Active)" : "Default Weights";
      $("train-status-badge").className = `badge badge-pill ${isCustom ? "badge-success" : "badge-dark"}`;
    }
    if ($("train-samples")) $("train-samples").textContent = modelStatus.sample_count || modelStatus.resolved_samples || 0;
    if ($("train-accuracy")) $("train-accuracy").textContent = modelStatus.directional_accuracy_pct ? `${modelStatus.directional_accuracy_pct}%` : "—";
    if ($("train-loss")) $("train-loss").textContent = modelStatus.loss !== undefined ? modelStatus.loss : "—";

    // Strategy parameters display
    const params = scanData.strategy_params || {};
    const p = params.parameters || params;
    if ($("opt-buy-score") && p.min_buy_score !== undefined) $("opt-buy-score").textContent = number(p.min_buy_score, 1);
    if ($("opt-tp") && p.take_profit_pct !== undefined) $("opt-tp").textContent = `+${number(p.take_profit_pct, 1)}%`;
    if ($("opt-sl") && p.stop_loss_pct !== undefined) $("opt-sl").textContent = `-${number(p.stop_loss_pct, 1)}%`;
    if ($("opt-hold") && p.max_holding_hours !== undefined) $("opt-hold").textContent = `${p.max_holding_hours}h`;

    const metrics = params.metrics || {};
    if ($("opt-win-rate")) $("opt-win-rate").textContent = metrics.win_rate_pct !== undefined ? `${number(metrics.win_rate_pct, 1)}%` : "—";
    if ($("opt-profit-factor")) $("opt-profit-factor").textContent = metrics.profit_factor !== undefined ? number(metrics.profit_factor, 2) : "—";
    if ($("opt-sharpe")) $("opt-sharpe").textContent = metrics.sharpe_ratio !== undefined ? number(metrics.sharpe_ratio, 2) : "—";
    if ($("opt-drawdown")) $("opt-drawdown").textContent = metrics.max_drawdown_pct !== undefined ? `-${number(metrics.max_drawdown_pct, 1)}%` : "—";
  }

  function updateSentiment(sentimentData) {
    if (!sentimentData) return;
    const fng = sentimentData.fear_and_greed || {};
    const val = Number(fng.value) || 50;
    const classification = fng.classification || "Neutral";

    if ($("fng-val")) $("fng-val").textContent = val;
    if ($("fng-classification")) $("fng-classification").textContent = classification;

    if ($("fng-needle")) {
      const deg = -90 + (Math.max(0, Math.min(100, val)) / 100) * 180;
      $("fng-needle").style.transform = `rotate(${deg}deg)`;
    }

    if ($("fng-badge")) {
      $("fng-badge").textContent = `${classification} (${val}/100)`;
      let badgeClass = "badge-secondary";
      if (val >= 65) badgeClass = "badge-success";
      else if (val >= 55) badgeClass = "badge-info";
      else if (val <= 30) badgeClass = "badge-danger";
      else if (val <= 45) badgeClass = "badge-warning";
      $("fng-badge").className = `badge badge-pill ${badgeClass}`;
    }

    if ($("fng-composite-val")) {
      $("fng-composite-val").textContent = `${sentimentData.composite_score || val}/100`;
    }
  }

  function renderNews(articles) {
    if (!$("news-feed")) return;
    if (!articles || articles.length === 0) {
      $("news-feed").innerHTML = '<div class="text-center py-4 text-muted">No matching news headlines found.</div>';
      return;
    }
    $("news-feed").innerHTML = articles.map(item => `
      <div class="news-card-item">
        <div class="news-headline">
          <a href="${escapeHtml(item.link || '#')}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>
        </div>
        <div class="news-meta">
          <span>${escapeHtml(item.source || 'News')} · ${escapeHtml((item.published_at || '').slice(0, 16))}</span>
          <span class="sentiment-pill sentiment-pill-${escapeHtml(item.sentiment_tag || 'neutral')}">${escapeHtml(item.sentiment_tag || 'neutral')}</span>
        </div>
      </div>`).join("");
  }

  async function loadNews(symbol="") {
    if (!root.dataset.newsUrl) return;
    try {
      const url = `${root.dataset.newsUrl}?symbol=${encodeURIComponent(symbol)}&limit=15`;
      const res = await request(url);
      renderNews(res.news || []);
    } catch (err) {
      if ($("news-feed")) $("news-feed").innerHTML = `<div class="text-center py-4 text-danger">${escapeHtml(err.message)}</div>`;
    }
  }

  async function load(force=false) {
    $("radar-refresh").disabled = true;
    $("radar-error").classList.add("d-none");
    try {
      const url = `${root.dataset.scanUrl}?limit=${$("radar-limit").value}&force=${force}`;
      scan = await request(url);
      $("radar-source").textContent = scan.source;
      $("radar-model").textContent = scan.model_version;
      $("radar-count").textContent = scan.results.length;
      $("radar-time").textContent = new Date(scan.generated_at * 1000).toLocaleTimeString();
      $("radar-results").innerHTML = scan.results.map((item, index) => `
        <tr data-instrument="${escapeHtml(item.instrument)}">
          <td>${index + 1}</td><td><strong>${escapeHtml(item.symbol)}</strong><br><small class="radar-muted">${escapeHtml(item.rating)}</small></td>
          <td><span class="score-pill score-${escapeHtml(item.rating)}">${number(item.score,1)}</span></td>
          <td class="${item.change_24h >= 0 ? "radar-positive":"radar-negative"}">${item.change_24h >= 0 ? "+":""}${number(item.change_24h)}%</td>
          <td>$${number(item.quote_volume_24h,0)}</td><td>${number(item.spread_bps)} bp</td><td>${number(item.rsi_14,1)}</td>
          <td>${number(item.risk_penalty,1)}</td><td><i class="fas fa-chevron-right"></i></td>
        </tr>`).join("") || '<tr><td colspan="9" class="text-center">No markets passed data-quality checks.</td></tr>';
      document.querySelectorAll("#radar-results tr[data-instrument]").forEach(row => row.addEventListener("click", () => showDetail(row.dataset.instrument)));

      updateStudio(scan);
      if (scan.market_sentiment) {
        updateSentiment(scan.market_sentiment);
        renderNews(scan.market_sentiment.recent_headlines || []);
      } else {
        await loadNews();
      }
    } catch (error) {
      $("radar-error").textContent = error.message;
      $("radar-error").classList.remove("d-none");
    } finally { $("radar-refresh").disabled = false; }
  }

  async function showDetail(instrument) {
    const url = root.dataset.detailUrl.replace("__INSTRUMENT__", encodeURIComponent(instrument));
    try {
      selected = await request(url);
      $("detail-symbol").textContent = `${selected.symbol} · ${number(selected.score,1)}/100`;
      $("detail-explanation").textContent = selected.explanation.summary;
      $("detail-sentiment").textContent = `Sentiment: ${selected.explanation.sentiment_label}`;

      const sVal = selected.explanation.sentiment ?? (selected.sentiment ? selected.sentiment.composite_score : null);
      const sLbl = selected.explanation.sentiment_label || (selected.sentiment ? selected.sentiment.sentiment_label : "Neutral");
      if ($("detail-sentiment-badge")) {
        $("detail-sentiment-badge").textContent = `Sentiment: ${sLbl}`;
        const sNum = Number(sVal) || 50;
        $("detail-sentiment-badge").className = `badge badge-pill ${sNum >= 60 ? "badge-success" : sNum <= 40 ? "badge-danger" : "badge-secondary"} px-3 py-2`;
      }

      // Populate coin-specific news catalysts
      const catalysts = selected.explanation.catalysts || [];
      const newsItems = selected.news || [];
      if ($("detail-catalysts-list")) {
        if (catalysts.length > 0 || newsItems.length > 0) {
          let itemsHtml = "";
          if (catalysts.length > 0) {
            itemsHtml += catalysts.map(c => `
              <div class="detail-news-item">
                <span><i class="fas fa-arrow-trend-up text-success mr-2"></i>${escapeHtml(c)}</span>
                <span class="sentiment-pill sentiment-pill-bullish">Catalyst</span>
              </div>`).join("");
          }
          if (newsItems.length > 0) {
            itemsHtml += newsItems.slice(0, 3).map(n => `
              <div class="detail-news-item">
                <a href="${escapeHtml(n.link || '#')}" target="_blank" rel="noopener noreferrer">${escapeHtml(n.title)}</a>
                <span class="sentiment-pill sentiment-pill-${escapeHtml(n.sentiment_tag || 'neutral')}">${escapeHtml(n.sentiment_tag || 'neutral')}</span>
              </div>`).join("");
          }
          $("detail-catalysts-list").innerHTML = itemsHtml;
        } else {
          $("detail-catalysts-list").innerHTML = '<small class="text-muted">No direct news catalysts detected for this market.</small>';
        }
      }

      $("detail-components").innerHTML = Object.entries(selected.components).map(([name,value]) => `<div><span>${escapeHtml(name.replace("_"," "))}</span><strong>${number(value,1)}</strong></div>`).join("");
      const watched = (scan.watchlist || []).includes(selected.instrument);
      $("detail-watch").textContent = watched ? "Remove from watchlist" : "Add to watchlist";
      $("detail-watch").dataset.enabled = watched ? "false" : "true";
      $("detail-paper").disabled = !scan.paper_handoff_enabled;
      $("detail-paper").title = scan.paper_handoff_enabled ? "Queue for an external paper executor" : "Enable only after validation with MARKET_RADAR_PAPER_HANDOFF_ENABLED=true";
      $("radar-detail").classList.remove("d-none");
      $("radar-detail").scrollIntoView({behavior:"smooth",block:"nearest"});
    } catch (error) { toastr.error(error.message, "Market detail unavailable"); }
  }

  $("radar-refresh").addEventListener("click", () => load(true));
  $("radar-limit").addEventListener("change", () => load(true));
  $("radar-detail-close").addEventListener("click", () => $("radar-detail").classList.add("d-none"));
  $("detail-watch").addEventListener("click", async () => {
    if (!selected) return;
    try {
      const result = await request(root.dataset.watchlistUrl, {method:"POST",body:JSON.stringify({instrument:selected.instrument,enabled:$("detail-watch").dataset.enabled === "true"})});
      scan.watchlist = result.watchlist; await showDetail(selected.instrument);
    } catch (error) { toastr.error(error.message); }
  });
  $("detail-paper").addEventListener("click", async () => {
    if (!selected || !confirm("Queue this signal as a paper-trading candidate? This does not submit an order.")) return;
    try { await request(root.dataset.paperUrl, {method:"POST",body:JSON.stringify({signal_id:selected.signal_id})}); toastr.success("Paper candidate queued; no order was submitted."); }
    catch (error) { toastr.error(error.message); }
  });

  // Self-Tuning Model Training handler
  const btnTrain = $("btn-train-model");
  if (btnTrain && root.dataset.trainUrl) {
    btnTrain.addEventListener("click", async () => {
      btnTrain.disabled = true;
      btnTrain.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Training…';
      try {
        const trainResult = await request(root.dataset.trainUrl, {method:"POST", body:JSON.stringify({bootstrap:true})});
        toastr.success(`AI Model successfully trained! Directional accuracy: ${trainResult.directional_accuracy_pct || 0}%`, "Training Complete");
        await load(true);
      } catch (err) {
        toastr.error(err.message, "Training Failed");
      } finally {
        btnTrain.disabled = false;
        btnTrain.innerHTML = '<i class="fas fa-play mr-1"></i> Run Training';
      }
    });
  }

  // Strategy Parameter Optimizer handler
  const btnOpt = $("btn-optimize-params");
  if (btnOpt && root.dataset.optimizeUrl) {
    btnOpt.addEventListener("click", async () => {
      btnOpt.disabled = true;
      btnOpt.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Optimizing…';
      try {
        const optResult = await request(root.dataset.optimizeUrl, {method:"POST", body:JSON.stringify({instrument:"BTC_USDT"})});
        toastr.success(`Optimized across ${optResult.total_tested_combinations || 0} parameter sets. Win Rate: ${optResult.metrics?.win_rate_pct || 0}%`, "Optimization Complete");
        await load(true);
      } catch (err) {
        toastr.error(err.message, "Optimization Failed");
      } finally {
        btnOpt.disabled = false;
        btnOpt.innerHTML = '<i class="fas fa-crosshairs mr-1"></i> Optimize Parameters';
      }
    });
  }

  // News filter tabs
  const newsFilters = $("news-filters");
  if (newsFilters) {
    newsFilters.querySelectorAll("button[data-filter]").forEach(btn => {
      btn.addEventListener("click", async () => {
        newsFilters.querySelectorAll("button").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        await loadNews(btn.dataset.filter);
      });
    });
  }

  load();
})();
