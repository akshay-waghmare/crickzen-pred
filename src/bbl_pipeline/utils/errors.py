from typing import Any
import structlog

logger = structlog.get_logger()

class ErrorHandler:
    """
    Handles errors during pipeline execution based on a configurable policy.
    Policies:
    - fail: Raise the exception immediately.
    - flag: Log the error as a warning (and potentially save to a DLQ) but continue.
    - skip: Log the error as a warning and continue (similar to flag for now, but implies discarding).
    """
    
    def __init__(self, policy: str = "skip"):
        self.policy = policy.lower()
        if self.policy not in ["skip", "flag", "fail"]:
            raise ValueError(f"Invalid error policy: {policy}. Must be one of: skip, flag, fail")

    def handle(self, error: Exception, context: dict[str, Any]) -> None:
        """
        Handle an error according to the configured policy.
        
        Args:
            error: The exception that occurred.
            context: Dictionary containing context about where the error occurred (e.g., file_path, record_id).
        """
        if self.policy == "fail":
            logger.error("Processing failed", error=str(error), **context)
            raise error
        
        elif self.policy == "flag":
            # In a future iteration, this could write to a separate 'bad_data' file.
            logger.warning("Flagging error for review", error=str(error), **context)
            
        elif self.policy == "skip":
            logger.warning("Skipping item due to error", error=str(error), **context)
