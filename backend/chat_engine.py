"""
chat_engine.py — v4.0
======================
Two public functions:
  ask(question, combo, history)   → contextual Q&A for a selected combination
  ask_global(question, full_result) → Q&A about the entire parsed file

Uses Chain-of-Thought (CoT) prompting for better technical accuracy.
Prompts live in config.py — not here.
"""

from __future__ import annotations
import requests, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import HF_TOKEN, HF_MODEL, SYSTEM_CHAT_PROMPT, SYSTEM_GLOBAL_CHAT_PROMPT

HF_ENDPOINT_V1  = "https://api-inference.huggingface.co/v1/chat/completions"
HF_ENDPOINT_OLD = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type":  "application/json",
}


# ─── Internal callers ──────────────────────────────────────────────────────────

def _call_v1(system: str, messages_payload: list, max_tokens: int = 500) -> str:
    payload = {
        "model":       HF_MODEL,
        "messages":    [{"role": "system", "content": system}] + messages_payload,
        "max_tokens":  max_tokens,
        "temperature": 0.3,
    }
    r = requests.post(HF_ENDPOINT_V1, headers=HEADERS, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_legacy(prompt: str, max_tokens: int = 500) -> str:
    payload = {
        "inputs":     prompt,
        "parameters": {"max_new_tokens": max_tokens, "temperature": 0.3, "return_full_text": False},
    }
    r = requests.post(HF_ENDPOINT_OLD, headers=HEADERS, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list) and data:
        return data[0].get("generated_text", "").strip()
    if isinstance(data, dict) and "error" in data:
        if "loading" in str(data["error"]).lower():
            return "⏳ Model is loading. Please try again in 20 seconds."
    return str(data)


# ─── Public API ───────────────────────────────────────────────────────────────

def ask(question: str, combo: dict, history: list = []) -> str:
    """
    Chain-of-Thought Q&A for a specific band combination.
    System prompt (with CoT instructions) is loaded from config.py.
    History is limited to last 4 turns to avoid context overflow.
    """
    messages = []

    # Inject combo context as first user turn so model has it
    messages.append({
        "role":    "user",
        "content": f"Band combination context:\n{json.dumps(combo, indent=2, default=str)[:1500]}",
    })
    messages.append({
        "role":    "assistant",
        "content": "Understood. I have the combination context. What would you like to know?",
    })

    # Inject last 4 history turns
    for turn in history[-4:]:
        messages.append({"role": "user",      "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["assistant"]})

    messages.append({"role": "user", "content": question})

    try:
        return _call_v1(SYSTEM_CHAT_PROMPT, messages)
    except Exception:
        try:
            combo_str = json.dumps(combo, indent=2, default=str)[:1000]
            hist_str  = "".join(
                f"\nUser: {t['user']}\nAssistant: {t['assistant']}"
                for t in history[-3:]
            )
            prompt = (
                f"<s>[INST] {SYSTEM_CHAT_PROMPT}\n\n"
                f"Combo:\n{combo_str}{hist_str}\n\nQuestion: {question} [/INST]"
            )
            return _call_legacy(prompt)
        except requests.exceptions.Timeout:
            return "⏳ Request timed out. Model may be cold-starting — try again in 30 seconds."
        except Exception as e:
            return f"❌ AI unavailable: {str(e)[:120]}"


def ask_global(question: str, full_result: dict) -> str:
    """
    CoT Q&A about the entire parsed UE capability file.
    Sends a compact summary of the full result as context.
    """
    # Build compact context — counts + samples, not the full JSON
    context = {
        "lte_band_count": len(full_result.get("lteBands", [])),
        "nr_band_count":  len(full_result.get("nrBands",  [])),
        "lte_ca_count":   len(full_result.get("lteca",    [])),
        "nr_ca_count":    len(full_result.get("nrca",     [])),
        "mrdc_count":     len(full_result.get("mrdc",     [])),
        "metadata":       full_result.get("metadata", {}),
        "lte_bands":      full_result.get("lteBands", [])[:10],
        "nr_bands":       full_result.get("nrBands",  [])[:10],
        "mrdc_sample":    full_result.get("mrdc",     [])[:3],
        "ai_enrichment":  full_result.get("ai_enrichment", {}),
    }
    context_str = json.dumps(context, indent=2, default=str)[:2500]

    messages = [
        {
            "role":    "user",
            "content": f"Full UE capability data:\n{context_str}",
        },
        {
            "role":    "assistant",
            "content": "Understood. I have the full capability data. What would you like to know?",
        },
        {
            "role":    "user",
            "content": question,
        },
    ]

    try:
        return _call_v1(SYSTEM_GLOBAL_CHAT_PROMPT, messages)
    except Exception:
        try:
            prompt = (
                f"<s>[INST] {SYSTEM_GLOBAL_CHAT_PROMPT}\n\n"
                f"UE Capability Data:\n{context_str}\n\nQuestion: {question} [/INST]"
            )
            return _call_legacy(prompt)
        except requests.exceptions.Timeout:
            return "⏳ Request timed out — try again in 30 seconds."
        except Exception as e:
            return f"❌ AI unavailable: {str(e)[:120]}"


# ── Legacy alias — kept for any old callers ──────────────────────────────────
def enrich_combination(combo: dict) -> str:
    """Backward-compat alias. Use ai_processor.enrich_single_combo() for new code."""
    from ai_processor import enrich_single_combo
    enriched = enrich_single_combo(combo)
    return enriched.get("ai_summary", "No summary available.")
