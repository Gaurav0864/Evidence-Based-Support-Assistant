"""Local evidence-based support assistant using fictional product guidance."""

import argparse
import json
import sys
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from knowledge import answer_question, load_examples, load_sources


ROOT = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
MAX_REQUEST_BYTES = 4096
STATIC_FILES = {
    "/static/style.css": ("static/style.css", "text/css; charset=utf-8"),
    "/static/app.js": ("static/app.js", "text/javascript; charset=utf-8"),
}


class AssistantRequestHandler(BaseHTTPRequestHandler):
    """Serve the local page and the evidence-grounded question API."""

    def __init__(self, *args, sources, examples, **kwargs):
        self.sources = sources
        self.examples = examples
        super().__init__(*args, **kwargs)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            self._send_file(ROOT / "templates" / "index.html", "text/html; charset=utf-8")
        elif path == "/api/sources":
            self._send_json(
                [
                    {
                        "id": source["id"],
                        "title": source["title"],
                        "section": source["section"],
                    }
                    for source in self.sources
                ]
            )
        elif path == "/api/examples":
            self._send_json(
                [{"question": example["question"]} for example in self.examples]
            )
        elif path in STATIC_FILES:
            relative_path, content_type = STATIC_FILES[path]
            self._send_file(ROOT / relative_path, content_type)
        else:
            self._send_json({"error": "Not found."}, status=404)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/ask":
            self._send_json({"error": "Not found."}, status=404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json({"error": "A valid Content-Length header is required."}, status=411)
            return
        if content_length < 1:
            self._send_json({"error": "Request body must not be empty."}, status=400)
            return
        if content_length > MAX_REQUEST_BYTES:
            self._send_json({"error": "Question is too large."}, status=413)
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json({"error": "Send the question as application/json."}, status=415)
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"error": "Request body must be valid UTF-8 JSON."}, status=400)
            return
        if not isinstance(payload, dict):
            self._send_json({"error": "Request body must be a JSON object."}, status=400)
            return

        result, error = answer_question(self.sources, payload.get("question"))
        if error:
            self._send_json({"error": error}, status=400)
            return
        self._send_json(result)

    def _send_file(self, path, content_type):
        try:
            content = path.read_bytes()
        except OSError:
            self._send_json({"error": "Required app file could not be read."}, status=500)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload, status=200):
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_string, *args):
        sys.stderr.write(
            "{} - {}\n".format(self.address_string(), format_string % args)
        )


def create_server(sources, examples, host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Build a local HTTP server with the validated assistant data."""
    handler = partial(AssistantRequestHandler, sources=sources, examples=examples)
    return ThreadingHTTPServer((host, port), handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="start the local browser app")
    parser.add_argument(
        "--ask",
        metavar="QUESTION",
        help="answer a question from the local fictional guides",
    )
    parser.add_argument(
        "--list-sources", action="store_true", help="list available fictional guides"
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="server host (default: 127.0.0.1)")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="server port (default: 8001)"
    )
    args = parser.parse_args(argv)

    try:
        sources = load_sources()
        examples = load_examples()
    except ValueError as error:
        print("Assistant data error: {}".format(error), file=sys.stderr)
        return 1

    if args.list_sources:
        for source in sources:
            print("{} - {} ({})".format(source["id"], source["title"], source["section"]))
        return 0

    if args.ask is not None:
        result, error = answer_question(sources, args.ask)
        if error:
            print(error, file=sys.stderr)
            return 2
        print(result["answer"])
        for citation in result["sources"]:
            print(
                "Source: {} — {} — {}".format(
                    citation["id"], citation["title"], citation["section"]
                )
            )
            print('Evidence: "{}"'.format(citation["excerpt"]))
        return 0

    if not args.serve:
        parser.print_help()
        return 0
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    server = create_server(sources, examples, args.host, args.port)
    print("Evidence-Based Support Assistant running at http://{}:{}/".format(
        args.host, args.port
    ))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping the local assistant.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
