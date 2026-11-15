import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import create_server
from knowledge import (
    ABSTAIN_ANSWER,
    KnowledgeDataError,
    answer_question,
    load_examples,
    load_sources,
)


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


if __name__ == "__main__":
    unittest.main()
