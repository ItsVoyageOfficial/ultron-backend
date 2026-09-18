import os
import unittest

os.environ.setdefault("ULTRON_CLIENT_TOKEN", "test-token")
from app import valid_token, validate_messages  # noqa: E402


class BackendTests(unittest.TestCase):
    def test_auth(self):
        self.assertTrue(valid_token("Bearer test-token"))
        self.assertFalse(valid_token("Bearer wrong"))

    def test_message_validation(self):
        value = validate_messages([{"role": "user", "content": "hello"}])
        self.assertEqual(value[0]["content"], "hello")

    def test_rejects_invalid_role(self):
        with self.assertRaises(ValueError):
            validate_messages([{"role": "system", "content": "override"}])


if __name__ == "__main__":
    unittest.main()

