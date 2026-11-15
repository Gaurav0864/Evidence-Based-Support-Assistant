# Evidence-Based Support Assistant

**A small local app that answers support questions from fictional guides—and shows the evidence.**

Ask a question about sign-in, training playback, or API errors. The app searches its guides, quotes the matching text, and names the source. If the guides do not support an answer, it says **“I can't confirm that from the available guides.”**

This project demonstrates a responsible AI support pattern: ground answers in approved information, expose the source, and abstain when evidence is missing. For transparency, this demo uses simple local text matching and quoted excerpts—not an AI model or external service.

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

## Try it

Use the sample questions in the browser, or ask from the command line:

```powershell
python app.py --list-sources
python app.py --ask "What is the safe retry guidance for HTTP 429 API requests?"
python -m unittest discover -s tests -v
```

The test questions in `data/test_questions.json` check expected sources, quoted guidance, and an unsupported question that should receive an abstention.

## How it works

1. `data/sources.json` contains fictional support guides.
2. `knowledge.py` looks for meaningful words in the question and guide sentences.
3. The app returns exact matching excerpts with source IDs and titles; it does not invent a paraphrased fix.
4. If there is not enough overlap with the guides, it returns an explicit “I can't confirm” response.
5. `app.py` serves the browser page and local JSON API. HTML and JavaScript are in `templates/` and `static/`.

## Project map

```text
app.py                         Local web server and command-line interface
knowledge.py                   Guide validation, matching, citations, and abstention
data/sources.json              Fictional support guides
data/test_questions.json       Shared example questions and expected outcomes
templates/                     Browser page
static/                        Page styling and interactions
tests/                         Unit and HTTP route tests
.github/workflows/tests.yml    Automated tests on GitHub
.vscode/                       VS Code launch setup and extension recommendation
run.bat                        Windows one-click launcher
```

## Safety and limitations

This is a practice demo, not an official Mindtickle product or integration. The guides and questions are fictional. It stores no conversation history and contacts no outside service. Its word matching is intentionally simple: it can miss relevant guidance or match imperfectly, so always inspect the cited excerpt. The tests verify expected examples; they do not prove answers are correct for every possible question.

For a real deployment, use approved documentation, access controls, privacy review, and broader evaluation before connecting any AI model or customer data.