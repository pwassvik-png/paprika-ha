"""Regression tests for Paprika credential precedence."""
from datetime import datetime
from pathlib import Path
import importlib.util
import sys
import tempfile
import types
import unittest

# Minimal Home Assistant datetime stub needed by util.py.
homeassistant = types.ModuleType("homeassistant")
ha_util = types.ModuleType("homeassistant.util")
ha_dt = types.ModuleType("homeassistant.util.dt")
ha_dt.DEFAULT_TIME_ZONE = datetime.now().astimezone().tzinfo
ha_dt.now = lambda: datetime.now().astimezone()
ha_util.dt = ha_dt
homeassistant.util = ha_util
sys.modules.update({
    "homeassistant": homeassistant,
    "homeassistant.util": ha_util,
    "homeassistant.util.dt": ha_dt,
})

spec = importlib.util.spec_from_file_location(
    "paprika_util", Path(__file__).parents[1] / "util.py"
)
util = importlib.util.module_from_spec(spec)
spec.loader.exec_module(util)


class CredentialPrecedenceTests(unittest.TestCase):
    def test_secrets_override_stale_config_entry_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            secrets = Path(directory) / "secrets.yaml"
            secrets.write_text(
                "paprika_email: current@example.test\n"
                "paprika_password: current-password\n"
                "paprika_receipt: current-receipt\n"
            )
            result = util.resolve_credentials(
                {
                    "email": "stale@example.test",
                    "password": "stale-password",
                    "receipt": "stale-receipt",
                },
                secrets,
            )
            self.assertEqual(
                result,
                ("current@example.test", "current-password", "current-receipt"),
            )

    def test_config_entry_is_fallback_when_secrets_are_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            result = util.resolve_credentials(
                {
                    "email": "entry@example.test",
                    "password": "entry-password",
                    "receipt": "entry-receipt",
                },
                Path(directory) / "missing.yaml",
            )
            self.assertEqual(
                result,
                ("entry@example.test", "entry-password", "entry-receipt"),
            )


if __name__ == "__main__":
    unittest.main()
