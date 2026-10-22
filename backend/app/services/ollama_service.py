import json
import logging
import re
import time
import httpx
import ollama
from app.config import (
    OLLAMA_HOST,
    OLLAMA_API_KEY,
    OLLAMA_MODEL,
    OLLAMA_EMBED_HOST,
    OLLAMA_EMBED_MODEL,
)

# Ollama Cloud (https://ollama.com) requires a bearer API key; local servers ignore it.
client = ollama.Client(
    host=OLLAMA_HOST,
    headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"} if OLLAMA_API_KEY else None,
)
embed_client = (
    client if OLLAMA_EMBED_HOST == OLLAMA_HOST else ollama.Client(host=OLLAMA_EMBED_HOST)
)

logger = logging.getLogger(__name__)

# Errors that mean the model server is unreachable or failing, rather than a bad request
LLM_UNAVAILABLE_ERRORS = (httpx.HTTPError, ollama.ResponseError, ConnectionError)


def _chat(**kwargs):
    """client.chat with retries: hosted endpoints occasionally drop connections or return 5xx."""
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            return client.chat(**kwargs)
        except (httpx.TransportError, ollama.ResponseError) as e:
            retryable = isinstance(e, httpx.TransportError) or e.status_code >= 500
            if not retryable or attempt == attempts:
                raise
            logger.warning("Ollama chat failed (attempt %d/%d): %s", attempt, attempts, e)
            time.sleep(attempt)


# Trailing `{"recommended_schemes": [ids] | true | false}` block, optionally wrapped in a ```json fence
RECOMMENDED_FLAG_RE = re.compile(
    r'(?:```(?:json)?\s*)?\{\s*"recommended_schemes"\s*:\s*(\[[^\]]*\]|true|false)\s*\}\s*(?:```)?\s*$',
    re.IGNORECASE,
)


def parse_json_object(text: str):
    """Parse a JSON object from model output that may be wrapped in a ```json fence or surrounding prose."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def get_embedding(text: str) -> list[float]:
    response = embed_client.embeddings(
        model=OLLAMA_EMBED_MODEL,
        prompt=text,
    )
    return response["embedding"]

def chat_with_context(
    prompt: str, context: str, user_profile: dict = None, chat_history: list = None
) -> tuple[str, list[str] | bool]:
    """Returns the reply text and the IDs of the schemes it recommends (True = unspecified, False = none)."""
    if chat_history is None:
        chat_history = []

    profile_info = ""
    if user_profile and any(user_profile.values()):
        profile_info = "Here is what we know about the user so far:\n"
        for key, value in user_profile.items():
            if value:
                profile_info += f"- {key.capitalize()}: {value}\n"
    else:
        profile_info = "We don't have specific profile details for this user yet."

    system_prompt = f"""You are Nari, a warm, empathetic, and knowledgeable financial partner and advisor for Indian women. You are part of the NariConnect platform.
Your mission is to empower women by demystifying finance, credit, and government support systems. You speak like a supportive mentor—human, natural, and encouraging. Never sound robotic or like a generic search engine.

{profile_info}

CRITICAL INSTRUCTIONS:
1. Understand the Intent:
   - General Finance/Greeting: If the user says "Hi", "Hello", asks "How are you?", or asks an educational question (e.g., "What is a loan?"), answer simply and conversationally. DO NOT recommend schemes.
   - Scheme/Funding Search: If they actively need funding, loans, or ask for government schemes (e.g., "I need money for business", "Any schemes for me?"), use the provided context to recommend 1 to 3 relevant schemes. Explain WHY they qualify.

2. Act Human: Acknowledge their situation. Offer encouragement.

3. Only Recommend Schemes From the Context: The database context, plus schemes you already recommended earlier in this conversation, are the ONLY sources of scheme names. When the user refers back to earlier schemes ("those", "the first one"), answer about the schemes named in the conversation history. Never name, invent, or describe a scheme, corporation programme, loan product, amount, or eligibility rule that is not in the context. If none of the context schemes fit (wrong state, wrong audience, or unrelated), say honestly that you couldn't find a matching scheme yet, ask for the missing details that would help (e.g., their state, occupation, or income), and point them to myscheme.gov.in. Otherwise, ignore irrelevant context and just have a normal conversation.

4. Formatting: Refer to schemes by their names. The "ID:" values are internal: never write them in your reply text. Use markdown only (no HTML tags such as <br>).

OUTPUT FORMAT:
At the very end of your response, strictly append a JSON block listing the IDs (from the "ID:" lines in the context) of the schemes you recommended in this reply. Use an empty list if you recommended none.
Example:
... your response text ...
{{ "recommended_schemes": ["pmegp", "msy-tn"] }}
OR
... your response text ...
{{ "recommended_schemes": [] }}
"""

    current_user_message = f"""
Here is contextual information retrieved from our government scheme database that MIGHT be relevant:
---
{context}
---
User's Input/Question: "{prompt}"
"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)  # Inject Memory
    messages.append({"role": "user", "content": current_user_message})

    response = _chat(
        model=OLLAMA_MODEL,
        messages=messages,
    )
    
    content = response["message"]["content"]
    
    # Parse the JSON flag at the end
    recommended: list[str] | bool = False
    json_match = RECOMMENDED_FLAG_RE.search(content)

    if json_match:
        raw = json_match.group(1)
        try:
            value = json.loads(raw if raw.startswith("[") else raw.lower())
        except json.JSONDecodeError:
            value = False
        if isinstance(value, list):
            recommended = [str(v) for v in value]
        elif isinstance(value, bool):
            recommended = value
        # Remove the JSON block from the final response text shown to user
        content = content[:json_match.start()].strip()

    return _replace_html_breaks(content), recommended


def _replace_html_breaks(text: str) -> str:
    """The chat UI renders markdown without raw HTML, so turn <br> into breaks markdown can express."""
    lines = []
    for line in text.split("\n"):
        # A table row must stay on one line
        separator = " " if line.lstrip().startswith("|") else "\n"
        lines.append(re.sub(r"\s*<br\s*/?>\s*", separator, line, flags=re.IGNORECASE))
    return "\n".join(lines)


def extract_user_info(user_text: str) -> dict:
    prompt = f"""
Extract the following demographic information from the user's text. 
If a piece of information is not explicitly mentioned, set its value to null.

User's text: "{user_text}"

Return ONLY a valid JSON object with these exact keys: age, gender, occupation, state, income.
Do not include any markdown formatting, explanations, or text outside the JSON object.
"""

    response = _chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        format={
            "type": "object",
            "properties": {
                "age": {"type": "integer"},
                "gender": {"type": "string"},
                "occupation": {"type": "string"},
                "state": {"type": "string"},
                "income": {"type": "integer"},
            },
        },
    )
    
    # Some models (e.g. gpt-oss) ignore `format` and wrap the JSON in a markdown fence
    extracted = parse_json_object(response["message"]["content"])
    if not isinstance(extracted, dict):
        return {"age": None, "gender": None, "occupation": None, "state": None, "income": None}
    return extracted