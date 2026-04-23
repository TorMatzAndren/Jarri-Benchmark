#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

EVALUATOR_VERSION = "fact_prose_eval_v7"


def normalize(text: str | None) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = text.strip().lower()
    text = text.replace("⁻", "-")
    text = text.replace("−", "-")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("°", "")
    text = text.replace("ₐ", "_a")
    text = text.replace("−1", "-1")
    text = text.replace("⁻¹", "^-1")
    text = text.replace("→", "->")
    text = re.sub(r"\s+", " ", text)
    return text


def count_words(text: str) -> int:
    return len(re.findall(r"\b\S+\b", text))


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def classify_confidence(score: float, flags: list[dict[str, Any]]) -> str:
    if score >= 95 and not flags:
        return "strict"
    if score >= 60:
        return "partial"
    return "incorrect"


def try_json_loads(text: str) -> dict[str, Any] | list[Any]:
    return json.loads(text)


def _coerce_jsonish_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, dict):
        preferred_keys = [
            "text",
            "step",
            "content",
            "description",
            "instruction",
            "rewrite",
            "summary",
            "value",
            "output",
            "answer",
            "title",
            "label",
            "message",
        ]

        collected: list[str] = []
        for key in preferred_keys:
            item = value.get(key)
            if item is not None:
                rendered = _coerce_jsonish_text(item)
                if rendered:
                    collected.append(rendered)

        if collected:
            return " ".join(collected).strip()

        fallback_parts: list[str] = []
        for key, item in value.items():
            rendered = _coerce_jsonish_text(item)
            if rendered:
                fallback_parts.append(f"{key}: {rendered}")

        return " ".join(fallback_parts).strip()

    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            rendered = _coerce_jsonish_text(item)
            if rendered:
                parts.append(rendered)
        return " ".join(parts).strip()

    return str(value).strip()


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            rendered = _coerce_jsonish_text(item)
            if rendered:
                parts.append(rendered)
        return parts

    rendered = _coerce_jsonish_text(value)
    return [rendered] if rendered else []


def _coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value:
            return default
        return int(value)

    text = _coerce_jsonish_text(value)
    if not text:
        return default

    try:
        return int(text)
    except ValueError:
        pass

    match = re.search(r"-?\d+", text)
    if match:
        try:
            return int(match.group(0))
        except ValueError:
            return default
    return default


def base_report(
    *,
    format_valid: bool,
    usable_output: bool,
    pipeline_usable: bool,
    schema_coerced: bool,
    hard_failure: bool,
    hard_failure_reason: str | None,
    confidence_classification: str,
    hallucination_flags: list[dict[str, Any]],
    score_percent: float,
    factual_accuracy_score: float = 0.0,
    hallucination_penalty: float = 0.0,
    reasoning_consistency_score: float = 0.0,
    compression_efficiency_score: float = 0.0,
    constraint_adherence_score: float = 0.0,
    schema_adherence_score: float = 0.0,
    semantic_shadow_score: float = 0.0,
    derived_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = {
        "evaluator_version": EVALUATOR_VERSION,
        "format_valid": format_valid,
        "usable_output": usable_output,
        "pipeline_usable": pipeline_usable,
        "schema_coerced": schema_coerced,
        "hard_failure": hard_failure,
        "hard_failure_reason": hard_failure_reason,
        "confidence_classification": confidence_classification,
        "hallucination_flags": hallucination_flags,
        "score": {
            "score_percent": round(score_percent, 2),
            "score_per_process": round(score_percent, 2),
            "factual_accuracy_score": round(factual_accuracy_score, 2),
            "hallucination_penalty": round(hallucination_penalty, 2),
            "reasoning_consistency_score": round(reasoning_consistency_score, 2),
            "compression_efficiency_score": round(compression_efficiency_score, 2),
            "constraint_adherence_score": round(constraint_adherence_score, 2),
            "schema_adherence_score": round(schema_adherence_score, 2),
            "semantic_shadow_score": round(semantic_shadow_score, 2),
        },
    }
    if derived_metrics is not None:
        report["derived_metrics"] = derived_metrics
    return report


def hard_failure_result(reason: str, *, semantic_shadow_score: float = 0.0) -> dict[str, Any]:
    return base_report(
        format_valid=False,
        usable_output=False,
        pipeline_usable=False,
        schema_coerced=False,
        hard_failure=True,
        hard_failure_reason=reason,
        confidence_classification="incorrect",
        hallucination_flags=[{"type": reason}],
        score_percent=0.0,
        factual_accuracy_score=0.0,
        hallucination_penalty=0.0,
        reasoning_consistency_score=0.0,
        compression_efficiency_score=0.0,
        constraint_adherence_score=0.0,
        schema_adherence_score=0.0,
        semantic_shadow_score=semantic_shadow_score,
    )


ALIASES = {
    "stores genetic information": [
        "stores genetic information",
        "genetic information storage",
        "stores hereditary information",
        "holds genetic information",
        "genetic material",
    ],
    "deoxyribonucleic acid": [
        "deoxyribonucleic acid",
    ],
    "normans": [
        "normans",
        "the normans",
        "william the conqueror",
        "duke william of normandy",
    ],
    "england": [
        "england",
        "united kingdom",
        "great britain",
        "britain",
    ],
    "m/s": [
        "m/s",
        "meters per second",
        "metres per second",
    ],
    "c/k": [
        "c/k",
        "c",
        "k",
        "celsius/kelvin",
        "kelvin/celsius",
        "°c",
        "celsius",
        "kelvin",
    ],
    "mol^-1": [
        "mol^-1",
        "mol-1",
        "mol⁻¹",
        "1/mol",
    ],
    "c": [
        "c",
    ],
    "n_a": [
        "n_a",
        "na",
        "nₐ",
    ],
}


def alias_match(gt: str, pred: Any) -> float:
    if pred is None:
        return 0.0
    gt_norm = normalize(gt)
    pred_norm = normalize(str(pred))
    accepted = ALIASES.get(gt_norm, [gt_norm])
    accepted_norm = [normalize(x) for x in accepted]
    return 1.0 if pred_norm in accepted_norm else 0.0


def near_alias_match(gt: str, pred: Any) -> float:
    if pred is None:
        return 0.0
    gt_norm = normalize(gt)
    pred_norm = normalize(str(pred))
    if pred_norm == gt_norm:
        return 1.0
    if gt_norm in pred_norm or pred_norm in gt_norm:
        return 0.7

    accepted = [normalize(x) for x in ALIASES.get(gt_norm, [gt_norm])]
    if pred_norm in accepted:
        return 1.0

    for accepted_value in accepted:
        if accepted_value in pred_norm or pred_norm in accepted_value:
            return 0.7
    return 0.0


def score_numeric_field(gt: float, pred: Any) -> float:
    try:
        pred_val = float(pred)
    except (TypeError, ValueError):
        return 0.0

    if pred_val == gt:
        return 1.0
    if gt == 0:
        return 0.8 if abs(pred_val) < 1e-9 else 0.0

    rel_err = abs(pred_val - gt) / abs(gt)
    if rel_err <= 0.001:
        return 0.8
    if rel_err <= 0.01:
        return 0.5
    return 0.0


def semantic_unit_present(unit: str, text: str) -> bool:
    unit_norm = normalize(unit)
    text_norm = normalize(text)

    unit_alias_map = {
        "began in 2018": ["began in 2018", "started in 2018"],
        "university robotics collaboration": ["university robotics collaboration", "robotics collaboration at a university"],
        "low-cost autonomous navigation": ["low-cost autonomous navigation", "affordable self-driving navigation"],
        "three prototype vehicles by 2020": ["three prototype vehicles by 2020", "three prototypes by 2020"],
        "sensor failures delayed deployment": ["sensor failures delayed deployment", "sensor issues delayed field deployment"],
        "switched in 2021 to lidar-assisted hybrid approach": ["switched in 2021 to lidar-assisted hybrid approach", "moved in 2021 to a lidar-assisted hybrid design"],
        "navigation errors reduced by 37 percent": ["reduced navigation errors by 37 percent", "navigation errors fell by 37 percent"],
        "municipal funding for snow-clearing route analysis": ["municipal funding for snow-clearing route analysis", "town funding for snow-clearing route analysis"],
        "not commercialized": ["not commercialized", "never commercialized"],
        "datasets widely used in academic research": ["datasets widely used in academic research", "datasets became widely used in research"],
        "compare log files from last run and current run": ["compare log files from last run and current run"],
        "exclude archived broken run unless missing data requires it": ["exclude archived broken run unless missing data requires it", "use the archived broken run only if data is missing"],
        "summary short enough for email": ["summary short enough for email", "summary brief enough for email"],
        "include failure reasons": ["include failure reasons", "include reasons for failures"],
        "check whether parser used new config": ["check whether parser used new config", "verify that the parser used the new config"],
        "mention major timing changes": ["mention major timing changes", "mention significant timing changes"],
        "include invalid rows": ["include invalid rows"],
        "include malformed json": ["include malformed json"],
        "output suitable for ops": ["output suitable for ops", "something ops can read without questions"],
    }

    candidates = unit_alias_map.get(unit_norm, [unit_norm])
    return any(normalize(candidate) in text_norm for candidate in candidates)


def count_ambiguity_patterns(text: str) -> int:
    patterns = [
        r"\bit\b",
        r"\bthat\b",
        r"\bsomething\b",
        r"\betc\b",
        r"\band so on\b",
    ]
    total = 0
    ntext = normalize(text)
    for pattern in patterns:
        total += len(re.findall(pattern, ntext))
    return total


def count_redundant_units(text: str) -> int:
    sentences = [normalize(x) for x in re.split(r"[.!?;]+", text) if normalize(x)]
    seen = set()
    dup = 0
    for sentence in sentences:
        if sentence in seen:
            dup += 1
        else:
            seen.add(sentence)
    return dup


def database_index_relevant(text: str) -> bool:
    normalized = normalize(text)
    key_terms = ["find", "search", "rows", "records", "faster", "look up", "locate", "without scanning everything"]
    return any(term in normalized for term in key_terms)


def iter_fenced_blocks(text: str) -> list[str]:
    pattern = re.compile(r"```(?:json)?\s*(.*?)```", flags=re.DOTALL | re.IGNORECASE)
    return [match.strip() for match in pattern.findall(text)]


def extract_balanced_json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    start_indices = []
    for idx, ch in enumerate(text):
        if ch in "{[":
            start_indices.append((idx, ch))

    for start_idx, opener in start_indices:
        closer = "}" if opener == "{" else "]"
        depth = 0
        in_string = False
        escape = False

        for end_idx in range(start_idx, len(text)):
            ch = text[end_idx]

            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    candidate = text[start_idx:end_idx + 1].strip()
                    candidates.append(candidate)
                    break

    candidates = list(dict.fromkeys(candidates))
    candidates.sort(key=len, reverse=True)
    return candidates


def parse_json_with_recovery(text: str) -> tuple[dict[str, Any] | list[Any] | None, str | None, bool]:
    try:
        return try_json_loads(text), None, False
    except Exception:
        pass

    fenced_blocks = iter_fenced_blocks(text)

    for block in fenced_blocks:
        try:
            return try_json_loads(block), None, True
        except Exception:
            continue

    candidates = extract_balanced_json_candidates(text)
    for candidate in candidates:
        try:
            return try_json_loads(candidate), None, True
        except Exception:
            continue

    return None, "invalid_json", False


def parse_fact_task_1_multi_block_items(text: str) -> tuple[dict[str, Any] | None, bool]:
    items: list[Any] = []

    blocks = iter_fenced_blocks(text)
    if not blocks:
        return None, False

    for block in blocks:
        try:
            parsed = try_json_loads(block)
        except Exception:
            continue

        if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
            items.extend(parsed["items"])
        elif isinstance(parsed, list):
            items.extend(parsed)

    if not items:
        return None, False

    return {"items": items}, True


def coerce_fact_task_1_root(parsed: Any) -> tuple[dict[str, Any] | None, bool]:
    if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
        return parsed, False
    if isinstance(parsed, list):
        return {"items": parsed}, True
    return None, False


def score_fact_task_1_semantic(pred: dict[str, Any], gt: dict[str, Any]) -> tuple[float, list[dict[str, Any]], dict[str, Any]]:
    gt_items = gt.get("items", [])
    pred_items = pred.get("items", [])

    gt_by_entity = {normalize(item["entity"]): item for item in gt_items if isinstance(item, dict) and "entity" in item}
    pred_by_entity = {
        normalize(item.get("entity")): item
        for item in pred_items
        if isinstance(item, dict) and item.get("entity") is not None
    }

    total_possible = 0.0
    total_awarded = 0.0
    hallucination_flags: list[dict[str, Any]] = []
    matched_entities = 0
    category_points = 0.0
    category_possible = 0.0
    field_mismatch_count = 0
    category_mismatch_count = 0

    for entity_key, gt_item in gt_by_entity.items():
        gt_fields = gt_item.get("fields", {})
        pred_item = pred_by_entity.get(entity_key)

        if pred_item is None:
            total_possible += len(gt_fields)
            category_possible += 1.0
            continue

        matched_entities += 1
        category_possible += 1.0
        pred_category = pred_item.get("category")
        gt_category = gt_item.get("category")
        category_match_score = near_alias_match(str(gt_category), pred_category)
        category_points += category_match_score
        if category_match_score < 1.0:
            category_mismatch_count += 1

        pred_fields = pred_item.get("fields", {})
        if not isinstance(pred_fields, dict):
            total_possible += len(gt_fields)
            field_mismatch_count += len(gt_fields)
            continue

        for field_name, gt_value in gt_fields.items():
            total_possible += 1.0
            pred_value = pred_fields.get(field_name)

            if isinstance(gt_value, (int, float)):
                awarded = score_numeric_field(float(gt_value), pred_value)
            else:
                awarded = near_alias_match(str(gt_value), pred_value)

            total_awarded += awarded
            if awarded < 1.0:
                field_mismatch_count += 1

        extra_fields = sorted(set(pred_fields.keys()) - set(gt_fields.keys()))
        for extra in extra_fields:
            hallucination_flags.append({"type": "extra_field", "entity": gt_item.get("entity"), "field": extra})

    extra_entities = sorted(set(pred_by_entity.keys()) - set(gt_by_entity.keys()))
    for extra_entity in extra_entities:
        hallucination_flags.append({"type": "extra_entity", "entity": pred_by_entity[extra_entity].get("entity")})

    field_score = 100.0 * total_awarded / total_possible if total_possible else 0.0
    entity_coverage_score = 100.0 * matched_entities / max(1, len(gt_by_entity))
    category_score = 100.0 * category_points / category_possible if category_possible else 0.0

    semantic_score = (
        0.65 * field_score +
        0.20 * entity_coverage_score +
        0.15 * category_score
    )

    details = {
        "field_score": round(field_score, 2),
        "entity_coverage_score": round(entity_coverage_score, 2),
        "category_score": round(category_score, 2),
        "matched_entities": matched_entities,
        "expected_entities": len(gt_by_entity),
        "field_mismatch_count": field_mismatch_count,
        "category_mismatch_count": category_mismatch_count,
    }
    return semantic_score, hallucination_flags, details


def evaluate_fact_task_1(text: str, gt: dict[str, Any]) -> dict[str, Any]:
    parsed, parse_error, parse_recovered = parse_json_with_recovery(text)

    multi_block_used = False
    if parse_error:
        merged, merged_ok = parse_fact_task_1_multi_block_items(text)
        if merged_ok:
            parsed = merged
            parse_error = None
            parse_recovered = True
            multi_block_used = True

    if parse_error:
        return hard_failure_result(parse_error)

    coerced, schema_coerced = coerce_fact_task_1_root(parsed)
    if coerced is None:
        return hard_failure_result("schema_invalid")

    semantic_score, hallucination_flags, details = score_fact_task_1_semantic(coerced, gt)

    strict_schema_score = 100.0
    if parse_recovered:
        strict_schema_score -= 20.0
    if schema_coerced:
        strict_schema_score -= 20.0
    if multi_block_used:
        strict_schema_score -= 20.0
    strict_schema_score = clamp(strict_schema_score)

    hallucination_penalty = -3.0 * len([flag for flag in hallucination_flags if flag["type"] == "extra_field"])
    hallucination_penalty += -6.0 * len([flag for flag in hallucination_flags if flag["type"] == "extra_entity"])

    final_score = clamp(0.8 * semantic_score + 0.2 * strict_schema_score + hallucination_penalty)

    pipeline_usable = strict_schema_score >= 80.0
    usable_output = semantic_score >= 40.0

    details["parse_recovered"] = parse_recovered
    details["schema_coerced"] = schema_coerced
    details["multi_block_merged"] = multi_block_used

    return base_report(
        format_valid=True,
        usable_output=usable_output,
        pipeline_usable=pipeline_usable,
        schema_coerced=(parse_recovered or schema_coerced or multi_block_used),
        hard_failure=False,
        hard_failure_reason=None,
        confidence_classification=classify_confidence(final_score, hallucination_flags),
        hallucination_flags=hallucination_flags,
        score_percent=final_score,
        factual_accuracy_score=semantic_score,
        hallucination_penalty=hallucination_penalty,
        reasoning_consistency_score=0.0,
        compression_efficiency_score=0.0,
        constraint_adherence_score=0.0,
        schema_adherence_score=strict_schema_score,
        semantic_shadow_score=semantic_score,
        derived_metrics=details,
    )


def evaluate_fact_task_2(text: str, gt: dict[str, Any]) -> dict[str, Any]:
    pred, parse_error, parse_recovered = parse_json_with_recovery(text)
    if parse_error:
        return hard_failure_result(parse_error)

    if not isinstance(pred, dict):
        return hard_failure_result("schema_invalid")
    if "steps" not in pred or "final_answer" not in pred:
        return hard_failure_result("schema_invalid")
    if not isinstance(pred["steps"], list) or not isinstance(pred["final_answer"], dict):
        return hard_failure_result("schema_invalid")

    steps = pred["steps"]
    final_answer = pred["final_answer"]
    matched_claims = 0
    exact_support_matches = 0
    hallucination_flags: list[dict[str, Any]] = []

    for req in gt["required_atomic_claims"]:
        found = None
        for step in steps:
            if not isinstance(step, dict):
                continue
            claim = normalize(step.get("claim"))
            if any(normalize(x) == claim for x in req["accepted_claim_texts"]):
                found = step
                break
        if found:
            matched_claims += 1
            support = found.get("supported_by_fact_ids", [])
            if sorted(support) == sorted(req["supported_by_fact_ids"]):
                exact_support_matches += 1
            else:
                hallucination_flags.append({"type": "incorrect_support_mapping", "claim_key": req["claim_key"]})

    reasoning_coverage_score = 50.0 * matched_claims / len(gt["required_atomic_claims"])
    support_mapping_score = 20.0 * exact_support_matches / len(gt["required_atomic_claims"])

    answer_text = normalize(final_answer.get("answer"))
    final_answer_score = 0.0
    if ("same year" in answer_text or "both events occurred in 1917" in answer_text) and (
        "before the treaty" in answer_text or "before the treaty of versailles" in answer_text
    ):
        final_answer_score = 20.0

    contradictions = []
    if "before the russian revolution" in answer_text and "same year" in answer_text:
        contradictions.append({"type": "contradiction", "detail": "same_year_vs_before"})
    if "after the russian revolution" in answer_text and "same year" in answer_text:
        contradictions.append({"type": "contradiction", "detail": "same_year_vs_after"})

    reasoning_consistency_score = 10.0 if not contradictions else 0.0
    hallucination_penalty = -5.0 * len([flag for flag in hallucination_flags if flag["type"] == "incorrect_support_mapping"]) - 10.0 * len(contradictions)

    strict_schema_score = 90.0 if parse_recovered else 100.0
    base_semantic = reasoning_coverage_score + support_mapping_score + final_answer_score + reasoning_consistency_score
    final_score = clamp(0.9 * base_semantic + 0.1 * strict_schema_score + hallucination_penalty)

    return base_report(
        format_valid=True,
        usable_output=True,
        pipeline_usable=not parse_recovered,
        schema_coerced=parse_recovered,
        hard_failure=False,
        hard_failure_reason=None,
        confidence_classification=classify_confidence(final_score, hallucination_flags + contradictions),
        hallucination_flags=hallucination_flags + contradictions,
        score_percent=final_score,
        factual_accuracy_score=final_answer_score,
        hallucination_penalty=hallucination_penalty,
        reasoning_consistency_score=reasoning_consistency_score,
        compression_efficiency_score=0.0,
        constraint_adherence_score=0.0,
        schema_adherence_score=strict_schema_score,
        semantic_shadow_score=base_semantic,
        derived_metrics={
            "parse_recovered": parse_recovered,
            "matched_claims": matched_claims,
            "expected_claims": len(gt["required_atomic_claims"]),
            "exact_support_matches": exact_support_matches,
            "expected_support_matches": len(gt["required_atomic_claims"]),
            "final_answer_score": final_answer_score,
            "contradiction_count": len(contradictions),
        },
    )


def evaluate_fact_task_3(text: str, gt: dict[str, Any]) -> dict[str, Any]:
    pred, parse_error, parse_recovered = parse_json_with_recovery(text)
    if parse_error:
        return hard_failure_result(parse_error)

    if not isinstance(pred, dict) or "items" not in pred or not isinstance(pred["items"], list):
        return hard_failure_result("schema_invalid")

    gt_map = {item["id"]: item for item in gt["items"]}
    pred_map = {item.get("id"): item for item in pred["items"] if isinstance(item, dict)}

    score = 0.0
    hallucination_flags: list[dict[str, Any]] = []
    accepted_false_premise = False
    classification_mismatch_count = 0

    for sid, gt_item in gt_map.items():
        item = pred_map.get(sid)
        if item is None:
            continue

        cls = normalize(item.get("classification"))
        note = normalize(item.get("correction_or_note"))
        if cls == gt_item["classification"]:
            score += 10.0
        else:
            classification_mismatch_count += 1
            if gt_item["classification"] in ("false", "ambiguous") and cls == "true":
                accepted_false_premise = True
                hallucination_flags.append({"type": "accepted_false_premise", "id": sid})

        if any(normalize(pattern) in note for pattern in gt_item["accepted_note_patterns"]):
            score += 5.0
        elif note:
            hallucination_flags.append({"type": "weak_or_invented_note", "id": sid})

    premise_quality = 10.0 if not accepted_false_premise else 0.0
    hallucination_penalty = (
        -8.0 * len([flag for flag in hallucination_flags if flag["type"] == "accepted_false_premise"])
        -3.0 * len([flag for flag in hallucination_flags if flag["type"] == "weak_or_invented_note"])
    )

    strict_schema_score = 90.0 if parse_recovered else 100.0
    semantic_base = score + premise_quality
    final_score = clamp(0.9 * semantic_base + 0.1 * strict_schema_score + hallucination_penalty)

    usable_output = not accepted_false_premise

    return base_report(
        format_valid=True,
        usable_output=usable_output,
        pipeline_usable=not parse_recovered,
        schema_coerced=parse_recovered,
        hard_failure=False,
        hard_failure_reason=None,
        confidence_classification=classify_confidence(final_score, hallucination_flags),
        hallucination_flags=hallucination_flags,
        score_percent=final_score,
        factual_accuracy_score=semantic_base,
        hallucination_penalty=hallucination_penalty,
        reasoning_consistency_score=0.0,
        compression_efficiency_score=0.0,
        constraint_adherence_score=0.0,
        schema_adherence_score=strict_schema_score,
        semantic_shadow_score=semantic_base,
        derived_metrics={
            "parse_recovered": parse_recovered,
            "classification_mismatch_count": classification_mismatch_count,
            "accepted_false_premise": accepted_false_premise,
        },
    )


def evaluate_prose_task_1(text: str, gt: dict[str, Any]) -> dict[str, Any]:
    try:
        pred = try_json_loads(text)
    except Exception:
        return hard_failure_result("invalid_json")

    if not isinstance(pred, dict) or "summary" not in pred or "word_count" not in pred:
        return hard_failure_result("schema_invalid")

    summary = str(pred["summary"]).strip()
    actual_word_count = count_words(summary)
    declared_word_count = _coerce_int(pred.get("word_count"), 0)

    semantic_hits = 0
    for unit in gt["key_units"]:
        if semantic_unit_present(unit, summary):
            semantic_hits += 1

    semantic_retention_score = semantic_hits * 6.0
    if actual_word_count <= gt["max_words"]:
        compression_compliance = 20.0
    elif actual_word_count <= gt["max_words"] + 7:
        compression_compliance = 10.0
    else:
        compression_compliance = 0.0

    repeated_units = count_redundant_units(summary)
    redundancy_control = max(0.0, 20.0 - 5.0 * repeated_units)
    compression_efficiency_score = semantic_retention_score + compression_compliance + redundancy_control
    final_score = clamp(compression_efficiency_score)

    return base_report(
        format_valid=True,
        usable_output=actual_word_count <= gt["max_words"] + 7,
        pipeline_usable=True,
        schema_coerced=False,
        hard_failure=False,
        hard_failure_reason=None,
        confidence_classification=classify_confidence(final_score, []),
        hallucination_flags=[],
        score_percent=final_score,
        factual_accuracy_score=0.0,
        hallucination_penalty=0.0,
        reasoning_consistency_score=0.0,
        compression_efficiency_score=compression_efficiency_score,
        constraint_adherence_score=compression_compliance + redundancy_control,
        schema_adherence_score=100.0,
        semantic_shadow_score=final_score,
        derived_metrics={
            "actual_word_count": actual_word_count,
            "declared_word_count": declared_word_count,
            "compression_ratio": round(actual_word_count / gt["source_word_count"], 4),
            "retention_density": round(semantic_retention_score / max(1, actual_word_count), 4),
            "semantic_hit_count": semantic_hits,
            "semantic_unit_count": len(gt["key_units"]),
            "repeated_unit_count": repeated_units,
        },
    )


def evaluate_prose_task_2(text: str, gt: dict[str, Any]) -> dict[str, Any]:
    try:
        pred = try_json_loads(text)
    except Exception:
        return hard_failure_result("invalid_json")

    if not isinstance(pred, dict):
        return hard_failure_result("schema_invalid")

    exact_structure = list(pred.keys()) == gt["required_sections"]
    structure_score = 20.0 if exact_structure else 0.0

    inputs_list = _coerce_string_list(pred.get("Inputs"))
    steps_list = _coerce_string_list(pred.get("Steps"))

    if len(steps_list) >= gt["required_step_properties"]["min_steps"]:
        structure_score += 10.0

    flattened = " ".join(
        [
            _coerce_jsonish_text(pred.get("Goal", "")),
            " ".join(inputs_list),
            " ".join(steps_list),
            _coerce_jsonish_text(pred.get("Output", "")),
        ]
    ).strip()

    hits = 0
    for unit in gt["required_content_units"]:
        if semantic_unit_present(unit, flattened):
            hits += 1
    completeness_score = 50.0 * hits / len(gt["required_content_units"])

    ambiguity_count = count_ambiguity_patterns(flattened)
    ambiguity_penalties = 5.0 * ambiguity_count
    ambiguity_reduction_score = max(0.0, 20.0 - ambiguity_penalties)
    final_score = clamp(structure_score + completeness_score + ambiguity_reduction_score)

    return base_report(
        format_valid=True,
        usable_output=structure_score >= 20.0,
        pipeline_usable=True,
        schema_coerced=False,
        hard_failure=False,
        hard_failure_reason=None,
        confidence_classification=classify_confidence(final_score, []),
        hallucination_flags=[],
        score_percent=final_score,
        factual_accuracy_score=0.0,
        hallucination_penalty=0.0,
        reasoning_consistency_score=0.0,
        compression_efficiency_score=0.0,
        constraint_adherence_score=structure_score + ambiguity_reduction_score,
        schema_adherence_score=100.0 if exact_structure else 60.0,
        semantic_shadow_score=final_score,
        derived_metrics={
            "exact_structure": exact_structure,
            "step_count": len(steps_list),
            "min_steps_required": gt["required_step_properties"]["min_steps"],
            "content_hit_count": hits,
            "required_content_unit_count": len(gt["required_content_units"]),
            "ambiguity_pattern_count": ambiguity_count,
            "inputs_item_count": len(inputs_list),
            "steps_item_count": len(steps_list),
        },
    )


def evaluate_prose_task_3(text: str, gt: dict[str, Any]) -> dict[str, Any]:
    try:
        pred = try_json_loads(text)
    except Exception:
        return hard_failure_result("invalid_json")

    if not isinstance(pred, dict) or set(pred.keys()) != {"intro", "bullets", "word_count"}:
        return hard_failure_result("schema_invalid")

    intro = _coerce_jsonish_text(pred.get("intro")).strip()
    bullets_raw = pred.get("bullets")
    if not isinstance(bullets_raw, list):
        return hard_failure_result("schema_invalid")

    bullets = _coerce_string_list(bullets_raw)
    declared_word_count = _coerce_int(pred.get("word_count"), 0)

    full_text = (intro + " " + " ".join(bullets)).strip()
    actual_word_count = count_words(full_text)

    constraint_score = 0.0
    penalties = 0.0
    banned_hits = 0

    if actual_word_count <= gt["max_words"]:
        constraint_score += 15.0
    elif actual_word_count <= gt["max_words"] + 15:
        penalties -= 5.0
    else:
        penalties -= 15.0

    if len(bullets) == 3:
        constraint_score += 20.0
    else:
        penalties -= 10.0 * abs(len(bullets) - 3)

    for term in gt["banned_terms"]:
        banned_hits += len(re.findall(re.escape(normalize(term)), normalize(full_text)))
    if banned_hits == 0:
        constraint_score += 20.0
    else:
        penalties -= 5.0 * banned_hits

    analogy_present = any(normalize(pattern) in normalize(full_text) for pattern in gt["analogy_patterns"])
    if analogy_present:
        constraint_score += 15.0
    else:
        penalties -= 10.0

    coherence_score = 0.0
    if intro:
        coherence_score += 5.0
    if len(set(normalize(str(x)) for x in bullets)) == len(bullets):
        coherence_score += 10.0
    if bullets and all(database_index_relevant(str(x)) for x in bullets):
        coherence_score += 5.0

    final_score = clamp(constraint_score + coherence_score + penalties)

    return base_report(
        format_valid=True,
        usable_output=actual_word_count <= gt["max_words"] + 15 and len(bullets) >= 1,
        pipeline_usable=True,
        schema_coerced=False,
        hard_failure=False,
        hard_failure_reason=None,
        confidence_classification=classify_confidence(final_score, []),
        hallucination_flags=[],
        score_percent=final_score,
        factual_accuracy_score=0.0,
        hallucination_penalty=penalties,
        reasoning_consistency_score=0.0,
        compression_efficiency_score=0.0,
        constraint_adherence_score=constraint_score,
        schema_adherence_score=100.0,
        semantic_shadow_score=final_score,
        derived_metrics={
            "actual_word_count": actual_word_count,
            "declared_word_count": declared_word_count,
            "bullet_count": len(bullets),
            "banned_term_hits": banned_hits,
            "analogy_present": analogy_present,
        },
    )


EVALUATORS = {
    "fact_task_1": evaluate_fact_task_1,
    "fact_task_2": evaluate_fact_task_2,
    "fact_task_3": evaluate_fact_task_3,
    "prose_task_1": evaluate_prose_task_1,
    "prose_task_2": evaluate_prose_task_2,
    "prose_task_3": evaluate_prose_task_3,
}


def derive_fact_prose_success(report: dict[str, Any]) -> bool:
    score_percent = float(report.get("score", {}).get("score_percent", 0.0) or 0.0)
    return (
        bool(report.get("format_valid", False))
        and not bool(report.get("hard_failure", False))
        and bool(report.get("pipeline_usable", False))
        and score_percent == 100.0
    )


def derive_fact_prose_failure_stage(report: dict[str, Any], task_id: str) -> str | None:
    if bool(report.get("hard_failure", False)) or not bool(report.get("format_valid", False)):
        return "format"

    score_percent = float(report.get("score", {}).get("score_percent", 0.0) or 0.0)
    if score_percent == 100.0 and bool(report.get("pipeline_usable", False)):
        return None

    if task_id.startswith("prose_"):
        constraint_score = float(report.get("score", {}).get("constraint_adherence_score", 0.0) or 0.0)
        compression_score = float(report.get("score", {}).get("compression_efficiency_score", 0.0) or 0.0)
        if constraint_score > 0.0 or compression_score > 0.0:
            return "constraint"

    return "semantic"


def derive_fact_prose_failure_type(report: dict[str, Any], task_id: str) -> str | None:
    if bool(report.get("hard_failure", False)) or not bool(report.get("format_valid", False)):
        return "format_violation"

    score_percent = float(report.get("score", {}).get("score_percent", 0.0) or 0.0)
    if score_percent == 100.0 and bool(report.get("pipeline_usable", False)):
        return None

    hallucination_flags = report.get("hallucination_flags", [])
    if hallucination_flags:
        return "semantic_error"

    if task_id.startswith("prose_"):
        return "constraint_violation"

    return "semantic_error"


def derive_fact_prose_failure_subtype(report: dict[str, Any], task_id: str) -> list[str]:
    subtypes: list[str] = []

    hard_failure_reason = report.get("hard_failure_reason")
    if hard_failure_reason:
        subtypes.append(str(hard_failure_reason))
        subtypes.append("hard_failure_result")

    if bool(report.get("schema_coerced", False)):
        subtypes.append("schema_coerced")

    derived = report.get("derived_metrics", {}) or {}
    hallucination_flags = report.get("hallucination_flags", []) or []

    if derived.get("parse_recovered"):
        subtypes.append("parse_recovered")
    if derived.get("multi_block_merged"):
        subtypes.append("multi_block_merged")

    for flag in hallucination_flags:
        flag_type = flag.get("type")
        if flag_type:
            subtypes.append(str(flag_type))

    if task_id == "fact_task_1":
        if _coerce_int(derived.get("matched_entities"), 0) < _coerce_int(derived.get("expected_entities"), 0):
            subtypes.append("low_entity_coverage")
        if _coerce_int(derived.get("field_mismatch_count"), 0) > 0:
            subtypes.append("field_value_mismatch")
        if _coerce_int(derived.get("category_mismatch_count"), 0) > 0:
            subtypes.append("category_mismatch")

    elif task_id == "fact_task_2":
        if _coerce_int(derived.get("matched_claims"), 0) < _coerce_int(derived.get("expected_claims"), 0):
            subtypes.append("incomplete_reasoning_chain")
        if float(derived.get("final_answer_score", 0.0) or 0.0) <= 0.0:
            subtypes.append("final_answer_mismatch")
        if _coerce_int(derived.get("contradiction_count"), 0) > 0:
            subtypes.append("contradiction_detected")

    elif task_id == "fact_task_3":
        if _coerce_int(derived.get("classification_mismatch_count"), 0) > 0:
            subtypes.append("classification_mismatch")

    elif task_id == "prose_task_1":
        actual = _coerce_int(derived.get("actual_word_count"), 0)
        declared = _coerce_int(derived.get("declared_word_count"), 0)
        if actual != declared:
            subtypes.append("declared_word_count_mismatch")
        if actual > 120:
            subtypes.append("word_count_violation")
        if _coerce_int(derived.get("semantic_hit_count"), 0) < _coerce_int(derived.get("semantic_unit_count"), 0):
            subtypes.append("low_semantic_retention")
        if _coerce_int(derived.get("repeated_unit_count"), 0) > 0:
            subtypes.append("redundancy_detected")

    elif task_id == "prose_task_2":
        if not bool(derived.get("exact_structure", False)):
            subtypes.append("structure_invalid")
        if _coerce_int(derived.get("step_count"), 0) < _coerce_int(derived.get("min_steps_required"), 0):
            subtypes.append("insufficient_steps")
        if _coerce_int(derived.get("content_hit_count"), 0) < _coerce_int(derived.get("required_content_unit_count"), 0):
            subtypes.append("missing_required_content_unit")
        if _coerce_int(derived.get("ambiguity_pattern_count"), 0) > 0:
            subtypes.append("ambiguity_detected")

    elif task_id == "prose_task_3":
        actual = _coerce_int(derived.get("actual_word_count"), 0)
        declared = _coerce_int(derived.get("declared_word_count"), 0)
        if actual != declared:
            subtypes.append("declared_word_count_mismatch")
        if actual > 120:
            subtypes.append("word_count_violation")
        if _coerce_int(derived.get("bullet_count"), 0) != 3:
            subtypes.append("bullet_count_mismatch")
        if _coerce_int(derived.get("banned_term_hits"), 0) > 0:
            subtypes.append("banned_term_present")
        if not bool(derived.get("analogy_present", False)):
            subtypes.append("missing_required_analogy")

    return sorted(set(subtypes))


def append_normalized_failure_schema(report: dict[str, Any], task_id: str) -> dict[str, Any]:
    report["success"] = derive_fact_prose_success(report)
    report["failure_stage"] = derive_fact_prose_failure_stage(report, task_id)
    report["failure_type"] = derive_fact_prose_failure_type(report, task_id)
    report["failure_subtype"] = derive_fact_prose_failure_subtype(report, task_id)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one factual/prose benchmark answer deterministically.")
    parser.add_argument("answer_file", help="Path to model output text file")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--save-report", required=True)
    args = parser.parse_args()

    answer_path = Path(args.answer_file)
    gt_path = Path(args.ground_truth)
    report_path = Path(args.save_report)

    if args.task_id not in EVALUATORS:
        raise SystemExit(f"Unsupported task-id: {args.task_id}")

    answer_text = answer_path.read_text(encoding="utf-8", errors="replace")
    gt = json.loads(gt_path.read_text(encoding="utf-8"))

    report = EVALUATORS[args.task_id](answer_text, gt)
    report["task_id"] = args.task_id
    report["answer_file"] = str(answer_path)
    report["ground_truth_file"] = str(gt_path)
    report = append_normalized_failure_schema(report, args.task_id)

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
