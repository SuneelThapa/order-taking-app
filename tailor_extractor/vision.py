import json
import os
import urllib.request


def _call_gemini_vision(prompt: str, image_base64: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": image_base64}}
            ]
        }],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 600}
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


CONTACT_VISION_PROMPT = """This is a handwritten note from a customer in a tailor shop.
Read the handwriting carefully and extract any contact or visit details.

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
  "hotel_name":     "hotel name if mentioned",
  "room_number":    "hotel room number",
  "departure_date": "departure date in YYYY-MM-DD format"
}

Rules:
- Return ONLY valid JSON, no explanation, no markdown, no backticks
- If a field is not mentioned or illegible, omit it
- Read carefully — handwriting may be imperfect
"""

MEASUREMENT_VISION_PROMPT = """This is a handwritten note from a tailor shop with body measurements.
Read the handwriting carefully and extract all measurements.

Return ONLY a JSON object with these fields (omit any field not mentioned):
{
  "neck": number, "shoulder": number, "sleeve": number, "biceps": number,
  "chest": number, "stomach": number, "hips": number,
  "length": number, "front": number, "back": number,
  "pants_waist": number, "pants_hip": number, "belly": number,
  "crotch": number, "thigh": number, "knee": number,
  "cuff": number, "pants_length": number,
  "height": number, "weight": number,
  "high_chest": number, "upper_hips": number,
  "deep_front": number, "deep_back": number,
  "shoulder_to_middle_breast": number,
  "shoulder_to_under_breast": number,
  "middle_breast_to_middle_breast": number,
  "shoulder_to_back": number,
  "shoulder_to_waist": number
}

Common abbreviations the tailor may use:
ch/C = chest, w/W = stomach/waist, pw = pants_waist, sh = shoulder,
sl/slv = sleeve, n/nk = neck, bi = biceps, L/len = length,
fr = front, bk = back, ph = pants_hip, cr = crotch, th = thigh,
kn = knee, cf = cuff, pl = pants_length, ht = height, wt = weight,
hc = high_chest, uh = upper_hips, df = deep_front, db = deep_back

Rules:
- Return ONLY valid JSON, no explanation, no markdown, no backticks
- All values must be numbers
- Read carefully — handwriting may be imperfect
- If illegible, omit that field
"""


def extract_contact_from_image(image_base64: str) -> dict:
    """Extract contact details from handwritten canvas image."""
    if not image_base64:
        return {}
    try:
        # Strip data URL prefix if present
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]
        raw = _call_gemini_vision(CONTACT_VISION_PROMPT, image_base64)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        return {"_error": str(e)}


def extract_measurements_from_image(image_base64: str) -> dict:
    """Extract body measurements from handwritten canvas image."""
    if not image_base64:
        return {}
    try:
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]
        raw = _call_gemini_vision(MEASUREMENT_VISION_PROMPT, image_base64)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        return {k: float(v) for k, v in result.items() if isinstance(v, (int, float))}
    except Exception as e:
        return {"_error": str(e)}