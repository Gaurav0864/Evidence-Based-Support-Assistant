import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from app import create_server
from knowledge import (
    ABSTAIN_ANSWER,
    KnowledgeDataError,
    answer_question,
    load_examples,
    load_sources,
)
from openai_client import OpenAIRequestError


class EvidenceAssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = load_sources()
        cls.examples = load_examples()

    def test_examples_are_grounded_in_expected_sources_or_abstain(self):
        source_ids = {source["id"] for source in self.sources}
        for example in self.examples:
            with self.subTest(question=example["question"]):
                result, error = answer_question(self.sources, example["question"])
                self.assertIsNone(error)
                returned_ids = {source["id"] for source in result["sources"]}
                if example["expected_abstain"]:
                    self.assertTrue(result["abstained"])
                    self.assertEqual(result["answer"], ABSTAIN_ANSWER)
                    self.assertEqual(returned_ids, set())
                else:
                    self.assertFalse(result["abstained"])
                    self.assertTrue(set(example["expected_source_ids"]) <= source_ids)
                    self.assertEqual(returned_ids, set(example["expected_source_ids"]))
                    cited_text = " ".join(
                        source["excerpt"].lower() for source in result["sources"]
                    )
                    for phrase in example["must_include"]:
                        self.assertIn(phrase.lower(), cited_text)

    def test_answer_quotes_only_source_text(self):
        result, error = answer_question(
            self.sources, "What should I check for an HTTP 401 sign-in failure?"
        )

        self.assertIsNone(error)
        source_text = next(
            source["text"] for source in self.sources if source["id"] == "GUIDE-AUTH-01"
        )
        self.assertIn(result["sources"][0]["excerpt"], source_text)
        self.assertEqual(result["sources"][0]["id"], "GUIDE-AUTH-01")

    def test_empty_and_overlong_questions_return_clear_validation_errors(self):
        self.assertEqual(
            answer_question(self.sources, " \n")[1],
            "Enter a question before searching the guides.",
        )
        _, error = answer_question(self.sources, "x" * 501)
        self.assertIn("500 characters or fewer", error)

    def test_source_loader_rejects_duplicate_ids(self):
        duplicate = [
            {
                "id": "GUIDE-X",
                "title": "First",
                "section": "One",
                "text": "First guidance.",
            },
            {
                "id": "GUIDE-X",
                "title": "Second",
                "section": "Two",
                "text": "Second guidance.",
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sources.json"
            path.write_text(json.dumps(duplicate), encoding="utf-8")
            with self.assertRaisesRegex(KnowledgeDataError, "Duplicate source ID"):
                load_sources(path)

    def test_http_page_sources_question_and_bad_input(self):
        server = create_server(self.sources, self.examples, port=0)
        thread = Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        base_url = "http://127.0.0.1:{}".format(server.server_address[1])

        with urlopen(base_url + "/") as response:
            page = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
        self.assertIn("Helpful answers should show their evidence.", page)

        with urlopen(base_url + "/api/sources") as response:
            sources = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
        self.assertEqual(len(sources), 4)

        request = Request(
            base_url + "/api/ask",
            data=json.dumps(
                {"question": "What is the safe retry guidance for HTTP 429 API requests?"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
        self.assertEqual(result["sources"][0]["id"], "RUNBOOK-API-429")
        self.assertIn("Retry-After", result["sources"][0]["excerpt"])

        invalid_request = Request(
            base_url + "/api/ask",
            data=b'{"question":""}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(invalid_request)
        self.assertEqual(error.exception.code, 400)
        error_body = json.loads(error.exception.read().decode("utf-8"))
        self.assertIn("Enter a question", error_body["error"])

        with self.assertRaises(HTTPError) as error:
            urlopen(base_url + "/missing")
        self.assertEqual(error.exception.code, 404)

    def test_openai_route_exposes_status_but_not_key_and_uses_retrieved_sources(self):
        ai_config = {"api_key": "test-secret", "model": "gpt-test"}
        server = create_server(
            self.sources, self.examples, port=0, ai_config=ai_config
        )
        thread = Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        base_url = "http://127.0.0.1:{}".format(server.server_address[1])

        with urlopen(base_url + "/api/status") as response:
            status = json.loads(response.read().decode("utf-8"))
        self.assertTrue(status["ai_enabled"])
        self.assertEqual(status["model"], "gpt-test")
        self.assertNotIn("test-secret", json.dumps(status))

        request = Request(
            base_url + "/api/ask",
            data=json.dumps(
                {"question": "What is the safe retry guidance for HTTP 429 API requests?"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with patch(
            "app.generate_answer",
            return_value={
                "answer": "Follow the documented retry interval.",
                "citation_ids": ["RUNBOOK-API-429"],
                "abstained": False,
            },
        ) as generate_mock:
            with urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))

        self.assertTrue(result["ai_used"])
        self.assertEqual(result["mode"], "openai")
        self.assertEqual(result["model"], "gpt-test")
        self.assertEqual(
            [source["id"] for source in result["sources"]], ["RUNBOOK-API-429"]
        )
        self.assertEqual(generate_mock.call_args.args[0], self.examples[2]["question"])

        unsupported_request = Request(
            base_url + "/api/ask",
            data=json.dumps(
                {"question": "Does the product support voice cloning in the mobile app?"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with patch("app.generate_answer") as generate_mock:
            with urlopen(unsupported_request) as response:
                unsupported = json.loads(response.read().decode("utf-8"))
        self.assertTrue(unsupported["abstained"])
        generate_mock.assert_not_called()

    def test_openai_failure_is_reported_instead_of_silently_using_local_answer(self):
        server = create_server(
            self.sources,
            self.examples,
            port=0,
            ai_config={"api_key": "test-secret", "model": "gpt-test"},
        )
        thread = Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        request = Request(
            "http://127.0.0.1:{}/api/ask".format(server.server_address[1]),
            data=json.dumps(
                {"question": "What is the safe retry guidance for HTTP 429 API requests?"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with patch(
            "app.generate_answer", side_effect=OpenAIRequestError("Provider unavailable.")
        ):
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
        self.assertEqual(error.exception.code, 502)
        error_body = json.loads(error.exception.read().decode("utf-8"))
        self.assertEqual(error_body["error"], "Provider unavailable.")


if __name__ == "__main__":
    unittest.main()
