import os
import sys
import time
import logging
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
import schedule

from app.config import validate_config, BASE_DIR
from app.orchestrator import run_pipeline

logger = logging.getLogger("tech-agent.web_entry")

def setup_logging():
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "web_scheduler.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8")
        ]
    )

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Respond to health checks from Render to keep the Web Service alive."""
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
        
    def log_message(self, format, *args):
        # Suppress noisy HTTP logs from health checks
        pass

def run_server():
    """Run a lightweight HTTP server on the port provided by Render."""
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Starting health check web server on port {port}...")
    server.serve_forever()

def job():
    """The daily pipeline job."""
    logger.info("Executing scheduled pipeline run...")
    try:
        success = run_pipeline(lookback_hours=24, dry_run=False)
        if success:
            logger.info("Pipeline execution finished successfully.")
        else:
            logger.error("Pipeline execution reported failure.")
    except Exception as e:
        logger.critical("Unhandled exception in pipeline execution: %s", e, exc_info=True)

def main():
    setup_logging()
    logger.info("Initializing Web Service scheduler...")

    # Strict config validation for production run
    validate_config(strict=True)

    # Start the HTTP server in a background daemon thread
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()

    # Schedule the job. 
    # Render servers run on UTC by default. 02:00 UTC = 07:30 IST.
    target_time = "02:00"
    schedule.every().day.at(target_time).do(job)
    logger.info(f"Pipeline scheduled to run every day at {target_time} UTC (07:30 AM IST).")

    # Keep the main thread alive and running the scheduler
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler.")
        sys.exit(0)

if __name__ == "__main__":
    main()
