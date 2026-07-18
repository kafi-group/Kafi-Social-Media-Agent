"""
Rival insights (Rival Review).

Compares Kafi Commodities' own LinkedIn performance (static snapshot used by the
Analytics page) against the latest rival snapshots and asks Gemini to produce
concrete, prioritized suggestions. Output is parsed into structured suggestion
cards for the UI.

NOTE: We intentionally do NOT call SocialAnalyticsService here. That path hits
Facebook/Instagram/YouTube/TikTok live APIs and was causing Get AI Suggestions
to hang / time out before Gemini ever ran (e.g. expired YouTube OAuth tokens).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.llm.ollama_client import LLMClient
from app.services.rival_service import RivalService
from app.utils.exceptions import LLMConnectionError
from app.utils.logger import logger

# Same LinkedIn-only snapshot shown on /dashboard/analytics (static).
_OUR_LINKEDIN_ANALYTICS = {
    "totals": {
        "impressions": 1516,
        "engagements": 34,
        "followers": 4794,
        "members_reached": 664,
        "profile_viewers": 207,
        "search_appearances": 4,
    },
    "platforms": {
        "linkedin": {
            "status": "ok",
            "followers": 4794,
            "views": 1516,
            "impressions": 1516,
            "engagements": 34,
            "likes": 30,
            "comments": 2,
            "reposts": 0,
            "saves": 1,
            "sends": 1,
            "in_network_pct": 57,
            "out_of_network_pct": 43,
            "members_reached": 664,
            "note": "Configured LinkedIn analytics.",
        }
    },
}


def _compact_metrics(metrics: dict) -> dict:
    """Keep only high-signal rival metrics to avoid blowing the token budget."""
    if not metrics:
        return {}
    keys = (
        "followers",
        "subscribers",
        "views",
        "total_views",
        "engagements",
        "recent_avg_engagement",
        "recent_avg_views",
        "media_count",
        "video_count",
        "likes",
        "comments",
        "posts",
        "videos",
    )
    compact = {key: metrics[key] for key in keys if metrics.get(key) is not None}
    return compact or metrics


def _rivals_payload(service: RivalService, rivals) -> list[dict]:
    payload = []
    for rival in rivals:
        latest = service.latest_snapshots(rival.id)
        platforms = {}
        for platform, snap in latest.items():
            platforms[platform] = {
                "status": snap.status,
                "metrics": _compact_metrics(snap.metrics or {}),
                "recent_items": (snap.recent_items or [])[:2],
            }
        payload.append({
            "name": rival.name,
            "category": rival.category,
            "platforms": platforms,
        })
    return payload


def _build_prompt(our_summary: dict, rivals_payload: list[dict]) -> str:
    return f"""You are a social media strategy analyst for Kafi Commodities, a Pakistani
spice, rice and chutney exporter that sells internationally. Compare OUR LinkedIn
performance against our RIVALS' latest public analytics, and identify what
rivals are doing better than us and what we should do about it.

OUR ANALYTICS (LinkedIn account snapshot):
{json.dumps(our_summary, indent=2, default=str)}

RIVAL ANALYTICS (public competitor data):
{json.dumps(rivals_payload, indent=2, default=str)}

Return ONLY a JSON array of exactly 5 suggestion objects (no prose, no markdown).
Keep every string field under 140 characters.
Each object MUST have exactly these keys:
- "rival": the rival name the insight is based on (or "Overall" if it spans several)
- "platform": one of "youtube", "instagram", "website", "linkedin", or "general"
- "observation": what the rival is doing / what the data shows (1 short sentence)
- "why_better": why this gives them an edge over us (1 short sentence)
- "recommendation": a concrete action Kafi Commodities should take (1 short sentence)
- "priority": one of "high", "medium", "low"

Base every insight on the numbers provided. If rival platform data is missing,
still give practical, category-relevant recommendations for LinkedIn and social.
Output the JSON array and nothing else."""


def _normalize_suggestion(item: dict) -> dict:
    return {
        "rival": item.get("rival", "Overall"),
        "platform": (item.get("platform") or "general").lower(),
        "observation": item.get("observation", ""),
        "why_better": item.get("why_better", ""),
        "recommendation": item.get("recommendation", ""),
        "priority": (item.get("priority") or "medium").lower(),
    }


def _extract_json_array_text(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    match = re.search(r"\[.*", text, re.DOTALL)
    return match.group(0) if match else text


def _repair_truncated_json_array(text: str) -> str:
    """Close a JSON array that was cut off mid-object (common when tokens run out)."""
    trimmed = text.strip()
    if not trimmed.startswith("["):
        return trimmed

    # Prefer fully closed objects; drop any trailing partial object.
    last_object_end = trimmed.rfind("}")
    if last_object_end != -1:
        repaired = trimmed[: last_object_end + 1].rstrip().rstrip(",")
        if not repaired.endswith("]"):
            repaired += "]"
        return repaired

    # Truncated inside the first object (no closing brace yet).
    if trimmed.count("{") > trimmed.count("}"):
        repaired = trimmed.rstrip().rstrip(",")
        if repaired.count('"') % 2 == 1:
            repaired += '"'
        repaired += "}"
        if not repaired.endswith("]"):
            repaired += "]"
        return repaired

    return "[]"


def _parse_suggestions_loose(text: str) -> list[dict]:
    """Best-effort parse of complete suggestion objects from partial JSON."""
    suggestions: list[dict] = []
    for match in re.finditer(
        r"\{[^{}]*?\"rival\"\s*:\s*\"[^\"]+\"[^{}]*?\}",
        text,
        re.DOTALL,
    ):
        try:
            item = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("observation"):
            suggestions.append(_normalize_suggestion(item))
    return suggestions


def _parse_suggestions(raw: str) -> list[dict]:
    """Extract a JSON array of suggestions from the LLM response, tolerantly."""
    if not raw:
        return []

    text = _extract_json_array_text(raw)
    candidates = [text, _repair_truncated_json_array(text)]

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            cleaned = [
                _normalize_suggestion(item)
                for item in data
                if isinstance(item, dict) and item.get("observation")
            ]
            if cleaned:
                return cleaned

    loose = _parse_suggestions_loose(text)
    if loose:
        logger.warning(
            "Parsed rival insights using fallback object extraction (%d items)",
            len(loose),
        )
        return loose

    logger.warning("Failed to parse rival insights JSON from LLM response")
    return []


def generate_insights(
    db: Session, rival_id: Optional[int] = None, days: int = 30
) -> dict:
    """Generate rival-vs-us suggestions. Scope to one rival via rival_id."""
    del days  # kept for API compatibility; our side uses static LinkedIn data
    service = RivalService(db)

    if rival_id is not None:
        rival = service.get_rival(rival_id)
        rivals = [rival] if rival else []
    else:
        rivals = service.list_rivals(active_only=True)

    if not rivals:
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "rival_count": 0,
            "suggestions": [],
            "message": "No rivals to analyze yet. Add a rival first.",
        }

    our_summary = _OUR_LINKEDIN_ANALYTICS
    rivals_payload = _rivals_payload(service, rivals)
    prompt = _build_prompt(our_summary, rivals_payload)

    logger.info(
        "Generating rival insights via Gemini (rivals=%d, no live analytics fetch)",
        len(rivals),
    )

    try:
        raw = LLMClient().generate(
            prompt,
            temperature=0.4,
            max_output_tokens=2048,
            response_mime_type="application/json",
        )
    except LLMConnectionError as exc:
        logger.error(f"Rival insights LLM call failed: {exc}")
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "rival_count": len(rivals),
            "suggestions": [],
            "message": f"AI suggestions unavailable: {exc}",
        }

    suggestions = _parse_suggestions(raw)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "rival_count": len(rivals),
        "our_summary": our_summary,
        "suggestions": suggestions,
        # Surface raw text only when structured parsing failed, for debugging.
        "raw": None if suggestions else raw,
        "message": None if suggestions else "Could not parse structured suggestions; showing raw output.",
    }
