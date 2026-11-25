/* AEGIS NEXUS — Civic Sentinel Government Command Portal Controller */

const state = {
  dashboard: null,
  selectedId: null,
  filter: "ALL",
  telemetryCache: {},
};

const CAUSE_LABELS = {
  cyberattack_like: "Cyberattack-like pattern",
  overload: "System / Civic Overload",
  connectivity_failure: "Connectivity / Link Failure",
  hardware_or_human_error: "Hardware / Human Error",
};

async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(errText || `HTTP ${res.status}`);
  }
  return res.json();
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderDashboard(data) {
  state.dashboard = data;
  document.getElementById("district-name").textContent = data.district_name;
  document.getElementById("scope-note").textContent = data.scope_note;
  document.getElementById("simulation-disclaimer").textContent = data.simulation_disclaimer;

  document.getElementById("kpi-critical").textContent = pad2(data.kpis.critical_alerts);
  document.getElementById("kpi-risk").textContent = pad2(data.kpis.services_at_risk);
  document.getElementById("kpi-monitored").textContent = pad2(data.kpis.institutions_monitored);
  document.getElementById("kpi-investigated").textContent = pad2(data.kpis.incidents_investigated);

  populateInjectorSelect(data.alerts);
  renderExtensionSectors(data.extension_sectors);
  renderAlertTable();

  if (!state.selectedId && data.alerts.length > 0) {
    selectAlert(data.alerts[0].institution.institution_id);
  } else if (state.selectedId) {
    selectAlert(state.selectedId);
  }
}

function populateInjectorSelect(alerts) {
  const sel = document.getElementById("inject-institution");
  if (!sel || sel.options.length > 0) return;
  alerts
    .slice()
    .sort((a, b) => a.institution.institution_id.localeCompare(b.institution.institution_id))
    .forEach((a) => {
      const opt = document.createElement("option");
      opt.value = a.institution.institution_id;
      opt.textContent = `${a.institution.institution_id} — ${a.institution.name}`;
      sel.appendChild(opt);
    });
}

function renderExtensionSectors(sectors) {
  const box = document.getElementById("extension-sectors-list");
  if (!box) return;
  box.innerHTML = sectors
    .map(
      (s) => `
      <div class="ext-item">
        <strong>${escapeHtml(s.sector)}</strong> &bull; <span class="inst-id">${escapeHtml(s.scope_stage)}</span>
        <div class="muted-text">${escapeHtml(s.example_signal)} (${escapeHtml(s.status)})</div>
      </div>`
    )
    .join("");
}

function renderAlertTable() {
  const tbody = document.getElementById("alert-table-body");
  const alerts = state.dashboard?.alerts || [];
  const filtered =
    state.filter === "ALL" ? alerts : alerts.filter((a) => a.level === state.filter);

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted-text">No institutions match the '${escapeHtml(state.filter)}' filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered
    .map((a) => {
      const inst = a.institution;
      const isSelected = state.selectedId === inst.institution_id;
      const rangeStr =
        a.impact.affected_citizens_high > 0
          ? `${a.impact.affected_citizens_low}–${a.impact.affected_citizens_high} citizens`
          : "Baseline (0 disrupted)";
      return `
        <tr data-inst-id="${escapeHtml(inst.institution_id)}" class="${isSelected ? "selected-row" : ""}">
          <td><strong>#${a.impact.priority_rank}</strong></td>
          <td><span class="level-badge level-${escapeHtml(a.level)}">${escapeHtml(a.level)}</span></td>
          <td>
            <div><strong>${escapeHtml(inst.name)}</strong></div>
            <div class="inst-id">${escapeHtml(inst.institution_id)} &bull; ${escapeHtml(inst.zone)} &bull; Sev ${a.drift.severity.toFixed(2)}</div>
          </td>
          <td>
            <div><strong>${rangeStr}</strong></div>
            <div class="inst-id">Score: ${a.impact.impact_score.toFixed(1)} (Illustrative)</div>
          </td>
          <td><span class="inst-id">${escapeHtml(a.workflow.status)}</span></td>
        </tr>`;
    })
    .join("");

  tbody.querySelectorAll("tr[data-inst-id]").forEach((row) => {
    row.addEventListener("click", () => selectAlert(row.dataset.instId));
  });
}

async function selectAlert(institutionId) {
  state.selectedId = institutionId;
  renderAlertTable();

  const alert = (state.dashboard?.alerts || []).find(
    (a) => a.institution.institution_id === institutionId
  );
  if (!alert) return;

  const badge = document.getElementById("inspector-badge");
  badge.className = `level-badge level-${alert.level}`;
  badge.textContent = `${alert.level} • Rank #${alert.impact.priority_rank}`;

  let telemetry = [];
  try {
    telemetry = await apiFetch(`/api/institutions/${encodeURIComponent(institutionId)}/telemetry?limit=24`);
  } catch (_) {
    telemetry = [alert.latest_telemetry];
  }

  const inst = alert.institution;
  const drift = alert.drift;
  const impact = alert.impact;
  const causes = alert.cause_probabilities;

  const impactHeroHtml = `
    <div class="impact-hero">
      <div>
        <div class="inst-id">ESTIMATED CITIZEN IMPACT RANGE (ILLUSTRATIVE)</div>
        <div class="impact-range-num">
          ${impact.affected_citizens_high > 0 ? `${impact.affected_citizens_low} – ${impact.affected_citizens_high} citizens` : "0 disrupted (Normal)"}
        </div>
        <div class="muted-text">Impact Score: <strong>${impact.impact_score.toFixed(1)}</strong> &bull; Priority Rank <strong>#${impact.priority_rank}</strong></div>
      </div>
      <div class="inst-id" style="text-align:right;">
        Capacity: ${inst.service_capacity}/day<br/>
        Footfall: ${inst.daily_footfall}/day<br/>
        Vuln Weight: ${inst.vulnerability_weight}x
      </div>
    </div>`;

  const signalsHtml =
    drift.top_contributing_signals.length > 0
      ? `<ul>${drift.top_contributing_signals
          .map((s) => `<li><strong>${escapeHtml(s.signal)}:</strong> ${escapeHtml(s.description)} (z=${s.z_score})</li>`)
          .join("")}</ul>`
      : `<p class="muted-text">${escapeHtml(drift.summary)}</p>`;

  let causeHtml = `<p class="muted-text">No fault signature active; cause classifier idle under normal baseline.</p>`;
  if (causes) {
    const entries = Object.keys(CAUSE_LABELS).map((k) => ({
      key: k,
      label: CAUSE_LABELS[k],
      prob: causes[k],
      dom: causes.dominant_cause === k,
    }));
    entries.sort((a, b) => b.prob - a.prob);
    causeHtml =
      entries
        .map(
          (e) => `
        <div class="prob-row">
          <div class="prob-label">
            <span>${escapeHtml(e.label)}</span>
            <strong>${(e.prob * 100).toFixed(1)}%</strong>
          </div>
          <div class="prob-bar-track">
            <div class="prob-bar-fill ${e.dom ? "dominant" : ""}" style="width:${(e.prob * 100).toFixed(1)}%"></div>
          </div>
        </div>`
        )
        .join("") +
      `<div class="inst-id">${escapeHtml(causes.note)} (Method: ${escapeHtml(causes.method)})</div>`;
  }

  let playbookHtml = "";
  if (alert.playbook) {
    const pb = alert.playbook;
    playbookHtml = `
      <div class="playbook-box ${pb.triggered ? "" : "standby"}">
        <strong>${pb.triggered ? "TRIGGERED:" : "STANDBY:"} ${escapeHtml(pb.title)}</strong>
        <div class="inst-id">Route to: ${escapeHtml(pb.department)} &bull; Alternate: ${escapeHtml(pb.alternate_centre)}</div>
        <ol>${pb.immediate_steps.map((st) => `<li>${escapeHtml(st)}</li>`).join("")}</ol>
      </div>`;
  }

  const wf = alert.workflow;
  const workflowHtml = `
    <div class="detail-card">
      <h4>Official Acknowledgement &amp; Restoration (Human-in-the-Loop)</h4>
      <p class="muted-text">
        Status: <strong>${escapeHtml(wf.status)}</strong>
        ${wf.acknowledged_by ? `&bull; Officer: <strong>${escapeHtml(wf.acknowledged_by)}</strong>` : ""}
        ${wf.notes ? `<br/>Notes: ${escapeHtml(wf.notes)}` : ""}
      </p>
      <div class="gov-form" style="margin-top:8px;">
        <input type="text" id="wf-officer" placeholder="Duty Official Name / Designation (e.g., District Nodal Officer)" value="${escapeHtml(wf.acknowledged_by || "District Nodal Officer")}" />
        <input type="text" id="wf-notes" placeholder="Action / Continuity Note (optional)" />
        <div class="workflow-row">
          <button type="button" class="btn btn-secondary" onclick="submitWorkflow('${escapeHtml(alert.alert_id)}', 'Acknowledged')">Acknowledge</button>
          <button type="button" class="btn btn-primary" onclick="submitWorkflow('${escapeHtml(alert.alert_id)}', 'Mitigating')">Deploy Continuity</button>
          <button type="button" class="btn btn-dark" onclick="submitWorkflow('${escapeHtml(alert.alert_id)}', 'Restored')">Mark Restored</button>
        </div>
      </div>
    </div>`;

  const sparkHtml = `
    <div class="sparkline-wrap">
      ${buildSparkCard("Response Latency (ms)", telemetry.map((t) => t.latency_ms), `${alert.latest_telemetry.latency_ms} ms`, "#0b2545")}
      ${buildSparkCard("Error Rate (%)", telemetry.map((t) => +(t.error_rate * 100).toFixed(2)), `${(alert.latest_telemetry.error_rate * 100).toFixed(2)}%`, "#b91c1c")}
    </div>`;

  document.getElementById("inspector-content").innerHTML = `
    <div>
      <h3 style="margin:0 0 2px 0; color:var(--navy-900);">${escapeHtml(inst.name)}</h3>
      <div class="inst-id">${escapeHtml(inst.institution_id)} &bull; ${escapeHtml(inst.responsible_department)}</div>
    </div>
    ${impactHeroHtml}
    ${sparkHtml}
    <div class="detail-card">
      <h4>DriftSentinel Explainability (Layer 2)</h4>
      <p class="muted-text">${escapeHtml(drift.summary)}</p>
      ${signalsHtml}
    </div>
    <div class="detail-card">
      <h4>Probabilistic Cause Breakdown (Layer 3)</h4>
      ${causeHtml}
    </div>
    ${playbookHtml}
    <div class="detail-card">
      <h4>Stated Impact Assumptions (Layer 4)</h4>
      <ul>${impact.assumptions.map((as) => `<li>${escapeHtml(as)}</li>`).join("")}</ul>
    </div>
    ${workflowHtml}
  `;
}

function buildSparkCard(title, values, latestLabel, strokeColor) {
  const w = 200;
  const h = 44;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values
    .map((v, i) => {
      const x = values.length === 1 ? w / 2 : (i / (values.length - 1)) * (w - 8) + 4;
      const y = h - 6 - ((v - min) / span) * (h - 12);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return `
    <div class="spark-card">
      <div class="spark-title"><span>${escapeHtml(title)}</span><strong>${escapeHtml(latestLabel)}</strong></div>
      <svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}">
        <polyline fill="none" stroke="${strokeColor}" stroke-width="2" points="${pts}" />
      </svg>
    </div>`;
}

async function submitWorkflow(alertId, status) {
  const officer = document.getElementById("wf-officer")?.value?.trim() || "District Nodal Officer";
  const notes = document.getElementById("wf-notes")?.value?.trim() || null;
  const res = await apiFetch(`/api/alerts/${encodeURIComponent(alertId)}/workflow`, {
    method: "POST",
    body: JSON.stringify({ status, official_name: officer, notes }),
  });
  renderDashboard(res.dashboard);
}

async function loadEvaluation() {
  const data = await apiFetch("/api/evaluation");
  const det = data.detection;
  const cls = data.cause_classification;
  const imp = data.impact_ranking;
  document.getElementById("eval-results").innerHTML = `
    <div class="eval-card">
      <h4>DriftSentinel Detection (Layer 2)</h4>
      <div class="metric-line"><span>Precision</span><span class="metric-val">${(det.precision * 100).toFixed(1)}%</span></div>
      <div class="metric-line"><span>Recall</span><span class="metric-val">${(det.recall * 100).toFixed(1)}%</span></div>
      <div class="metric-line"><span>False Alarm Rate</span><span class="metric-val">${(det.false_alarm_rate * 100).toFixed(2)}%</span></div>
      <div class="metric-line"><span>Mean Time to Detect</span><span class="metric-val">${det.mean_time_to_detect_ticks} ticks</span></div>
      <div class="metric-line"><span>Fault Episodes Caught</span><span class="metric-val">${det.episodes_detected} / ${det.episodes_total}</span></div>
    </div>
    <div class="eval-card">
      <h4>Cause Classifier vs. Rule Baseline (Layer 3)</h4>
      <div class="metric-line"><span>ML Accuracy (Shifted Test)</span><span class="metric-val">${(cls.ml_accuracy * 100).toFixed(1)}%</span></div>
      <div class="metric-line"><span>Rule Baseline Accuracy</span><span class="metric-val">${(cls.rule_baseline_accuracy * 100).toFixed(1)}%</span></div>
      <div class="metric-line"><span>ML Brier Score (lower=better)</span><span class="metric-val">${cls.ml_brier_score}</span></div>
      <div class="metric-line"><span>Rule Baseline Brier Score</span><span class="metric-val">${cls.rule_baseline_brier_score}</span></div>
      <div class="metric-line"><span>Hold-Out Fault (${escapeHtml(cls.holdout_fault_test.held_out_fault)})</span><span class="metric-val">${(cls.holdout_fault_test.ml_accuracy_on_unseen_fault * 100).toFixed(1)}%</span></div>
    </div>
    <div class="eval-card">
      <h4>Citizen Impact Ranking (Layer 4)</h4>
      <div class="metric-line"><span>Spearman Rank Correlation</span><span class="metric-val">${imp.spearman_rank_correlation}</span></div>
      <div class="metric-line"><span>Expected Ranks</span><span class="metric-val">[${imp.expected_ranks.join(", ")}]</span></div>
      <div class="metric-line"><span>Predicted Ranks</span><span class="metric-val">[${imp.predicted_ranks.join(", ")}]</span></div>
      <div class="metric-line"><span>Exact Priority Match</span><span class="metric-val">${imp.exact_match ? "YES" : "NO"}</span></div>
    </div>
  `;
}

async function loadGovernance() {
  const data = await apiFetch("/api/governance");
  document.getElementById("gov-positioning").innerHTML = `
    <p><strong>${escapeHtml(data.positioning.civic_sentinel_role)}</strong></p>
    <p class="muted-text">India's existing national cybersecurity &amp; response institutions that Civic Sentinel complements:</p>
    <ul>${data.positioning.existing_national_systems.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>
  `;
  document.getElementById("gov-privacy").innerHTML = `
    <ul>${data.privacy_and_ethics.map((p) => `<li>${escapeHtml(p)}</li>`).join("")}</ul>
  `;
  document.getElementById("gov-claims").innerHTML = `
    <table class="gov-table">
      <thead><tr><th>Say (Defensible &amp; Honest)</th><th>Do Not Say</th></tr></thead>
      <tbody>
        ${data.claims_guardrails
          .map(
            (c) => `<tr><td><strong>${escapeHtml(c.say)}</strong></td><td class="muted-text">${escapeHtml(c.do_not_say)}</td></tr>`
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function setupEventHandlers() {
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-tab").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });

  document.querySelectorAll(".pill[data-filter]").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".pill[data-filter]").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      state.filter = pill.dataset.filter;
      renderAlertTable();
    });
  });

  document.getElementById("btn-run-demo").addEventListener("click", async () => {
    const data = await apiFetch("/api/demo/scenario/hospital-failure", { method: "POST" });
    state.selectedId = "HOSP-01";
    renderDashboard(data);
  });

  document.getElementById("btn-step").addEventListener("click", async () => {
    const data = await apiFetch("/api/demo/step?steps=1", { method: "POST" });
    renderDashboard(data);
  });

  document.getElementById("btn-reset").addEventListener("click", async () => {
    const data = await apiFetch("/api/demo/reset", { method: "POST" });
    state.selectedId = data.alerts[0]?.institution.institution_id || null;
    renderDashboard(data);
  });

  document.getElementById("inject-intensity").addEventListener("input", (e) => {
    document.getElementById("intensity-val").textContent = e.target.value;
  });

  document.getElementById("inject-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const institution_id = document.getElementById("inject-institution").value;
    const fault_type = document.getElementById("inject-fault").value;
    const intensity = parseFloat(document.getElementById("inject-intensity").value);
    const data = await apiFetch("/api/demo/inject", {
      method: "POST",
      body: JSON.stringify({ institution_id, fault_type, intensity }),
    });
    state.selectedId = institution_id;
    renderDashboard(data);
    document.querySelector('.nav-tab[data-tab="dashboard"]').click();
  });

  document.getElementById("btn-refresh-eval").addEventListener("click", loadEvaluation);
}

window.submitWorkflow = submitWorkflow;

async function init() {
  setupEventHandlers();
  const dashboard = await apiFetch("/api/dashboard");
  renderDashboard(dashboard);
  loadEvaluation();
  loadGovernance();
}

init().catch((err) => {
  console.error("Failed to initialize AEGIS NEXUS portal:", err);
});
