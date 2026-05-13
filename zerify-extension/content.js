// Zerify Content Script
// Injects "Verify with Zerify" button into ChatGPT, Claude, Gemini

const ZERIFY_API = "https://zerify-infra.onrender.com/verify";
const ZERIFY_KEY = "zfy_sk_zerify_demo_permanent_2026";

function getPlatform() {
  const host = window.location.hostname;
  if (host.includes("chatgpt.com") || host.includes("openai.com")) return "chatgpt";
  if (host.includes("claude.ai")) return "claude";
  if (host.includes("gemini.google.com")) return "gemini";
  return null;
}

function getLastAIResponse() {
  const platform = getPlatform();
  if (platform === "chatgpt") {
    const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
    if (messages.length === 0) return null;
    return messages[messages.length - 1].innerText.trim();
  }
  if (platform === "claude") {
    const all = document.querySelectorAll('.prose');
    if (all.length === 0) return null;
    return all[all.length - 1].innerText.trim();
  }
  if (platform === "gemini") {
    const messages = document.querySelectorAll('.model-response-text, .response-content');
    if (messages.length === 0) return null;
    return messages[messages.length - 1].innerText.trim();
  }
  return null;
}

// ── FEATURE: Capture Last 3 Conversation Steps ──────────────────────────────
function getLastUserPrompt() {
  const platform = getPlatform();
  let elements = [];
  if (platform === "chatgpt") elements = document.querySelectorAll('[data-message-author-role="user"]');
  else if (platform === "claude") elements = document.querySelectorAll('[data-testid="user-message"]');
  else if (platform === "gemini") elements = document.querySelectorAll('.query-text, .user-query');

  if (!elements || elements.length === 0) return "Verify this AI response";

  // Grab the last 3 user messages to give the AI Judge full conversation context
  const lastThree = Array.from(elements).slice(-3).map(el => el.innerText.trim());
  return lastThree.join("\n\n---\n\n").substring(0, 1500);
}

// ── Smarter task type detection ──────────────────────────────────────────────
function detectTaskType(intent, response) {
  const i = intent.toLowerCase();
  const r = response.toLowerCase();

  const scriptIntentSignals = [
    "youtube script", "yt script", "video script", "write a script",
    "write me a script", "5 minute script", "minute youtube", "blog post",
    "linkedin post", "instagram caption", "twitter thread", "tiktok script"
  ];
  if (scriptIntentSignals.some(s => i.includes(s))) return "script";

  const medicalIntent = ["dosage", "dose", "medicine", "medication", "symptom",
    "diagnosis", "treatment", "disease", "paracetamol", "ibuprofen",
    "antibiotic", "prescription", "medical", "doctor", "patient", "surgery"];
  if (medicalIntent.some(w => i.includes(w))) return "medical";

  const legalIntent = ["law", "legal", "lawyer", "contract", "lawsuit",
    "attorney", "jurisdiction", "rights", "liability", "sue", "court"];
  if (legalIntent.some(w => i.includes(w))) return "legal";

  const codePatterns = [
    /def [a-z_]+\(/, /function [a-z_]+\(/, /^import [a-z]/m, /^from [a-z]/m,
    /class [A-Z]/, /\bconst \w+ =/, /\blet \w+ =/, /\bvar \w+ =/,
    /```(python|javascript|js|ts|java|cpp|c\+\+)/i, /SELECT .+ FROM /i,
  ];
  if (codePatterns.some(p => p.test(r))) return "code";

  return "text";
}

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

function createResultPanel() {
  const panel = document.createElement("div");
  panel.id = "zerify-result-panel";
  panel.style.cssText = `
    position: fixed; bottom: 130px; right: 20px; z-index: 99999;
    background: #111111; border: 1px solid #333; border-radius: 12px;
    padding: 16px; width: 340px; max-height: 500px; overflow-y: auto;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px; color: #f0f0f0;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5); display: none;
  `;
  return panel;
}

async function runVerification() {
  const btn = document.getElementById("zerify-verify-btn");
  const panel = document.getElementById("zerify-result-panel");
  const aiResponse = getLastAIResponse();
  const userPrompt = getLastUserPrompt();

  if (!aiResponse) {
    showPanel(panel, null, "Could not find AI response. Try after the AI finishes responding.", null);
    return;
  }

  btn.innerHTML = `<span>⟳</span> Verifying...`;
  btn.style.background = "#374151";
  btn.disabled = true;

  const taskType = detectTaskType(userPrompt, aiResponse);
  const apiTaskType = (taskType === "medical" || taskType === "legal") ? "text" : taskType;

  try {
    const response = await fetch(ZERIFY_API, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": ZERIFY_KEY },
      body: JSON.stringify({
        task_type: apiTaskType,
        intent: userPrompt,
        ai_claim: "AI has responded to the user request",
        output: aiResponse.substring(0, 3000),
        language: "python"
      })
    });

    const result = await response.json();
    showPanel(panel, result, null, taskType);
  } catch (err) {
    showPanel(panel, null, "Cannot connect to Zerify API. Check your internet connection.", null);
  } finally {
    btn.innerHTML = `<span style="margin-right:5px">⚡</span>Verify with Zerify`;
    btn.style.background = "#7c3aed";
    btn.disabled = false;
  }
}

function showPanel(panel, result, errorMsg, taskType) {
  panel.style.display = "block";

  if (errorMsg) {
    panel.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
        <div style="font-weight:700;font-size:14px;color:#f59e0b">⚠ Zerify</div>
        <div id="zerify-close-btn" style="cursor:pointer;color:#666;font-size:18px">×</div>
      </div>
      <div style="color:#9ca3af;font-size:12px;line-height:1.5">${errorMsg}</div>`;
    return;
  }

  const verified = result.verified;
  const statusColor = verified ? "#22c55e" : "#ef4444";
  const statusIcon = verified ? "✓" : "✗";
  const statusText = verified ? "VERIFIED — AI did what it claimed" : "FAILED — AI output has issues";
  const conf = Math.round((result.confidence || 0) * 100);
  const displayType = taskType || result.task_type || "text";

  window._zerifyRetryPrompt = result.retry_prompt || '';
  
  let retryHtml = (result.retry_prompt || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  retryHtml = retryHtml.replace(/(\d+[\)\.] )/g, '<br><span style="color:#f59e0b;font-weight:600">$1</span>');
  retryHtml = retryHtml.replace(/\n/g, '<br>');

  let issuesSection = '';
  if (!verified) {
    issuesSection = `
      <div style="margin-bottom:10px;">
        <div style="color:#9ca3af;font-size:11px;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.05em">What's wrong</div>
        <div style="color:#e5e7eb;font-size:12px;line-height:1.6;background:#1a1a1a;padding:8px;border-radius:6px;border-left:3px solid ${statusColor}">
          ${result.reason || 'No reason provided'}
        </div>
      </div>

      ${result.retry_prompt ? `
      <div style="background:#0d1f0d;border:1px solid rgba(34,197,94,0.3);border-radius:8px;padding:10px;margin-top:8px;">
        <div style="color:#22c55e;font-size:11px;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.05em;font-weight:600">↳ Fix — copy and paste into your AI</div>
        <div style="color:#86efac;font-size:12px;font-family:monospace;line-height:1.7;word-break:break-word">${retryHtml}</div>
        <button id="zerify-copy-btn"
                style="margin-top:10px;background:#166534;color:#bbf7d0;border:1px solid rgba(34,197,94,0.3);
                       border-radius:5px;padding:6px 12px;font-size:11px;cursor:pointer;width:100%;font-weight:600">
          📋 Copy fix prompt
        </button>
      </div>
      ` : ''}
    `;
  } else {
    issuesSection = `
      <div style="margin-bottom:10px;">
        <div style="color:#9ca3af;font-size:11px;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.05em">Verification Notes</div>
        <div style="color:#e5e7eb;font-size:12px;line-height:1.6;background:#1a1a1a;padding:8px;border-radius:6px;border-left:3px solid ${statusColor}">
          ${result.reason || 'Everything looks correct.'}
        </div>
      </div>
    `;
  }

  panel.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
      <div style="display:flex;align-items:center;gap:8px;">
        <div style="width:28px;height:28px;background:#1a1a2e;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:#7c3aed">Z</div>
        <div style="font-weight:700;font-size:14px">Zerify</div>
        <div style="background:#1f1f2e;color:#7c3aed;font-size:10px;padding:2px 6px;border-radius:4px;font-family:monospace">${displayType}</div>
      </div>
      <div id="zerify-close-btn" style="cursor:pointer;color:#555;font-size:20px;padding:0 4px">×</div>
    </div>

    <div style="background:${verified ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)'};
                border:1px solid ${verified ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'};
                border-radius:8px;padding:10px;margin-bottom:10px;">
      <div style="color:${statusColor};font-weight:700;font-size:13px;margin-bottom:4px">
        ${statusIcon} ${statusText}
      </div>
      <div style="color:#9ca3af;font-size:11px;font-family:monospace">
        confidence: ${conf}% · ${result.check_type || displayType}
      </div>
    </div>

    ${issuesSection}

    <div style="margin-top:10px;padding-top:10px;border-top:1px solid #222;
                display:flex;justify-content:space-between;align-items:center">
      <div style="color:#444;font-size:10px;font-family:monospace">id: ${result.id || '—'}</div>
      <span id="zerify-dash-link" style="color:#7c3aed;font-size:11px;text-decoration:none;cursor:pointer;">View dashboard →</span>
    </div>
  `;

  // ── FEATURE: Bulletproof Event Delegation ──────────────────────────────────
  panel.onclick = function(event) {
    const target = event.target;

    // 1. Cross / Close Button
    if (target.id === 'zerify-close-btn') {
      panel.style.display = 'none';
    }

    // 2. Dashboard Link
    if (target.id === 'zerify-dash-link') {
      window.open('[https://zerify-infra.onrender.com/dashboard](https://zerify-infra.onrender.com/dashboard)', '_blank');
    }

    // 3. Copy Fix Prompt Button
    if (target.id === 'zerify-copy-btn') {
      const text = window._zerifyRetryPrompt;
      if (!text) return;
      
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
          target.textContent = "✓ Copied!";
          target.style.background = "#14532d";
          setTimeout(() => {
            target.textContent = "📋 Copy fix prompt";
            target.style.background = "#166534";
          }, 2000);
        }).catch(() => zerifyFallbackCopy(text, target));
      } else {
        zerifyFallbackCopy(text, target);
      }
    }
  };
}

function zerifyFallbackCopy(text, btnElement) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
  if (btnElement) {
    btnElement.textContent = "✓ Copied!";
    setTimeout(() => { btnElement.textContent = "📋 Copy fix prompt"; }, 2000);
  }
}

function injectZerify() {
  if (document.getElementById("zerify-verify-btn")) return;
  const btn = createVerifyButton();
  const panel = createResultPanel();
  document.body.appendChild(panel);
  document.body.appendChild(btn);
}

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