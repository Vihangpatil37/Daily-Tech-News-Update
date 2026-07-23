import sys
import argparse
import logging
from app.config import validate_config
from app.orchestrator import run_pipeline


def setup_logging():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Tech Intelligence Daily AI Agent — Local Entrypoint")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline and render HTML preview locally without sending email.")
    parser.add_argument("--lookback", type=int, default=24, help="Lookback window in hours (default: 24).")
    parser.add_argument("--recipient", type=str, default=None, help="Override recipient email address.")
    
    args = parser.parse_args()

    validate_config(strict=False)

    success = run_pipeline(
        lookback_hours=args.lookback,
        dry_run=args.dry_run,
        recipient_override=args.recipient
    )

    if not success and not args.dry_run:
        print("[!] Pipeline completed with warnings/errors. Check logs for details.")
        sys.exit(1)
    else:
        print("[OK] Pipeline executed successfully.")


if __name__ == "__main__":
    main()
