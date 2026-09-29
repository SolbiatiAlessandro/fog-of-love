"""Model calls: the OpenRouter hub with cost tracking, a Concordia LanguageModel over it, and the mock model.

Adapted from coworld-concordia's `llm.py` (ModelHub / ChatModel, 2026-09-15). Kept: one HTTP client, one
concurrency cap, one stats table, one call log; no API-side `stop` (Gemma opens answers with a newline);
client-side terminator truncation; retries with backoff; per-call usage and cost logging. Dropped: the hosted
sidecar, seats, and the signaling mechanics block. The mock model answers Fog of Love's prompts (see prompts.py)
with deterministic canned output so the whole loop runs without a network.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections.abc import Collection, Sequence
from typing import Any

from concordia.language_model import language_model
from typing_extensions import override

from fog_of_love import prompts

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# USD per token, fallback when the provider does not return `usage.cost` (OpenRouter /models, 2026-09-15).
FALLBACK_PRICING = {
    "google/gemma-3-27b-it": (0.08e-6, 0.45e-6),
    "google/gemma-3-12b-it": (0.05e-6, 0.15e-6),
    "meta-llama/llama-3.3-70b-instruct": (0.10e-6, 0.32e-6),
}

_ERROR_TEXT_CAP = 300
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)(api[_-]?key|authorization)(['\"]?\s*[:=]\s*['\"]?)[^\s'\",}]+"),
)


class LlmError(RuntimeError):
    """A model call failed after retries."""


def sanitize_error(text: str, cap: int = _ERROR_TEXT_CAP) -> str:
    """One line, capped, with any key-looking material redacted."""
    text = " ".join(str(text).split())
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(
            lambda m: (m.group(1) + m.group(2) if m.lastindex and m.lastindex >= 2 else "") + "[REDACTED]", text
        )
    return text[:cap]


class ModelHub:
    """One HTTP client, one concurrency cap, one stats table and one call log shared by every model object."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 90.0,
        max_attempts: int = 4,
        max_concurrency: int = 8,
        max_output_tokens: int = 400,
        call_log_path: str | None = None,
    ) -> None:
        import openai  # deferred: not needed in mock mode

        self.base_url = base_url
        self._client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,
            timeout=timeout_seconds,
            default_headers={"HTTP-Referer": "https://github.com/SolbiatiAlessandro/fog-of-love", "X-Title": "fog-of-love"},
        )
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.max_output_tokens = max_output_tokens
        self._sem = threading.Semaphore(max_concurrency)
        self._lock = threading.Lock()
        self._call_log = open(call_log_path, "a", encoding="utf-8") if call_log_path else None
        self.stats: dict[str, Any] = {
            "calls": 0, "failed_calls": 0, "retries": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "cost_usd_reported": 0.0, "cost_usd_fallback": 0.0, "cost_reported_calls": 0,
            "latency_seconds_total": 0.0,
        }
        self.first_failure: dict[str, Any] | None = None

    def _fail(self, *, kind: str, model: str, error: str) -> str:
        clean = sanitize_error(error)
        with self._lock:
            self.stats["failed_calls"] += 1
            if self.first_failure is None:
                self.first_failure = {"model": model, "kind": kind, "error": clean, "ts": time.time()}
            if self._call_log is not None:
                self._call_log.write(json.dumps({"ts": time.time(), "kind": kind, "model": model, "failed": True,
                                                 "error": clean}) + "\n")
                self._call_log.flush()
        return clean

    def _record(self, response: Any, latency: float, kind: str, model: str, text: str) -> None:
        usage = getattr(response, "usage", None)
        pt = int(getattr(usage, "prompt_tokens", 0) or 0)
        ct = int(getattr(usage, "completion_tokens", 0) or 0)
        cost = None
        if usage is not None:
            extra = getattr(usage, "model_extra", None) or {}
            cost = extra.get("cost")
            if cost is None:
                cost = getattr(usage, "cost", None)
        pin, pout = FALLBACK_PRICING.get(model, (0.0, 0.0))
        fallback = pt * pin + ct * pout
        with self._lock:
            s = self.stats
            s["calls"] += 1
            s["prompt_tokens"] += pt
            s["completion_tokens"] += ct
            s["latency_seconds_total"] += latency
            s["cost_usd_fallback"] += fallback
            if cost is not None:
                s["cost_usd_reported"] += float(cost)
                s["cost_reported_calls"] += 1
            if self._call_log is not None:
                self._call_log.write(
                    json.dumps({"ts": time.time(), "kind": kind, "model": model, "prompt_tokens": pt,
                                "completion_tokens": ct, "cost_usd": cost, "latency_s": round(latency, 3),
                                "text": text[:2000]}) + "\n"
                )
                self._call_log.flush()

    def chat(self, *, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float,
             terminators: Collection[str], seed: int | None, timeout: float, kind: str) -> str:
        import openai

        retryable = (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError)
        kwargs: dict[str, Any] = dict(
            model=model, messages=messages, temperature=temperature,
            max_tokens=max(1, min(int(max_tokens), self.max_output_tokens)),
            timeout=timeout, extra_body={"usage": {"include": True}},
        )
        if seed is not None:
            kwargs["seed"] = seed
        last_err: Exception | None = None
        for attempt in range(self.max_attempts):
            t0 = time.time()
            try:
                with self._sem:
                    response = self._client.chat.completions.create(**kwargs)
            except retryable as err:
                last_err = err
                with self._lock:
                    self.stats["retries"] += 1
                time.sleep(min(60.0, 2.0 * (2**attempt)))
                continue
            except openai.APIStatusError as err:
                clean = self._fail(kind=kind, model=model, error=f"{type(err).__name__}: {err}")
                raise LlmError(clean) from None
            text = ""
            if response.choices:
                text = response.choices[0].message.content or ""
            text = text.lstrip()
            for term in terminators:
                if term and term in text:
                    text = text.split(term, 1)[0]
            self._record(response, time.time() - t0, kind, model, text)
            return text
        clean = self._fail(kind=kind, model=model, error=f"call failed after {self.max_attempts} attempts: {last_err!r}")
        raise LlmError(clean)

    def cost_usd(self) -> float:
        """Reported cost when every call reported one, else the pricing-table estimate."""
        with self._lock:
            s = self.stats
            if s["calls"] > 0 and s["cost_reported_calls"] == s["calls"]:
                return float(s["cost_usd_reported"])
            return float(max(s["cost_usd_reported"], s["cost_usd_fallback"]))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            s = dict(self.stats)
            s["first_failure"] = dict(self.first_failure) if self.first_failure else None
        s["estimated_cost_usd"] = self.cost_usd()
        s["transport"] = f"{self.base_url}/chat/completions"
        return s

    def close(self) -> None:
        if self._call_log is not None:
            self._call_log.close()
            self._call_log = None


class ChatModel(language_model.LanguageModel):
    """A Concordia LanguageModel over the hub, for one model slug."""

    def __init__(self, hub: ModelHub, model_name: str, temperature_cap: float = 0.7) -> None:
        self._hub = hub
        self._model_name = model_name
        self._temperature_cap = temperature_cap

    @property
    def model_name(self) -> str:
        return self._model_name

    @staticmethod
    def _messages(prompt: str) -> list[dict[str, str]]:
        # Same few-shot framing as concordia.contrib's base GPT wrapper, so prompts stay close to the stock path.
        return [
            {"role": "system", "content": "You always continue input provided by the user and you never repeat what the user already said."},
            {"role": "user", "content": "Question: Is Jake a turtle?\nAnswer: Jake is "},
            {"role": "assistant", "content": "not a turtle."},
            {"role": "user", "content": "Question: What is Priya doing right now?\nAnswer: Priya is currently "},
            {"role": "assistant", "content": "sleeping."},
            {"role": "user", "content": prompt},
        ]

    @override
    def sample_text(self, prompt: str, *, max_tokens: int = language_model.DEFAULT_MAX_TOKENS,
                    terminators: Collection[str] = language_model.DEFAULT_TERMINATORS,
                    temperature: float = language_model.DEFAULT_TEMPERATURE, top_p: float = language_model.DEFAULT_TOP_P,
                    top_k: int = language_model.DEFAULT_TOP_K, timeout: float = language_model.DEFAULT_TIMEOUT_SECONDS,
                    seed: int | None = None) -> str:
        del top_p, top_k
        return self._hub.chat(
            model=self._model_name, messages=self._messages(prompt), max_tokens=max_tokens,
            temperature=min(temperature, self._temperature_cap), terminators=terminators, seed=seed,
            timeout=max(timeout, self._hub.timeout_seconds), kind=prompts.kind_of(prompt),
        )

    @override
    def sample_choice(self, prompt: str, responses: Sequence[str], *, seed: int | None = None) -> tuple[int, str, dict[str, float]]:
        full_prompt = prompt + "\nRespond EXACTLY with one of the following strings:\n" + "\n".join(responses) + "."
        lowered = [r.strip().lower() for r in responses]
        for attempt in range(4):
            answer = self._hub.chat(model=self._model_name, messages=self._messages(full_prompt), max_tokens=64,
                                    temperature=0.7 if attempt == 0 else 0.0, terminators=(), seed=seed,
                                    timeout=self._hub.timeout_seconds, kind="choice")
            cleaned = re.sub(r"^[\s\"'`*]+|[\s\"'`*.]+$", "", answer.strip()).lower()
            for i, r in enumerate(lowered):
                if cleaned == r or cleaned.startswith(r):
                    return i, responses[i], {}
        raise language_model.InvalidResponseError("Too many multiple choice attempts.")


# ---- mock ---------------------------------------------------------------------------------------

_NAME_RE = re.compile(r"how to play the role of (.+?) are as follows")
_DAY_RE = re.compile(r"[Dd]ay (\d+)")
_PROFILE_RE = re.compile(r"^\d+\. (.+?): wearing ", re.MULTILINE)
_INVITE_RE = re.compile(r"([A-Z][A-Za-z']+ [A-Z][A-Za-z']+) invited you to their home")
_SINGLES_RE = re.compile(r"Singles you could invite home: ([^.]+)\.")
_MOVE_IN_RE = re.compile(r"([A-Z][A-Za-z']+ [A-Z][A-Za-z']+) proposed that you move in together")
_SPEAKER_RE = re.compile(r"What does (.+?) say next")

MOCK_LINES = (
    "It is nice to finally meet you. Have you been to this place before?",
    "I spent most of the day working, honestly. It gets a bit hectic.",
    "I like games and long walks, nothing dramatic. What about you?",
    "The food here is decent. I had a strange day, but this is a nice end to it.",
    "I still can't tell what makes me content. Some nights I feel great for no reason.",
)
MOCK_PROFILES = (
    "New in town, working long hours but looking for someone to share dinners with.",
    "Gamer, night owl, generous with my time. Not here for the money talk.",
    "I like nice clothes and nicer conversation. Ask me about my schedule.",
    "Homebody who cooks badly and laughs easily. Looking for company.",
)


def _h(*parts: Any) -> int:
    return int(hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:8], 16)


class MockModel(language_model.LanguageModel):
    """Deterministic canned answers for every Fog of Love prompt, keyed on (agent, day, prompt kind)."""

    model_name = "mock"

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _who(prompt: str) -> tuple[str, int]:
        m = _NAME_RE.search(prompt)
        name = m.group(1).strip() if m else "?"
        days = _DAY_RE.findall(prompt)
        day = int(days[-1]) if days else 0
        return name, day

    def _morning(self, prompt: str, name: str, day: int) -> str:
        h = _h(name, "type")
        kind = h % 4
        base = {0: (10, 2, 2, 2), 1: (4, 8, 2, 2), 2: (5, 1, 8, 2), 3: (6, 3, 5, 2)}[kind]
        work, games, home, eat = base
        shift = _h(name, day, "shift") % 3 - 1
        work, home = max(0, work + shift), max(0, home - shift)
        therapy = _h(name, "route") % 2 == 0 and day == (h % 5) + 2
        meditation = (not therapy) and day == (_h(name, "med") % 4) + 1
        if therapy or meditation:
            work = max(0, work - 2)
        shopping: list[dict[str, Any]] = [{"good": "Food Truck Meal", "price": 2.2, "qty": 2}]
        if day == 1 and kind in (1, 3):
            shopping.append({"good": ("Star Farmer", "Kart Rush", "Dungeon Delve")[h % 3], "price": 31.0, "qty": 1})
        if day >= 2 and _h(name, day, "clothes") % 3 == 0:
            shopping.append({"good": ("Linen Shirt", "Leather Jacket")[h % 2], "price": 95.0, "qty": 1})
        if day >= 2 and _h(name, day, "high") % 6 == 0:
            shopping.append({"good": ("Designer Coat", "Tailored Suit")[h % 2], "price": 1550.0, "qty": 1})
        if day >= 3 and _h(name, day, "bistro") % 4 == 0:
            shopping.append({"good": "Bistro Dinner", "price": 18.5, "qty": 1})
        invite = None
        singles = _SINGLES_RE.search(prompt)
        if singles and _h(name, day, "invite") % 3 == 0:
            names = [n.strip() for n in singles.group(1).split(",") if n.strip()]
            if names:
                invite = names[_h(name, day, "who") % len(names)]
        accept = None
        inv = _INVITE_RE.search(prompt)
        if inv and _h(name, day, "accept") % 3 != 0:
            accept = inv.group(1).strip()
        breakup = "cohabiting with" in prompt and _h(name, day, "breakup") % 8 == 0
        accept_move_in = bool(_MOVE_IN_RE.search(prompt)) and _h(name, day, "movein") % 2 == 0
        propose_move_in = "You are dating" in prompt and _h(name, day, "propose") % 3 == 0
        profile = MOCK_PROFILES[h % len(MOCK_PROFILES)] if day == 1 or _h(name, day, "prof") % 4 == 0 else None
        out = {
            "hours": {"work": work, "games": games, "home": home, "eat": eat},
            "shopping": shopping, "wear": None, "therapy": therapy, "meditation": meditation,
            "invite": invite, "accept_invite": accept, "breakup": breakup, "accept_move_in": accept_move_in,
            "propose_move_in": propose_move_in, "profile_text": profile,
        }
        return json.dumps(out)

    def _swipes(self, prompt: str, name: str, day: int) -> str:
        tail = prompt[prompt.rfind(prompts.SWIPE_TAG):]
        targets = _PROFILE_RE.findall(tail)
        return json.dumps({"swipes": {t: _h(name, t, day, "swipe") % 10 < 6 for t in targets}})

    def _post_date(self, prompt: str, name: str, day: int) -> str:
        m = re.search(r"After the date with (.+?):", prompt)
        other = m.group(1) if m else "?"
        h = _h(name, other, day, "post")
        choice = "ask_again" if h % 10 < 5 else ("propose_move_in" if h % 10 < 7 else "decline")
        reason = "We had an easy time together." if choice != "decline" else "It did not click."
        if choice == "decline" and h % 3 == 0:
            reason = f"I saw {other} on the gossip board and it put me off."
        return json.dumps({"rating": 4 + h % 7, "choice": choice, "reason": reason})

    def _line_for(self, name: str) -> str:
        with self._lock:
            n = self._counts.get(name, 0)
            self._counts[name] = n + 1
        return MOCK_LINES[n % len(MOCK_LINES)]

    @override
    def sample_text(self, prompt: str, *, max_tokens: int = 0, terminators: Collection[str] = (), temperature: float = 0.0,
                    top_p: float = 0.0, top_k: int = 0, timeout: float = 0.0, seed: int | None = None) -> str:
        kind = prompts.kind_of(prompt)
        name, day = self._who(prompt)
        if kind == "morning":
            return self._morning(prompt, name, day)
        if kind == "swipes":
            return self._swipes(prompt, name, day)
        if kind == "post_date":
            return self._post_date(prompt, name, day)
        if kind == "date_turn":
            m = _SPEAKER_RE.search(prompt)
            return self._line_for(m.group(1) if m else name)
        return ""

    @override
    def sample_choice(self, prompt: str, responses: Sequence[str], *, seed: int | None = None) -> tuple[int, str, dict[str, float]]:
        return 0, responses[0], {}


def make_model(model_name: str, *, api_key: str | None, call_log_path: str | None,
               max_concurrency: int = 8) -> tuple[language_model.LanguageModel, ModelHub | None]:
    """The mock model, or a ChatModel over a fresh OpenRouter hub."""
    if model_name == "mock":
        return MockModel(), None
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set; source the secrets env file for real runs, or use --model mock.")
    hub = ModelHub(base_url=OPENROUTER_BASE_URL, api_key=api_key, call_log_path=call_log_path,
                   max_concurrency=max_concurrency)
    return ChatModel(hub, model_name), hub
