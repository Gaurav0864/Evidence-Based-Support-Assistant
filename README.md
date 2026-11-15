# Evidence-Based Support Assistant

**A small local app that answers support questions from fictional guides—and shows the evidence.**

Ask a question about sign-in, training playback, or API errors. The app searches its guides, quotes the matching text, and names the source. If the guides do not support an answer, it says **“I can't confirm that from the available guides.”**

This project demonstrates a responsible AI support pattern: ground answers in approved information, expose the source, and abstain when evidence is missing. It first finds relevant guide excerpts locally. If OpenAI is configured, the Responses API drafts an answer using only those excerpts; the UI still shows the cited evidence so you can check the draft.

## Run on Windows

**You need Python 3.7 or newer. No packages need to be installed.**

### In VS Code

1. Select **File → Open Folder...** and choose this project folder.
2. If prompted, install the recommended Python extension.
3. Press **F5** and choose **Evidence-Based Support Assistant**.
4. Open <http://127.0.0.1:8001> in your browser.

Or double-click `run.bat`, or run in the VS Code terminal:

```powershell
python app.py --serve
```

Press **Ctrl+C** in the terminal to stop the server. If port `8001` is busy:

```powershell
python app.py --serve --port 8002
```

## Enable OpenAI

The app works without an API key in **evidence-only mode**. To enable OpenAI:

1. Copy `.env.example` to a new file named `.env` in this folder.
2. Open `.env` and add your own key after `OPENAI_API_KEY=`.
3. Save the file, then start or restart the app.

The key is read by the local server and sent to OpenAI only in the API authorization header; it is never sent to the browser or committed. The app sends OpenAI only the question and matching fictional guide excerpts. API use may incur charges. Never use real customer data or logs unless your company has approved that use.

## Try it

Use the sample questions in the browser, or ask from the command line:

```powershell
python app.py --list-sources
python app.py --ask "What is the safe retry guidance for HTTP 429 API requests?"
python -m unittest discover -s tests -v
```

The test questions in `data/test_questions.json` check expected sources, quoted guidance, and an unsupported question that should receive an abstention. Tests mock OpenAI requests; they do not need a key or make paid API calls.

## How it works

1. `data/sources.json` contains fictional support guides.
2. `knowledge.py` finds relevant sentences locally. If no guide supports the question, the app abstains without contacting OpenAI.
3. When enabled, `openai_client.py` sends the question and matched excerpts to OpenAI's Responses API and checks that returned citations refer only to those excerpts.
4. The browser displays the AI draft alongside the exact guide excerpts. Review the evidence; citations do not guarantee that every generated sentence is correct.
5. `app.py` serves the browser page and local JSON API. HTML and JavaScript are in `templates/` and `static/`.

## Project map

```text
app.py                         Local web server and command-line interface
knowledge.py                   Guide validation, matching, citations, and abstention
openai_client.py               Optional OpenAI Responses API connection
data/sources.json              Fictional support guides
data/test_questions.json       Shared example questions and expected outcomes
.env.example                   Safe template for local OpenAI settings
templates/                     Browser page
static/                        Page styling and interactions
tests/                         Unit and HTTP route tests
.github/workflows/tests.yml    Automated tests on GitHub
.vscode/                       VS Code launch setup and extension recommendation
run.bat                        Windows one-click launcher
```

## Safety and limitations

This is a practice demo, not an official Mindtickle product or integration. The guides and questions are fictional. In OpenAI mode, the question and matched excerpts are sent to the OpenAI API; the app does not store conversation history. Local text matching can miss relevant guidance, and a model can still produce unsupported wording. Always inspect the cited excerpt. The tests verify expected examples and mocked API handling; they do not prove answers are correct for every possible question.

For a real deployment, use approved documentation, access controls, privacy review, and broader evaluation before using any AI model or customer data.