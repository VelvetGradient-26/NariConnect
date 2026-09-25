import json
import re
import ollama
from app.config import OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_EMBED_MODEL

client = ollama.Client(host=OLLAMA_HOST)

def get_embedding(text: str) -> list[float]:
    response = client.embeddings(
        model=OLLAMA_EMBED_MODEL,
        prompt=text,
    )
    return response["embedding"]

def chat_with_context(prompt: str, context: str, user_profile: dict = None, chat_history: list = None) -> tuple[str, bool]:
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

3. Handle Irrelevant Context Gracefully: If the database context below does not match the user's question, ignore the context completely and just have a normal conversation.

OUTPUT FORMAT:
At the very end of your response, strictly append a JSON block indicating if you recommended schemes.
Example:
... your response text ...
{{ "recommended_schemes": true }}
OR
... your response text ...
{{ "recommended_schemes": false }}
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

    response = client.chat(
        model=OLLAMA_MODEL,
        messages=messages,
    )
    
    content = response["message"]["content"]
    
    # Parse the JSON flag at the end
    should_show_schemes = False
    json_match = re.search(r'\{\s*"recommended_schemes"\s*:\s*(true|false)\s*\}\s*$', content, re.IGNORECASE)
    
    if json_match:
        should_show_schemes = json_match.group(1).lower() == 'true'
        # Remove the JSON block from the final response text shown to user
        content = content[:json_match.start()].strip()
        
    return content, should_show_schemes


def extract_user_info(user_text: str) -> dict:
    prompt = f"""
Extract the following demographic information from the user's text. 
If a piece of information is not explicitly mentioned, set its value to null.

User's text: "{user_text}"

Return ONLY a valid JSON object with these exact keys: age, gender, occupation, state, income.
Do not include any markdown formatting, explanations, or text outside the JSON object.
"""

    response = client.chat(
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
    
    empty = {"age": None, "gender": None, "occupation": None, "state": None, "income": None}
    try:
        extracted = json.loads(response["message"]["content"])
    except json.JSONDecodeError:
        # Fallback in case the LLM messes up the JSON formatting
        return empty
    return extracted if isinstance(extracted, dict) else empty