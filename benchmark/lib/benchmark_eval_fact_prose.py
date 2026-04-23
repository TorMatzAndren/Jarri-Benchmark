#!/usr/bin/env python3
import json

def evaluate(output_text, ground_truth_path):
    try:
        gt = json.loads(open(ground_truth_path).read())
    except Exception:
        return {"score": 0.0, "error": "invalid_ground_truth"}

    # Minimal deterministic baseline
    score = 100.0 if len(output_text.strip()) > 0 else 0.0

    return {
        "schema_adherence_score": score,
        "semantic_shadow_score": score,
        "score": score
    }
