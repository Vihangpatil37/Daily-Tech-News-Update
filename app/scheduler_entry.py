import sys
import logging
from pathlib import Path
from app.config import validate_config, BASE_DIR
from app.orchestrator import run_pipeline


def setup_scheduler_logging():
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "scheduler.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8")
        ]
    )


def main():
    setup_scheduler_logging()
    logger = logging.getLogger("tech-agent.scheduler")
    logger.info("Executing Render Cron Job scheduler entrypoint...")

    # Strict config validation for production run
    validate_config(strict=True)

    try:
        success = run_pipeline(lookback_hours=24, dry_run=False)
        if success:
            logger.info("Cron job execution finished successfully.")
            sys.exit(0)
        else:
            logger.error("Cron job execution reported failure.")
            sys.exit(1)
    except Exception as e:
        logger.critical("Unhandled exception in scheduler execution: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
