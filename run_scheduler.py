import argparse
from pipeline.scheduler import start_scheduler

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scheduler del pipeline — Everwod")
    parser.add_argument("--hours",     type=int, default=24, help="Intervalo entre ejecuciones en horas (default: 24)")
    parser.add_argument("--workspace", type=int, help="ID del workspace (omitir = todos)")
    parser.add_argument("--days",      type=int, default=90, help="Ventana de análisis en días")
    args = parser.parse_args()

    start_scheduler(interval_hours=args.hours, workspace_id=args.workspace, days=args.days)
