import unittest
from unittest.mock import patch

from device_client import DeviceClient


class FrameAfterTest(unittest.TestCase):
    def test_only_post_input_frame_can_already_be_in_the_receipt(self):
        client = DeviceClient.__new__(DeviceClient)
        client.hello = {"features": ["frame_after_ns"]}
        receipt = {"seq": 11, "input_ns": 100}
        frame = {"seq": 11, "image_ns": 110, "timestamp_comparable": True}

        with patch.object(client, "frame", return_value=(frame, b"")) as request:
            self.assertEqual(frame, client.frame_after(receipt)[0])
            request.assert_called_once_with(min_seq=0, after_ns=100)

        with patch.object(client, "frame", return_value=(frame, b"")) as request:
            self.assertEqual(frame, client.frame_after(receipt, min_seq=11)[0])
            request.assert_called_once_with(min_seq=11, after_ns=100)

    def test_rejects_a_frame_at_the_input_boundary(self):
        client = DeviceClient.__new__(DeviceClient)
        client.hello = {"features": ["frame_after_ns"]}
        frame = {"seq": 11, "image_ns": 100, "timestamp_comparable": True}
        with patch.object(client, "frame", return_value=(frame, b"")):
            with self.assertRaises(ConnectionError):
                client.frame_after({"seq": 10, "input_ns": 100})


if __name__ == "__main__":
    unittest.main()
