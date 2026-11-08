import unittest

from lib.sparkappserver import device_address


class DeviceAddressTest(unittest.TestCase):

    def test_device_address_from_bluez_path(self):
        self.assertEqual(device_address('/org/bluez/hci0/dev_FC_41_16_CE_C3_2C'),
                         'FC:41:16:CE:C3:2C')

    def test_non_device_path(self):
        self.assertEqual(device_address('/org/bluez/hci0'), '')


if __name__ == '__main__':
    unittest.main()
