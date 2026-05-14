import argparse
from pipeline.orchestrator import run_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline de detección de patrones conversacionales — Everwod"
    )
    parser.add_argument("--workspace", type=int, help="ID del workspace a analizar (omitir = todos)")
    parser.add_argument("--days",      type=int, default=90, help="Ventana de análisis en días (default: 90)")
    args = parser.parse_args()

    run_pipeline(workspace_id=args.workspace, days=args.days)
