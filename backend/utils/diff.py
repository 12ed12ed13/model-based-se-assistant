"""Diff utilities for comparing model versions and analysis reports."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_REL_TYPE = "association"


def build_version_diff(
    previous_report: Optional[Dict[str, Any]],
    current_report: Dict[str, Any],
    previous_ir: Optional[Dict[str, Any]],
    current_ir: Dict[str, Any],
) -> Dict[str, Any]:
    """Produce a structured diff summary between two analyses/models."""

    prev_metrics = (previous_report or {}).get("quality_metrics", {})
    curr_metrics = (current_report or {}).get("quality_metrics", {})

    structure_diff = diff_model_ir(previous_ir or {}, current_ir or {})
    relationship_diff = diff_relationships(previous_ir or {}, current_ir or {})
    metrics_diff = diff_metrics(prev_metrics, curr_metrics)
    findings_diff = diff_findings(previous_report or {}, current_report or {})

    summary_bits = []
    if structure_diff["classes_added"]:
        summary_bits.append(f"{len(structure_diff['classes_added'])} classes added")
    if structure_diff["classes_removed"]:
        summary_bits.append(f"{len(structure_diff['classes_removed'])} classes removed")
    if findings_diff["resolved_findings"]:
        summary_bits.append(f"{len(findings_diff['resolved_findings'])} issues resolved")
    if findings_diff["new_findings"]:
        summary_bits.append(f"{len(findings_diff['new_findings'])} new issues detected")
    if not summary_bits:
        summary_bits.append("No major structural changes detected")

    return {
        "structure": structure_diff,
        "relationships": relationship_diff,
        "metrics": metrics_diff,
        "findings": findings_diff,
        "summary": ", ".join(summary_bits),
    }


def diff_model_ir(previous: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    prev_classes = _index_by_name(previous.get("classes", []))
    curr_classes = _index_by_name(current.get("classes", []))

    added = sorted(name for name in curr_classes.keys() - prev_classes.keys())
    removed = sorted(name for name in prev_classes.keys() - curr_classes.keys())

    modified = []
    for name in sorted(prev_classes.keys() & curr_classes.keys()):
        prev_cls = prev_classes[name]
        curr_cls = curr_classes[name]
        attr_diff = _diff_named_items(prev_cls.get("attributes", []), curr_cls.get("attributes", []))
        method_diff = _diff_named_items(prev_cls.get("methods", []), curr_cls.get("methods", []), value_keys=["params", "returns"])

        if attr_diff["added"] or attr_diff["removed"] or attr_diff["changed"] or method_diff["added"] or method_diff["removed"] or method_diff["changed"]:
            modified.append(
                {
                    "name": name,
                    "attributes": attr_diff,
                    "methods": method_diff,
                }
            )

    return {
        "classes_added": added,
        "classes_removed": removed,
        "classes_modified": modified,
    }


def diff_relationships(previous: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    prev_rels = _index_relationships(previous.get("relationships", []))
    curr_rels = _index_relationships(current.get("relationships", []))

    added = [curr_rels[key] for key in curr_rels.keys() - prev_rels.keys()]
    removed = [prev_rels[key] for key in prev_rels.keys() - curr_rels.keys()]

    changed = []
    for key in prev_rels.keys() & curr_rels.keys():
        prev = prev_rels[key]
        curr = curr_rels[key]
        if prev.get("multiplicity") != curr.get("multiplicity") or prev.get("type") != curr.get("type"):
            changed.append({
                "from": key[0],
                "to": key[1],
                "previous": prev,
                "current": curr,
            })

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def diff_metrics(previous: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Dict[str, Optional[float]]]:
    keys = set(previous.keys()) | set(current.keys())
    result: Dict[str, Dict[str, Optional[float]]] = {}
    for key in sorted(keys):
        prev_val = previous.get(key)
        curr_val = current.get(key)
        delta = None
        if isinstance(prev_val, (int, float)) and isinstance(curr_val, (int, float)):
            delta = curr_val - prev_val
        result[key] = {
            "previous": prev_val,
            "current": curr_val,
            "delta": delta,
        }
    return result


def diff_findings(previous: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    prev_findings = previous.get("findings", []) or []
    curr_findings = current.get("findings", []) or []

    prev_index = {_finding_signature(f): f for f in prev_findings}
    curr_index = {_finding_signature(f): f for f in curr_findings}

    resolved = [prev_index[key] for key in prev_index.keys() - curr_index.keys()]
    new = [curr_index[key] for key in curr_index.keys() - prev_index.keys()]
    persistent = []
    for key in prev_index.keys() & curr_index.keys():
        prev = prev_index[key]
        curr = curr_index[key]
        if prev.get("severity") != curr.get("severity"):
            curr = {**curr, "severity_change": f"{prev.get('severity')} -> {curr.get('severity')}"}
        persistent.append(curr)

    return {
        "resolved_findings": resolved,
        "new_findings": new,
        "persistent_findings": persistent,
    }


# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------

def _index_by_name(items: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {item.get("name"): item for item in items if item.get("name")}


def _diff_named_items(
    previous: Sequence[Dict[str, Any]],
    current: Sequence[Dict[str, Any]],
    value_keys: Optional[List[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    prev_index = _index_by_name(previous)
    curr_index = _index_by_name(current)

    added = [curr_index[name] for name in curr_index.keys() - prev_index.keys()]
    removed = [prev_index[name] for name in prev_index.keys() - curr_index.keys()]

    changed = []
    for name in prev_index.keys() & curr_index.keys():
        prev_item = prev_index[name]
        curr_item = curr_index[name]
        keys_to_compare = value_keys or [key for key in curr_item.keys() if key != "name"]
        if any(prev_item.get(k) != curr_item.get(k) for k in keys_to_compare):
            changed.append({
                "name": name,
                "previous": {k: prev_item.get(k) for k in keys_to_compare},
                "current": {k: curr_item.get(k) for k in keys_to_compare},
            })

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def _index_relationships(relationships: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
    indexed = {}
    for rel in relationships:
        from_cls = rel.get("from")
        to_cls = rel.get("to")
        rel_type = rel.get("type", DEFAULT_REL_TYPE)
        if not from_cls or not to_cls:
            continue
        key = (from_cls, to_cls, rel_type)
        indexed[key] = rel
    return indexed


def _finding_signature(finding: Dict[str, Any]) -> Tuple[str, Tuple[str, ...], str]:
    principle = finding.get("violated_principle") or finding.get("category") or ""
    entities = tuple(sorted(finding.get("affected_entities", [])))
    issue = (finding.get("issue", "") or finding.get("title", ""))[:120]
    return (principle, entities, issue)
