"""
ai_assist_parser — Hybrid AI-Assisted Parser Package
=====================================================
Dynamic, future-proof hybrid parser for UE Capability data.

Architecture:
  Rule Parser (unchanged) → Gap Detection → AI Assist → Validation
  → Safe Merge → AI Enrichment → Final JSON with Provenance

Public API:
  run_hybrid_pipeline(raw_text, parsed_json) → enriched parsed_json

Modules:
  walker.py       — Generic structure-agnostic tree traversal
  gap_detector.py — Pattern-based gap detection (never modifies parser logic)
  ai_assist.py    — Controlled AI calls (ONE batched call for all gaps)
  validator.py    — Strict validation of AI output before merge
  merger.py       — Safe merge: fill-only, never overwrite
  enrichment.py   — Global AI enrichment (ONE call for summary/confidence)
  pipeline.py     — Orchestration, confidence scoring, provenance tracking
"""

from .pipeline import run_hybrid_pipeline

__all__ = ["run_hybrid_pipeline"]
