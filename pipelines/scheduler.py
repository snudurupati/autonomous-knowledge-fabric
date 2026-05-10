import time
import logging
import os
import sys
from pipelines.batch_resolver import run_batch_resolver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/scheduler.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def start_scheduler(interval_secs=3600):
    """
    Persistent scheduler that runs the batch resolver at a fixed interval.
    """
    logger.info(f"🚀 Batch Resolver Scheduler started. Interval: {interval_secs}s (1 hour)")
    
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("❌ GEMINI_API_KEY not found. Please source .env.omni first.")
        sys.exit(1)

    while True:
        try:
            logger.info("📅 Starting hourly batch resolution cycle...")
            start_time = time.time()
            
            run_batch_resolver()
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Cycle complete. Took {elapsed:.1f}s.")
            
            logger.info(f"😴 Sleeping for {interval_secs}s...")
            time.sleep(interval_secs)
            
        except KeyboardInterrupt:
            logger.info("🛑 Scheduler stopped by user.")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected error in scheduler: {e}")
            logger.info("😴 Retrying in 60s...")
            time.sleep(60)

if __name__ == "__main__":
    # Ensure backups directory exists for logging
    os.makedirs("backups", exist_ok=True)
    start_scheduler()
