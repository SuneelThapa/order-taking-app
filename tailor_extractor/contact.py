import json
import os
import urllib.request


def _call_gemini(prompt: str) -> str:
    """Call Gemini API and return raw text response."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 500}
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


CONTACT_PROMPT = """Extract contact and visit details from the following freeform text written by a tailor's staff member.

Return ONLY a JSON object with these fields (omit any field not mentioned):
{
  "name":           "full name",
  "phone":          "phone number as written",
  "email":          "email address",
  "street_address": "street address",
  "city":           "city",
  "state":          "state or province",
  "postcode":       "postal or zip code",
  "country":        "country",
  "hotel_name":     "hotel name if staying at a hotel",
  "room_number":    "hotel room number",
  "departure_date": "departure date in YYYY-MM-DD format if mentioned"
}

Rules:
- Return ONLY valid JSON, no explanation, no markdown, no backticks
- If a field is not mentioned, omit it entirely
- Phone: keep as written
- Departure date: convert any date format to YYYY-MM-DD
- Hotel hints: words like stay, hotel, room, checking out

Text to extract from:
"""


def extract_contact(text: str) -> dict:
    """
    Extract contact and visit info from freeform text.

    Example:
        extract_contact("John Smith, 081-234-5678, john@gmail.com, Marriott room 502, leaves 25 June")
        → {"name": "John Smith", "phone": "081-234-5678", ...}
    """
    if not text or not text.strip():
        return {}
    try:
        raw = _call_gemini(CONTACT_PROMPT + text.strip())
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        return {"_error": str(e)}