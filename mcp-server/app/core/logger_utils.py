"""Low-level logging helper used by :class:`app.core.mcp_logger.MCPLogger`.

Lives in ``core/`` (not a separate ``utils/`` role) because it is a
foundational logging concern that ``core/mcp_logger`` depends on. Keeping it
here preserves the one-directional dependency rule: ``core/`` never imports
from a higher layer.
"""


class LoggerUtils:
    """Static helpers for emitting structured ``extra`` fields to plain-text logs."""

    @staticmethod
    def log_with_extra(msg, *args, logger, extra=None, **kwargs):
        """Log *msg*, then one line per key/value pair in *extra*.

        Used when ``extra`` fields need to be visible in plain-text local log
        files, since the standard logging formatter does not automatically
        print the contents of an ``extra`` dict.

        Args:
            msg (str): The primary log message.
            *args: Positional format arguments forwarded to each logger call
                (e.g. ``"val: %s", val``).
            logger (callable): The bound logger method to write with
                (e.g. ``logger.info``, ``logger.error``).
            extra (dict | None): Structured key/value fields to log
                individually after the main message. Defaults to None.
            **kwargs: Additional keyword arguments forwarded to each logger
                call (e.g. ``exc_info``, ``stack_info``).

        Returns:
            None
        """
        # Main message first, then one line per extra key.
        if extra:
            for key, value in extra.items():
                logger(f"{key}: {value}", *args, **kwargs)
