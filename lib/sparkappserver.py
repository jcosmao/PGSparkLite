#####################################################################
# Spark App Server
#
# Lets the official Spark app (Android) connect to the Pi instead of the
# amp. The app talks classic Bluetooth SPP (RFCOMM channel 2), like
# PGSparkLite; each connection is handed to the SparkProxy, which relays
# it to the amp.
#
# BlueZ on LibreELEC has no SDP compat mode, so the serial port service
# is registered through the D-Bus ProfileManager1 API. Needs the system
# D-Bus socket (/run/dbus) and python3-dbus / python3-gi.
#
# Security: only paired + trusted devices may connect (BlueZ enforces it),
# then the optional allow list from AppProxySettings. The Pi is only
# discoverable, with a no-PIN pairing agent, during open_pairing().
#####################################################################

import socket
import threading
import time

SPP_UUID = '00001101-0000-1000-8000-00805f9b34fb'
PROFILE_PATH = '/pgsparklite/spark_app'
AGENT_PATH = '/pgsparklite/agent'
ADAPTER_PATH = '/org/bluez/hci0'
ADAPTER = 'org.bluez.Adapter1'
DEVICE = 'org.bluez.Device1'
PROPS = 'org.freedesktop.DBus.Properties'


def device_address(device_path):
    """/org/bluez/hci0/dev_FC_41_16_CE_C3_2C -> FC:41:16:CE:C3:2C"""
    name = str(device_path).rsplit('/', 1)[-1]
    if not name.startswith('dev_'):
        return ''
    return name[4:].replace('_', ':').upper()


class SparkAppServer:

    def __init__(self, on_connection, is_allowed=lambda address: True,
                 on_paired=lambda address: None, channel=2, name=None,
                 log=print):
        """on_connection(sock) is called for each accepted app connection,
        is_allowed(address) filters them, on_paired(address) is called for
        a device paired during open_pairing()."""
        self.on_connection = on_connection
        self.is_allowed = is_allowed
        self.on_paired = on_paired
        self.channel = channel
        self.name = name
        self.log = log
        self.ready = threading.Event()
        self.pairing_until = None
        self._thread = None
        self._loop = None
        self._glib = None
        self._dbus = None
        self._bus = None
        self._adapter = None
        self._agent_registered = False
        self._pairing_timer = None

    ##################
    # Public API (any thread)
    ##################

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_name(self, name):
        self.name = name
        if name:
            self._call(lambda: self._adapter.Set(ADAPTER, 'Alias', name))

    def adapter_name(self):
        return self._call(lambda: str(self._adapter.Get(ADAPTER, 'Alias')))

    def paired_devices(self):
        """[{'address', 'name', 'connected'}] for every paired device."""
        def collect():
            manager = self._dbus.Interface(
                self._bus.get_object('org.bluez', '/'),
                'org.freedesktop.DBus.ObjectManager')
            devices = []
            for path, ifaces in manager.GetManagedObjects().items():
                dev = ifaces.get(DEVICE)
                if not dev or not dev.get('Paired', False):
                    continue
                devices.append({
                    'address': str(dev.get('Address',
                                           device_address(path))).upper(),
                    'name': str(dev.get('Alias', dev.get('Name', ''))),
                    'connected': bool(dev.get('Connected', False)),
                })
            return sorted(devices, key=lambda d: d['name'].lower())
        return self._call(collect) or []

    def open_pairing(self, seconds=120):
        """Make the Pi discoverable and accept pairing without PIN."""
        def start():
            if not self._agent_registered:
                agents = self._dbus.Interface(
                    self._bus.get_object('org.bluez', '/org/bluez'),
                    'org.bluez.AgentManager1')
                agents.RegisterAgent(AGENT_PATH, 'NoInputNoOutput')
                agents.RequestDefaultAgent(AGENT_PATH)
                self._agent_registered = True
            self._adapter.Set(ADAPTER, 'Pairable', True)
            self._adapter.Set(ADAPTER, 'DiscoverableTimeout',
                              self._dbus.UInt32(seconds))
            self._adapter.Set(ADAPTER, 'Discoverable', True)
            if self._pairing_timer is not None:
                self._glib.source_remove(self._pairing_timer)
            self._pairing_timer = self._glib.timeout_add_seconds(
                seconds, self._close_pairing)
            self.log('Spark app server: pairing open for %ds' % seconds)
        self._call(start)
        self.pairing_until = time.time() + seconds

    def close_pairing(self):
        def stop():
            if self._pairing_timer is not None:
                self._glib.source_remove(self._pairing_timer)
            self._close_pairing()
        self._call(stop)

    @property
    def pairing_open(self):
        return (self.pairing_until is not None and
                time.time() < self.pairing_until)

    ##################
    # GLib loop thread
    ##################

    def _close_pairing(self):
        self._pairing_timer = None
        self.pairing_until = None
        try:
            self._adapter.Set(ADAPTER, 'Discoverable', False)
            if self._agent_registered:
                agents = self._dbus.Interface(
                    self._bus.get_object('org.bluez', '/org/bluez'),
                    'org.bluez.AgentManager1')
                agents.UnregisterAgent(AGENT_PATH)
                self._agent_registered = False
        except self._dbus.DBusException as e:
            self.log('Spark app server: closing pairing failed:', e)
        self.log('Spark app server: pairing closed')
        return False  # one-shot GLib timer

    def _call(self, fn, timeout=10):
        """Run fn in the GLib thread (the D-Bus objects live there)."""
        if not self.ready.wait(timeout):
            raise RuntimeError('Bluetooth (BlueZ) not available')
        if threading.current_thread() is self._thread:
            return fn()
        done = threading.Event()
        result = {}

        def run():
            try:
                result['value'] = fn()
            except Exception as e:  # handed back to the caller
                result['error'] = e
            done.set()
            return False

        self._glib.idle_add(run)
        if not done.wait(timeout):
            raise RuntimeError('Bluetooth (BlueZ) not responding')
        if 'error' in result:
            raise result['error']
        return result.get('value')

    def _run(self):
        try:
            import dbus
            import dbus.service
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib
        except ImportError as e:
            self.log('Spark app server disabled, missing module:', e)
            return
        self._dbus, self._glib = dbus, GLib
        server = self

        class Profile(dbus.service.Object):
            @dbus.service.method('org.bluez.Profile1',
                                 in_signature='oha{sv}', out_signature='')
            def NewConnection(self, device, fd, properties):
                sock = socket.socket(fileno=fd.take())
                # BlueZ hands over a non-blocking fd
                sock.setblocking(True)
                address = device_address(device)
                if not server.is_allowed(address):
                    server.log('Spark app connection rejected (not allowed):',
                               address)
                    sock.close()
                    return
                server.log('Spark app connection from', address)
                try:
                    server.on_connection(sock)
                except Exception as e:
                    server.log('Spark app connection refused:', e)
                    sock.close()

            @dbus.service.method('org.bluez.Profile1',
                                 in_signature='o', out_signature='')
            def RequestDisconnection(self, device):
                pass

            @dbus.service.method('org.bluez.Profile1',
                                 in_signature='', out_signature='')
            def Release(self):
                pass

        class Agent(dbus.service.Object):
            """No-PIN pairing, registered only while pairing is open."""

            def _paired(self, device):
                props = dbus.Interface(
                    server._bus.get_object('org.bluez', device), PROPS)
                props.Set(DEVICE, 'Trusted', True)
                address = device_address(device)
                server.log('Paired', address)
                server.on_paired(address)

            @dbus.service.method('org.bluez.Agent1', in_signature='os',
                                 out_signature='')
            def AuthorizeService(self, device, uuid):
                pass

            @dbus.service.method('org.bluez.Agent1', in_signature='ou',
                                 out_signature='')
            def RequestConfirmation(self, device, passkey):
                self._paired(device)

            @dbus.service.method('org.bluez.Agent1', in_signature='o',
                                 out_signature='')
            def RequestAuthorization(self, device):
                self._paired(device)

            @dbus.service.method('org.bluez.Agent1', in_signature='o',
                                 out_signature='s')
            def RequestPinCode(self, device):
                return '0000'

            @dbus.service.method('org.bluez.Agent1', in_signature='o',
                                 out_signature='u')
            def RequestPasskey(self, device):
                return dbus.UInt32(0)

            @dbus.service.method('org.bluez.Agent1', in_signature='',
                                 out_signature='')
            def Cancel(self):
                pass

            @dbus.service.method('org.bluez.Agent1', in_signature='',
                                 out_signature='')
            def Release(self):
                pass

        try:
            DBusGMainLoop(set_as_default=True)
            self._bus = dbus.SystemBus()
            self._adapter = dbus.Interface(
                self._bus.get_object('org.bluez', ADAPTER_PATH), PROPS)
            if self.name:
                self._adapter.Set(ADAPTER, 'Alias', self.name)
            # Hidden outside pairing: only already paired devices connect
            self._adapter.Set(ADAPTER, 'Discoverable', False)

            Agent(self._bus, AGENT_PATH)
            Profile(self._bus, PROFILE_PATH)
            profiles = dbus.Interface(
                self._bus.get_object('org.bluez', '/org/bluez'),
                'org.bluez.ProfileManager1')
            profiles.RegisterProfile(PROFILE_PATH, SPP_UUID, {
                'Name': 'Serial Port Service - Channel %d' % self.channel,
                'Role': 'server',
                'Channel': dbus.UInt16(self.channel),
                # Paired (encrypted link) and trusted devices only
                'RequireAuthentication': True,
                'RequireAuthorization': True,
                'AutoConnect': False,
            })
        except dbus.DBusException as e:
            self.log('Spark app server failed to start:', e)
            return

        alias = self._adapter.Get(ADAPTER, 'Alias')
        self.log('Spark app server ready: connect the app to "%s"' % alias)
        self._loop = GLib.MainLoop()
        self.ready.set()
        self._loop.run()
