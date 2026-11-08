#####################################################################
# Spark Proxy
#
# Shares one Bluetooth link to the amp between PGSparkLite and the
# official Spark app (connected to the Pi, see sparkappserver.py).
#
#   amp  -> PGSparkLite (local) and the app
#   app  -> amp, frame by frame, plus a copy on the monitor socket so
#           PGSparkLite can follow what the app changes
#   local -> amp, frame by frame
#
# PGSparkLite talks to `local` and `monitor` exactly like it talks to a
# Bluetooth socket, so the rest of the code does not need to know.
#####################################################################

import socket
import threading

FRAME_START = b'\x01\xfe'
FRAME_HEADER_LEN = 7   # length byte is at offset 6


class FrameSplitter:
    """Cut a byte stream into Spark frames (01 fe ... length at [6])."""

    def __init__(self):
        self.buffer = b''

    def feed(self, data):
        self.buffer += data
        frames = []
        while True:
            start = self.buffer.find(FRAME_START)
            if start < 0:
                # Keep a trailing 0x01, it may be the start of the next frame
                self.buffer = self.buffer[-1:] if self.buffer.endswith(b'\x01') else b''
                return frames
            self.buffer = self.buffer[start:]
            if len(self.buffer) < FRAME_HEADER_LEN:
                return frames
            length = self.buffer[6]
            if length < FRAME_HEADER_LEN:
                # Not a real frame start, skip it
                self.buffer = self.buffer[2:]
                continue
            if len(self.buffer) < length:
                return frames
            frames.append(self.buffer[:length])
            self.buffer = self.buffer[length:]


class SparkProxy:

    def __init__(self, amp_sock, log=print):
        self.amp = amp_sock
        self.log = log
        self.local, self._local_peer = socket.socketpair()
        self.monitor, self._monitor_peer = socket.socketpair()
        self._amp_write_lock = threading.Lock()
        self._app_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._app = None
        self.closed = False

    ##################
    # Public API
    ##################

    def start(self):
        for target in (self._pump_amp, self._pump_local, self._drain_monitor):
            threading.Thread(target=target, daemon=True).start()

    @property
    def app_connected(self):
        return self._app is not None

    def attach_app(self, sock):
        """Relay a new Spark app connection, replacing any previous one."""
        if self.closed:
            self._close_socket(sock)
            return False
        with self._app_lock:
            old, self._app = self._app, sock
        if old is not None:
            self.log('Spark app: previous connection replaced')
            self._close_socket(old)
        threading.Thread(target=self._pump_app, args=(sock,),
                         daemon=True).start()
        self.log('Spark app connected')
        return True

    def close(self):
        with self._close_lock:
            if self.closed:
                return
            self.closed = True
        with self._app_lock:
            app, self._app = self._app, None
        for sock in (app, self.amp, self._local_peer, self._monitor_peer):
            if sock is not None:
                self._close_socket(sock)

    ##################
    # Pumps
    ##################

    def _pump_amp(self):
        try:
            while True:
                data = self.amp.recv(4096)
                if not data:
                    break
                self._local_peer.sendall(data)
                app = self._app
                if app is not None:
                    try:
                        app.sendall(data)
                    except OSError:
                        self._detach_app(app)
        except OSError:
            pass
        if not self.closed:
            self.log('Spark proxy: amp link closed')
        self.close()

    def _pump_local(self):
        splitter = FrameSplitter()
        try:
            while True:
                data = self._local_peer.recv(4096)
                if not data:
                    break
                for frame in splitter.feed(data):
                    self._write_amp(frame)
        except OSError:
            pass
        self.close()

    def _pump_app(self, sock):
        splitter = FrameSplitter()
        try:
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                for frame in splitter.feed(data):
                    self._write_amp(frame)
                    try:
                        self._monitor_peer.sendall(frame)
                    except OSError:
                        pass
        except OSError:
            pass
        self._detach_app(sock)

    def _drain_monitor(self):
        # The monitor listener answers app commands with acks: drop them,
        # the real amp already acknowledged them to the app.
        try:
            while self._monitor_peer.recv(4096):
                pass
        except OSError:
            pass

    ##################
    # Helpers
    ##################

    def _write_amp(self, frame):
        with self._amp_write_lock:
            try:
                self.amp.sendall(frame)
            except OSError:
                self.close()

    def _detach_app(self, sock):
        with self._app_lock:
            if self._app is not sock:
                self._close_socket(sock)
                return
            self._app = None
        self._close_socket(sock)
        self.log('Spark app disconnected')

    @staticmethod
    def _close_socket(sock):
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass
