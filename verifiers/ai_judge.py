import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

JUDGE_PROMPTS = {
    "code": """You are a strict code verification judge.

ORIGINAL INTENT: {intent}
CODE SUBMITTED:
{output}
EXECUTION RESULT: {exec_result}

Evaluate:
- Does the code run without errors?
- Does it correctly solve the intent?
- Are there syntax errors or logic errors?

Respond ONLY in valid JSON:
{{
  "verified": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Exact issue: line X has Y problem",
  "fix": "Here is the corrected code: [paste exact corrected code]",
  "retry_prompt": "Fix this exact error in the code: [describe exact fix needed with line reference]"
}}""",

    "text": """You are a strict content verification judge.

ORIGINAL INTENT: {intent}
ACTUAL OUTPUT:
{output}

Evaluate:
- Does the output FULLY answer what was asked?
- Is anything missing or wrong?

Respond ONLY in valid JSON:
{{
  "verified": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Specific: missing X, Y, Z",
  "fix": "The correct complete answer should include: [list exactly what is missing]",
  "retry_prompt": "Rewrite your answer. You must include: 1) [specific thing] 2) [specific thing] 3) [specific thing]. Do not skip any of these."
}}""",

    "script": """You are a YouTube/content script verification judge.

ORIGINAL INTENT: {intent}
SCRIPT:
{output}

Rules:
- If script has hook + body + over 200 words = verified true
- Only fail if under 100 words, off-topic, or no structure
- Never fail for missing legal disclaimers

Respond ONLY in valid JSON:
{{
  "verified": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Specific script issue",
  "fix": "The script needs: [exact improvements]",
  "retry_prompt": "Rewrite the script with: 1) A stronger hook in first 30 seconds 2) At least 400 words 3) Clear CTA at the end saying [specific CTA]"
}}""",

    "medical": """You are a strict medical content verification judge.

ORIGINAL INTENT: {intent}
MEDICAL OUTPUT:
{output}

Check:
- Is medical information complete and safe?
- Are dosages, warnings, or critical info missing?
- Does it recommend consulting a doctor?

Respond ONLY in valid JSON:
{{
  "verified": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Specific medical issue: missing X warning",
  "fix": "The safe and complete answer must include: [exact missing medical info]",
  "retry_prompt": "Rewrite with: 1) weight-based dosing if applicable 2) age-specific warnings 3) contraindications 4) explicitly recommend consulting a doctor before use"
}}""",

    "legal": """You are a strict legal content verification judge.

ORIGINAL INTENT: {intent}
LEGAL OUTPUT:
{output}

Check:
- Is legal information accurate?
- Are jurisdiction caveats missing?
- Does it recommend consulting a lawyer?

Respond ONLY in valid JSON:
{{
  "verified": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Specific legal issue: missing X caveat",
  "fix": "The complete legal answer must include: [exact missing legal points]",
  "retry_prompt": "Rewrite including: 1) jurisdiction-specific caveats 2) exceptions to the rule 3) recommend consulting a qualified lawyer for this specific situation"
}}""",

    "image": """You are verifying AI-generated images against the user's request.

ORIGINAL INTENT: {intent}
VERIFICATION NOTES: {output}

Respond ONLY in valid JSON:
{{
  "verified": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Specific image issue",
  "fix": "Images need: [exact fix]",
  "retry_prompt": "Regenerate the images with: [specific corrections needed]"
}}"""
}


def run_ai_judge(intent: str, ai_claim: str, output: str, task_type: str = "text", exec_result: str = "") -> dict:
    intent_lower = intent.lower()

    if task_type == "text":
        script_signals = ["youtube script", "blog post", "video script",
                          "script about", "write a script", "5 minute script",
                          "minute youtube", "write me a script"]
        if any(w in intent_lower for w in script_signals):
            task_type = "script"
        else:
            medical_words = ["doctor", "patient", "diagnosis", "symptom", "medicine",
                             "drug", "dose", "treatment", "disease", "medical",
                             "hospital", "prescription", "surgery", "dosage"]
            legal_words = ["law", "legal", "lawyer", "court", "contract",
                           "lawsuit", "attorney", "jurisdiction", "statute", "liability"]
            if any(w in intent_lower for w in medical_words):
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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=600
    )

    raw = response.choices[0].message.content.strip()

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

    try:
        result = json.loads(raw)
        fix = str(result.get("fix", ""))
        retry = str(result.get("retry_prompt", ""))
        # Combine fix + retry into one powerful prompt
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