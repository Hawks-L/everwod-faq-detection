import re
import psycopg2.extras
from pipeline.db import get_conn
from pipeline.config import DAYS_LOOKBACK


def extract_user_messages(workspace_id=None, days=None):
    days = int(days or DAYS_LOOKBACK)

    conditions = [
        "cm.message->>'role' = 'user'",
        "cm.message->'content'->0->'text'->>'value' IS NOT NULL",
        "LENGTH(cm.message->'content'->0->'text'->>'value') > 10",
        f"cm.created_at >= NOW() - INTERVAL '{days} days'",
    ]
    params = []
    if workspace_id:
        conditions.append("ac.workspace_id = %s")
        params.append(workspace_id)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            cm.id,
            cm.agent_chat_id::text   AS agent_chat_id,
            ac.workspace_id,
            cm.message->'content'->0->'text'->>'value' AS text,
            cm.created_at
        FROM chat_messages cm
        JOIN agent_chats ac ON cm.agent_chat_id = ac.id
        WHERE {where}
        ORDER BY cm.created_at DESC
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    messages = []
    for row in rows:
        text = _normalize(row["text"])
        if text:
            messages.append({
                "id":            row["id"],
                "agent_chat_id": row["agent_chat_id"],
                "workspace_id":  row["workspace_id"],
                "text":          text,
                "created_at":    row["created_at"],
            })
    return messages


_GREETINGS = re.compile(
    r"^(hola|buenas|buen\s(d[ií]a|tarde|noche)|buenos\s(d[ií]as|tardes|noches)|"
    r"hey|hi|hello|ok|okay|gracias|thanks|sí|si|no|👋|🤝)[\s!.?,]*$",
    re.IGNORECASE,
)

# Contact list pattern: "Name Lastname - 573XXXXXXXXX" repeated entries
_CONTACT_LIST = re.compile(r"573\d{9}", re.IGNORECASE)


def _normalize(text):
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"https?://\S+", "", text)    # remove URLs
    text = re.sub(r"\s+", " ", text).strip()     # collapse whitespace
    if len(text) < 15:
        return None
    if _GREETINGS.match(text):
        return None
    # Filter contact lists (contain Colombian phone numbers in bulk)
    if len(_CONTACT_LIST.findall(text)) >= 3:
        return None
    return text
