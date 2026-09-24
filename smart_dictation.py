import re
from typing import Optional

# Common Whisper hallucinations triggered by silence, breathing, or background noise
HALLUCINATION_PATTERNS = [
    r"^(thank you|thanks for watching|thank you for watching|thanks for listening|thank you very much)[.!]?$",
    r"^(subtitles by|transcript by|transcribed by|translated by|captioning by).*$",
    r"^\[(music|applause|laughter|silence|whispering|sighs|cheering)\]$",
    r"^\((music|applause|laughter|silence|whispering|sighs|cheering)\)$",
    r"^[♪♫#\*\-\s]+$",
    r"^(you|bye|hello|goodbye|see you next time|please subscribe|subscribe|like and subscribe)[.!]?$",
    r"^(MBC 뉴스|KBS 뉴스|SBS 뉴스|YTN|시청해 주셔서 감사합니다).*$",
]
HALLUCINATION_REGEXES = [re.compile(p, re.IGNORECASE) for p in HALLUCINATION_PATTERNS]


def is_hallucination(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return True
    for rx in HALLUCINATION_REGEXES:
        if rx.match(cleaned):
            return True
    # Check for excessive repetitive word loops (e.g., "you know you know you know you know")
    words = cleaned.lower().split()
    if len(words) >= 6:
        unique_words = set(words)
        if len(unique_words) <= 2:
            return True
    return False


def clean_filler_words(text: str) -> str:
    """Removes verbal filler words and stuttered duplicates."""
    # Remove standalone filler words (um, uh, er, ah, erm)
    text = re.sub(r"\b(um+|uh+|er+|ah+|erm+)\b[,\s]*", "", text, flags=re.IGNORECASE)
    # Remove stuttered duplicated words (e.g. "I I think" -> "I think", "the the" -> "the")
    text = re.sub(r"\b([a-zA-Z]+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    # Clean up double spaces created by filler removal
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def format_spoken_punctuation(text: str) -> str:
    """Converts spoken punctuation phrases into actual punctuation marks."""
    # We do case-insensitive boundary matches
    replacements = [
        # New lines & paragraphs
        (r"\b(?:new paragraph)\b", "\n\n"),
        (r"\b(?:new line|newline)\b", "\n"),
        # Punctuation
        (r"\b(?:period|full stop)\b", "."),
        (r"\b(?:comma)\b", ","),
        (r"\b(?:question mark)\b", "?"),
        (r"\b(?:exclamation mark|exclamation point)\b", "!"),
        (r"\b(?:colon)\b", ":"),
        (r"\b(?:semi-colon|semicolon)\b", ";"),
        (r"\b(?:ellipsis|dot dot dot)\b", "..."),
        (r"\b(?:dash|hyphen)\b", " - "),
        # Parentheses & Quotes
        (r"\b(?:open parenthesis|open paren)\b", "("),
        (r"\b(?:close parenthesis|close paren)\b", ")"),
        (r"\b(?:open quote|open quotes|quote)\b", '"'),
        (r"\b(?:close quote|close quotes|unquote)\b", '"'),
    ]

    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    return text


def normalize_typography(text: str) -> str:
    """Fixes punctuation spacing, capitalization, and formatting."""
    # Remove space before standard punctuation marks
    text = re.sub(r"\s+([.,!?:;])", r"\1", text)
    # Ensure a space after punctuation if followed by a letter/digit
    text = re.sub(r"([.,!?:;])([A-Za-z0-9])", r"\1 \2", text)
    # Clean whitespace around newlines
    text = re.sub(r"[ \t]*\n+[ \t]*", "\n", text)
    # Fix quotes spacing: " word " -> "word"
    text = re.sub(r'"\s+([^"]+?)\s+"', r'"\1"', text)
    # Fix parentheses spacing: ( word ) -> (word)
    text = re.sub(r'\(\s+([^)]+?)\s+\)', r'(\1)', text)
    # Fix contractions spacing (e.g. don ' t -> don't)
    text = re.sub(r"\b(\w+)\s+'\s+([tT|sS|dD|m|re|ve|ll])\b", r"\1'\2", text)

    # Capitalize after periods, question marks, exclamation marks, or newlines
    def _cap_match(match):
        punct = match.group(1)
        space = match.group(2)
        char = match.group(3)
        return f"{punct}{space}{char.upper()}"

    text = re.sub(r"([.!?\n]+)(\s*)([a-z])", _cap_match, text)

    # Capitalize very first character of the text
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text.strip()


def process_smart_dictation(
    raw_text: str,
    enable_smart: bool = True,
    format_punctuation: bool = True,
    clean_fillers: bool = True,
) -> str:
    """Runs smart dictation post-processing pipeline."""
    if not raw_text:
        return ""

    if is_hallucination(raw_text):
        return ""

    text = raw_text.strip()
    if not enable_smart:
        return text

    if format_punctuation:
        text = format_spoken_punctuation(text)

    if clean_fillers:
        text = clean_filler_words(text)

    text = normalize_typography(text)
    return text


def run_ai_polish(text: str, provider: str = "openai", api_key: Optional[str] = None) -> str:
    """Optional LLM pass to polish grammar, flow, and tone while strictly preserving meaning."""
    if not text or not api_key:
        return text

    prompt = (
        "You are an AI dictation editor. Clean up the following speech-to-text transcript. "
        "Fix any grammar, remove redundant verbal clutter, and format cleanly, "
        "while strictly preserving all original facts, names, terminology, and tone. "
        "Return ONLY the polished transcript without commentary or quotes.\n\n"
        f"Transcript:\n{text}"
    )

    try:
        if provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000,
            )
            polished = resp.choices[0].message.content.strip()
            return polished if polished else text

        elif provider == "groq":
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000,
            )
            polished = resp.choices[0].message.content.strip()
            return polished if polished else text

        elif provider == "gemini":
            import requests

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2},
            }
            res = requests.post(url, json=payload, timeout=8)
            if res.status_code == 200:
                data = res.json()
                cand = data.get("candidates", [{}])[0]
                part = cand.get("content", {}).get("parts", [{}])[0]
                polished = part.get("text", "").strip()
                return polished if polished else text

    except Exception:
        # Fallback to unpolished text on network/API failure
        return text

    return text
