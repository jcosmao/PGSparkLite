import socket
import threading
import time
import unittest

from lib.external.SparkClass import SparkMessage
from lib.external.SparkCommsClass import SparkComms
from lib.external.SparkReaderClass import SparkReadMessage
from lib.sparklistener import SparkListener
from lib.sparkproxy import FrameSplitter, SparkProxy

# Frames captured between the official Spark app and a Spark 40
APP_GET_NAME = bytes.fromhex(
    '01fe000053fe170000000000000000' '00f00101000211f7')
AMP_NAME_REPLY = bytes.fromhex(
    '01fe000041ff230000000000000000' '00f001055d03110208285370'
    '61726b00203430f7')


def recv_exactly(sock, size, timeout=2.0):
    sock.settimeout(timeout)
    data = b''
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            break
        data += chunk
    return data


def wait_for(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class FrameSplitterTest(unittest.TestCase):

    def test_splits_concatenated_frames(self):
        splitter = FrameSplitter()
        frames = splitter.feed(APP_GET_NAME + AMP_NAME_REPLY)
        self.assertEqual(frames, [APP_GET_NAME, AMP_NAME_REPLY])

    def test_reassembles_frame_sent_in_pieces(self):
        splitter = FrameSplitter()
        self.assertEqual(splitter.feed(APP_GET_NAME[:3]), [])
        self.assertEqual(splitter.feed(APP_GET_NAME[3:10]), [])
        self.assertEqual(splitter.feed(APP_GET_NAME[10:]), [APP_GET_NAME])

    def test_drops_garbage_before_frame_start(self):
        splitter = FrameSplitter()
        self.assertEqual(splitter.feed(b'\x00\x13' + APP_GET_NAME),
                         [APP_GET_NAME])


class SparkProxyTest(unittest.TestCase):

    def setUp(self):
        # amp_remote plays the amp, app_remote plays the Spark app
        self.amp_sock, self.amp_remote = socket.socketpair()
        self.proxy = SparkProxy(self.amp_sock)
        self.proxy.start()

    def tearDown(self):
        self.proxy.close()
        self.amp_remote.close()
        self.proxy.local.close()
        self.proxy.monitor.close()

    def attach_app(self):
        app_sock, app_remote = socket.socketpair()
        self.proxy.attach_app(app_sock)
        self.addCleanup(app_remote.close)
        return app_remote

    def test_local_writes_reach_the_amp(self):
        self.proxy.local.sendall(APP_GET_NAME)
        self.assertEqual(recv_exactly(self.amp_remote, len(APP_GET_NAME)),
                         APP_GET_NAME)

    def test_amp_data_reaches_local_without_app(self):
        self.amp_remote.sendall(AMP_NAME_REPLY)
        self.assertEqual(recv_exactly(self.proxy.local, len(AMP_NAME_REPLY)),
                         AMP_NAME_REPLY)

    def test_app_and_amp_are_relayed_both_ways(self):
        app = self.attach_app()

        app.sendall(APP_GET_NAME)
        self.assertEqual(recv_exactly(self.amp_remote, len(APP_GET_NAME)),
                         APP_GET_NAME)

        self.amp_remote.sendall(AMP_NAME_REPLY)
        self.assertEqual(recv_exactly(app, len(AMP_NAME_REPLY)),
                         AMP_NAME_REPLY)
        # PGSparkLite sees the amp traffic too
        self.assertEqual(recv_exactly(self.proxy.local, len(AMP_NAME_REPLY)),
                         AMP_NAME_REPLY)

    def test_app_frames_are_copied_to_the_monitor(self):
        app = self.attach_app()
        app.sendall(APP_GET_NAME)
        self.assertEqual(recv_exactly(self.proxy.monitor, len(APP_GET_NAME)),
                         APP_GET_NAME)

    def test_frames_from_app_and_local_never_interleave(self):
        app = self.attach_app()
        msg = SparkMessage()
        local_frame = msg.change_effect_parameter('Twin', 0, 0.5)[0]
        app_frame = msg.change_effect_parameter('Twin', 1, 0.25)[0]

        def send_split(sock, frame, count):
            for _ in range(count):
                # Byte by byte, to give the other writer every chance to cut in
                for i in range(len(frame)):
                    sock.sendall(frame[i:i + 1])

        count = 20
        writers = [
            threading.Thread(target=send_split,
                             args=(self.proxy.local, local_frame, count)),
            threading.Thread(target=send_split, args=(app, app_frame, count)),
        ]
        for w in writers:
            w.start()
        for w in writers:
            w.join()

        total = (len(local_frame) + len(app_frame)) * count
        received = recv_exactly(self.amp_remote, total)
        frames = FrameSplitter().feed(received)
        self.assertEqual(len(frames), 2 * count)
        self.assertEqual(frames.count(local_frame), count)
        self.assertEqual(frames.count(app_frame), count)

    def test_new_app_connection_replaces_the_old_one(self):
        first = self.attach_app()
        second = self.attach_app()

        first.settimeout(2)
        self.assertEqual(first.recv(16), b'')  # closed by the proxy

        self.amp_remote.sendall(AMP_NAME_REPLY)
        self.assertEqual(recv_exactly(second, len(AMP_NAME_REPLY)),
                         AMP_NAME_REPLY)

    def test_app_disconnect_keeps_the_amp_link(self):
        app = self.attach_app()
        app.close()
        self.assertTrue(wait_for(lambda: not self.proxy.app_connected))

        self.proxy.local.sendall(APP_GET_NAME)
        self.assertEqual(recv_exactly(self.amp_remote, len(APP_GET_NAME)),
                         APP_GET_NAME)

    def test_amp_disconnect_closes_everything(self):
        app = self.attach_app()
        self.amp_remote.close()

        self.proxy.local.settimeout(2)
        self.assertEqual(self.proxy.local.recv(16), b'')
        app.settimeout(2)
        self.assertEqual(app.recv(16), b'')
        self.assertTrue(self.proxy.closed)

    def test_closing_local_closes_the_amp(self):
        # PGSparkLite ejecting the amp must release it
        self.proxy.local.close()
        self.amp_remote.settimeout(2)
        self.assertEqual(self.amp_remote.recv(16), b'')

    def test_attach_after_close_is_refused(self):
        self.proxy.close()
        app_sock, app_remote = socket.socketpair()
        self.addCleanup(app_remote.close)
        self.assertFalse(self.proxy.attach_app(app_sock))
        app_remote.settimeout(2)
        self.assertEqual(app_remote.recv(16), b'')


class SparkCommsEofTest(unittest.TestCase):

    def test_closed_link_raises_instead_of_spinning(self):
        ours, theirs = socket.socketpair()
        theirs.close()
        ours.settimeout(2)
        with self.assertRaises(ConnectionError):
            SparkComms(ours).get_block()
        ours.close()


class FakeNotifier:
    def __init__(self):
        self.events = []

    def raise_event(self, name, data=None):
        self.events.append((name, data))


class AppMonitorParsingTest(unittest.TestCase):
    """App commands copied to the monitor are decoded by the usual listener."""

    def setUp(self):
        self.amp_sock, self.amp_remote = socket.socketpair()
        self.proxy = SparkProxy(self.amp_sock)
        self.proxy.start()
        self.notifier = FakeNotifier()
        listener = SparkListener(SparkReadMessage(),
                                 SparkComms(self.proxy.monitor),
                                 self.notifier)
        threading.Thread(target=listener.start, daemon=True).start()
        app_sock, self.app = socket.socketpair()
        self.proxy.attach_app(app_sock)

    def tearDown(self):
        self.proxy.close()
        self.amp_remote.close()
        self.app.close()
        self.proxy.local.close()
        self.proxy.monitor.close()

    def callbacks(self):
        return [data for name, data in self.notifier.events
                if name == 'callback']

    def test_parameter_change_from_app(self):
        frame = SparkMessage().change_effect_parameter('Twin', 2, 0.75)[0]
        self.app.sendall(frame)
        self.assertTrue(wait_for(lambda: self.callbacks()))
        data = self.callbacks()[0]
        self.assertEqual(data['Effect'], 'Twin')
        self.assertEqual(data['Parameter'], 2)
        self.assertAlmostEqual(data['Value'], 0.75, places=3)

    def test_hardware_preset_change_from_app(self):
        frame = SparkMessage().change_hardware_preset(2)[0]
        self.app.sendall(frame)
        self.assertTrue(wait_for(lambda: self.callbacks()))
        self.assertEqual(self.callbacks()[0]['NewPreset'], 2)

    def test_effect_onoff_from_app(self):
        frame = SparkMessage().turn_effect_onoff('DelayMono', 'Off')[0]
        self.app.sendall(frame)
        self.assertTrue(wait_for(lambda: self.callbacks()))
        data = self.callbacks()[0]
        self.assertEqual(data['ChangeEffectState'], 'DelayMono')
        self.assertEqual(data['OnOff'], 'Off')


if __name__ == '__main__':
    unittest.main()
