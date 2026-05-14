import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from pipeline.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


@contextmanager
def get_conn():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_faq_suggestions_table():
    sql = """
    CREATE TABLE IF NOT EXISTS faq_suggestions (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id    BIGINT NOT NULL,
        question        TEXT NOT NULL,
        suggested_answer TEXT,
        cluster_id      INTEGER,
        message_count   INTEGER DEFAULT 0,
        sample_messages JSONB DEFAULT '[]',
        status          VARCHAR(20) DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected')),
        created_at      TIMESTAMP DEFAULT NOW(),
        updated_at      TIMESTAMP DEFAULT NOW(),
        reviewed_at     TIMESTAMP,
        reviewed_by     VARCHAR(255)
    );
    CREATE INDEX IF NOT EXISTS idx_faq_suggestions_workspace
        ON faq_suggestions(workspace_id);
    CREATE INDEX IF NOT EXISTS idx_faq_suggestions_status
        ON faq_suggestions(status);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    print("  Tabla faq_suggestions lista.")
