import unittest
from unittest.mock import patch, MagicMock
import os
from twiliocaller import telephony

class TestTelephony(unittest.TestCase):
    @patch('twiliocaller.telephony.Client')
    def test_make_call_success(self, mock_client):
        os.environ['TWILIO_ACCOUNT_SID'] = 'test_sid'
        os.environ['TWILIO_AUTH_TOKEN'] = 'test_token'
        os.environ['TWILIO_PHONE_NUMBER'] = '+10000000000'
        mock_instance = mock_client.return_value
        mock_instance.calls.create.return_value.sid = 'CA1234567890'
        telephony.make_call('+12223334444', 'Hello!')
        mock_instance.calls.create.assert_called_once()

    def test_make_call_missing_env(self):
        for var in ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER']:
            if var in os.environ:
                del os.environ[var]
        with self.assertRaises(ValueError):
            telephony.make_call('+12223334444', 'Hello!')

if __name__ == '__main__':
    unittest.main()
