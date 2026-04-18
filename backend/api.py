"""
api.py — Samsung PRISM FastAPI Backend v4.0
============================================
Architecture:
  POST /upload         → parse → format → confidence → AI PROCESSOR → store → return summary
  GET  /combinations   → list all combos (table view with ai_confidence + validation_status)
  GET  /combination/{id} → single combo detail (with AI explanation, cached — no re-call)
  POST /chat           → chatbot (question + combo context, CoT prompting)
  POST /chat/global    → chatbot on entire parsed file
  GET  /health         → status check
  GET  /stats          → dashboard statistics
"""

from __future__ import annotations
import os, sys, json, time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from entry_point          import find_entry_point
from sequential_extractor import extract_all
from output_formatter     import format_output, validate_output
from confidence_engine    import score_output
from chat_engine          import ask, ask_global
from ai_processor         import enrich_output, enrich_single_combo

app = FastAPI(title="Samsung PRISM — UE Capability Parser", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_store: dict = {
    "result":       None,
    "combinations": [],
    "chat_history": {},
    "upload_time":  None,
    "filename":     None,
}


def _flatten_combos(result: dict) -> list:
    rows = []
    idx = 0

    # Pull top-level AI enrichment if available (from upload-time enrich_output call)
    top_ai = result.get("ai_enrichment", {})

    for combo in result.get("lteca", []):
        bands = [f"E-B{c['band']}" for c in combo.get("components", [])]
        rows.append({
            "id":               idx,
            "type":             "LTE-CA",
            "bands_summary":    " + ".join(bands),
            "bands":            bands,
            "bcs":              combo.get("bcs"),
            "has_mrdc":         False,
            "feature_set":      None,
            "raw":              combo,
            "ai_summary":       None,
            "ai_explanation":   None,   # kept for backward compat
            "ai_confidence":    None,
            "validation_status": None,
            "anomalies":        [],
            "spec_refs":        [],
            "flags":            [],
        })
        idx += 1

    for combo in result.get("nrca", []):
        bands = [f"NR-B{c['band']}" for c in combo.get("components", [])]
        fsc = None
        if combo.get("customData"):
            fsc = combo["customData"][0].get("featureSetCombination")
        rows.append({
            "id":               idx,
            "type":             "NR-CA",
            "bands_summary":    " + ".join(bands),
            "bands":            bands,
            "bcs":              combo.get("bcs"),
            "has_mrdc":         False,
            "feature_set":      fsc,
            "raw":              combo,
            "ai_summary":       None,
            "ai_explanation":   None,
            "ai_confidence":    None,
            "validation_status": None,
            "anomalies":        [],
            "spec_refs":        [],
            "flags":            [],
        })
        idx += 1

    for combo in result.get("mrdc", []):
        lte_bands = [f"E-B{c['band']}"  for c in combo.get("componentsLte", [])]
        nr_bands  = [f"NR-B{c['band']}" for c in combo.get("componentsNr",  [])]
        bands     = lte_bands + nr_bands
        fsc = dps = srxt = None
        if combo.get("customData"):
            cd   = combo["customData"][0]
            fsc  = cd.get("featureSetCombination")
            dps  = cd.get("dynamicPowerSharingENDC")
            srxt = cd.get("simultaneousRxTxInterBandENDC")
        rows.append({
            "id":               idx,
            "type":             "MRDC",
            "bands_summary":    " + ".join(bands),
            "bands":            bands,
            "lte_bands":        lte_bands,
            "nr_bands":         nr_bands,
            "has_mrdc":         True,
            "feature_set":      fsc,
            "dynamic_power_sharing":  dps,
            "simultaneous_rx_tx":     srxt,
            "raw":              combo,
            "ai_summary":       None,
            "ai_explanation":   None,
            "ai_confidence":    None,
            "validation_status": None,
            "anomalies":        [],
            "spec_refs":        [],
            "flags":            [],
        })
        idx += 1

    return rows


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status":             "ok",
        "model":              f"{__import__('config').HF_MODEL} (HuggingFace API)",
        "parsed":             _store["result"] is not None,
        "filename":           _store["filename"],
        "upload_time":        _store["upload_time"],
        "total_combinations": len(_store["combinations"]),
    }


@app.get("/stats")
def stats():
    if not _store["result"]:
        return {"error": "No data parsed yet"}
    r      = _store["result"]
    combos = _store["combinations"]
    ai_enrich = r.get("ai_enrichment", {})

    lte_ca_count = len([c for c in combos if c["type"] == "LTE-CA"])
    nr_ca_count  = len([c for c in combos if c["type"] == "NR-CA"])
    mrdc_count   = len([c for c in combos if c["type"] == "MRDC"])
    validation   = r.get("validation", {})

    return {
        "lte_bands":    len(r.get("lteBands", [])),
        "nr_bands":     len(r.get("nrBands",  [])),
        "lte_ca":       lte_ca_count,
        "nr_ca":        nr_ca_count,
        "mrdc":         mrdc_count,
        "total":        len(combos),
        "confidence":   validation.get("score", 0),
        "decision":     validation.get("decision", "unknown"),
        "flags":        validation.get("flags", []),
        "per_section":  validation.get("per_section", {}),
        "metadata":     r.get("metadata", {}),
        # AI enrichment at file level
        "ai_summary":         ai_enrich.get("ai_summary"),
        "ai_confidence":      ai_enrich.get("ai_confidence"),
        "ai_validation":      ai_enrich.get("validation_status"),
        "ai_anomalies":       ai_enrich.get("anomalies", []),
        "ai_spec_refs":       ai_enrich.get("spec_refs", []),
    }


@app.get("/download")
def download_json():
    """
    Download the full parsed + AI-enriched result as a JSON file.
    Filename matches the uploaded file (e.g. result_UE_Capa.json).
    """
    if not _store["result"]:
        raise HTTPException(404, "No data parsed yet. Upload a file first.")

    base = (_store["filename"] or "result").rsplit(".", 1)[0]
    filename = f"prism_{base}.json"

    content = json.dumps(_store["result"], indent=2, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    text    = content.decode(errors="replace")
    start   = time.time()

    # ── Step 1: Rule-based parsing (UNCHANGED — parser is truth) ────────────
    entry_info = find_entry_point(text)
    extracted  = extract_all(text)
    
    # ── Step 1.5: Hybrid AI Assist strictly for gap-filling ─────────────────
    from ai_assist_parser import run_hybrid_pipeline
    extracted = run_hybrid_pipeline(text, extracted)
    
    result     = format_output(extracted, entry_info, file.filename)
    validation = score_output(result)
    result["validation"] = validation

    # Step 2 logic has been integrated inside run_hybrid_pipeline.

    # ── Step 3: Flatten combos and store ────────────────────────────────────
    combos = _flatten_combos(result)

    _store["result"]       = result
    _store["combinations"] = combos
    _store["chat_history"] = {}
    _store["upload_time"]  = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _store["filename"]     = file.filename

    elapsed   = round(time.time() - start, 2)
    ai_enrich = result.get("ai_enrichment", {})
    ai_notes  = result.get("ai_notes", {})

    # Combine flags and AI warnings
    flags = validation.get("flags", [])
    if ai_notes.get("warnings"):
        flags.extend([f"[AI] {w}" for w in ai_notes["warnings"]])

    # If AI computed a hybrid severity confidence, use it over the naive score
    hybrid_confidence = ai_notes.get("confidence", validation.get("score"))

    return {
        "status":   "success",
        "filename": file.filename,
        "rat_type": entry_info.get("rat_type"),
        "metadata": result.get("metadata"),
        "elapsed_seconds": elapsed,
        "summary": {
            "lte_bands": len(result.get("lteBands", [])),
            "nr_bands":  len(result.get("nrBands",  [])),
            "lte_ca":    len(result.get("lteca",    [])),
            "nr_ca":     len(result.get("nrca",     [])),
            "mrdc":      len(result.get("mrdc",     [])),
            "total_combinations": len(combos),
        },
        "confidence":        hybrid_confidence,
        "decision":          validation.get("decision"),
        "flags":             flags,
        "ai_confidence":     ai_enrich.get("confidence"),
        "ai_validation":     ai_enrich.get("validation_status"),
        "ai_summary":        ai_enrich.get("summary"),
        "ai_anomalies":      ai_enrich.get("issues", []),
    }


@app.get("/combinations")
def get_combinations(type_filter: Optional[str] = None, page: int = 1, limit: int = 50):
    if not _store["combinations"]:
        return {"combinations": [], "total": 0, "page": 1, "pages": 0}

    combos = _store["combinations"]
    if type_filter and type_filter.upper() != "ALL":
        combos = [c for c in combos if c["type"] == type_filter.upper()]

    total = len(combos)
    pages = (total + limit - 1) // limit
    start = (page - 1) * limit
    end   = start + limit

    table = []
    for c in combos[start:end]:
        table.append({
            "id":                   c["id"],
            "type":                 c["type"],
            "bands_summary":        c["bands_summary"],
            "feature_set":          c.get("feature_set"),
            "has_mrdc":             c["has_mrdc"],
            "dynamic_power_sharing": c.get("dynamic_power_sharing"),
            "ai_confidence":        c.get("ai_confidence"),
            "validation_status":    c.get("validation_status"),
            "ai_summary":           c.get("ai_summary"),
        })

    return {"combinations": table, "total": total, "page": page, "pages": pages}


@app.get("/combination/{combo_id}")
def get_combination(combo_id: int):
    combos = _store["combinations"]
    if not combos:
        raise HTTPException(404, "No data parsed yet. Upload a file first.")

    match = next((c for c in combos if c["id"] == combo_id), None)
    if not match:
        raise HTTPException(404, f"Combination {combo_id} not found.")

    # Spec refs per combo type
    spec_refs = {
        "LTE-CA": "3GPP TS 36.306 §4.3.6 / TS 36.331 §6.3.6",
        "NR-CA":  "3GPP TS 38.306 §4.2.7 / TS 38.331 §6.3.2",
        "MRDC":   "3GPP TS 37.340 §5.3 / TS 38.331 §6.3.2",
    }
    match["spec_reference"] = spec_refs.get(match["type"], "3GPP TS 38.331")
    match["chat_history"]   = _store["chat_history"].get(combo_id, [])

    # ── Per-combo AI enrichment — ONLY if missing (cache respected) ──────────
    if match.get("ai_confidence") is None:
        try:
            match = enrich_single_combo(match)
            # Update the cached store entry
            for c in _store["combinations"]:
                if c["id"] == combo_id:
                    c.update({
                        "ai_summary":        match.get("ai_summary"),
                        "ai_confidence":     match.get("ai_confidence"),
                        "validation_status": match.get("validation_status"),
                        "anomalies":         match.get("anomalies", []),
                        "spec_refs":         match.get("spec_refs", []),
                    })
                    break
        except Exception as e:
            match["ai_summary"]    = f"AI enrichment unavailable: {str(e)[:100]}"
            match["ai_confidence"] = None

    return match


class ChatRequest(BaseModel):
    combo_id: int
    question: str


class GlobalChatRequest(BaseModel):
    question: str


@app.post("/chat")
def chat(req: ChatRequest):
    combos = _store["combinations"]
    if not combos:
        raise HTTPException(400, "No data parsed yet.")

    combo = next((c for c in combos if c["id"] == req.combo_id), None)
    if not combo:
        raise HTTPException(404, f"Combination {req.combo_id} not found.")

    history = _store["chat_history"].get(req.combo_id, [])
    answer  = ask(question=req.question, combo=combo.get("raw", combo), history=history)

    history.append({"user": req.question, "assistant": answer, "timestamp": time.strftime("%H:%M")})
    _store["chat_history"][req.combo_id] = history

    return {
        "combo_id":       req.combo_id,
        "question":       req.question,
        "answer":         answer,
        "history_length": len(history),
    }


@app.post("/chat/global")
def global_chat(req: GlobalChatRequest):
    if not _store["result"]:
        raise HTTPException(400, "No data parsed yet.")

    answer = ask_global(
        question=req.question,
        full_result=_store["result"],
    )
    return {"question": req.question, "answer": answer}


@app.delete("/chat/{combo_id}")
def clear_chat(combo_id: int):
    _store["chat_history"][combo_id] = []
    return {"status": "cleared", "combo_id": combo_id}


# ── SPA Frontend Serving (Deployment Mode) ──────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.isdir(frontend_dir):
    # Mount the assets directory specifically
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")
    
    # Catch-all route to serve the React index.html for client-side routing
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str, request: Request):
        # Ignore API routes to prevent shadowing
        if full_path.startswith("upload") or full_path.startswith("health") or full_path.startswith("stats") or full_path.startswith("combinations") or full_path.startswith("combination") or full_path.startswith("download") or full_path.startswith("chat"):
            raise HTTPException(status_code=404, detail="API route not found")
        
        # Check if the requested path corresponds to a real file (like vite.svg)
        potential_file = os.path.join(frontend_dir, full_path)
        if os.path.isfile(potential_file):
            return FileResponse(potential_file)
            
        return FileResponse(os.path.join(frontend_dir, "index.html"))

if __name__ == "__main__":
    import uvicorn
    # Use standard host and port to bind globally. Reload is off for production.
    uvicorn.run("api:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
