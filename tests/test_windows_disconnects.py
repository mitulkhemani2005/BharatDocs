import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.core.asyncio_errors import windows_disconnect_handler


class WindowsDisconnectTests(unittest.TestCase):
    def loop(self, previous=None):
        loop = Mock()
        loop.handler = previous
        loop.get_exception_handler.side_effect = lambda: loop.handler
        loop.set_exception_handler.side_effect = lambda handler: setattr(loop, 'handler', handler)
        return loop

    def context(self, code=10054, callback='_ProactorBasePipeTransport._call_connection_lost'):
        error = ConnectionResetError('Client reset')
        error.winerror = code
        return {'exception': error, 'handle': SimpleNamespace(_callback=SimpleNamespace(
            __module__='asyncio.proactor_events', __qualname__=callback))}

    @patch('backend.core.asyncio_errors.sys.platform', 'win32')
    def test_only_expected_cleanup_reset_is_handled(self):
        loop = self.loop()
        with windows_disconnect_handler(loop):
            loop.handler(loop, self.context())
            loop.default_exception_handler.assert_not_called()
            for context in (self.context(10053), self.context(callback='active_request'), {'exception': ValueError('real error')}):
                loop.handler(loop, context)
                loop.default_exception_handler.assert_called_with(context)
        self.assertIsNone(loop.handler)

    @patch('backend.core.asyncio_errors.sys.platform', 'win32')
    def test_previous_handler_receives_unrelated_errors_and_is_restored(self):
        previous = Mock()
        loop = self.loop(previous)
        context = {'exception': RuntimeError('real error')}
        with windows_disconnect_handler(loop):
            loop.handler(loop, context)
            previous.assert_called_once_with(loop, context)
        self.assertIs(loop.handler, previous)

    @patch('backend.core.asyncio_errors.sys.platform', 'linux')
    def test_other_platforms_keep_their_handler(self):
        loop = self.loop()
        with windows_disconnect_handler(loop):
            loop.set_exception_handler.assert_not_called()


if __name__ == '__main__':
    unittest.main()
