(() => {
  "use strict";

  const root = document.getElementById("ai-training-root");
  if (!root) return;
  const $ = (id) => document.getElementById(id);

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[character]));

  async function request(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
  }

  function render(profile) {
    const ready = profile && profile.status === "ready" && profile.profile_exists !== false;
    $("training-status").textContent = ready ? "Training active" : "Not trained";
    $("training-status").className = `badge training-status-badge ${ready ? "badge-success" : "badge-dark"}`;
    $("training-date-range").textContent = ready ? `${profile.start_date} → ${profile.end_date}` : "—";
    $("training-active-timeframe").textContent = ready ? profile.timeframe : "—";
    $("training-total-candles").textContent = ready ? Number(profile.total_candles || 0).toLocaleString() : "0";
    $("training-pair-count").textContent = ready ? profile.instrument_count || 0 : "0";

    const download = $("download-training-profile");
    if (ready) {
      download.href = root.dataset.downloadUrl;
      download.classList.remove("disabled");
      download.removeAttribute("aria-disabled");
    } else {
      download.href = "#";
      download.classList.add("disabled");
      download.setAttribute("aria-disabled", "true");
    }

    const summaries = ready ? Object.values(profile.instruments || {}) : [];
    $("training-results-body").innerHTML = summaries.length ? summaries.map((item) => {
      const regimeClass = item.regime === "bullish" ? "success" : item.regime === "bearish" ? "danger" : "warning";
      const returnClass = Number(item.total_return_pct) >= 0 ? "text-success" : "text-danger";
      return `<tr>
        <td class="font-weight-bold">${escapeHtml(item.instrument)}</td>
        <td><span class="badge badge-${regimeClass}">${escapeHtml(item.regime)}</span></td>
        <td class="${returnClass}">${Number(item.total_return_pct).toFixed(2)}%</td>
        <td>${Number(item.return_volatility_pct).toFixed(3)}%</td>
        <td>${Number(item.up_candle_pct).toFixed(1)}%</td>
        <td>${Number(item.candle_count).toLocaleString()}</td>
      </tr>`;
    }).join("") : '<tr><td colspan="6" class="text-center text-muted py-4">No historical profile has been created.</td></tr>';

    $("training-last-updated").textContent = ready
      ? `Profile built ${new Date(profile.trained_at * 1000).toLocaleString()}. It is now available to the selected trading AI.`
      : "The Trader will use default live-only context until training completes.";
  }

  async function loadStatus() {
    try {
      render(await request(root.dataset.statusUrl));
    } catch (error) {
      toastr.error(error.message, "Training status unavailable");
    }
  }

  $("btn-run-historical-training").addEventListener("click", async () => {
    const button = $("btn-run-historical-training");
    const instruments = Array.from(document.querySelectorAll("#training-pairs input:checked")).map((input) => input.value);
    if (!instruments.length) {
      toastr.warning("Select at least one trading pair.", "Training");
      return;
    }
    button.disabled = true;
    $("training-progress").classList.remove("d-none");
    try {
      const profile = await request(root.dataset.runUrl, {
        method: "POST",
        body: JSON.stringify({
          start_date: $("training-start-date").value,
          end_date: $("training-end-date").value,
          timeframe: $("training-timeframe").value,
          instruments,
        }),
      });
      render(profile);
      toastr.success(`${Number(profile.total_candles).toLocaleString()} candles distilled into AI context.`, "Training complete");
    } catch (error) {
      toastr.error(error.message, "Training failed");
    } finally {
      button.disabled = false;
      $("training-progress").classList.add("d-none");
    }
  });

  loadStatus();
})();
