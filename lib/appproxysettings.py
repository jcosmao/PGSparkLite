#####################################################################
# Spark app proxy settings
#
# Stored as JSON next to the database (/data/spark_app_proxy.json in
# Docker), editable by hand or from the Settings page:
#
#   {
#     "enabled": true,
#     "name": "",            # Bluetooth name, "" = "Spark 40 Audio"
#     "allowed_devices": ["FC:41:16:CE:C3:2C"]   # [] = any paired phone
#   }
#
# When the file does not exist yet, the SPARK_APP_PROXY* environment
# variables (or config.py) give the initial values.
#####################################################################

import json
import os
import threading

FILE_NAME = 'spark_app_proxy.json'
# The Android Spark app only offers devices with the amp's Bluetooth name
DEFAULT_NAME = 'Spark 40 Audio'


def _flag(value, default):
    if value is None or value == '':
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def normalise_address(address):
    return str(address).strip().upper()


def parse_addresses(value):
    """'fc:41:...; AA:BB:...' or a list -> sorted unique upper-case list"""
    if not value:
        return []
    if isinstance(value, str):
        value = value.replace(';', ',').split(',')
    return sorted({normalise_address(a) for a in value if str(a).strip()})


def default_path(env=os.environ):
    if env.get('SPARK_APP_PROXY_CONFIG'):
        return env['SPARK_APP_PROXY_CONFIG']
    db = env.get('PGSPARKLITE_DB', 'pgsparklite.db')
    return os.path.join(os.path.dirname(os.path.abspath(db)), FILE_NAME)


class AppProxySettings:

    def __init__(self, path=None, env=os.environ, config=None):
        self.path = path or default_path(env)
        self._lock = threading.Lock()
        self.enabled = _flag(env.get('SPARK_APP_PROXY'),
                             getattr(config, 'app_proxy', False))
        self.name = (env.get('SPARK_APP_PROXY_NAME') or
                     getattr(config, 'app_proxy_name', None) or '')
        self.allowed_devices = parse_addresses(
            env.get('SPARK_APP_PROXY_DEVICES') or
            getattr(config, 'app_proxy_devices', None))
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path) as f:
            data = json.load(f)
        self.enabled = _flag(data.get('enabled'), self.enabled)
        self.name = str(data.get('name') or '')
        self.allowed_devices = parse_addresses(data.get('allowed_devices'))

    def as_dict(self):
        return {
            'enabled': self.enabled,
            'name': self.name,
            'allowed_devices': list(self.allowed_devices),
        }

    def save(self):
        with self._lock:
            tmp = self.path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(self.as_dict(), f, indent=2)
                f.write('\n')
            os.replace(tmp, self.path)

    def update(self, enabled=None, name=None, allowed_devices=None):
        if enabled is not None:
            self.enabled = _flag(enabled, self.enabled)
        if name is not None:
            self.name = str(name).strip()
        if allowed_devices is not None:
            self.allowed_devices = parse_addresses(allowed_devices)
        self.save()

    def allow(self, address):
        """Add a phone paired from the Settings page to a non empty list."""
        address = normalise_address(address)
        if self.allowed_devices and address not in self.allowed_devices:
            self.allowed_devices = sorted(self.allowed_devices + [address])
            self.save()
            return True
        return False

    @property
    def bluetooth_name(self):
        """Name the Pi must advertise for the Spark app to find it."""
        return self.name or DEFAULT_NAME

    def is_allowed(self, address):
        return (not self.allowed_devices or
                normalise_address(address) in self.allowed_devices)
