import logging
import ray
from ray.util.state import list_actors

logger = logging.getLogger(__name__)


def cleanup_zombies(ignore_errors: bool = True):
    """
    Cleanup hooks for Ray workers (Zombie Purge).

    1. Connects to Ray (if initialized).
    2. Kills idle actors or specific worker types associated with the pipeline.
    3. Clears object store.

    This function is designed to be called in a finally block or post-execution hook.
    """
    if not ray.is_initialized():
        logger.debug("Ray not initialized. Skipping zombie purge.")
        return

    try:
        logger.info("Starting Ray Zombie Purge...")

        # Attempt to list active actors for logging purposes
        try:
            # list_actors is available in Ray 2.x
            actors = list_actors(filters=[("state", "=", "ALIVE")])
            if actors:
                logger.info(f"Found {len(actors)} active actors. Initiating shutdown sequence.")
                for actor in actors:
                    # Log details about the zombie actor
                    name = actor.get("name", "unnamed")
                    class_name = actor.get("class_name", "unknown")
                    actor_id = actor.get("actor_id", "unknown")
                    logger.debug(f"Purging Actor: {actor_id} ({class_name}:{name})")
            else:
                logger.info("No active actors found.")
        except Exception as e:
            # Fallback if state API is not available or fails
            logger.debug(f"Could not list actors for detailed logging: {e}")

        # Shutdown Ray to kill all workers and clear the object store
        # This is the most reliable way to ensure a clean slate for the next run
        ray.shutdown()
        logger.info("Ray shutdown complete. Object store and workers cleared.")

    except Exception as e:
        msg = f"Error during Ray cleanup: {e}"
        if not ignore_errors:
            logger.error(msg)
            raise e
        logger.warning(msg)
