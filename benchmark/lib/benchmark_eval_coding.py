#!/usr/bin/env python3
import subprocess

def evaluate(code_path):
    try:
        subprocess.check_output(
            ["python3", code_path],
            stderr=subprocess.STDOUT,
            timeout=10
        )
        return {
            "execution_status": "success",
            "artifact_usability": "usable",
            "score": 100.0
        }
    except subprocess.CalledProcessError:
        return {
            "execution_status": "runtime_error",
            "artifact_usability": "unusable",
            "score": 0.0
        }
    except Exception:
        return {
            "execution_status": "failure",
            "artifact_usability": "unusable",
            "score": 0.0
        }
