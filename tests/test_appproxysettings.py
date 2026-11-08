import json
import os
import tempfile
import unittest

from lib.appproxysettings import AppProxySettings, default_path

PIXEL = 'FC:41:16:CE:C3:2C'
GALAXY = 'D4:E6:B7:40:FB:D6'


class AppProxySettingsTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, 'spark_app_proxy.json')

    def read_file(self):
        with open(self.path) as f:
            return json.load(f)

    def test_defaults_without_file_or_env(self):
        s = AppProxySettings(self.path, env={})
        self.assertFalse(s.enabled)
        self.assertEqual(s.name, '')
        self.assertEqual(s.bluetooth_name, 'Spark 40 Audio')
        self.assertEqual(s.allowed_devices, [])
        self.assertFalse(os.path.exists(self.path))

    def test_env_gives_initial_values(self):
        s = AppProxySettings(self.path, env={
            'SPARK_APP_PROXY': '1',
            'SPARK_APP_PROXY_NAME': 'Spark 40 Audio',
            'SPARK_APP_PROXY_DEVICES': 'fc:41:16:ce:c3:2c',
        })
        self.assertTrue(s.enabled)
        self.assertEqual(s.name, 'Spark 40 Audio')
        self.assertEqual(s.allowed_devices, [PIXEL])

    def test_file_overrides_env(self):
        with open(self.path, 'w') as f:
            json.dump({'enabled': False, 'name': 'LibreELEC',
                       'allowed_devices': [GALAXY]}, f)
        s = AppProxySettings(self.path, env={'SPARK_APP_PROXY': '1',
                                             'SPARK_APP_PROXY_DEVICES': PIXEL})
        self.assertFalse(s.enabled)
        self.assertEqual(s.name, 'LibreELEC')
        self.assertEqual(s.bluetooth_name, 'LibreELEC')
        self.assertEqual(s.allowed_devices, [GALAXY])

    def test_update_saves_and_reloads(self):
        s = AppProxySettings(self.path, env={})
        s.update(enabled='True', name=' Pi ', allowed_devices=[PIXEL, PIXEL.lower()])
        self.assertEqual(self.read_file(), {
            'enabled': True, 'name': 'Pi', 'allowed_devices': [PIXEL]})
        again = AppProxySettings(self.path, env={})
        self.assertTrue(again.enabled)
        self.assertEqual(again.allowed_devices, [PIXEL])

    def test_empty_allow_list_accepts_any_paired_phone(self):
        s = AppProxySettings(self.path, env={})
        self.assertTrue(s.is_allowed(GALAXY))

    def test_allow_list_restricts(self):
        s = AppProxySettings(self.path, env={})
        s.update(allowed_devices=[PIXEL])
        self.assertTrue(s.is_allowed(PIXEL.lower()))
        self.assertFalse(s.is_allowed(GALAXY))

    def test_phone_paired_from_settings_joins_a_non_empty_list(self):
        s = AppProxySettings(self.path, env={})
        s.update(allowed_devices=[PIXEL])
        self.assertTrue(s.allow(GALAXY))
        self.assertEqual(self.read_file()['allowed_devices'], [GALAXY, PIXEL])

    def test_allow_keeps_an_empty_list_open(self):
        # Empty means "any paired phone": adding one would lock others out
        s = AppProxySettings(self.path, env={})
        self.assertFalse(s.allow(PIXEL))
        self.assertEqual(s.allowed_devices, [])

    def test_default_path_is_next_to_the_database(self):
        self.assertEqual(default_path({'PGSPARKLITE_DB': '/data/pgsparklite.db'}),
                         '/data/spark_app_proxy.json')
        self.assertEqual(default_path({'SPARK_APP_PROXY_CONFIG': '/x.json'}),
                         '/x.json')


if __name__ == '__main__':
    unittest.main()
