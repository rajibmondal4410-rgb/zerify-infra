// Zerify Content Script
// Injects "Verify with Zerify" button into ChatGPT, Claude, Gemini

const ZERIFY_API = "https://zerify-infra.onrender.com/verify";
const ZERIFY_KEY = "zfy_sk_zerify_demo_permanent_2026";

// ── Detect platform ──────────────────────────────────────────────────────────
function getPlatform() {
  const host = window.location.hostname;
  if (host.includes("chatgpt.com") || host.includes("openai.com")) return "chatgpt";
  if (host.includes("claude.ai")) return "claude";
  if (host.includes("gemini.google.com")) return "gemini";
  return null;
}

// ── Get last AI response ─────────────────────────────────────────────────────
function getLastAIResponse() {
  const platform = getPlatform();
  if (platform === "chatgpt") {
    const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
    if (messages.length === 0) return null;
    return messages[messages.length - 1].innerText.trim();
  }
  if (platform === "claude") {
    const messages = document.querySelectorAll('.font-claude-message, [data-is-streaming="false"]');
    if (messages.length === 0) {
      const all = document.querySelectorAll('.prose');
      if (all.length === 0) return null;
      return all[all.length - 1].innerText.trim();
    }
    return messages[messages.length - 1].innerText.trim();
  }
  if (platform === "gemini") {
    const messages = document.querySelectorAll('.model-response-text, .response-content');
    if (messages.length === 0) return null;
    return messages[messages.length - 1].innerText.trim();
  }
  return null;
}

// ── Get last user prompt ─────────────────────────────────────────────────────
function getLastUserPrompt() {
  const platform = getPlatform();
  if (platform === "chatgpt") {
    const msgs = document.querySelectorAll('[data-message-author-role="user"]');
    if (msgs.length === 0) return "Verify this AI response";
    return msgs[msgs.length - 1].innerText.trim().substring(0, 300);
  }
  if (platform === "claude") {
    const msgs = document.querySelectorAll('.human-turn, [data-testid="user-message"]');
    if (msgs.length === 0) return "Verify this AI response";
    return msgs[msgs.length - 1].innerText.trim().substring(0, 300);
  }
  if (platform === "gemini") {
    const msgs = document.querySelectorAll('.query-text, .user-query');
    if (msgs.length === 0) return "Verify this AI response";
    return msgs[msgs.length - 1].innerText.trim().substring(0, 300);
  }
  return "Verify this AI response";
}

// ── Auto detect task type ────────────────────────────────────────────────────
function detectTaskType(text) {
  const t = text.toLowerCase();
  const codeSignals = [
    "def ", "function ", "import ", "class ", "```",
    "return ", "const ", "var ", "let ", "print(",
    "console.log", "<!doctype", "<html", "SELECT ", "FROM "
  ];
  if (codeSignals.some(s => t.includes(s.toLowerCase()))) return "code";

  const scriptSignals = ["youtube script", "blog post", "linkedin post", "video script", "hook", "intro hook", "call to action"];
  if (scriptSignals.some(s => t.includes(s))) return "script";

  const medicalSignals = ["symptom", "diagnosis", "dosage", "treatment", "medicine", "patient", "doctor", "disease", "prescription"];
  if (medicalSignals.some(s => t.includes(s))) return "medical";

  const legalSignals = ["law", "legal", "contract", "lawsuit", "attorney", "jurisdiction", "rights", "liability"];
  if (legalSignals.some(s => t.includes(s))) return "legal";

  return "text";
}

// ── Create verify button ─────────────────────────────────────────────────────
function createVerifyButton() {
  const btn = document.createElement("button");
  btn.id = "zerify-verify-btn";
  btn.innerHTML = `<span style="margin-right:5px">⚡</span>Verify with Zerify`;
  btn.style.cssText = `
    position: fixed; bottom: 80px; right: 20px; z-index: 99999;
    background: #7c3aed; color: white; border: none; border-radius: 8px;
    padding: 10px 16px; font-size: 13px; font-weight: 600; cursor: pointer;
    box-shadow: 0 4px 12px rgba(124,58,237,0.4);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    transition: all 0.2s; display: flex; align-items: center; gap: 4px;
  `;
  btn.onmouseover = () => btn.style.background = "#6d28d9";
  btn.onmouseout = () => btn.style.background = "#7c3aed";
  btn.onclick = runVerification;
  return btn;
}

// ── Create result panel ──────────────────────────────────────────────────────
function createResultPanel() {
  const panel = document.createElement("div");
  panel.id = "zerify-result-panel";
  panel.style.cssText = `
    position: fixed; bottom: 130px; right: 20px; z-index: 99999;
    background: #111111; border: 1px solid #333; border-radius: 12px;
    padding: 16px; width: 340px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px; color: #f0f0f0;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5); display: none;
  `;
  return panel;
}

// ── Main verification ────────────────────────────────────────────────────────
async function runVerification() {
  const btn = document.getElementById("zerify-verify-btn");
  const panel = document.getElementById("zerify-result-panel");
  const aiResponse = getLastAIResponse();
  const userPrompt = getLastUserPrompt();

  if (!aiResponse) {
    showPanel(panel, null, "Could not find AI response. Try after AI finishes responding.");
    return;
  }

  btn.innerHTML = `<span>⟳</span> Verifying...`;
  btn.style.background = "#374151";
  btn.disabled = true;

  // Detect task type from BOTH prompt and response
  const taskType = detectTaskType(userPrompt + " " + aiResponse);

  try {
    const response = await fetch(ZERIFY_API, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": ZERIFY_KEY },
      body: JSON.stringify({
        task_type: taskType,
        intent: userPrompt,
        ai_claim: "AI has responded to the user request",
        output: aiResponse.substring(0, 3000),
        language: "python"
      })
    });

    const result = await response.json();
    showPanel(panel, result, null, taskType);
  } catch (err) {
    showPanel(panel, null, `Cannot connect to Zerify API. Make sure Zerify server is running.`);
  } finally {
    btn.innerHTML = `<span style="margin-right:5px">⚡</span>Verify with Zerify`;
    btn.style.background = "#7c3aed";
    btn.disabled = false;
  }
}

// ── Show result panel ────────────────────────────────────────────────────────
function showPanel(panel, result, errorMsg, taskType) {
  panel.style.display = "block";

  if (errorMsg) {
    panel.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
        <div style="font-weight:700;font-size:14px;color:#f59e0b">⚠ Zerify</div>
        <div onclick="document.getElementById('zerify-result-panel').style.display='none'"
             style="cursor:pointer;color:#666;font-size:18px">×</div>
      </div>
      <div style="color:#9ca3af;font-size:12px;line-height:1.5">${errorMsg}</div>`;
    return;
  }

  const verified = result.verified;
  const statusColor = verified ? "#22c55e" : "#ef4444";
  const statusIcon = verified ? "✓" : "✗";
  const statusText = verified ? "VERIFIED — AI did what it claimed" : "FAILED — AI output has issues";
  const conf = Math.round((result.confidence || 0) * 100);

  // Format retry prompt as numbered steps if it contains "1)"
  let retryHtml = result.retry_prompt || "";
  if (retryHtml.includes("1)") || retryHtml.includes("1.")) {
    // Already structured — display as-is with line breaks
    retryHtml = retryHtml.replace(/(\d+[\)\.]\s)/g, '<br><span style="color:#f59e0b">$1</span>');
  }

  panel.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
      <div style="display:flex;align-items:center;gap:8px;">
        <div style="width:28px;height:28px;background:#1a1a2e;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:#7c3aed">Z</div>
        <div style="font-weight:700;font-size:14px">Zerify</div>
        <div style="background:#1f1f2e;color:#7c3aed;font-size:10px;padding:2px 6px;border-radius:4px;font-family:monospace">${taskType || 'text'}</div>
      </div>
      <div onclick="document.getElementById('zerify-result-panel').style.display='none'"
           style="cursor:pointer;color:#555;font-size:20px;padding:0 4px">×</div>
    </div>

    <div style="background:${verified ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)'};
                border:1px solid ${verified ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'};
                border-radius:8px;padding:10px;margin-bottom:10px;">
      <div style="color:${statusColor};font-weight:700;font-size:13px;margin-bottom:4px">
        ${statusIcon} ${statusText}
      </div>
      <div style="color:#9ca3af;font-size:11px;font-family:monospace">
        confidence: ${conf}% · check: ${result.check_type || taskType} · cost: ${result.cost || '$0.005'}
      </div>
    </div>

    <div style="margin-bottom:10px;">
      <div style="color:#9ca3af;font-size:11px;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.05em">What's wrong</div>
      <div style="color:#e5e7eb;font-size:12px;line-height:1.6;background:#1a1a1a;padding:8px;border-radius:6px;border-left:3px solid ${statusColor}">
        ${result.reason || 'No reason provided'}
      </div>
    </div>

    ${!verified && result.retry_prompt ? `
    <div style="background:#0d1f0d;border:1px solid rgba(34,197,94,0.3);border-radius:8px;padding:10px;margin-top:8px;">
      <div style="color:#22c55e;font-size:11px;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.05em;font-weight:600">↳ Fix — copy and paste into your AI</div>
      <div style="color:#86efac;font-size:12px;font-family:monospace;line-height:1.7;word-break:break-word">${retryHtml}</div>
      <button onclick="copyRetryPrompt('${encodeURIComponent(result.retry_prompt)}')"
              style="margin-top:10px;background:#166534;color:#bbf7d0;border:1px solid rgba(34,197,94,0.3);
                     border-radius:5px;padding:6px 12px;font-size:11px;cursor:pointer;width:100%;font-weight:600">
        📋 Copy fix prompt
      </button>
    </div>
    ` : ''}

    <div style="margin-top:10px;padding-top:10px;border-top:1px solid #222;
                display:flex;justify-content:space-between;align-items:center">
      <div style="color:#444;font-size:10px;font-family:monospace">id: ${result.id || '—'}</div>
      <a href="https://zerify-infra.onrender.com/dashboard" target="_blank"
         style="color:#7c3aed;font-size:11px;text-decoration:none">View dashboard →</a>
    </div>
  `;
}

// ── Copy retry prompt ────────────────────────────────────────────────────────
window.copyRetryPrompt = function(encoded) {
  const text = decodeURIComponent(encoded);
  navigator.clipboard.writeText(text).then(() => {
    const btns = document.querySelectorAll('#zerify-result-panel button');
    btns.forEach(b => {
      b.textContent = "✓ Copied — paste into AI";
      setTimeout(() => b.textContent = "📋 Copy fix prompt", 2000);
    });
  });
};

// ── Inject UI ────────────────────────────────────────────────────────────────
function injectZerify() {
  if (document.getElementById("zerify-verify-btn")) return;
  const btn = createVerifyButton();
  const panel = createResultPanel();
  document.body.appendChild(panel);
  document.body.appendChild(btn);
}

// ── Watch for page changes ───────────────────────────────────────────────────
const observer = new MutationObserver(() => {
  if (!document.getElementById("zerify-verify-btn")) injectZerify();
});

if (document.body) {
  injectZerify();
  observer.observe(document.body, { childList: true, subtree: true });
} else {
  document.addEventListener("DOMContentLoaded", () => {
    injectZerify();
    observer.observe(document.body, { childList: true, subtree: true });
  });
}