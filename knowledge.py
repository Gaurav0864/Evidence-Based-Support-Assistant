"""Load fictional support guides and return answers backed by quoted evidence."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCES_FILE = ROOT / "data" / "sources.json"
EXAMPLES_FILE = ROOT / "data" / "test_questions.json"
ABSTAIN_ANSWER = "I can't confirm that from the available guides."
MAX_QUESTION_LENGTH = 500
STOP_WORDS = {
    "a", "about", "an", "and", "are", "can", "do", "does", "for", "from",
    "check", "checks", "error", "errors", "failure", "failures", "how", "http",
    "i", "in", "is", "it", "me", "of", "on", "or", "request", "requests",
    "should", "the", "this", "to", "what", "when", "where", "which", "who",
    "why", "with", "would", "you", "your",
}


class KnowledgeDataError(ValueError):
    """Raised when guide or test-question data is missing or malformed."""


def _read_json(path, expected_type, label):
    try:
        with path.open(encoding="utf-8") as data_file:
            data = json.load(data_file)
    except (OSError, json.JSONDecodeError) as error:
        raise KnowledgeDataError("Could not read {}: {}".format(label, error)) from error
    if not isinstance(data, expected_type):
        raise KnowledgeDataError("{} must contain {}.".format(label, expected_type.__name__))
    return data


def load_sources(path=SOURCES_FILE):
    """Read guide records and validate their fields and unique identifiers."""
    records = _read_json(Path(path), list, "source file")
    required_fields = ("id", "title", "section", "text")
    sources = []
    seen_ids = set()
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise KnowledgeDataError("Source {} must be an object.".format(index))
        invalid_fields = [
            field
            for field in required_fields
            if not isinstance(record.get(field), str) or not record[field].strip()
        ]
        if invalid_fields:
            raise KnowledgeDataError(
                "Source {} has missing or invalid fields: {}.".format(
                    index, ", ".join(invalid_fields)
                )
            )
        source_id = record["id"].strip()
        if source_id in seen_ids:
            raise KnowledgeDataError("Duplicate source ID: {}.".format(source_id))
        seen_ids.add(source_id)
        sources.append({field: record[field].strip() for field in required_fields})
    if not sources:
        raise KnowledgeDataError("Source file must include at least one guide.")
    return sources


def load_examples(path=EXAMPLES_FILE):
    """Read the shared examples used by the UI and the grounding tests."""
    examples = _read_json(Path(path), list, "test-question file")
    required_fields = ("question", "expected_source_ids", "must_include", "expected_abstain")
    for index, example in enumerate(examples, start=1):
        if not isinstance(example, dict):
            raise KnowledgeDataError("Example {} must be an object.".format(index))
        if not isinstance(example.get("question"), str) or not example["question"].strip():
            raise KnowledgeDataError("Example {} needs a question.".format(index))
        if not isinstance(example.get("expected_source_ids"), list):
            raise KnowledgeDataError(
                "Example {} needs a list of expected source IDs.".format(index)
            )
        if not isinstance(example.get("must_include"), list):
            raise KnowledgeDataError(
                "Example {} needs a list of expected answer phrases.".format(index)
            )
        if not isinstance(example.get("expected_abstain"), bool):
            raise KnowledgeDataError(
                "Example {} needs a true/false expected_abstain value.".format(index)
            )
        if example["expected_abstain"] and example["expected_source_ids"]:
            raise KnowledgeDataError(
                "Abstaining example {} must not expect cited sources.".format(index)
            )
        for field in ("expected_source_ids", "must_include"):
            if not all(isinstance(value, str) for value in example[field]):
                raise KnowledgeDataError(
                    "Example {} contains invalid {} values.".format(index, field)
                )
    return examples


def _terms(text):
    return {
        term.lower()
        for term in re.findall(r"[a-zA-Z0-9]+", text)
        if term.lower() not in STOP_WORDS and len(term) > 1
    }


def _sentences(text):
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def answer_question(sources, question):
    """Return exact supporting guide sentences or a clear abstention."""
    if not isinstance(question, str) or not question.strip():
        return None, "Enter a question before searching the guides."
    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        return None, "Question must be {} characters or fewer.".format(MAX_QUESTION_LENGTH)

    question_terms = _terms(question)
    matches = []
    for source in sources:
        scored_sentences = []
        matched_terms = set()
        for sentence in _sentences(source["text"]):
            overlap = question_terms & _terms(sentence)
            if overlap:
                matched_terms.update(overlap)
                scored_sentences.append((len(overlap), sentence))
        if len(matched_terms) >= 2:
            matches.append((len(matched_terms), source, scored_sentences[:3]))

    matches.sort(key=lambda item: (-item[0], item[1]["id"]))
    if not matches:
        return {
            "answer": ABSTAIN_ANSWER,
            "abstained": True,
            "sources": [],
            "ai_used": False,
            "mode": "evidence",
        }, None

    citations = []
    for _, source, excerpts in matches[:2]:
        citations.append(
            {
                "id": source["id"],
                "title": source["title"],
                "section": source["section"],
                "excerpt": " ".join(sentence for _, sentence in excerpts),
            }
        )
    return {
        "answer": "Evidence found in the cited local guide excerpts.",
        "abstained": False,
        "sources": citations,
        "ai_used": False,
        "mode": "evidence",
    }, None
