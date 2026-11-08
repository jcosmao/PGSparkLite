import socket
import time
import unittest

from lib.external.SparkClass import SparkMessage
from lib.sparkampserver import SparkAmpServer


class FakeSocketIO:
    def __init__(self):
        self.emitted = []

    def emit(self, event, data=None):
        self.emitted.append((event, data))


def wait_for(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class AppProxyServerTest(unittest.TestCase):

    def setUp(self):
        self.server = SparkAmpServer(FakeSocketIO())
        self.server.app_settings.enabled = True
        self.callbacks = []
        self.server.callback_event = self.callbacks.append
        self.amp_sock, self.amp_remote = socket.socketpair()
        self.server.start_proxy(self.amp_sock)
        self.server.connected = True

    def tearDown(self):
        self.server.proxy.close()
        self.server.bt_sock.close()
        self.amp_remote.close()

    def test_pgsparklite_writes_go_through_the_proxy(self):
        frame = SparkMessage().change_hardware_preset(1)[0]
        self.server.bt_sock.send(frame)
        self.amp_remote.settimeout(2)
        self.assertEqual(self.amp_remote.recv(len(frame)), frame)

    def test_app_command_reaches_amp_and_updates_pgsparklite(self):
        app_sock, app = socket.socketpair()
        self.addCleanup(app.close)
        self.server.app_connection(app_sock)

        frame = SparkMessage().change_effect_parameter('Twin', 3, 0.5)[0]
        app.sendall(frame)

        self.amp_remote.settimeout(2)
        self.assertEqual(self.amp_remote.recv(len(frame)), frame)
        self.assertTrue(wait_for(lambda: self.callbacks))
        self.assertEqual(self.callbacks[0]['Effect'], 'Twin')
        self.assertEqual(self.callbacks[0]['Parameter'], 3)

    def test_app_refused_when_proxy_disabled(self):
        self.server.app_settings.enabled = False
        app_sock, app = socket.socketpair()
        self.addCleanup(app.close)
        self.server.app_connection(app_sock)
        app.settimeout(2)
        self.assertEqual(app.recv(16), b'')

    def test_app_refused_while_amp_disconnected(self):
        self.server.connected = False
        app_sock, app = socket.socketpair()
        self.addCleanup(app.close)
        self.server.app_connection(app_sock)
        app.settimeout(2)
        self.assertEqual(app.recv(16), b'')

    def test_monitor_only_forwards_decoded_commands(self):
        from lib.sparkampserver import AppMonitorNotifier

        class Recorder:
            def __init__(self):
                self.events = []

            def raise_event(self, name, **kwargs):
                self.events.append(name)

        recorder = Recorder()
        monitor = AppMonitorNotifier(recorder)
        monitor.raise_event('connection_lost')
        monitor.raise_event('preset_corrupt')
        monitor.raise_event('callback', data={})
        self.assertEqual(recorder.events, ['callback'])


if __name__ == '__main__':
    unittest.main()
