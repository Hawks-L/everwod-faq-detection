from typing import Optional

import psycopg2.extras
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pipeline.db import get_conn

app = FastAPI(
    title="Everwod — FAQ Suggestions API",
    description="Valida sugerencias de FAQs generadas automáticamente desde conversaciones de WhatsApp.",
    version="1.0.0",
)


# ── Schemas ──────────────────────────────────────────────────────────────────

class ReviewBody(BaseModel):
    reviewed_by: Optional[str] = "admin"


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}


@app.get("/suggestions", tags=["Sugerencias"])
def list_suggestions(
    workspace_id: Optional[int] = None,
    status: str = "pending",
):
    """Lista sugerencias de FAQs filtradas por workspace y estado."""
    conditions = ["status = %s"]
    params: list = [status]

    if workspace_id:
        conditions.append("workspace_id = %s")
        params.append(workspace_id)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT id, workspace_id, question, suggested_answer,
               cluster_id, message_count, sample_messages, status, created_at
        FROM faq_suggestions
        WHERE {where}
        ORDER BY message_count DESC
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [dict(r) for r in rows]


@app.get("/suggestions/stats", tags=["Sugerencias"])
def suggestions_stats():
    """Resumen de sugerencias por estado."""
    sql = "SELECT status, COUNT(*) AS total FROM faq_suggestions GROUP BY status"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@app.post("/suggestions/{suggestion_id}/approve", tags=["Validación"])
def approve(suggestion_id: str, body: ReviewBody):
    """Aprueba una sugerencia y la marca como lista para agregar al agente."""
    return _set_status(suggestion_id, "approved", body.reviewed_by)


@app.post("/suggestions/{suggestion_id}/reject", tags=["Validación"])
def reject(suggestion_id: str, body: ReviewBody):
    """Rechaza una sugerencia."""
    return _set_status(suggestion_id, "rejected", body.reviewed_by)


@app.get("/suggestions/{suggestion_id}", tags=["Sugerencias"])
def get_suggestion(suggestion_id: str):
    """Detalle de una sugerencia específica."""
    sql = "SELECT * FROM faq_suggestions WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, [suggestion_id])
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada")
    return dict(row)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_status(suggestion_id: str, status: str, reviewed_by: Optional[str]):
    sql = """
        UPDATE faq_suggestions
        SET status      = %s,
            reviewed_by = %s,
            reviewed_at = NOW(),
            updated_at  = NOW()
        WHERE id = %s
        RETURNING id, question, status
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (status, reviewed_by, suggestion_id))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Sugerencia no encontrada")
    return dict(row)
