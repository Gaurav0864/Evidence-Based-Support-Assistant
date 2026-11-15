import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openai_client import (
    DEFAULT_MODEL,
    OpenAIRequestError,
    generate_answer,
    load_openai_config,
)


def api_response(answer, citation_ids):
    output_text = json.dumps(
        {"answer": answer, "citation_ids": citation_ids}
    )
    return {
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": output_text}],
            }
        ]
    }


class OpenAIClientTests(unittest.TestCase):
    def test_reads_local_key_but_process_environment_takes_precedence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "OPENAI_API_KEY='local-key'\nOPENAI_MODEL=gpt-from-file\n",
                encoding="utf-8",
            )

            config = load_openai_config(
                env_path, environ={"OPENAI_MODEL": "gpt-from-environment"}
            )

        self.assertEqual(config["api_key"], "local-key")
        self.assertEqual(config["model"], "gpt-from-environment")

    def test_sends_question_and_retrieved_excerpts_and_accepts_valid_citation(self):
        sources = [
            {
                "id": "RUNBOOK-API-429",
                "title": "API rate limits",
                "section": "Retry guidance",
                "excerpt": "Wait for the Retry-After interval before retrying.",
            }
        ]
        response_body = api_response(
            "Wait for the documented Retry-After interval before retrying.",
            ["RUNBOOK-API-429"],
        )
        with patch(
            "openai_client.urlopen",
            return_value=io.BytesIO(json.dumps(response_body).encode("utf-8")),
        ) as urlopen_mock:
            result = generate_answer(
                "How should I retry this 429?", sources, {"api_key": "test-key", "model": "gpt-test"}
            )

        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        user_input = json.loads(payload["input"][1]["content"])
        self.assertEqual(payload["model"], "gpt-test")
        self.assertEqual(user_input["question"], "How should I retry this 429?")
        self.assertEqual(
            user_input["evidence"][0]["excerpt"], sources[0]["excerpt"]
        )
        self.assertNotIn("api_key", payload)
        self.assertEqual(result["citation_ids"], ["RUNBOOK-API-429"])
        self.assertFalse(result["abstained"])

    def test_rejects_citation_outside_retrieved_sources(self):
        response_body = api_response("Unsupported draft.", ["OTHER-GUIDE"])
        with patch(
            "openai_client.urlopen",
            return_value=io.BytesIO(json.dumps(response_body).encode("utf-8")),
        ):
            with self.assertRaisesRegex(OpenAIRequestError, "not provided"):
                generate_answer(
                    "Question",
                    [{"id": "GUIDE-A", "excerpt": "A verified excerpt."}],
                    {"api_key": "test-key", "model": DEFAULT_MODEL},
                )

    def test_openai_can_explicitly_abstain_without_citations(self):
        response_body = api_response(
            "I can't confirm that from the available guides.", []
        )
        with patch(
            "openai_client.urlopen",
            return_value=io.BytesIO(json.dumps(response_body).encode("utf-8")),
        ):
            result = generate_answer(
                "Question",
                [{"id": "GUIDE-A", "excerpt": "A verified excerpt."}],
                {"api_key": "test-key", "model": DEFAULT_MODEL},
            )

        self.assertTrue(result["abstained"])
        self.assertEqual(result["citation_ids"], [])


if __name__ == "__main__":
    unittest.main()
