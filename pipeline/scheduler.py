from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from pipeline.orchestrator import run_pipeline


def start_scheduler(interval_hours=24, workspace_id=None, days=None, run_now=True):
    scheduler = BlockingScheduler(timezone="America/Bogota")

    scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(hours=interval_hours),
        kwargs={"workspace_id": workspace_id, "days": days},
        id="faq_pipeline",
        replace_existing=True,
        next_run_time=datetime.now() if run_now else None,
    )

    print("=" * 55)
    print("  SCHEDULER: Pipeline de Detección de FAQs")
    print("=" * 55)
    print(f"  Intervalo : cada {interval_hours} hora(s)")
    print(f"  Workspace : {'todos' if not workspace_id else workspace_id}")
    print(f"  Ventana   : {days or 90} días")
    print(f"  Zona horaria: America/Bogota")
    print(f"  Primera ejecución: {'inmediata' if run_now else 'en ' + str(interval_hours) + 'h'}")
    print("\nPresiona Ctrl+C para detener.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler detenido.")
