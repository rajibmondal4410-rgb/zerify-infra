import subprocess
import tempfile
import os
import re

def run_code_check(code: str, language: str = "python") -> dict:
    if language.lower() not in ["python", "py"]:
        return {
            "passed": False,
            "output": None,
            "error": f"Language '{language}' not supported yet. Only Python supported.",
            "syntax_errors": []
        }

    # Quick syntax check first (no execution)
    syntax_errors = check_syntax(code)
    if syntax_errors:
        return {
            "passed": False,
            "output": None,
            "error": f"Syntax error: {syntax_errors[0]}",
            "syntax_errors": syntax_errors
        }

    # Execute in temp file
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        os.unlink(tmp_path)

        if result.returncode == 0:
            return {
                "passed": True,
                "output": result.stdout.strip(),
                "error": None,
                "syntax_errors": []
            }
        else:
            # Extract the most useful part of the error
            error_msg = result.stderr.strip()
            error_lines = error_msg.split('\n')
            # Get last meaningful error line
            relevant_error = next(
                (l for l in reversed(error_lines) if l.strip() and not l.startswith(' ')),
                error_msg
            )
            return {
                "passed": False,
                "output": None,
                "error": relevant_error,
                "full_error": error_msg,
                "syntax_errors": []
            }

    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "output": None,
            "error": "Code execution timed out after 10 seconds — possible infinite loop",
            "syntax_errors": []
        }
    except Exception as e:
        return {
            "passed": False,
            "output": None,
            "error": str(e),
            "syntax_errors": []
        }

def check_syntax(code: str) -> list:
    """Fast syntax check without executing"""
    try:
        compile(code, "<string>", "exec")
        return []
    except SyntaxError as e:
        return [f"Line {e.lineno}: {e.msg}"]