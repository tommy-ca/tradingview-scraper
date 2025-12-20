class RetryHandler:
    """
    Handles exponential backoff logic for retrying operations.
    """

    def __init__(self, max_retries: int = 5, initial_delay: float = 1.0, max_delay: float = 60.0, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def get_delay(self, attempt: int) -> float:
        """
        Calculates the delay for a given attempt number.
        """
        delay = self.initial_delay * (self.backoff_factor**attempt)
        return min(delay, self.max_delay)

    def __iter__(self):
        for attempt in range(self.max_retries):
            yield self.get_delay(attempt)
