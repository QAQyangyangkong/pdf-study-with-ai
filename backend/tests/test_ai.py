import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from studynote.ai.generation import AIService, APIError, NoRedirect, exam_prompt, http_transport
from studynote.core.config import AIConfig
from studynote.database.repositories.workspace import Database
from tests.helpers import FakeKeys, fake_response


class AITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "study.sqlite3")
        self.calls = []
        def transport(url, key, payload):
            self.calls.append((url, key, payload))
            return fake_response()
        self.ai = AIService(self.db, FakeKeys(), transport)
        self.config = AIConfig()

    def tearDown(self):
        self.temp.cleanup()

    def test_cache_prevents_duplicate_network_call_and_charges_actual_usage(self):
        result = self.ai.generate(self.config, "根据教材生成笔记")
        repeated = self.ai.generate(self.config, "根据教材生成笔记")
        self.assertFalse(result.cached)
        self.assertTrue(repeated.cached)
        self.assertEqual(repeated.amount, 0)
        self.assertEqual(len(self.calls), 1)
        self.assertAlmostEqual(self.db.spent(), (40 * .3 + 60 * 1.2) / 1_000_000)
        self.assertEqual(self.calls[0][2]["thinking"], {"type": "disabled"})

    def test_cache_is_separated_by_model_endpoint_preference_and_length(self):
        base = self.ai.estimate(self.config, "偏好一").fingerprint
        fingerprints = [self.ai.estimate(config, prompt).fingerprint for config, prompt in (
            (replace(self.config, model="other"), "偏好一"),
            (replace(self.config, base_url="https://example.org/v1"), "偏好一"),
            (self.config, "偏好二"), (replace(self.config, max_output_tokens=3000), "偏好一"))]
        self.assertNotIn(base, fingerprints)
        self.assertEqual(len(set(fingerprints)), 4)

    def test_cached_response_does_not_require_secret_or_budget(self):
        self.ai.generate(self.config, "note")
        with patch.object(self.ai.key_store, "load", side_effect=ValueError("no key")):
            self.assertTrue(self.ai.generate(replace(self.config, daily_budget=.000001), "note").cached)

    def test_budget_stops_request_before_network(self):
        with self.assertRaisesRegex(ValueError, "预算"):
            self.ai.generate(replace(self.config, daily_budget=.000001), "note")
        self.assertFalse(self.calls)
        self.assertEqual(self.db.spent(), 0)

    def test_failed_request_keeps_reservation_and_is_not_cached(self):
        def fail(*args):
            raise APIError("timeout")
        self.ai.transport = fail
        estimate = self.ai.estimate(self.config, "note")
        with self.assertRaises(APIError):
            self.ai.generate(self.config, "note")
        self.assertAlmostEqual(self.db.spent(), estimate.amount)
        self.assertEqual(self.db.rows("SELECT status FROM usage")[0]["status"], "uncertain")
        self.assertIsNone(self.db.cached(estimate.fingerprint))

    def test_missing_usage_is_estimated_and_empty_or_truncated_response_not_cached(self):
        response = fake_response()
        response.pop("usage")
        self.ai.transport = lambda *args: response
        result = self.ai.generate(self.config, "missing usage")
        self.assertAlmostEqual(result.amount, self.ai.estimate(self.config, "missing usage changed").amount
                         - len(" changed") * self.config.input_price / 1_000_000)
        self.assertEqual(self.db.rows("SELECT status FROM usage")[0]["status"], "estimated")
        for finish, content in (("length", "partial"), ("stop", "")):
            response = {"choices": [{"message": {"content": content}, "finish_reason": finish}]}
            self.ai.transport = lambda *args: response
            with self.assertRaises(APIError):
                self.ai.generate(self.config, finish)

    def test_oversized_material_is_rejected_without_truncation(self):
        with self.assertRaisesRegex(ValueError, "16000"):
            self.ai.generate(self.config, "文" * 16001)
        self.assertFalse(self.calls)
        self.assertEqual(self.db.spent(), 0)

    def test_concurrent_reservations_do_not_exceed_budget(self):
        def reserve(_):
            try:
                self.db.reserve("model", .6, 1)
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=4) as executor:
            self.assertEqual(sum(executor.map(reserve, range(4))), 1)
        self.assertAlmostEqual(self.db.spent(), .6)

    def test_secondary_model_requires_setup_and_uses_separate_prices(self):
        with self.assertRaises(ValueError):
            self.config.selected(True)
        selected = replace(self.config, secondary_model="deepseek-v4-pro").selected(True)
        self.assertEqual(selected.model, "deepseek-v4-pro")
        self.assertEqual(selected.input_price, 1.32)
        self.assertEqual(selected.output_price, 3.96)

    def test_config_rejects_insecure_addresses_and_non_finite_prices(self):
        for url in ("http://example.org", "https://a:b@example.org", "https://example.org?key=x", "https://example.org#key"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                replace(self.config, base_url=url).validate()
        for value in (float("nan"), float("inf"), 0, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(self.config, input_price=value).validate()

    def test_provider_errors_are_sanitized_and_no_redirect_is_allowed(self):
        for code in (400, 401, 402, 403, 404, 429, 500, 302):
            error = HTTPError("https://example.org", code, "secret-api-key", None, None)
            with patch("studynote.ai.providers.openai.build_opener") as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(APIError) as caught:
                    http_transport("https://example.org", "test-key", {})
                self.assertNotIn("secret-api-key", str(caught.exception))
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, None, None, "https://other.org"))

    def test_network_error_does_not_repeat_call(self):
        with patch("studynote.ai.providers.openai.build_opener") as opener:
            opener.return_value.open.side_effect = URLError("Bearer secret")
            with self.assertRaises(APIError) as caught:
                http_transport("https://example.org", "secret", {})
            self.assertNotIn("Bearer secret", str(caught.exception))
            self.assertEqual(opener.return_value.open.call_count, 1)

    def test_exam_prompt_keeps_years_and_missing_year_visible(self):
        prompt = exam_prompt([({"title": "A", "year": "2024", "course": "电路"}, "题1"),
                              ({"title": "B", "year": "", "course": "电路"}, "题2")], "重点公式")
        self.assertIn("2024", prompt)
        self.assertIn("未提供", prompt)
        self.assertIn("题1", prompt)
        self.assertIn("题2", prompt)
