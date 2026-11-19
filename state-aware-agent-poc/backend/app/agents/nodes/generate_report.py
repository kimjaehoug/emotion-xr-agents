"""Gap / Trend / Classify / Report / Save 노드."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.agents.state import AgentState
from app.core.config import get_settings
from app.policies.state_policy import StatePolicy, suggest_contributing_factors
from app.services.gap_service import compute_cognitive_gaps
from app.services.llm_service import OllamaLLMService
from app.services.trend_service import analyze_trends


def compute_cognitive_gap(state: AgentState) -> Dict[str, Any]:
    validated = state.get("validated_input") or {}
    metrics = validated.get("cognitive_metrics") or {}
    baseline = state.get("baseline")
    gaps = compute_cognitive_gaps(metrics, baseline)
    return {"cognitive_gaps": gaps}


def analyze_trend(state: AgentState) -> Dict[str, Any]:
    settings = get_settings()
    gaps = dict(state.get("cognitive_gaps") or {})
    episodes = state.get("recent_episodes") or []
    result = analyze_trends(
        gaps,
        episodes,
        window=settings.recent_episode_window,
        persistence_threshold=settings.persistence_threshold,
    )
    return {
        "cognitive_gaps": result["gaps"],
        "trend_analysis": {
            "multi_metric_shift": result["multi_metric_shift"],
            "out_of_range_metrics": result["out_of_range_metrics"],
            "recent_window_size": result["recent_window_size"],
        },
    }


def classify_state(state: AgentState) -> Dict[str, Any]:
    settings = get_settings()
    policy = StatePolicy(settings)
    validated = state.get("validated_input") or {}
    dq = validated.get("data_quality") or {}
    trend = state.get("trend_analysis") or {}
    route = state.get("route") or "complete_report"

    # 강제 경로
    if route == "error_response":
        classification = policy.classify(
            gaps={},
            baseline_source="none",
            confidence=0.0,
            completeness=0.0,
            multi_metric_shift=False,
            has_input_error=True,
        )
    elif route == "unknown_report":
        classification = policy.classify(
            gaps=state.get("cognitive_gaps") or {},
            baseline_source="none",
            confidence=float(dq.get("cognitive_confidence", 0)),
            completeness=float(dq.get("completeness", 0)),
            multi_metric_shift=False,
        )
    elif route == "low_confidence_report":
        classification = policy.classify(
            gaps=state.get("cognitive_gaps") or {},
            baseline_source=state.get("baseline_source") or "none",
            confidence=float(dq.get("cognitive_confidence", 0)),
            completeness=float(dq.get("completeness", 0)),
            multi_metric_shift=bool(trend.get("multi_metric_shift")),
        )
    else:
        classification = policy.classify(
            gaps=state.get("cognitive_gaps") or {},
            baseline_source=state.get("baseline_source") or "none",
            confidence=float(dq.get("cognitive_confidence", 0)),
            completeness=float(dq.get("completeness", 0)),
            multi_metric_shift=bool(trend.get("multi_metric_shift")),
        )

    warnings = list(state.get("warnings") or [])
    warnings.extend(classification.warnings)

    return {
        "classification": {
            "state_level": classification.state_level,
            "requires_response": classification.requires_response,
            "additional_observation_required": classification.additional_observation_required,
            "analysis_confidence": classification.analysis_confidence,
            "reasons": classification.reasons,
        },
        "warnings": list(dict.fromkeys(warnings)),
    }


def _gap_for_report(gaps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, g in gaps.items():
        out[name] = {
            "current": g.get("current_value"),
            "baseline": g.get("baseline_center"),
            "deviation": g.get("absolute_deviation"),
            "relative_deviation": g.get("relative_deviation"),
            "lower_bound": g.get("lower_bound"),
            "upper_bound": g.get("upper_bound"),
            "in_normal_range": g.get("in_normal_range"),
            "status": g.get("status", "unknown"),
            "trend": g.get("trend", "insufficient_data"),
            "persistent": bool(g.get("persistent", False)),
            "persistence_count": int(g.get("persistence_count") or 0),
        }
    return out


def generate_state_report(state: AgentState) -> Dict[str, Any]:
    validated = state.get("validated_input") or {}
    classification = state.get("classification") or {}
    gaps = state.get("cognitive_gaps") or {}
    baseline = state.get("baseline") or {}
    baseline_source = state.get("baseline_source") or "none"
    warnings = list(state.get("warnings") or [])
    context = validated.get("context") or {}

    report_gaps = _gap_for_report(gaps)
    factors = suggest_contributing_factors(gaps, context)

    # 오류 경로
    if state.get("route") == "error_response":
        report = {
            "state_report_id": f"SR-{uuid4().hex[:8].upper()}",
            "user_id": state.get("user_id") or "",
            "session_id": state.get("session_id") or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state_level": "UNKNOWN",
            "baseline": {"source": "none", "version": None, "reliability": None},
            "cognitive_gap": {},
            "context_summary": {},
            "analysis_confidence": 0.0,
            "requires_response": False,
            "additional_observation_required": True,
            "warnings": warnings + (state.get("validation_errors") or []),
            "possible_contributing_factors": [],
            "narrative_observation": None,
            "error": state.get("error"),
        }
        return {"state_report": report}

    llm = OllamaLLMService()
    narrative = llm.generate_narrative(
        state_level=str(classification.get("state_level", "UNKNOWN")),
        cognitive_gap=report_gaps,
        warnings=warnings,
        context_summary={
            "content_id": context.get("content_id"),
            "content_type": context.get("content_type"),
            "difficulty": context.get("difficulty"),
            "visual_complexity": context.get("visual_complexity"),
            "audio_stimulation": context.get("audio_stimulation"),
            "elapsed_time_min": context.get("elapsed_time_min"),
        },
        baseline_source=baseline_source,
        analysis_confidence=(
            float(classification["analysis_confidence"])
            if classification.get("analysis_confidence") is not None
            else None
        ),
        contributing_factors=factors,
    )

    report = {
        "state_report_id": f"SR-{uuid4().hex[:8].upper()}",
        "user_id": validated.get("user_id") or state.get("user_id"),
        "session_id": validated.get("session_id") or state.get("session_id"),
        "timestamp": validated.get("timestamp"),
        "state_level": classification.get("state_level", "UNKNOWN"),
        "baseline": {
            "source": baseline_source,
            "version": baseline.get("version") if baseline else None,
            "reliability": baseline.get("reliability") if baseline else None,
        },
        "cognitive_gap": report_gaps,
        "context_summary": {
            "content_id": context.get("content_id"),
            "content_type": context.get("content_type"),
            "difficulty": context.get("difficulty"),
            "visual_complexity": context.get("visual_complexity"),
            "audio_stimulation": context.get("audio_stimulation"),
            "elapsed_time_min": context.get("elapsed_time_min"),
        },
        "analysis_confidence": classification.get("analysis_confidence", 0.0),
        "requires_response": classification.get("requires_response", False),
        "additional_observation_required": classification.get(
            "additional_observation_required", True
        ),
        "warnings": warnings,
        "possible_contributing_factors": factors,
        "narrative_observation": narrative,
        "emotion_context": validated.get("emotion_context"),
    }
    return {"state_report": report}


def build_summary_payload(
    *,
    user_id: str,
    recent_episodes: List[Dict[str, Any]],
    latest_report: Dict[str, Any],
) -> Dict[str, Any]:
    """Summary Memory JSON 구성."""
    levels: Dict[str, int] = {}
    metric_out_counts: Dict[str, int] = {
        "cognitive_load": 0,
        "attention": 0,
        "fatigue": 0,
    }
    recent_summaries: List[Dict[str, Any]] = []

    for ep in recent_episodes[:10]:
        level = ep.get("state_level") or ""
        levels[level] = levels.get(level, 0) + 1
        report = ep.get("state_report_json") or ep.get("state_report") or {}
        cg = report.get("cognitive_gap") or ep.get("gap_json") or {}
        for m in metric_out_counts:
            status = (cg.get(m) or {}).get("status")
            if status in ("above_baseline", "below_baseline"):
                metric_out_counts[m] += 1
        recent_summaries.append(
            {
                "session_id": ep.get("session_id"),
                "state_level": level,
                "timestamp": report.get("timestamp") or str(ep.get("created_at")),
            }
        )

    # 최신 리포트 반영
    latest_level = latest_report.get("state_level")
    if latest_level:
        levels[latest_level] = levels.get(latest_level, 0) + 1

    frequent = sorted(metric_out_counts.items(), key=lambda x: x[1], reverse=True)
    patterns: List[str] = []
    if frequent and frequent[0][1] >= 2:
        patterns.append(f"최근 세션에서 '{frequent[0][0]}' 지표 이탈이 반복 관찰됨.")
    if levels.get("ACTION_REQUIRED", 0) >= 2:
        patterns.append("ACTION_REQUIRED 상태가 최근 반복 관찰됨.")
    if levels.get("WATCH", 0) >= 3:
        patterns.append("WATCH 상태가 빈번히 관찰됨.")

    baseline_candidate = latest_report.get("state_level") == "NORMAL" and not (
        latest_report.get("warnings") or []
    )

    return {
        "user_id": user_id,
        "long_term_state_summary": {
            "state_level_counts": levels,
            "dominant_recent_level": max(levels, key=levels.get) if levels else None,
        },
        "recurring_patterns": patterns,
        "frequently_deviating_metrics": [
            {"metric": m, "count": c} for m, c in frequent if c > 0
        ],
        "recent_sessions": recent_summaries[:10],
        "baseline_update_candidate": {
            "eligible": baseline_candidate,
            "note": "NORMAL이며 경고가 없는 세션만 후보로 표시(확정 갱신 아님).",
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
