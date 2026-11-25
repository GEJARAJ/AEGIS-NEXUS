/* AEGIS NEXUS — Cyber Resilience Sentinel (DoT / CERT-In Prototype) Portal Controller */

const state = {
  dashboard: null,
  selectedId: null,
  filter: "ALL",
  telemetryCache: {},
};

const CAUSE_LABELS = {
  cyberattack_like: "Cyberattack / Control-Plane Signaling Flood",
  overload: "Traffic Saturation / DDoS-Induced Overload",
  connectivity_failure: "Backhaul / Subsea Link Degradation",
  hardware_or_human_error: "Core Hardware / Misconfiguration Fault",
};

const TELECOM_NODE_CATALOG = {
  "HOSP-01": {
    name: "Chennai Submarine Cable Landing Station (CLS) & NIXI IXP Hub",
    tier: "Core / CLS Hub",
    tierClass: "tier-core",
    dept: "DoT Chennai LSA / NIXI Core Switching & Subsea Ops",
    alternate: "ECR Redundant CLS Optical Ring & Bengaluru IXP Transit",
    services: ["UPI / NPCI Core", "Emergency 112", "e-Hospital Backbone"],
  },
  "HOSP-02": {
    name: "Coimbatore Regional Core Gateway & MPLS Transit Hub",
    tier: "Core / CLS Hub",
    tierClass: "tier-core",
    dept: "DoT Tamil Nadu LSA / Western Optical Core NOC",
    alternate: "Salem-Madurai Redundant DWDM Optical Ring",
    services: ["UPI / Payments", "Emergency 112", "e-Hospital Connectivity"],
  },
  "HOSP-03": {
    name: "Madurai Southern Gateway & Emergency 112 Switching Hub",
    tier: "Core / CLS Hub",
    tierClass: "tier-core",
    dept: "DoT Tamil Nadu LSA / Critical Emergency Routing Cell",
    alternate: "Trichy Core Failover Switch & Satellite VSAT Backhaul",
    services: ["Emergency 112 Routing", "e-Hospital Connectivity", "UPI / Payments"],
  },
  "PDS-01": { name: "BharatNet PoP-01 Kaveri Delta (Thanjavur Rural Ring)" },
  "PDS-02": { name: "BharatNet PoP-02 Palayam GPON Aggregation Node" },
  "PDS-03": { name: "5G Core & BharatNet PoP-03 Melur Block BTS Cluster" },
  "PDS-04": { name: "BharatNet PoP-04 Vallam Rural Fiber Relay" },
  "PDS-05": { name: "BharatNet PoP-05 Thiruvaiyaru Grama OLT Node" },
  "PDS-06": { name: "BharatNet PoP-06 Orathanadu East Backhaul Hub" },
  "PDS-07": { name: "BharatNet PoP-07 Sengipatti Rural 4G/5G Tower Ring" },
  "PDS-08": { name: "5G Edge & Backhaul PoP-08 Budalur Junction" },
  "PDS-09": { name: "5G Edge & Backhaul PoP-09 Peravurani Market Node" },
  "PDS-10": { name: "District Backhaul & 5G PoP-10 Pattukkottai West" },
  "PDS-11": { name: "Coastal Backhaul & BharatNet PoP-11 Adirampattinam" },
  "PDS-12": { name: "BharatNet PoP-12 Madukkur Grama Fiber Access Node" },
  "PDS-13": { name: "5G Core & Backhaul PoP-13 Nanjikottai Ward-4" },
  "PDS-14": { name: "BharatNet PoP-14 Gandarvakottai Border BTS Relay" },
  "PDS-15": { name: "5G Edge & Backhaul PoP-15 Ammapettai Access Ring" },
  "PDS-16": { name: "District Backhaul & 5G PoP-16 Papanasam Town" },
  "PDS-17": { name: "5G Core UPF & Metro Fiber PoP-17 Kumbakonam South" },
  "PDS-18": { name: "5G Core & e-Hospital Link PoP-18 Medical College Road" },
  "PDS-19": { name: "Metro Backhaul & 5G PoP-19 Railway Colony" },
  "PDS-20": { name: "Chennai Central 5G Core UPF & Metro Fiber PoP-20" },
};

function getTelecomNodeView(inst) {
  const entry = TELECOM_NODE_CATALOG[inst.institution_id] || {};
  const isCore = inst.service_type === "hospital_registration";
  return {
    name: entry.name || inst.name,
    tier: entry.tier || (isCore ? "Core / CLS Hub" : "5G / BharatNet PoP"),
    tierClass: entry.tierClass || (isCore ? "tier-core" : "tier-pop"),
    dept: entry.dept || (isCore ? "DoT Chennai LSA / Core Optical NOC" : "DoT Tamil Nadu LSA / BharatNet & TSP Access Ops"),
    alternate: entry.alternate || (isCore ? "Redundant DWDM Optical Ring" : "Intra-Circle Roaming (ICR) Partner BTS & Redundant BharatNet Ring"),
    services: entry.services || ["UPI / Payments", "Emergency 112 Routing", "e-Hospital Connectivity"],
  };
}

function getTelecomPlaybookView(alert) {
  if (!alert.playbook) return null;
  const inst = alert.institution;
  const node = getTelecomNodeView(inst);
  const isCore = inst.service_type === "hospital_registration";
  if (isCore) {
    return {
      title: "Core Gateway Cyber Containment & Traffic Isolation Playbook",
      triggered: alert.playbook.triggered,
      department: node.dept,
      alternate: node.alternate,
      steps: [
        "Isolate anomalous signaling/request flood signatures and enforce edge BGP/WAF rate-limiting on the gateway.",
        "Apply zero-trust ACLs and QoS allow-listing to protect UPI/NPCI settlement, Emergency 112 routing, and e-Hospital links.",
        `Failover clean transit sessions onto redundant DWDM optical ring (${node.alternate}).`,
        "Escalate zero-PII indicators of compromise (IOCs) and telemetry to CERT-In, NCIIPC, and DoT Security Wing (TERM Cell).",
      ],
    };
  }
  return {
    title: "5G Core / BharatNet Threat Containment & Link Failover Playbook",
    triggered: alert.playbook.triggered,
    department: node.dept,
    alternate: node.alternate,
    steps: [
      "Quarantine anomalous AAA / Diameter / 5G NAS authentication bursts and apply per-node signaling rate caps.",
      "Activate Intra-Circle Roaming (ICR) and redundant BharatNet optical ring failover to preserve 112 & UPI connectivity.",
      `Shift clean subscriber sessions to ${node.alternate}.`,
      "Dispatch zero-PII security telemetry to CERT-In, DoT Security Wing / TERM Cell, and State Cyber SOC.",
    ],
  };
}

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

function renderDashboard(data, options = {}) {
  state.dashboard = data;
  document.getElementById("district-name").textContent = "Tamil Nadu & Chennai LSA (Simulation Prototype)";
  document.getElementById("scope-note").textContent =
    "Protected LSA Scope: 3 Core Gateway / Submarine CLS & IXP Hubs (HOSP-*) + 20 District Backhaul / 5G Core & BharatNet PoPs (PDS-*) (23 nodes).";
  document.getElementById("simulation-disclaimer").textContent =
    "All telemetry, threat probabilities, and subscriber-impact ranges are synthetic and illustrative. Real deployment requires formal DoT / CERT-In authorization and a DPDP-compliant data-sharing agreement.";

  document.getElementById("kpi-critical").textContent = pad2(data.kpis.critical_alerts);
  document.getElementById("kpi-risk").textContent = pad2(data.kpis.services_at_risk);
  document.getElementById("kpi-monitored").textContent = pad2(data.kpis.institutions_monitored);
  document.getElementById("kpi-investigated").textContent = pad2(data.kpis.incidents_investigated);

  populateInjectorSelect(data.alerts);
  populateCampaignTargets(data.alerts);
  renderExtensionSectors(data.extension_sectors);
  renderAlertTable();
  if (options.refreshAccessories !== false) {
    loadAccessoriesState();
  }

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
      const node = getTelecomNodeView(a.institution);
      opt.value = a.institution.institution_id;
      opt.textContent = `${a.institution.institution_id} — ${node.name}`;
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
      const node = getTelecomNodeView(inst);
      const isSelected = state.selectedId === inst.institution_id;
      const rangeStr =
        a.impact.affected_citizens_high > 0
          ? `${a.impact.affected_citizens_low}–${a.impact.affected_citizens_high}k subscribers`
          : "Baseline (0 disrupted)";
      return `
        <tr data-inst-id="${escapeHtml(inst.institution_id)}" class="${isSelected ? "selected-row" : ""}">
          <td><strong>#${a.impact.priority_rank}</strong></td>
          <td><span class="level-badge level-${escapeHtml(a.level)}">${escapeHtml(a.level)}</span></td>
          <td>
            <div><strong>${escapeHtml(node.name)}</strong> <span class="node-tier-badge ${node.tierClass}">${escapeHtml(node.tier)}</span></div>
            <div class="inst-id">${escapeHtml(inst.institution_id)} &bull; ${escapeHtml(inst.zone)} &bull; Sev ${a.drift.severity.toFixed(2)}</div>
          </td>
          <td>
            <div><strong>${rangeStr}</strong></div>
            <div class="inst-id">UPI / 112 / e-Hospital &bull; Score: ${a.impact.impact_score.toFixed(1)} (Illustrative)</div>
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
  const node = getTelecomNodeView(inst);
  const drift = alert.drift;
  const impact = alert.impact;
  const causes = alert.cause_probabilities;

  const impactHeroHtml = `
    <div class="impact-hero">
      <div>
        <div class="inst-id">ESTIMATED SUBSCRIBERS &amp; CRITICAL SERVICES AT RISK (ILLUSTRATIVE)</div>
        <div class="impact-range-num">
          ${impact.affected_citizens_high > 0 ? `${impact.affected_citizens_low} – ${impact.affected_citizens_high}k subscribers` : "0 disrupted (Protected / Normal)"}
        </div>
        <div class="muted-text">Blast-Radius Score: <strong>${impact.impact_score.toFixed(1)}</strong> &bull; Defense Priority <strong>#${impact.priority_rank}</strong></div>
        <div class="critical-services-strip">
          ${node.services.map((svc) => `<span class="service-pill">${escapeHtml(svc)}</span>`).join("")}
        </div>
      </div>
      <div class="inst-id" style="text-align:right;">
        Link Cap: ${inst.service_capacity} Gbps eq.<br/>
        Peak Traffic: ${inst.daily_footfall}k sess.<br/>
        Criticality: ${inst.vulnerability_weight}x
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
  const pb = getTelecomPlaybookView(alert);
  if (pb) {
    playbookHtml = `
      <div class="playbook-box ${pb.triggered ? "" : "standby"}">
        <strong>${pb.triggered ? "TRIGGERED:" : "STANDBY:"} ${escapeHtml(pb.title)}</strong>
        <div class="inst-id">Route to: ${escapeHtml(pb.department)} &bull; Alternate Ring: ${escapeHtml(pb.alternate)}</div>
        <ol>${pb.steps.map((st) => `<li>${escapeHtml(st)}</li>`).join("")}</ol>
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
      <h3 style="margin:0 0 2px 0; color:var(--navy-900);">${escapeHtml(node.name)} <span class="node-tier-badge ${node.tierClass}">${escapeHtml(node.tier)}</span></h3>
      <div class="inst-id">${escapeHtml(inst.institution_id)} &bull; ${escapeHtml(node.dept)}</div>
    </div>
    ${impactHeroHtml}
    ${sparkHtml}
    <div class="detail-card">
      <h4>DriftSentinel Anomaly &amp; Attack Telemetry (Layer 2)</h4>
      <p class="muted-text">${escapeHtml(drift.summary)}</p>
      ${signalsHtml}
    </div>
    <div class="detail-card">
      <h4>Probabilistic Threat &amp; Cause Attribution (Layer 3)</h4>
      ${causeHtml}
    </div>
    ${playbookHtml}
    <div class="detail-card">
      <h4>Blast-Radius &amp; Impact Assumptions (Layer 4)</h4>
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

  document.getElementById("camp-intensity").addEventListener("input", (e) => {
    document.getElementById("camp-intensity-val").textContent = e.target.value;
  });

  document.getElementById("btn-sel-hospitals").addEventListener("click", () => {
    setCampaignTargetSelection(["HOSP-01", "HOSP-02", "HOSP-03"]);
  });

  document.getElementById("btn-sel-pds").addEventListener("click", () => {
    setCampaignTargetSelection(["PDS-01", "PDS-03", "PDS-05"]);
  });

  document.getElementById("btn-sel-none").addEventListener("click", () => {
    setCampaignTargetSelection([]);
  });

  document.getElementById("campaign-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const checked = Array.from(document.querySelectorAll(".camp-target-cb:checked")).map((cb) => cb.value);
    if (checked.length === 0) {
      alert("Select at least one target institution for the campaign.");
      return;
    }
    const fault_type = document.getElementById("camp-fault").value;
    const intensity = parseFloat(document.getElementById("camp-intensity").value);
    const duration_ticks = parseInt(document.getElementById("camp-duration").value, 10) || 4;
    const seed = parseInt(document.getElementById("camp-seed").value, 10) || 42;
    const name = document.getElementById("camp-name").value.trim() || null;
    const reset_before_run = document.getElementById("camp-reset-seed").checked;

    const payload = {
      name,
      targets: checked.map((institution_id) => ({ institution_id, fault_type, intensity })),
      duration_ticks,
      seed,
      reset_before_run,
      step_immediately: 2,
    };
    const res = await apiFetch("/api/accessories/fault-injector/campaigns", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.selectedId = checked[0];
    renderDashboard(res.dashboard, { refreshAccessories: false });
    renderAccessoriesState(res.state);
  });

  document.getElementById("btn-clear-accessory").addEventListener("click", async () => {
    const res = await apiFetch("/api/accessories/fault-injector/clear", { method: "POST" });
    renderDashboard(res.dashboard, { refreshAccessories: false });
    renderAccessoriesState(res.state);
  });
}

function populateCampaignTargets(alerts) {
  const grid = document.getElementById("camp-targets-grid");
  if (!grid || grid.children.length > 0) return;
  const sorted = alerts
    .slice()
    .sort((a, b) => a.institution.institution_id.localeCompare(b.institution.institution_id));
  grid.innerHTML = sorted
    .map((a) => {
      const id = a.institution.institution_id;
      return `
        <label class="target-chip">
          <input type="checkbox" class="camp-target-cb" value="${escapeHtml(id)}" />
          <span><strong>${escapeHtml(id)}</strong> ${escapeHtml(a.institution.zone)}</span>
        </label>`;
    })
    .join("");
}

function setCampaignTargetSelection(ids) {
  const wanted = new Set(ids);
  document.querySelectorAll(".camp-target-cb").forEach((cb) => {
    cb.checked = wanted.has(cb.value);
  });
}

async function loadAccessoriesState() {
  try {
    const accState = await apiFetch("/api/accessories/fault-injector");
    renderAccessoriesState(accState);
  } catch (err) {
    console.error("Failed to load accessory state:", err);
  }
}

async function launchPresetCampaign(presetId, defaultSeed, durationTicks) {
  const res = await apiFetch("/api/accessories/fault-injector/campaigns", {
    method: "POST",
    body: JSON.stringify({
      preset_id: presetId,
      duration_ticks: durationTicks,
      seed: defaultSeed,
      reset_before_run: true,
      step_immediately: 2,
    }),
  });
  if (res.campaign?.ground_truth?.length > 0) {
    state.selectedId = res.campaign.ground_truth[0].institution_id;
  }
  renderDashboard(res.dashboard, { refreshAccessories: false });
  renderAccessoriesState(res.state);
}

function renderAccessoriesState(accState) {
  if (!accState) return;
  document.getElementById("acc-current-tick").textContent = accState.current_tick;

  const badge = document.getElementById("acc-status-badge");
  if (accState.status.active) {
    badge.className = "level-badge level-Warning";
    badge.textContent = `Active (${accState.status.active_items} slots)`;
  } else {
    badge.className = "level-badge level-Normal";
    badge.textContent = "Idle";
  }

  const presetsBox = document.getElementById("accessory-presets-list");
  const allPresets = [
    ...(accState.telecom_presets || []).map((p) => ({ ...p, isTelecom: true })),
    ...(accState.presets || []).map((p) => ({ ...p, isTelecom: false })),
  ];
  presetsBox.innerHTML = allPresets
    .map(
      (p) => `
      <div class="preset-card ${p.isTelecom ? "telecom-featured" : ""}">
        <div class="preset-head">
          <div>
            <strong>${escapeHtml(p.title)}</strong>
            ${p.isTelecom ? '<span class="node-tier-badge tier-core">DoT / CERT-In Featured</span>' : ""}
            <div class="inst-id">${escapeHtml(p.category)} &bull; ${p.recommended_duration_ticks} ticks &bull; Seed ${p.default_seed}</div>
          </div>
          <button type="button" class="btn ${p.isTelecom ? "btn-primary" : "btn-secondary"}" onclick="launchPresetCampaign('${escapeHtml(p.preset_id)}', ${p.default_seed}, ${p.recommended_duration_ticks})">
            Launch Preset
          </button>
        </div>
        <p class="muted-text" style="margin-top:6px;">${escapeHtml(p.description)}</p>
        <div class="inst-id" style="margin-top:4px;">${escapeHtml(p.ground_truth_summary)}</div>
      </div>`
    )
    .join("");

  const activeBody = document.getElementById("acc-active-body");
  if (accState.active_injections.length === 0) {
    activeBody.innerHTML = `<tr><td colspan="7" class="muted-text">No timed accessory injections active.</td></tr>`;
  } else {
    activeBody.innerHTML = accState.active_injections
      .map(
        (inj) => `
        <tr>
          <td><strong>${escapeHtml(inj.campaign_name)}</strong><div class="inst-id">${escapeHtml(inj.campaign_id)}</div></td>
          <td><strong>${escapeHtml(inj.institution_id)}</strong></td>
          <td><code>${escapeHtml(inj.fault_type)}</code> (${inj.intensity}x)</td>
          <td>${escapeHtml(CAUSE_LABELS[inj.expected_cause] || inj.expected_cause || "N/A")}</td>
          <td><span class="inst-id">${inj.starts_at_tick} .. ${inj.ends_at_tick}</span></td>
          <td><strong>${inj.remaining_ticks}</strong> ticks</td>
          <td><span class="level-badge ${inj.active_now ? "level-Critical" : "level-Warning"}">${inj.active_now ? "ACTIVE" : "SCHEDULED"}</span></td>
        </tr>`
      )
      .join("");
  }

  const histBox = document.getElementById("acc-history-list");
  if (accState.campaign_history.length === 0) {
    histBox.innerHTML = `<p class="muted-text">No accessory campaigns launched yet.</p>`;
  } else {
    histBox.innerHTML = accState.campaign_history
      .map(
        (c) => `
        <div class="ext-item">
          <strong>${escapeHtml(c.name)}</strong>
          <span class="inst-id">(${escapeHtml(c.campaign_id)} &bull; Seed ${c.seed} &bull; Ticks ${c.started_at_tick}..${c.ends_at_tick})</span>
          <div class="muted-text" style="margin-top:4px;">
            Ground Truth: ${c.ground_truth
              .map(
                (gt) =>
                  `${escapeHtml(gt.institution_id)}: ${escapeHtml(gt.fault_type)} -> ${escapeHtml(gt.expected_cause || "none")} [${gt.start_tick}..${gt.end_tick}]`
              )
              .join(" | ")}
          </div>
        </div>`
      )
      .join("");
  }
}

window.launchPresetCampaign = launchPresetCampaign;

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
