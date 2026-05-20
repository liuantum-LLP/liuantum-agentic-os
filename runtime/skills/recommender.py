"""Local recommendation engine for Liuant Agentic OS v2.5.0.

Recommends packs, skills, and workflows based on:
- Installed skills (complementary packs)
- Workflow templates (missing skills for workflows)
- Local catalog (similar packs)
- Permission profile (low-risk alternatives)
- Query keyword matching
- Trust state
- Lint score
- Compatibility with installed packs
- Local usage analytics
- Starter pack priority

No network calls or telemetry.

v2.5.0 additions: factor breakdown, explain mode, improved ranking.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.skills.packs import (
    _load_catalog,
    _load_pack_registry,
    list_imported_packs,
)
from runtime.skills.registry import list_installed_skills
from runtime.skills.workflows import list_workflows


def _get_installed_skill_ids() -> set[str]:
    """Get set of installed skill IDs."""
    return {s["id"] for s in list_installed_skills()}


def _get_installed_pack_ids() -> set[str]:
    """Get set of imported pack IDs."""
    return {p["pack_id"] for p in list_imported_packs()}


def _get_catalog_packs() -> list[dict[str, Any]]:
    """Get all catalog packs."""
    return _load_catalog().get("packs", [])


def _score_pack_for_query(pack: dict[str, Any], query: str, installed_skills: set[str], installed_packs: set[str], workflows: list[dict[str, Any]]) -> dict[str, Any]:
    """Score a pack for a query with factor breakdown."""
    pack_id = pack.get("pack_id", "")
    if pack_id in installed_packs:
        return None

    factors = {}
    total_score = 0

    # Query keyword match (0-30)
    query_lower = query.lower()
    searchable = " ".join([
        pack.get("pack_id", ""),
        pack.get("name", ""),
        pack.get("description", ""),
        " ".join(pack.get("skills", [])),
        " ".join(pack.get("tags", [])),
    ]).lower()

    query_match = 0
    query_terms = query_lower.split()
    for term in query_terms:
        if term in searchable:
            query_match += 10
    query_match = min(query_match, 30)
    if query_match > 0:
        factors["query_match"] = query_match
        total_score += query_match

    # Installed skill gaps (0-20)
    pack_skills = set(pack.get("skills", []))
    gap_skills = pack_skills - installed_skills
    if gap_skills:
        gap_score = min(len(gap_skills) * 5, 20)
        factors["skill_gap_fill"] = gap_score
        total_score += gap_score

    # Workflow match (0-20)
    workflow_match = 0
    for wf in workflows:
        wf_skills = set()
        for step in wf.get("steps", []):
            wf_skills.add(step.get("skill_id", ""))
        overlap = pack_skills & wf_skills
        if overlap:
            workflow_match += min(len(overlap) * 5, 10)
    workflow_match = min(workflow_match, 20)
    if workflow_match > 0:
        factors["workflow_match"] = workflow_match
        total_score += workflow_match

    # Trust bonus (0-10)
    risk_summary = pack.get("risk_summary", {})
    if risk_summary.get("critical", 0) == 0 and risk_summary.get("high", 0) == 0:
        factors["low_risk_bonus"] = 10
        total_score += 10

    # Starter pack priority (0-10)
    tags = pack.get("tags", [])
    if "starter" in [t.lower() for t in tags]:
        factors["starter_priority"] = 10
        total_score += 10

    # Catalog verification bonus (0-10)
    if pack.get("verified", False):
        factors["verified_bonus"] = 10
        total_score += 10

    if total_score == 0 and not query:
        total_score = 50
        factors["default_score"] = 50

    reason_parts = []
    if "query_match" in factors:
        reason_parts.append(f"Matches query ({factors['query_match']}pts)")
    if "skill_gap_fill" in factors:
        reason_parts.append(f"Fills {len(gap_skills)} skill gap(s)")
    if "workflow_match" in factors:
        reason_parts.append(f"Supports workflow(s)")
    if "low_risk_bonus" in factors:
        reason_parts.append("Low risk")
    if "starter_priority" in factors:
        reason_parts.append("Starter pack")
    if "verified_bonus" in factors:
        reason_parts.append("Verified in catalog")

    reason = "; ".join(reason_parts) if reason_parts else "Available in catalog"

    return {
        "pack_id": pack_id,
        "name": pack.get("name", ""),
        "description": pack.get("description", ""),
        "version": pack.get("version", ""),
        "skills": pack.get("skills", []),
        "risk_summary": risk_summary,
        "score": total_score,
        "reason": reason,
        "factors": factors,
    }


def recommend_packs(query: str = "", limit: int = 5, explain: bool = False) -> list[dict[str, Any]]:
    """Recommend packs from catalog not yet imported.

    Args:
        query: Optional search query for keyword matching.
        limit: Maximum number of recommendations.
        explain: If True, include factor breakdown.

    Returns:
        List of recommended packs with score and reason.
    """
    installed_packs = _get_installed_pack_ids()
    installed_skills = _get_installed_skill_ids()
    catalog = _get_catalog_packs()
    from runtime.skills.workflows import _get_workflow_by_id
    workflows = []
    for wf in list_workflows():
        full_wf = _get_workflow_by_id(wf["workflow_id"])
        if full_wf:
            workflows.append(full_wf)

    recommendations = []
    for pack in catalog:
        result = _score_pack_for_query(pack, query, installed_skills, installed_packs, workflows)
        if result:
            if not explain:
                result.pop("factors", None)
            recommendations.append(result)

    recommendations.sort(key=lambda x: x["score"], reverse=True)
    return recommendations[:limit]


def recommend_skills_for_workflow(workflow_id: str) -> dict[str, Any]:
    """Recommend missing skills for a workflow.

    Args:
        workflow_id: Workflow ID to check.

    Returns:
        Recommendation with missing skills and install suggestions.
    """
    from runtime.skills.workflows import _get_workflow_by_id
    workflow = _get_workflow_by_id(workflow_id)

    if not workflow:
        return {"status": "error", "message": f"Workflow '{workflow_id}' not found"}

    installed_skills = _get_installed_skill_ids()
    steps = workflow.get("steps", [])

    missing_skills = []
    for step in steps:
        skill_id = step.get("skill_id", "")
        if skill_id and skill_id not in installed_skills:
            missing_skills.append(skill_id)

    if not missing_skills:
        return {
            "status": "ok",
            "workflow_id": workflow_id,
            "message": "All required skills are installed",
        }

    catalog = _get_catalog_packs()
    pack_suggestions = []
    for pack in catalog:
        pack_skills = set(pack.get("skills", []))
        missing_in_pack = pack_skills & set(missing_skills)
        if missing_in_pack:
            pack_suggestions.append({
                "pack_id": pack.get("pack_id", ""),
                "name": pack.get("name", ""),
                "provides_skills": list(missing_in_pack),
            })

    return {
        "status": "missing_skills",
        "workflow_id": workflow_id,
        "missing_skills": missing_skills,
        "pack_suggestions": pack_suggestions,
    }


def recommend_by_category(category: str, limit: int = 5) -> list[dict[str, Any]]:
    """Recommend packs by category/tag.

    Args:
        category: Category or tag to filter by.
        limit: Maximum number of recommendations.

    Returns:
        List of recommended packs.
    """
    return recommend_packs(query=category, limit=limit)


def recommend_low_risk_alternatives(pack_id: str) -> list[dict[str, Any]]:
    """Recommend lower-risk alternatives to a pack.

    Args:
        pack_id: Pack ID to find alternatives for.

    Returns:
        List of lower-risk packs with similar skills.
    """
    catalog = _get_catalog_packs()
    target_pack = None
    for pack in catalog:
        if pack.get("pack_id") == pack_id:
            target_pack = pack
            break

    if not target_pack:
        return []

    target_skills = set(target_pack.get("skills", []))
    target_risk = target_pack.get("risk_summary", {})
    target_high_risk = target_risk.get("high", 0) + target_risk.get("critical", 0)

    alternatives = []
    for pack in catalog:
        if pack.get("pack_id") == pack_id:
            continue

        pack_skills = set(pack.get("skills", []))
        overlap = pack_skills & target_skills
        if not overlap:
            continue

        pack_risk = pack.get("risk_summary", {})
        pack_high_risk = pack_risk.get("high", 0) + pack_risk.get("critical", 0)

        if pack_high_risk < target_high_risk:
            alternatives.append({
                "pack_id": pack.get("pack_id", ""),
                "name": pack.get("name", ""),
                "shared_skills": list(overlap),
                "risk_summary": pack_risk,
                "reason": "Lower risk alternative",
            })

    return alternatives


def get_recommendations(query: str = "", limit: int = 5, explain: bool = False, for_workflow: str = "") -> dict[str, Any]:
    """Get general recommendations based on query.

    Args:
        query: Optional search query.
        limit: Maximum number of recommendations.
        explain: If True, include factor breakdown.
        for_workflow: Optional workflow ID to match against.

    Returns:
        Combined recommendations.
    """
    results = {
        "packs": [],
        "workflows": [],
        "skills_needed": [],
    }

    if for_workflow:
        wf_rec = recommend_skills_for_workflow(for_workflow)
        if wf_rec.get("status") == "missing_skills":
            results["skills_needed"] = wf_rec.get("missing_skills", [])
            results["packs"] = recommend_packs(query=" ".join(results["skills_needed"]), limit=limit, explain=explain)
    elif query:
        results["packs"] = recommend_packs(query=query, limit=limit, explain=explain)
    else:
        results["packs"] = recommend_packs(limit=limit, explain=explain)

    workflows = list_workflows()
    for wf in workflows[:limit]:
        wf_id = wf.get("workflow_id", "")
        skill_rec = recommend_skills_for_workflow(wf_id)
        if skill_rec.get("status") == "missing_skills":
            results["workflows"].append({
                "workflow_id": wf_id,
                "name": wf.get("name", ""),
                "missing_skills": skill_rec.get("missing_skills", []),
            })

    return results
