(function () {
  "use strict";

  const form = document.getElementById("question-form");
  const questionInput = document.getElementById("question");
  const askButton = document.getElementById("ask-button");
  const answerContent = document.getElementById("answer-content");
  const errorMessage = document.getElementById("form-error");

  function addTextElement(parent, tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    parent.appendChild(element);
    return element;
  }

  function renderAnswer(result) {
    answerContent.replaceChildren();
    addTextElement(
      answerContent,
      "h2",
      result.abstained ? "abstain-title" : "answer-title",
      result.answer
    );

    if (result.ai_used) {
      addTextElement(
        answerContent,
        "p",
        "ai-draft-note",
        "AI draft (" + result.model + "). Check the source excerpts before using it."
      );
    }

    if (result.abstained) {
      addTextElement(
        answerContent,
        "p",
        "note",
        result.ai_used
          ? "The answer was not supported by the matched guides, so no sources are cited."
          : "No sources are cited because the available guides do not support this answer."
      );
      return;
    }

    addTextElement(answerContent, "h3", "", "Supporting sources");
    const list = document.createElement("ol");
    list.className = "citation-list";
    result.sources.forEach(function (source) {
      const item = document.createElement("li");
      addTextElement(item, "strong", "citation-title", source.title);
      addTextElement(item, "span", "citation-meta", source.id + " · " + source.section);
      const quote = document.createElement("blockquote");
      quote.textContent = source.excerpt;
      item.appendChild(quote);
      list.appendChild(item);
    });
    answerContent.appendChild(list);
  }

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.hidden = false;
  }

  async function ask(question) {
    errorMessage.hidden = true;
    askButton.disabled = true;
    askButton.textContent = "Searching…";
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question })
      });
      const payload = await response.json();
      if (!response.ok) {
        showError(payload.error || "The question could not be checked.");
        return;
      }
      renderAnswer(payload);
    } catch (error) {
      showError("Could not reach the local app. Check that its server is running.");
    } finally {
      askButton.disabled = false;
      askButton.textContent = "Find evidence";
    }
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    ask(questionInput.value);
  });

  fetch("/api/status").then(function (response) {
    if (!response.ok) throw new Error("Could not load AI settings.");
    return response.json();
  }).then(function (status) {
    const message = status.ai_enabled
      ? "OpenAI is enabled (" + status.model + "). Your question and matched guide excerpts are sent to OpenAI for a draft."
      : "Evidence-only mode: no question is sent outside this computer. Add an OpenAI key in your local .env file to enable AI.";
    document.getElementById("ai-status").textContent = message;
  }).catch(function () {
    document.getElementById("ai-status").textContent =
      "AI settings could not be checked. Evidence search is still available.";
  });

  Promise.all([
    fetch("/api/sources").then(function (response) {
      if (!response.ok) throw new Error("Could not load guides.");
      return response.json();
    }),
    fetch("/api/examples").then(function (response) {
      if (!response.ok) throw new Error("Could not load sample questions.");
      return response.json();
    })
  ]).then(function (data) {
    const sources = data[0];
    const examples = data[1];
    document.getElementById("guide-count").textContent =
      sources.length + (sources.length === 1 ? " guide" : " guides");

    const sourceList = document.getElementById("source-list");
    sources.forEach(function (source) {
      const card = document.createElement("article");
      card.className = "source-card";
      addTextElement(card, "span", "pill", source.id);
      addTextElement(card, "h3", "", source.title);
      addTextElement(card, "p", "note", source.section);
      sourceList.appendChild(card);
    });

    const exampleList = document.getElementById("examples");
    examples.forEach(function (example) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "example-button";
      button.textContent = example.question;
      button.addEventListener("click", function () {
        questionInput.value = example.question;
        ask(example.question);
      });
      exampleList.appendChild(button);
    });
  }).catch(function () {
    document.getElementById("guide-count").textContent = "Guides unavailable";
    showError("Could not load the sample guides. Restart the local app and try again.");
  });
}());
