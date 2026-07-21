const API = "https://convene-backend-0fwn.onrender.com";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let token = localStorage.getItem("convene_token") || null;
let userId = localStorage.getItem("convene_user_id") || null;
let userEmail = localStorage.getItem("convene_email") || null;
let presets = [];
let currentEventSource = null;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function authHeaders() {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function showMsg(id, text, type) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = `msg ${type}`;
  show(el);
}

function showView(name) {
  document.querySelectorAll(".view").forEach(v => hide(v));

  const loggedOut = !token;
  document.getElementById("nav-login").className = loggedOut ? "" : "hidden";
  document.getElementById("nav-debate").className = loggedOut ? "hidden" : "";
  document.getElementById("nav-history").className = loggedOut ? "hidden" : "";
  document.getElementById("nav-user").className = loggedOut ? "hidden" : "";
  document.getElementById("nav-logout").className = loggedOut ? "hidden" : "";

  if (token && userEmail) {
    document.getElementById("nav-user").textContent = userEmail;
  }

  if (name === "signup") { show(document.getElementById("view-signup")); return; }
  if (name === "login") { show(document.getElementById("view-login")); return; }

  if (loggedOut) { showView("login"); return; }

  if (name === "debate") {
    show(document.getElementById("view-debate"));
    loadPresets();
    return;
  }
  if (name === "history") {
    show(document.getElementById("view-history"));
    loadHistory();
    return;
  }
  if (name === "live") { show(document.getElementById("view-live")); return; }
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

async function handleSignup(e) {
  e.preventDefault();
  const email = document.getElementById("signup-email").value;
  const password = document.getElementById("signup-password").value;
  try {
    const res = await fetch(`${API}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Signup failed");
    token = data.access_token;
    userId = data.user_id;
    userEmail = email;
    localStorage.setItem("convene_token", token);
    localStorage.setItem("convene_user_id", userId);
    localStorage.setItem("convene_email", email);
    showView("debate");
  } catch (err) {
    showMsg("signup-msg", err.message, "error");
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;
  try {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    token = data.access_token;
    userId = data.user_id;
    userEmail = email;
    localStorage.setItem("convene_token", token);
    localStorage.setItem("convene_user_id", userId);
    localStorage.setItem("convene_email", email);
    showView("debate");
  } catch (err) {
    showMsg("login-msg", err.message, "error");
  }
}

function logout() {
  token = null;
  userId = null;
  userEmail = null;
  localStorage.removeItem("convene_token");
  localStorage.removeItem("convene_user_id");
  localStorage.removeItem("convene_email");
  if (currentEventSource) { currentEventSource.close(); currentEventSource = null; }
  showView("login");
}

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------

async function loadPresets() {
  if (presets.length) { populatePresets(); return; }
  try {
    const res = await fetch(`${API}/presets`);
    presets = await res.json();
    populatePresets();
  } catch (err) {
    showMsg("debate-msg", "Failed to load presets: " + err.message, "error");
  }
}

function populatePresets() {
  const sel = document.getElementById("debate-preset");
  sel.innerHTML = "";
  for (const p of presets) {
    const opt = document.createElement("option");
    opt.value = p.preset_id;
    opt.textContent = p.display_name;
    sel.appendChild(opt);
  }
}

// ---------------------------------------------------------------------------
// Create Debate
// ---------------------------------------------------------------------------

async function handleCreateDebate(e) {
  e.preventDefault();
  const options = [
    document.getElementById("debate-opt1").value.trim(),
    document.getElementById("debate-opt2").value.trim(),
    document.getElementById("debate-opt3").value.trim(),
  ].filter(Boolean);

  if (options.length < 2) { showMsg("debate-msg", "Need at least 2 options.", "error"); return; }

  const body = {
    preset_id: document.getElementById("debate-preset").value,
    question: document.getElementById("debate-question").value.trim(),
    options,
    constraints: {
      team_size: parseInt(document.getElementById("debate-team").value) || 3,
      timeline: document.getElementById("debate-timeline").value.trim() || "6 months",
    },
  };

  const budget = document.getElementById("debate-budget").value.trim();
  if (budget) body.constraints.budget = budget;

  try {
    const res = await fetch(`${API}/debate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to create debate");
    showView("live");
    startStream(data.debate_id, body.question);
  } catch (err) {
    showMsg("debate-msg", err.message, "error");
  }
}

// ---------------------------------------------------------------------------
// SSE Stream
// ---------------------------------------------------------------------------

function startStream(debateId, question) {
  const feed = document.getElementById("live-feed");
  const resultDiv = document.getElementById("live-result");
  feed.innerHTML = "";
  resultDiv.classList.add("hidden");
  document.getElementById("live-title").textContent = question || "Debate";
  document.getElementById("live-status").textContent = "analyzing";
  document.getElementById("live-status").className = "badge";

  if (currentEventSource) currentEventSource.close();
  currentEventSource = new EventSource(`${API}/debate/${debateId}/stream?token=${encodeURIComponent(token || "")}`);

  currentEventSource.addEventListener("agent_stance", (e) => {
    const d = JSON.parse(e.data);
    feed.innerHTML += `
      <div class="feed-item">
        <span class="tag stance">AGENT STANCE</span>
        <div><strong>${d.agent_name}</strong> → <strong>${d.option}</strong> <span class="score">${d.score}/10</span></div>
        <div class="reasoning">${d.reasoning}</div>
      </div>`;
    feed.scrollTop = feed.scrollHeight;
  });

  currentEventSource.addEventListener("tool_call", (e) => {
    const d = JSON.parse(e.data);
    feed.innerHTML += `
      <div class="feed-item">
        <span class="tag tool">TOOL CALL</span>
        <div><span class="tool-name">${d.tool_name}</span>: ${d.query}</div>
        <div class="reasoning">${d.result_summary}</div>
      </div>`;
    feed.scrollTop = feed.scrollHeight;
  });

  currentEventSource.addEventListener("cross_exam", (e) => {
    const d = JSON.parse(e.data);
    feed.innerHTML += `
      <div class="feed-item">
        <span class="tag cross">CROSS-EXAM</span>
        <div class="agents">${d.from_agent} → ${d.to_agent}</div>
        <div class="challenge">"${d.challenge}"</div>
        <div class="response">"${d.response}"</div>
      </div>`;
    feed.scrollTop = feed.scrollHeight;
  });

  currentEventSource.addEventListener("consensus_final", (e) => {
    const d = JSON.parse(e.data);
    const status = document.getElementById("live-status");
    status.textContent = "complete";
    status.className = "badge complete";

    document.getElementById("result-winner").innerHTML = `
      <div class="winner">${d.winning_option}</div>
      <div class="meta">${d.confidence_pct}% confidence · ${d.agreement_pct}% agreement</div>`;

    let rows = d.option_breakdown.map(o =>
      `<tr><td>${o.option}</td><td>${o.average_score}</td><td>${o.why_it_lost || "WINNER"}</td></tr>`
    ).join("");
    document.getElementById("result-breakdown").innerHTML =
      `<table><thead><tr><th>Option</th><th>Avg Score</th><th>Note</th></tr></thead><tbody>${rows}</tbody></table>`;

    document.getElementById("result-rationale").textContent = d.rationale;
    resultDiv.classList.remove("hidden");
    feed.scrollTop = feed.scrollHeight;
  });

  currentEventSource.addEventListener("error", (e) => {
    if (e.data) {
      const d = JSON.parse(e.data);
      const status = document.getElementById("live-status");
      status.textContent = "failed";
      status.className = "badge failed";
      feed.innerHTML += `<div class="feed-item"><span class="tag cross">ERROR</span><div>${d.message}</div></div>`;
    }
  });

  currentEventSource.onerror = () => {
    currentEventSource.close();
  };
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------

async function loadHistory() {
  const list = document.getElementById("history-list");
  list.innerHTML = '<div class="empty">Loading...</div>';
  try {
    const res = await fetch(`${API}/debates/mine`, { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    const data = await res.json();
    if (!data.length) { list.innerHTML = '<div class="empty">No debates yet.</div>'; return; }
    list.innerHTML = data.map(d => `
      <div class="history-item" onclick="viewHistoryDebate('${d.id}')">
        <div>
          <div class="q">${d.question}</div>
          <div class="meta">${d.preset_id} · ${new Date(d.created_at).toLocaleString()}</div>
        </div>
        <span class="status-badge ${d.status}">${d.status}</span>
      </div>`).join("");
  } catch (err) {
    list.innerHTML = `<div class="empty">Failed to load: ${err.message}</div>`;
  }
}

async function viewHistoryDebate(debateId) {
  showView("live");
  const feed = document.getElementById("live-feed");
  const resultDiv = document.getElementById("live-result");
  feed.innerHTML = '<div class="empty">Loading result...</div>';
  resultDiv.classList.add("hidden");

  try {
    const res = await fetch(`${API}/debate/${debateId}/result`, { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (res.status === 404) {
      feed.innerHTML = '<div class="empty">This debate is no longer available.</div>';
      document.getElementById("live-title").textContent = "Past Debate";
      const status = document.getElementById("live-status");
      status.textContent = "expired";
      status.className = "badge failed";
      return;
    }
    if (res.status === 202) {
      feed.innerHTML = '<div class="empty">This debate did not complete before the server restarted.</div>';
      document.getElementById("live-title").textContent = "Past Debate";
      const status = document.getElementById("live-status");
      status.textContent = "incomplete";
      status.className = "badge failed";
      return;
    }
    if (!res.ok) throw new Error((await res.json()).detail || "Failed");
    const r = await res.json();

    document.getElementById("live-title").textContent = r.question;
    const status = document.getElementById("live-status");
    status.textContent = r.status;
    status.className = `badge ${r.status}`;

    feed.innerHTML = "";
    for (const s of r.agent_stances) {
      feed.innerHTML += `
        <div class="feed-item">
          <span class="tag stance">AGENT STANCE</span>
          <div><strong>${s.agent_name}</strong> → <strong>${s.option}</strong> <span class="score">${s.score}/10</span></div>
          <div class="reasoning">${s.reasoning}</div>
        </div>`;
    }
    for (const c of r.cross_exam_transcript) {
      feed.innerHTML += `
        <div class="feed-item">
          <span class="tag cross">CROSS-EXAM</span>
          <div class="agents">${c.from_agent} → ${c.to_agent}</div>
          <div class="challenge">"${c.challenge}"</div>
          <div class="response">"${c.response}"</div>
        </div>`;
    }

    const d = r.consensus;
    document.getElementById("result-winner").innerHTML = `
      <div class="winner">${d.winning_option}</div>
      <div class="meta">${d.confidence_pct}% confidence · ${d.agreement_pct}% agreement</div>`;
    let rows = d.option_breakdown.map(o =>
      `<tr><td>${o.option}</td><td>${o.average_score}</td><td>${o.why_it_lost || "WINNER"}</td></tr>`
    ).join("");
    document.getElementById("result-breakdown").innerHTML =
      `<table><thead><tr><th>Option</th><th>Avg Score</th><th>Note</th></tr></thead><tbody>${rows}</tbody></table>`;
    document.getElementById("result-rationale").textContent = d.rationale;
    resultDiv.classList.remove("hidden");
  } catch (err) {
    feed.innerHTML = `<div class="empty">${err.message}</div>`;
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

if (token) {
  showView("debate");
} else {
  showView("login");
}
