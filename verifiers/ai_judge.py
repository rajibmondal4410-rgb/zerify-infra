import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

JUDGE_PROMPTS = {
    "code": """You are a strict code verification judge. Be precise and binary.

ORIGINAL INTENT: {intent}
AI CLAIMED: {ai_claim}

CODE SUBMITTED:
{output}

EXECUTION RESULT: {exec_result}

Evaluate EXACTLY:
- Does the code run without errors?
- Does it correctly solve what was asked?
- Are there syntax errors, logic errors, missing colons, wrong indentation?

Give confidence as your TRUE certainty — 1.0 only if absolutely certain, 0.5 if ambiguous.
Point to the EXACT line or character that is wrong in the reason.

Respond ONLY in valid JSON:
{{"verified": true/false, "confidence": 0.0-1.0, "reason": "specific failure: line X has Y problem", "retry_prompt": "Fix line X: change Y to Z"}}""",

    "text": """You are a strict content verification judge.

ORIGINAL INTENT: {intent}
AI CLAIMED: {ai_claim}

ACTUAL OUTPUT:
{output}

Evaluate EXACTLY:
- Does the output FULLY answer what was asked?
- Is it too short, incomplete, or missing key sections?
- Does it contain wrong information?
- Is it off-topic?

Be specific about EXACTLY what is missing or wrong.
Give confidence as your TRUE certainty — do NOT default to 0.8.

Respond ONLY in valid JSON:
{{"verified": true/false, "confidence": 0.0-1.0, "reason": "specific: missing X, Y, Z sections", "retry_prompt": "Rewrite including: 1) X 2) Y 3) Z with specific details"}}""",

    "script": """You are a YouTube/content script verification judge.

ORIGINAL INTENT: {intent}
AI CLAIMED: {ai_claim}

SCRIPT:
{output}

Rules:
- If the script has a hook, body content, and is over 200 words — verified=true
- Do NOT fail for missing legal disclaimers — that is not a script quality issue
- Only fail if: too short under 100 words, completely off-topic, or has no structure at all

Check:
1. Does it have an opening hook?
2. Is it over 200 words?
3. Does it match the topic requested?

Give confidence as your TRUE certainty.

Respond ONLY in valid JSON:
{{"verified": true/false, "confidence": 0.0-1.0, "reason": "specific script issue only", "retry_prompt": "Rewrite with: 1) stronger hook 2) more specific content 3) clear CTA at end"}}""",

    "medical": """You are a strict medical content verification judge.

ORIGINAL INTENT: {intent}
AI CLAIMED: {ai_claim}

MEDICAL OUTPUT:
{output}

Check EXACTLY:
- Is the medical information accurate and complete?
- Are critical symptoms, dosages, or warnings missing?
- Does it recommend professional consultation where needed?
- Are there any dangerous omissions or errors?

Give confidence as your TRUE certainty.

Respond ONLY in valid JSON:
{{"verified": true/false, "confidence": 0.0-1.0, "reason": "specific medical issue: missing X warning, wrong Y dosage", "retry_prompt": "Rewrite including: 1) specific missing information 2) safety warnings 3) recommend doctor consultation"}}""",

    "legal": """You are a strict legal content verification judge.

ORIGINAL INTENT: {intent}
AI CLAIMED: {ai_claim}

LEGAL OUTPUT:
{output}

Check EXACTLY:
- Is the legal information accurate for the jurisdiction mentioned?
- Are critical legal caveats or exceptions missing?
- Does it recommend professional legal counsel where needed?
- Are there dangerous omissions or incorrect statements?

Give confidence as your TRUE certainty.

Respond ONLY in valid JSON:
{{"verified": true/false, "confidence": 0.0-1.0, "reason": "specific legal issue: missing X caveat, wrong Y statement", "retry_prompt": "Rewrite including: 1) specific missing legal points 2) jurisdiction caveats 3) recommend consulting a lawyer"}}""",

    "image": """You are verifying whether AI-generated images match the user's request.

ORIGINAL INTENT: {intent}
AI CLAIMED: {ai_claim}
VERIFICATION NOTES: {output}

Based on the existence and hash checks, determine if images were correctly generated.

Respond ONLY in valid JSON:
{{"verified": true/false, "confidence": 0.0-1.0, "reason": "specific issue with images", "retry_prompt": "precise fix instruction"}}"""
}


def run_ai_judge(intent: str, ai_claim: str, output: str, task_type: str = "text", exec_result: str = "") -> dict:
    intent_lower = intent.lower()
    output_lower = output.lower()

    if task_type == "text":
        # Check SCRIPT first — user asked for a script
        script_signals = ["youtube script", "blog post", "video script",
                          "script about", "write a script", "5 minute script",
                          "minute youtube", "write me a script"]
        if any(w in intent_lower for w in script_signals):
            task_type = "script"
        else:
            # Only check medical/legal if NOT a script
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
        max_tokens=400
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
        return {
            "verified": bool(result.get("verified", False)),
            "confidence": float(result.get("confidence", 0.7)),
            "reason": str(result.get("reason", "Verification incomplete")),
            "retry_prompt": str(result.get("retry_prompt", ""))
        }
    except json.JSONDecodeError:
        return {
            "verified": False,
            "confidence": 0.5,
            "reason": "Judge returned invalid response",
            "retry_prompt": f"Please redo this task carefully: {intent}"
        }