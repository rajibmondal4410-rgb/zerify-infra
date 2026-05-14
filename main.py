from fastapi.responses import HTMLResponse
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
from models import VerifyRequest, VerifyResponse, VerificationRecord
from verifiers.code_verifier import run_code_check
from verifiers.hash_verifier import check_files_exist, check_unique_images
from verifiers.text_verifier import basic_text_check
from verifiers.script_verifier import check_script
from verifiers.ai_judge import run_ai_judge
from auth import validate_api_key, generate_api_key, get_all_verifications, record_verification, DEMO_KEY, get_key_stats
from dotenv import load_dotenv
from datetime import datetime
import uuid

load_dotenv()

app = FastAPI(
    title="Zerify API",
    description="Zerify verifies, that AI did what it claimed.",
    version="0.2.0",
    docs_url="/docs"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    path = os.path.join(static_dir, "dashboard.html")
    with open(path) as f:
        return f.read()

@app.get("/signup", response_class=HTMLResponse)
def signup():
    path = os.path.join(static_dir, "signup.html")
    with open(path) as f:
        return f.read()

# ─────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────
@app.get("/")
def root():
    return {
        "product": "Zerify",
        "tagline": "Zerify verifies, that AI did what it claimed",
        "version": "0.2.0",
        "status": "running",
        "endpoints": {
            "verify": "POST /verify",
            "dashboard": "GET /dashboard",
            "new_key": "POST /keys/new",
            "my_stats": "GET /keys/stats",
            "docs": "GET /docs"
        }
    }

# ─────────────────────────────────────────
# API KEY MANAGEMENT
# ─────────────────────────────────────────
@app.post("/keys/new")
def create_key(name: str = "default"):
    key = generate_api_key(name)
    return {
        "api_key": key,
        "name": name,
        "message": "Add this to your requests as header: X-API-Key: <your_key>",
        "example": f'headers = {{"X-API-Key": "{key}"}}'
    }

@app.get("/keys/stats")
def key_stats(api_key: str = Depends(validate_api_key)):
    stats = get_key_stats(api_key)
    return {
        "api_key": api_key[:12] + "...",
        "name": stats.get("name", "unknown"),
        "total_calls": stats.get("calls", 0),
        "recent_verifications": stats.get("verifications", [])[-10:]
    }

@app.get("/demo-key")
def get_demo_key():
    """For testing — returns the pre-created demo key"""
    return {"demo_api_key": DEMO_KEY, "note": "Use this for testing only"}

# ─────────────────────────────────────────
# DASHBOARD DATA
# ─────────────────────────────────────────
@app.get("/dashboard/data")
def dashboard_data():
    verifications = get_all_verifications()
    total = len(verifications)
    passed = sum(1 for v in verifications if v.get("verified"))
    failed = total - passed
    
    by_type = {}
    for v in verifications:
        t = v.get("task_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round((passed / total * 100) if total > 0 else 0, 1),
        "by_type": by_type,
        "recent": verifications[:20]
    }

# ─────────────────────────────────────────
# MAIN VERIFY ENDPOINT
# ─────────────────────────────────────────
@app.post("/verify", response_model=VerifyResponse)
def verify(req: VerifyRequest, api_key: str = Depends(validate_api_key)):
    verification_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().isoformat()

    result = _run_verification(req)
    
    # Record this verification
    record = {
        "id": verification_id,
        "api_key": api_key,
        "task_type": req.task_type,
        "intent": req.intent[:100],
        "verified": result["verified"],
        "confidence": result["confidence"],
        "reason": result["reason"],
        "retry_prompt": result["retry_prompt"],
        "cost": result["cost"],
        "timestamp": timestamp
    }
    record_verification(api_key, record)

    return VerifyResponse(
        id=verification_id,
        verified=result["verified"],
        check_type=result["check_type"],
        confidence=result["confidence"],
        reason=result["reason"],
        retry_prompt=result["retry_prompt"],
        cost=result["cost"],
        task_type=req.task_type,
        timestamp=timestamp,
        retries_used=0
    )

def _run_verification(req: VerifyRequest) -> dict:
    """Core verification logic — separated so retry loop can call it"""

    # ── CODE ──
    if req.task_type == "code":
        code_result = run_code_check(req.output, req.language)

        judge_input = req.output
        # If it failed, pass the exact error to the AI Judge so it can explain how to fix it
        exec_result = code_result.get("output", "") if code_result["passed"] else code_result.get("error", "Execution failed")

        # ALWAYS run the AI judge to get the precise fix and retry prompt
        ai_result = run_ai_judge(req.intent, req.ai_claim, judge_input, task_type="code", exec_result=exec_result)

        # It is only verified if BOTH the code runs AND the AI judge approves
        is_verified = code_result["passed"] and ai_result["verified"]

        return {
            "verified": is_verified,
            "check_type": "code_execution + ai_judge",
            "confidence": ai_result["confidence"],
            "reason": ai_result["reason"],
            "retry_prompt": ai_result["retry_prompt"],
            "cost": "$0.005"
        }

        judge_input = req.output
        exec_result = code_result.get("output", "")
        ai_result = run_ai_judge(req.intent, req.ai_claim, judge_input, task_type="code", exec_result=exec_result)

        return {
            "verified": ai_result["verified"],
            "check_type": "code_execution + ai_judge",
            "confidence": ai_result["confidence"],
            "reason": ai_result["reason"],
            "retry_prompt": ai_result["retry_prompt"],
            "cost": "$0.005"
        }

    # ── SCRIPT (YouTube / Blog / Social) ──
    elif req.task_type == "script":
        platform = "youtube"
        if "blog" in req.intent.lower():
            platform = "blog"
        elif "linkedin" in req.intent.lower():
            platform = "linkedin"
        elif "twitter" in req.intent.lower() or "tweet" in req.intent.lower():
            platform = "twitter"

        script_check = check_script(req.intent, req.output, platform)

        if not script_check["passed"]:
            return {
                "verified": False,
                "check_type": "script_check",
                "confidence": 1.0,
                "reason": script_check["reason"],
                "retry_prompt": f"Rewrite the script. Problem: {script_check['reason']}. Original request: {req.intent}",
                "cost": "$0.0001"
            }

        ai_result = run_ai_judge(req.intent, req.ai_claim, req.output, task_type="script")
        return {
            "verified": ai_result["verified"],
            "check_type": f"script_check ({platform}) + ai_judge",
            "confidence": ai_result["confidence"],
            "reason": ai_result["reason"],
            "retry_prompt": ai_result["retry_prompt"],
            "cost": "$0.005"
        }

    # ── TEXT / MEDICAL / LEGAL ── (medical+legal use text pipeline with smart judge)
    elif req.task_type in ["text", "medical", "legal"]:
        basic = basic_text_check(req.intent, req.output)

        if not basic["passed"]:
            return {
                "verified": False,
                "check_type": "basic_text_check",
                "confidence": 1.0,
                "reason": basic["reason"],
                "retry_prompt": f"Answer was invalid. Please properly answer: {req.intent}",
                "cost": "$0.0001"
            }

        ai_result = run_ai_judge(req.intent, req.ai_claim, req.output, task_type="text")
        return {
            "verified": ai_result["verified"],
            "check_type": "text + ai_judge",
            "confidence": ai_result["confidence"],
            "reason": ai_result["reason"],
            "retry_prompt": ai_result["retry_prompt"],
            "cost": "$0.005"
        }

    # ── FILE ──
    elif req.task_type == "file":
        if not req.file_paths:
            return {
                "verified": False,
                "check_type": "file_existence",
                "confidence": 1.0,
                "reason": "No file paths provided to verify",
                "retry_prompt": "Provide the paths of files that were created",
                "cost": "$0.0001"
            }

        results = check_files_exist(req.file_paths)
        missing = [r["path"] for r in results if not r["exists"]]

        if missing:
            return {
                "verified": False,
                "check_type": "file_existence",
                "confidence": 1.0,
                "reason": f"Missing files: {missing}",
                "retry_prompt": f"These files were NOT created: {missing}. Create them now.",
                "cost": "$0.0001"
            }

        return {
            "verified": True,
            "check_type": "file_existence",
            "confidence": 1.0,
            "reason": f"All {len(req.file_paths)} files exist",
            "retry_prompt": "",
            "cost": "$0.0001"
        }

    # ── IMAGE ──
    elif req.task_type == "image":
        if not req.file_paths:
            return {
                "verified": False,
                "check_type": "image_hash",
                "confidence": 1.0,
                "reason": "No image paths provided",
                "retry_prompt": "Provide paths to the generated images",
                "cost": "$0.0001"
            }

        exists_check = check_files_exist(req.file_paths)
        missing = [r["path"] for r in exists_check if not r["exists"]]
        if missing:
            return {
                "verified": False,
                "check_type": "image_existence",
                "confidence": 1.0,
                "reason": f"Images not found: {missing}",
                "retry_prompt": f"These images were not generated: {missing}. Regenerate them.",
                "cost": "$0.0001"
            }

        unique_check = check_unique_images(req.file_paths)
        if not unique_check["all_unique"]:
            dupes = [d["file"] for d in unique_check["duplicates"]]
            return {
                "verified": False,
                "check_type": "image_hash",
                "confidence": 1.0,
                "reason": f"Duplicate images detected: {dupes}",
                "retry_prompt": f"Images {dupes} are exact duplicates. Regenerate with different seed/prompt variation.",
                "cost": "$0.0001"
            }

        return {
            "verified": True,
            "check_type": "image_hash",
            "confidence": 0.95,
            "reason": f"All {len(req.file_paths)} images exist and are unique",
            "retry_prompt": "",
            "cost": "$0.0001"
        }

    # ── UNSUPPORTED ──
    else:
        return {
            "verified": False,
            "check_type": "unknown",
            "confidence": 0.0,
            "reason": f"task_type '{req.task_type}' not supported. Use: code, text, script, file, image",
            "retry_prompt": "",
            "cost": "$0"
        }
    
@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return """
    <html>
        <head>
            <title>Zerify Privacy Policy</title>
            <style>
                body { font-family: sans-serif; padding: 50px; line-height: 1.6; max-width: 800px; margin: auto; background-color: #f9f9f9; }
                h1 { color: #7c3aed; }
                .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Privacy Policy for Zerify</h1>
                <p><strong>Last Updated: May 14, 2026</strong></p>
                <p>Zerify is committed to your privacy. This policy explains our data practices.</p>
                
                <h3>1. Data Usage</h3>
                <p>We process AI-generated content and your prompts solely to identify hallucinations. We do not store this data permanently on our servers.</p>
                
                <h3>2. No Data Selling</h3>
                <p>We do not sell, trade, or transfer your data to any third parties.</p>
                
                <h3>3. Required Permissions</h3>
                <p>The 'activeTab' and 'storage' permissions are used only to show the verification UI and handle session states.</p>
                
                <p>For support: <strong>rajibmondal4410@gmail.com</strong></p>
            </div>
        </body>
    </html>
    """