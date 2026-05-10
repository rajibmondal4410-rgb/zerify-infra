def basic_text_check(intent: str, output: str) -> dict:
    if not output or output.strip() == "":
        return {"passed": False, "reason": "Output is empty", "needs_ai_judge": False}

    if len(output.strip()) < 10:
        return {"passed": False, "reason": "Output is too short to be meaningful", "needs_ai_judge": False}

    intent_words = set(intent.lower().split())
    output_words = set(output.lower().split())
    overlap = intent_words.intersection(output_words)
    if len(overlap) / max(len(intent_words), 1) > 0.8 and len(output.split()) < 20:
        return {"passed": False, "reason": "Output appears to just repeat the question", "needs_ai_judge": False}

    return {"passed": True, "reason": "Passed basic checks", "needs_ai_judge": True}