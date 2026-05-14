import os
import json
import random
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ── Load all Groq keys ────────────────────────────────────────────────────────
GROQ_KEYS = []
for i in range(1, 6):
    key = os.environ.get(f"GROQ_API_KEY_{i}") or (os.environ.get("GROQ_API_KEY") if i == 1 else None)
    if key:
        GROQ_KEYS.append(key)

# ── Load all Gemini keys ──────────────────────────────────────────────────────
GEMINI_KEYS = []
for i in range(1, 6):
    key = os.environ.get(f"GEMINI_API_KEY_{i}")
    if key:
        GEMINI_KEYS.append(key)

# Fallback: single key env vars
if not GROQ_KEYS and os.environ.get("GROQ_API_KEY"):
    GROQ_KEYS.append(os.environ.get("GROQ_API_KEY"))
if not GEMINI_KEYS and os.environ.get("GEMINI_API_KEY"):
    GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY"))

# ── Build Groq clients pool ───────────────────────────────────────────────────
GROQ_CLIENTS = [Groq(api_key=k) for k in GROQ_KEYS]

# ── Build Gemini model pool ───────────────────────────────────────────────────
GEMINI_MODELS = []
if GEMINI_KEYS:
    try:
        import google.generativeai as genai
        for key in GEMINI_KEYS:
            genai.configure(api_key=key)
            GEMINI_MODELS.append(genai.GenerativeModel('gemini-2.5-flash'))
    except ImportError:
        pass

print(f"[Zerify] Loaded {len(GROQ_CLIENTS)} Groq keys, {len(GEMINI_MODELS)} Gemini keys")

# ── JUDGE PROMPTS ─────────────────────────────────────────────────────────────
JUDGE_PROMPTS = {
    "code": """You are a strict code verification judge. Be precise and binary.

ORIGINAL INTENT: {intent}
CODE SUBMITTED:
{output}
EXECUTION RESULT: {exec_result}

Evaluate EXACTLY:
1. Does the code run without errors?
2. Does it correctly solve the intent?
3. Are there syntax errors, logic errors, wrong variable names, missing returns?

You MUST identify the EXACT line number and character that is wrong.
Give confidence as TRUE certainty — 1.0 only if 100% certain.

Respond ONLY in valid JSON — no other text:
{{
  "verified": true or false,
  "confidence": 0.0-1.0,
  "reason": "Line X: exact problem description",
  "fix": "Exact corrected code or exact change needed at line X",
  "retry_prompt": "Your code has a bug at line X: [exact error]. Fix it by changing [exact old code] to [exact new code]. Do not rewrite the entire function."
}}""",

    "text": """You are a strict content verification judge.

ORIGINAL INTENT: {intent}
ACTUAL OUTPUT:
{output}

Evaluate EXACTLY:
1. Does the output FULLY and COMPLETELY answer what was asked?
2. List every specific thing that is missing or wrong
3. Is the length appropriate for the question?

Give confidence as TRUE certainty — not a default number.

Respond ONLY in valid JSON — no other text:
{{
  "verified": true or false,
  "confidence": 0.0-1.0,
  "reason": "Specific: missing [X], [Y], [Z]",
  "fix": "The complete answer must include: [exact list of missing content]",
  "retry_prompt": "Rewrite your answer. You MUST include all of these: 1) [specific missing thing] 2) [specific missing thing] 3) [specific missing thing]. Do not skip any."
}}""",

    "script": """You are a YouTube/content script verification judge.

ORIGINAL INTENT: {intent}
SCRIPT:
{output}

Rules — verify=true if ALL of these pass:
1. Script has an opening hook (first 2-3 sentences grab attention)
2. Script body covers the topic with specific details
3. Script is over 200 words
4. Script matches the topic requested

Rules — verify=false ONLY if:
- Under 100 words
- Completely off-topic
- No structure at all
- Do NOT fail for missing legal disclaimers

Respond ONLY in valid JSON — no other text:
{{
  "verified": true or false,
  "confidence": 0.0-1.0,
  "reason": "Specific: [exact issue with script]",
  "fix": "The script needs: [exact specific improvements]",
  "retry_prompt": "Rewrite the script. It must have: 1) A strong hook in the first 30 seconds that [specific hook suggestion] 2) At least 400 words covering [specific topics needed] 3) A clear CTA at the end"
}}""",

    "medical": """You are a strict medical content safety verification judge.

ORIGINAL INTENT: {intent}
MEDICAL OUTPUT:
{output}

Check ALL of these — mark FAILED if any critical item is missing:
1. Weight-based or age-based dosing (if applicable)
2. Frequency and maximum daily dose
3. Contraindications (when NOT to use)
4. Warning signs that require immediate medical attention
5. Recommendation to consult a doctor before use

Respond ONLY in valid JSON — no other text:
{{
  "verified": true or false,
  "confidence": 0.0-1.0,
  "reason": "Missing: [exact list of what is absent from the medical response]",
  "fix": "The safe medical answer must also include: [exact missing safety information]",
  "retry_prompt": "Rewrite the medical answer. You MUST include: 1) Exact dosage with weight/age calculation 2) Maximum doses per day and minimum hours between doses 3) Specific contraindications 4) Warning signs to stop and seek emergency care 5) Explicitly say: consult your doctor or pharmacist before giving this medication"
}}""",

    "legal": """You are a strict legal content verification judge.

ORIGINAL INTENT: {intent}
LEGAL OUTPUT:
{output}

Check ALL of these — mark FAILED if missing:
1. Jurisdiction-specific applicability stated
2. Key exceptions or edge cases mentioned
3. Recommendation to consult a qualified lawyer
4. Any dangerous oversimplifications corrected

Respond ONLY in valid JSON — no other text:
{{
  "verified": true or false,
  "confidence": 0.0-1.0,
  "reason": "Missing: [exact legal gaps in the response]",
  "fix": "The complete legal answer must also include: [exact missing legal caveats]",
  "retry_prompt": "Rewrite the legal answer. You MUST include: 1) Which jurisdiction this applies to and where it may differ 2) Key exceptions to this rule 3) Potential consequences of getting this wrong 4) Explicitly recommend: consult a qualified lawyer for your specific situation"
}}""",

    "image": """You are verifying AI-generated images against the user's request.

ORIGINAL INTENT: {intent}
VERIFICATION NOTES: {output}

Respond ONLY in valid JSON — no other text:
{{
  "verified": true or false,
  "confidence": 0.0-1.0,
  "reason": "Specific image issue",
  "fix": "Images need: [exact fix]",
  "retry_prompt": "Regenerate the images. Make sure: 1) Each image is visually unique 2) Images match this description: [intent] 3) Use a different random seed for each image"
}}"""
}


def _get_provider():
    """Smart load balancer — picks the least-loaded available provider."""
    has_groq = len(GROQ_CLIENTS) > 0
    has_gemini = len(GEMINI_MODELS) > 0

    if has_groq and has_gemini:
        # 50/50 split between Groq and Gemini
        if random.random() < 0.5:
            return "groq", random.choice(GROQ_CLIENTS)
        else:
            return "gemini", random.choice(GEMINI_MODELS)
    elif has_groq:
        return "groq", random.choice(GROQ_CLIENTS)
    elif has_gemini:
        return "gemini", random.choice(GEMINI_MODELS)
    else:
        raise Exception("No AI provider available. Check API keys.")


def _call_provider(provider_type, provider, prompt):
    """Call the selected provider and return raw text."""
    if provider_type == "groq":
        response = provider.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=600
        )
        return response.choices[0].message.content.strip()
    else:
        import google.generativeai as genai
        response = provider.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.0, max_output_tokens=600)
        )
        return response.text.strip()


def _parse_json(raw):
    """Extract and parse JSON from model response."""
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)


def run_ai_judge(intent: str, ai_claim: str, output: str, task_type: str = "text", exec_result: str = "") -> dict:
    intent_lower = intent.lower()

    # Auto-detect task type
    if task_type == "text":
        script_signals = ["youtube script", "yt script", "video script", "write a script",
                          "write me a script", "5 minute script", "minute youtube",
                          "blog post", "linkedin post", "tiktok script"]
        medical_words = ["doctor", "patient", "diagnosis", "symptom", "medicine",
                         "drug", "dose", "dosage", "treatment", "disease", "medical",
                         "hospital", "prescription", "surgery", "paracetamol",
                         "ibuprofen", "antibiotic", "medication"]
        legal_words = ["law", "legal", "lawyer", "court", "contract",
                       "lawsuit", "attorney", "jurisdiction", "statute", "liability", "sue"]

        if any(w in intent_lower for w in script_signals):
            task_type = "script"
        elif any(w in intent_lower for w in medical_words):
            task_type = "medical"
        elif any(w in intent_lower for w in legal_words):
            task_type = "legal"

    template = JUDGE_PROMPTS.get(task_type, JUDGE_PROMPTS["text"])
    prompt = template.format(
        intent=intent,
        ai_claim=ai_claim,
        output=output[:3000],
        exec_result=exec_result
    )

    raw = None

    # Step 1: Shuffle and try all Groq keys until one works
    import random
    groq_pool = list(GROQ_CLIENTS)
    random.shuffle(groq_pool)
    
    for client in groq_pool:
        try:
            raw = _call_provider("groq", client, prompt)
            break  # Success! Exit the loop immediately
        except Exception as e:
            print(f"[Zerify] Groq key failed ({e}), trying next...")
            continue

    # Step 2: If ALL Groq keys fail, fallback to Gemini keys
    if not raw:
        print("[Zerify] All Groq keys failed. Falling back to Gemini.")
        gemini_pool = list(GEMINI_MODELS)
        random.shuffle(gemini_pool)
        
        for model in gemini_pool:
            try:
                raw = _call_provider("gemini", model, prompt)
                break  # Success! Exit the loop immediately
            except Exception as e:
                print(f"[Zerify] Gemini key failed ({e}), trying next...")
                continue

    # Step 3: If absolutely everything is dead, return the graceful error
    if not raw:
        return {
            "verified": False,
            "confidence": 0.5,
            "reason": "Verification service temporarily unavailable",
            "retry_prompt": f"Please redo this task carefully: {intent}"
        }

    try:
        result = _parse_json(raw)
        fix = str(result.get("fix", ""))
        retry = str(result.get("retry_prompt", ""))

        combined_retry = ""
        if fix and retry:
            combined_retry = f"{fix}\n\n{retry}"
        elif fix:
            combined_retry = fix
        elif retry:
            combined_retry = retry

        return {
            "verified": bool(result.get("verified", False)),
            "confidence": float(result.get("confidence", 0.7)),
            "reason": str(result.get("reason", "Verification incomplete")),
            "retry_prompt": combined_retry
        }
    except json.JSONDecodeError:
        return {
            "verified": False,
            "confidence": 0.5,
            "reason": "Judge returned invalid response",
            "retry_prompt": f"Please redo this task carefully: {intent}"
        }