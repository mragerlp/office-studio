"""Exercise the provider wire formats with synthetic responses and zero network access."""
import os
import unittest
from unittest.mock import patch

import providers


class DraftProvidersTest(unittest.TestCase):
    def test_demo_and_unconfigured_choices_make_no_requests(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(providers, "_post") as post:
            options = providers.list_providers()
            self.assertEqual(["demo"], [o["id"] for o in options if o["configured"]])
            self.assertIn("Simulated draft", providers.generate_draft("demo", "Review", "Sample"))
            for provider in ("openai", "anthropic", "gemini", "unknown"):
                with self.assertRaises(providers.ProviderError):
                    providers.generate_draft(provider, "Role", "Sample")
            post.assert_not_called()

    def test_provider_requests_and_text_extraction(self):
        examples = {
            "openai": ("api.openai.com", "/v1/responses", {
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "Draft"}]}],
            }),
            "anthropic": ("api.anthropic.com", "/v1/messages", {
                "content": [{"type": "text", "text": "Draft"}],
            }),
            "gemini": ("generativelanguage.googleapis.com", "/v1beta/models/example-model:generateContent", {
                "candidates": [{"content": {"parts": [{"thought": True, "text": "omitted"}, {"text": "Draft"}]}}],
            }),
        }
        for provider, (host, path, response) in examples.items():
            _, key_var, model_var = providers.PROVIDERS[provider]
            with self.subTest(provider=provider), patch.dict(os.environ, {
                key_var: "test-fixture-value", model_var: "example-model",
            }, clear=True), patch.object(providers, "_post", return_value=response) as post:
                self.assertEqual("Draft", providers.generate_draft(provider, "Sample lane", "Sample brief"))
                target, route, headers, payload = post.call_args.args
                self.assertEqual((host, path), (target, route))
                self.assertIn("test-fixture-value", str(headers))
                self.assertNotIn("test-fixture-value", str(payload))
                self.assertIn("Sample brief", str(payload))
                self.assertIn("Sample lane", str(payload))
                post.return_value = {}
                with self.assertRaises(providers.ProviderError):
                    providers.generate_draft(provider, "Role", "Sample")

    def test_allowlisted_models_are_visible_without_credentials(self):
        with patch.dict(os.environ, {"OFFICE_OPENAI_MODEL": "fixture-default",
                                   "OFFICE_OPENAI_MODELS": " fixture-alt,fixture-default,fixture-alt,https://example.invalid/model "}, clear=True):
            choice = next(p for p in providers.list_providers() if p["id"] == "openai")
            self.assertEqual(choice["models"], ["fixture-default", "fixture-alt"])
            self.assertFalse(choice["configured"])
            self.assertEqual(providers.resolve_route("openai", "fixture-alt"), {"provider": "openai", "model": "fixture-alt"})
            with self.assertRaises(providers.ProviderError), patch.object(providers, "_post") as post:
                providers.generate_draft("openai", "Role", "Brief", model="fixture-alt")
            post.assert_not_called()

    def test_model_overrides_never_change_provider_hosts(self):
        fixtures = {"openai": {"output": [{"type": "message", "content": [{"type": "output_text", "text": "Draft"}]}]},
                    "anthropic": {"content": [{"type": "text", "text": "Draft"}]},
                    "gemini": {"candidates": [{"content": {"parts": [{"text": "Draft"}]}}]}}
        for provider, response in fixtures.items():
            _, secret, variable = providers.PROVIDERS[provider]
            with self.subTest(provider=provider), patch.dict(os.environ, {
                    secret: "test-fixture-value", variable: "fixture-default", variable + "S": "fixture-alt"}, clear=True), \
                    patch.object(providers, "_post", return_value=response) as post:
                self.assertEqual(providers.generate_draft(provider, "Role", "Brief", model="fixture-alt"), "Draft")
                host, path, headers, payload = post.call_args.args
                if provider == "gemini":
                    self.assertEqual(host, "generativelanguage.googleapis.com")
                    self.assertEqual(path, "/v1beta/models/fixture-alt:generateContent")
                else:
                    self.assertEqual(host, {"openai": "api.openai.com", "anthropic": "api.anthropic.com"}[provider])
                    self.assertEqual(payload["model"], "fixture-alt")
                post.reset_mock()
                for invalid in ("unlisted-fixture", "https://example.invalid/model", "../../private", {}, 1):
                    with self.assertRaises(providers.ProviderError):
                        providers.generate_draft(provider, "Role", "Brief", model=invalid)
                post.assert_not_called()

    def test_demo_and_allowlist_only_default(self):
        with patch.dict(os.environ, {"OFFICE_GEMINI_MODELS": "fixture-first,fixture-second"}, clear=True):
            self.assertEqual(providers.resolve_route("gemini"), {"provider": "gemini", "model": "fixture-first"})
            self.assertEqual(providers.resolve_route("demo"), {"provider": "demo", "model": ""})
            self.assertEqual(providers.list_providers()[0]["models"], [])
            for source, model in (("unknown", ""), ("demo", "fixture-model"), ([], "")):
                with self.assertRaises(providers.ProviderError):
                    providers.resolve_route(source, model)


if __name__ == "__main__":
    unittest.main()
