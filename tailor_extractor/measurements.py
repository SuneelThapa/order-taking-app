import json
import os
import urllib.request


def _call_gemini(prompt: str) -> str:
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


MEASUREMENT_PROMPT = """Extract body measurements from freeform text written by a tailor.

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

Common abbreviations:
- ch/C/chest → chest
- w/W/wst/waist → stomach
- pw/pants waist → pants_waist
- sh/sho/shoulder → shoulder
- sl/slv/sleeve → sleeve
- n/nk/neck → neck
- bi/bic/bicep → biceps
- hip/H → hips
- len/L/length → length
- fr/front → front
- bk/back → back
- ph/pants hip → pants_hip
- cr/crotch → crotch
- th/thigh → thigh
- kn/knee → knee
- cf/cuff → cuff
- pl/pant len/pants length → pants_length
- ht/height → height
- wt/weight → weight
- hc/high chest → high_chest
- uh/upper hip → upper_hips
- df/deep front → deep_front
- db/deep back → deep_back
- smb/sh to mid breast → shoulder_to_middle_breast
- sub/sh to under breast → shoulder_to_under_breast
- mb/mid breast → middle_breast_to_middle_breast
- sb/sh to back → shoulder_to_back
- sw/sh to waist → shoulder_to_waist

Rules:
- Return ONLY valid JSON, no explanation, no markdown, no backticks
- All values must be numbers (decimal allowed e.g. 17.5)
- Separator can be space, comma, dash, equals, colon
- Ignore non-measurement text

Text to extract from:
"""


def extract_measurements(text: str) -> dict:
    """
    Extract body measurements from freeform tailor shorthand.

    Example:
        extract_measurements("ch38 w34 sh17.5 sl25 neck15.5")
        → {"chest": 38, "stomach": 34, "shoulder": 17.5, "sleeve": 25, "neck": 15.5}
    """
    if not text or not text.strip():
        return {}
    try:
        raw = _call_gemini(MEASUREMENT_PROMPT + text.strip())
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        return {k: float(v) for k, v in result.items() if isinstance(v, (int, float))}
    except Exception as e:
        return {"_error": str(e)}