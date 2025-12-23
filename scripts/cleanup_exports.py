import glob
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cleanup")


def cleanup():
    files = glob.glob("export/*.json")
    count = 0
    for f in files:
        try:
            os.remove(f)
            count += 1
        except Exception as e:
            logger.error(f"Failed to delete {f}: {e}")

    logger.info(f"Deleted {count} files from export/")


if __name__ == "__main__":
    cleanup()
