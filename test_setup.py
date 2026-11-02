"""Synthetic, offline checks for the terminal provider wizard."""
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from configure_providers import configure_session
from providers import list_providers


class SetupTests(unittest.TestCase):
    def test_four_connectors_and_session_only_key(self):
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(io.StringIO()) as log:
            self.assertEqual([p["id"] for p in list_providers()], ["demo", "openai", "anthropic", "gemini", "meta"])
            with patch("builtins.input", side_effect=["4", "example-muse,example-muse-alt", ""]), \
                    patch("getpass.getpass", return_value="synthetic-wizard-test"):
                configure_session()
            muse = list_providers()[-1]
            self.assertTrue(muse["configured"])
            self.assertEqual(muse["models"], ["example-muse", "example-muse-alt"])
            self.assertNotIn("synthetic-wizard-test", log.getvalue())

    def test_blank_key_does_not_enable_provider(self):
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(io.StringIO()), \
                patch("builtins.input", side_effect=["1", "fixture-model", ""]), \
                patch("getpass.getpass", return_value=""):
            configure_session()
            self.assertEqual(["demo"], [p["id"] for p in list_providers() if p["configured"]])
