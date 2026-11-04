"""Offline regression cases for reserved drafting and incomplete provider replies."""
import hashlib
import json
import os
import threading
import unittest
import uuid
from unittest.mock import patch

import providers
import test_office as fixtures


class DraftSafetyTests(unittest.TestCase):
    setUp = fixtures.FileHandoffTests.setUp
    start_server = fixtures.FileHandoffTests.start_server
    stop_server = fixtures.FileHandoffTests.stop_server
    request = fixtures.FileHandoffTests.request
    create = fixtures.FileHandoffTests.create
    restaurant = fixtures.FileHandoffTests.restaurant
    upload = fixtures.FileHandoffTests.upload
    job = fixtures.FileHandoffTests.job

    def test_last_draft_slot_is_reserved_before_provider_dispatch(self):
        office = self.a.rsplit("/", 1)[-1]
        with self.httpd.store.connection(write=True) as db:
            item = self.httpd.store.get(db, office)
            item["drafts"] = [{"id": uuid.uuid4().hex, "status": "approved"} for _ in range(99)]
            self.httpd.store.save(db, item)
        entered, release, replies = threading.Event(), threading.Event(), []

        def slow(*args, **kwargs):
            if entered.is_set():
                return "Second request wrongly dispatched without a slot."
            entered.set()
            if not release.wait(4):
                raise RuntimeError("Test provider was not released")
            return "A complete fictional reply."

        first = {"agent": "CRIMSON", "brief": "First request", "provider": "demo", "requestId": uuid.uuid4().hex}
        second = {**first, "brief": "Second request", "requestId": uuid.uuid4().hex}
        with patch.object(providers, "generate_draft", side_effect=slow) as generate:
            thread = threading.Thread(target=lambda: replies.append(self.request("POST", self.a + "/drafts", first)))
            thread.start()
            try:
                self.assertTrue(entered.wait(2))
                status, rejected = self.request("POST", self.a + "/drafts", second)
                self.assertEqual(status, 409, rejected)
                self.assertIn("limit", rejected["error"].lower())
                self.assertEqual(generate.call_count, 1, "The unavailable slot must be rejected before provider dispatch")
            finally:
                release.set()
                thread.join(5)
        self.assertEqual(replies[0][0], 201, replies)
        self.assertEqual(len(self.request("GET", self.a)[1]["drafts"]), 100)

    def test_interrupted_demo_attempt_can_resume_after_restart(self):
        source = self.upload(self.a, "A fictional inquiry.")
        job = self.job(source)
        # Reproduce an interrupted process after its durable reservation but before generation.
        with self.httpd.store.connection(write=True) as db:
            db.execute("INSERT INTO draft_requests(office,id,fingerprint,state) VALUES (?,?,?,'started')",
                       (self.a.rsplit("/", 1)[-1], job["requestId"],
                        hashlib.sha256(json.dumps(job, sort_keys=True).encode("ascii")).hexdigest()))
        self.stop_server()
        self.start_server()
        with patch.object(providers, "_post", side_effect=AssertionError("No external provider allowed")):
            status, item = self.request("POST", self.a + "/drafts", job)
            self.assertEqual(status, 201, item)
            draft, = item["drafts"]
            self.assertEqual((draft["requestId"], draft["source"], draft["provider"]),
                             (job["requestId"], source, "demo"))
            self.assertEqual(self.request("POST", self.a + "/drafts", job), (200, item))

    def test_interrupted_live_attempt_is_not_automatically_redispatched(self):
        source = self.upload(self.a, "A fictional inquiry.")
        job = self.job(source, provider="openai", model="fixture", shareFile=True)
        with self.httpd.store.connection(write=True) as db:
            db.execute("INSERT INTO draft_requests(office,id,fingerprint,state) VALUES (?,?,?,'started')",
                       (self.a.rsplit("/", 1)[-1], job["requestId"],
                        hashlib.sha256(json.dumps(job, sort_keys=True).encode("ascii")).hexdigest()))
        self.stop_server()
        self.start_server()
        with patch.object(providers, "generate_draft", side_effect=AssertionError("Do not redispatch uncertain billing")):
            status, response = self.request("POST", self.a + "/drafts", job)
            self.assertEqual((status, response.get("code")), (409, "draft_attempt_started"))
            self.assertEqual(self.request("GET", self.a)[1]["drafts"], [])

    def test_brief_only_request_token_deduplicates_after_restart(self):
        job = {"agent": "CRIMSON", "brief": "Fictional brief only", "provider": "demo", "requestId": uuid.uuid4().hex}
        status, item = self.request("POST", self.a + "/drafts", job)
        self.assertEqual(status, 201, item)
        self.stop_server()
        self.start_server()
        with patch.object(providers, "generate_draft", side_effect=AssertionError("Must return the saved result")):
            self.assertEqual(self.request("POST", self.a + "/drafts", job), (200, item))
            self.assertEqual(len(item["drafts"]), 1)

    def test_incomplete_live_reply_leaves_no_saved_or_downloadable_draft(self):
        job = {"agent": "CRIMSON", "brief": "Fictional brief", "provider": "openai",
               "model": "fixture", "requestId": uuid.uuid4().hex}
        response = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": "Partial reply"}]}]}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic", "OFFICE_OPENAI_MODEL": "fixture"}, clear=True), \
             patch.object(providers, "_post", return_value=response) as call:
            status, error = self.request("POST", self.a + "/drafts", job)
            self.assertEqual((status, error.get("code")), (502, "draft_attempt_failed"))
            self.assertIn("did not complete", error["error"])
            self.assertEqual(self.request("GET", self.a)[1]["drafts"], [])
            self.assertEqual(self.request("POST", self.a + "/drafts", job)[0], 409)
            self.assertEqual(call.call_count, 1)

    def test_inflight_capacity_and_request_id_are_scoped_to_each_office(self):
        entered, release, replies = threading.Event(), threading.Event(), []
        job = {"agent": "CRIMSON", "brief": "Fictional request", "provider": "demo", "requestId": uuid.uuid4().hex}

        def slow_first(*args, **kwargs):
            if entered.is_set():
                return "Office two reply"
            entered.set()
            if not release.wait(4):
                raise RuntimeError("Test provider was not released")
            return "Office one reply"

        with patch.object(providers, "generate_draft", side_effect=slow_first):
            thread = threading.Thread(target=lambda: replies.append(self.request("POST", self.a + "/drafts", job)))
            thread.start()
            try:
                self.assertTrue(entered.wait(2))
                status, second = self.request("POST", self.b + "/drafts", job)
                self.assertEqual(status, 201, second)
                self.assertEqual(second["drafts"][0]["text"], "Office two reply")
                self.assertEqual(self.request("GET", self.a)[1]["drafts"], [])
            finally:
                release.set()
                thread.join(5)
        self.assertEqual(replies[0][0], 201)
        self.assertEqual(replies[0][1]["drafts"][0]["text"], "Office one reply")


class ProviderCompletionTests(unittest.TestCase):
    def test_incomplete_or_blocked_text_is_never_an_approvable_draft(self):
        cases = [
            ("openai", {"status": "incomplete", "output": [{"type": "message", "content": [{"type": "output_text", "text": "Partial"}]}]}),
            ("anthropic", {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "Partial"}]}),
            ("gemini", {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "Partial"}]}}]}),
            ("meta", {"choices": [{"finish_reason": "length", "message": {"content": "Partial"}}]}),
        ]
        for provider, response in cases:
            # Missing finish metadata must not turn the same partial text into success.
            missing = json.loads(json.dumps(response))
            if provider == "openai":
                del missing["status"]
            elif provider == "anthropic":
                del missing["stop_reason"]
            elif provider == "gemini":
                del missing["candidates"][0]["finishReason"]
            else:
                del missing["choices"][0]["finish_reason"]
            for variant in (response, missing):
                with self.subTest(provider=provider, metadata=variant != missing):
                    _, key_var, model_var = providers.PROVIDERS[provider]
                    with patch.dict(os.environ, {key_var: "synthetic", model_var: "fixture"}, clear=True), \
                         patch.object(providers, "_post", return_value=variant):
                        with self.assertRaisesRegex(providers.ProviderError, "complete"):
                            providers.generate_draft(provider, "Fictional instruction", "Fictional brief")


if __name__ == "__main__":
    unittest.main()
