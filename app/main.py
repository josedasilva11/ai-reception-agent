"""FastAPI application exposing the reception agent webhook.

Serves the webhook endpoint that turns a customer message into a structured
response, plus a small browser demo page at the site root.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.agent import AgentResponse, handle_message
from app.config import BusinessProfile, load_business_profile

app = FastAPI(title="AI Reception Agent", version="1.0.0")


class WebhookRequest(BaseModel):
    """Incoming webhook payload."""

    message: str = Field(..., min_length=1, description="Customer message text.")


def get_profile() -> BusinessProfile:
    """Load the business profile fresh per request so config edits apply live."""
    return load_business_profile()


@app.get("/health")
def health() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}


@app.get("/profile")
def profile() -> BusinessProfile:
    """Return the active business profile, useful for debugging the config."""
    return get_profile()


@app.post("/webhook", response_model=AgentResponse)
def webhook(payload: WebhookRequest) -> AgentResponse:
    """Main entry point: turn a customer message into a structured reply."""
    return handle_message(payload.message, get_profile())


@app.get("/", response_class=HTMLResponse)
def demo_page() -> str:
    """Serve the built in browser demo page."""
    profile_name = get_profile().name
    return _DEMO_HTML.replace("{{BUSINESS_NAME}}", profile_name)


_DEMO_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Reception Agent</title>
  <style>
    :root { color-scheme: light dark; }
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      max-width: 640px; margin: 3rem auto; padding: 0 1rem; line-height: 1.5;
    }
    h1 { font-size: 1.4rem; margin-bottom: 0.2rem; }
    .sub { color: #888; margin-top: 0; font-size: 0.9rem; }
    #log { border: 1px solid #ccc4; border-radius: 10px; padding: 1rem;
      min-height: 180px; margin: 1rem 0; }
    .msg { margin: 0.5rem 0; }
    .me { text-align: right; }
    .bubble { display: inline-block; padding: 0.5rem 0.8rem; border-radius: 12px;
      max-width: 80%; }
    .me .bubble { background: #2563eb; color: #fff; }
    .bot .bubble { background: #6b728022; }
    .meta { font-size: 0.75rem; color: #888; margin-top: 0.2rem; }
    form { display: flex; gap: 0.5rem; }
    input { flex: 1; padding: 0.6rem; border-radius: 8px; border: 1px solid #ccc; }
    button { padding: 0.6rem 1rem; border: 0; border-radius: 8px;
      background: #2563eb; color: #fff; cursor: pointer; }
  </style>
</head>
<body>
  <h1>{{BUSINESS_NAME}} reception agent</h1>
  <p class="sub">Ask about services, hours, or request a booking.</p>
  <div id="log"></div>
  <form id="f">
    <input id="m" autocomplete="off"
      placeholder="e.g. Can I book a gel manicure this week?" />
    <button type="submit">Send</button>
  </form>
  <script>
    const log = document.getElementById('log');
    const form = document.getElementById('f');
    const input = document.getElementById('m');

    function add(cls, html) {
      const d = document.createElement('div');
      d.className = 'msg ' + cls;
      d.innerHTML = html;
      log.appendChild(d);
      log.scrollTop = log.scrollHeight;
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      add('me', '<span class="bubble">' + text + '</span>');
      input.value = '';
      try {
        const res = await fetch('/webhook', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text })
        });
        const data = await res.json();
        let meta = 'intent: ' + data.intent + ' | qualified: ' + data.qualified;
        if (data.suggested_slots.length) {
          const slots = data.suggested_slots
            .map(s => new Date(s).toLocaleString())
            .join(', ');
          meta += '<br>slots: ' + slots;
        }
        add('bot', '<span class="bubble">' + data.reply + '</span>' +
          '<div class="meta">' + meta + '</div>');
      } catch (err) {
        add('bot', '<span class="bubble">Sorry, something went wrong.</span>');
      }
    });
  </script>
</body>
</html>
"""
