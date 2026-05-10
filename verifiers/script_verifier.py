"""
Script verifier for YouTube videos, blog posts, LinkedIn posts, social content.
This is a pure text analysis — no AI needed for basic checks.
"""

import re

FILLER_PHRASES = [
    "in today's video", "don't forget to subscribe", "hit the like button",
    "in this article", "in conclusion", "to summarize", "as you can see",
    "it goes without saying", "needless to say", "at the end of the day",
    "at this point in time", "due to the fact that", "in order to",
    "delve into", "dive deep", "game changer", "leverage", "synergy",
    "it's important to note", "i'm going to be talking about"
]

PLATFORM_MINIMUMS = {
    "youtube": 300,
    "blog": 500,
    "linkedin": 100,
    "twitter": 20,
    "instagram": 30,
    "tiktok": 50,
    "default": 100
}

def check_script(intent: str, output: str, platform: str = "youtube") -> dict:
    """
    Run C+H checks on script content before sending to AI judge.
    Returns pass/fail with specific failure reasons.
    """
    issues = []
    word_count = len(output.split())
    min_words = PLATFORM_MINIMUMS.get(platform.lower(), PLATFORM_MINIMUMS["default"])

    # Check 1 — Empty output
    if not output or output.strip() == "":
        return {
            "passed": False,
            "reason": "Script is completely empty",
            "needs_ai_judge": False,
            "word_count": 0
        }

    # Check 2 — Too short
    if word_count < min_words:
        return {
            "passed": False,
            "reason": f"Script is too short ({word_count} words). Minimum for {platform}: {min_words} words",
            "needs_ai_judge": False,
            "word_count": word_count
        }

    # Check 3 — Just repeated the prompt back
    intent_words = set(intent.lower().split())
    output_words = set(output.lower().split())
    overlap_ratio = len(intent_words & output_words) / max(len(intent_words), 1)
    if overlap_ratio > 0.75 and word_count < 50:
        return {
            "passed": False,
            "reason": "Script appears to just repeat the original request",
            "needs_ai_judge": False,
            "word_count": word_count
        }

    # Check 4 — Filler phrase overload (3+ is a problem)
    filler_count = sum(1 for phrase in FILLER_PHRASES if phrase in output.lower())
    if filler_count >= 3:
        issues.append(f"Contains {filler_count} generic filler phrases — script feels AI-generated")

    # Check 5 — No structure (for longer content)
    if word_count > 200:
        has_hook = any(output[:200].count(c) > 0 for c in ["?", "!", "You", "Have you", "Ever"])
        if not has_hook:
            issues.append("Missing a hook in the opening — first 200 chars don't engage")

    # Passed basic checks
    return {
        "passed": True,
        "reason": "Passed basic checks" + (f". Warnings: {'; '.join(issues)}" if issues else ""),
        "needs_ai_judge": True,
        "word_count": word_count,
        "warnings": issues
    }