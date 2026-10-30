"""Handle Windows transport cleanup after a client resets its connection."""

import logging
import sys
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def windows_disconnect_handler(loop):
    if sys.platform != "win32":
        yield
        return

    previous = loop.get_exception_handler()

    def handle_exception(active_loop, context):
        error = context.get("exception")
        callback = getattr(context.get("handle"), "_callback", None)
        if (
            isinstance(error, ConnectionResetError)
            and getattr(error, "winerror", None) == 10054
            and getattr(callback, "__module__", "") == "asyncio.proactor_events"
            and getattr(callback, "__qualname__", "") == "_ProactorBasePipeTransport._call_connection_lost"
        ):
            logger.info("A client closed its HTTP connection during Windows socket cleanup.")
            return
        if previous is not None:
            previous(active_loop, context)
        else:
            active_loop.default_exception_handler(context)

    loop.set_exception_handler(handle_exception)
    try:
        yield
    finally:
        if loop.get_exception_handler() is handle_exception:
            loop.set_exception_handler(previous)
