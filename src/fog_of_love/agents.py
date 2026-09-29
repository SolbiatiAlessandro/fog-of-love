"""Agent state (ours) and the Concordia entity (Instructions + context + persona memories + observations)."""

from __future__ import annotations

import dataclasses
import json
import re
from typing import Any

import numpy as np
from concordia.agents import entity_agent_with_logging
from concordia.associative_memory import basic_associative_memory
from concordia.components import agent as agent_components
from concordia.language_model import language_model
from concordia.typing import entity as entity_lib

from fog_of_love import goods, prompts
from fog_of_love.needs import Needs
from fog_of_love.vendor import personas

OBSERVATION_HISTORY = 40


class DummyEmbedder:
    """Zero vectors: we only use recency retrieval, never associative retrieval."""

    def __init__(self, dimension: int = 8) -> None:
        self._zero = np.zeros(dimension, dtype=np.float32)

    def __call__(self, text: str) -> np.ndarray:
        return self._zero


@dataclasses.dataclass
class AgentState:
    name: str
    persona_summary: str
    cash: float
    wearing: str
    inventory: dict[str, int]
    needs: Needs
    games: dict[str, float] = dataclasses.field(default_factory=dict)  # game id -> current yield
    status: str = "single"  # single | dating | cohabiting
    partner: str | None = None
    partner_since: int | None = None  # day the current relationship started (dating), kept through cohabiting
    exes: dict[str, int] = dataclasses.field(default_factory=dict)  # name -> day of breakup
    profile_text: str = ""
    pending_invites: list[str] = dataclasses.field(default_factory=list)  # inviters, resolved next morning
    pending_move_in: str | None = None  # partner who proposed, resolved next morning
    last_sentence: str | None = None
    sum_u: float = 0.0
    # today's decision (reset each morning)
    hours: dict[str, int] = dataclasses.field(default_factory=dict)
    therapy: bool = False
    meditation: bool = False
    visit_with: str | None = None  # the other party of today's home visit
    home_hours_adjusted: bool = False  # home hours raised to cover an accepted visit
    date_tonight: str | None = None

    @property
    def meals(self) -> int:
        return sum(q for gid, q in self.inventory.items() if goods.category(gid) == "Food")

    def eat(self, meals: int) -> int:
        """Consumes up to `meals` meals (cheapest first); returns how many were eaten."""
        eaten = 0
        for gid in sorted((g for g in self.inventory if goods.category(g) == "Food"), key=goods.list_price):
            while eaten < meals and self.inventory.get(gid, 0) > 0:
                self.inventory[gid] -= 1
                if self.inventory[gid] == 0:
                    del self.inventory[gid]
                eaten += 1
        return eaten

    def owned_clothing(self) -> list[str]:
        return [g for g, q in self.inventory.items() if q > 0 and goods.category(g) == "Clothing"]

    def add_item(self, gid: str, qty: int) -> None:
        self.inventory[gid] = self.inventory.get(gid, 0) + qty
        if goods.category(gid) == "Games" and gid not in self.games:
            self.games[gid] = 1.0
        if goods.category(gid) == "Clothing":
            tiers = {"Low": 0, "Mid": 1, "High": 2}
            if tiers[goods.tier(gid)] > tiers[goods.tier(self.wearing)]:
                self.wearing = gid

    def status_line(self) -> str:
        if self.status == "cohabiting":
            return f"cohabiting with {self.partner}"
        if self.status == "dating":
            return f"dating {self.partner}"
        return "single"

    def public(self) -> dict[str, Any]:
        return {"name": self.name, "persona_summary": self.persona_summary, "cash": round(self.cash, 2),
                "wearing": self.wearing}


def persona_summary(name: str) -> str:
    """The `description` field of the persona line, or the first memory."""
    mems = personas.PERSONA_MEMORIES[name]
    for m in mems:
        if m.startswith("[Persona]"):
            try:
                return json.loads(m[len("[Persona]"):].strip()).get("description", m)
            except json.JSONDecodeError:
                return m
    return mems[0] if mems else name


def pick_names(num_agents: int, seed: int) -> list[str]:
    rng = np.random.default_rng(seed)
    names = list(personas.PERSONA_MEMORIES.keys())
    idx = rng.choice(len(names), size=min(num_agents, len(names)), replace=False)
    return [names[i] for i in idx]


def starting_cash(num_agents: int, seed: int) -> list[float]:
    """The signaling example's 'mixed' distribution (poor / middle / upper / rich), under the run seed."""
    np.random.seed(seed)
    return [round(float(c), 2) for c in personas.generate_cash_values("mixed", num_agents)]


def build_entity(name: str, model: language_model.LanguageModel) -> entity_agent_with_logging.EntityAgentWithLogging:
    """Concordia's default Instructions, the Love Town context, the persona memories, recent observations; one
    model call per act (ConcatActComponent, no intermediate questions)."""
    memory_bank = basic_associative_memory.AssociativeMemoryBank(sentence_embedder=DummyEmbedder())
    memory = agent_components.memory.AssociativeMemory(memory_bank=memory_bank)
    instructions = agent_components.instructions.Instructions(agent_name=name, pre_act_label="\nInstructions")
    context = agent_components.constant.Constant(state=prompts.CONTEXT, pre_act_label="\nContext")
    persona = agent_components.constant.Constant(
        state="\n".join(personas.PERSONA_MEMORIES[name]), pre_act_label=f"\nMemories of {name}"
    )
    observation_to_memory = agent_components.observation.ObservationToMemory()
    observation = agent_components.observation.LastNObservations(
        history_length=OBSERVATION_HISTORY, pre_act_label="\nRecent events (oldest to latest)"
    )
    components = {
        "Instructions": instructions,
        "Context": context,
        "Persona": persona,
        "ObservationToMemory": observation_to_memory,
        agent_components.observation.DEFAULT_OBSERVATION_COMPONENT_KEY: observation,
        agent_components.memory.DEFAULT_MEMORY_COMPONENT_KEY: memory,
    }
    act = agent_components.concat_act_component.ConcatActComponent(
        model=model, component_order=list(components.keys()), prefix_entity_name=False, randomize_choices=False
    )
    return entity_agent_with_logging.EntityAgentWithLogging(agent_name=name, act_component=act, context_components=components)


# ---- JSON from the model ------------------------------------------------------------------------

def extract_json(text: str) -> dict[str, Any] | None:
    """The first balanced {...} block that parses as a JSON object (code fences tolerated)."""
    if not text:
        return None
    text = text.replace("```json", "```").replace("```", "")
    start = text.find("{")
    while start >= 0:
        depth = 0
        for i in range(start, len(text)):
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start:i + 1]
                    try:
                        obj = json.loads(chunk)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        cleaned = re.sub(r",\s*([}\]])", r"\1", chunk)
                        try:
                            obj = json.loads(cleaned)
                            if isinstance(obj, dict):
                                return obj
                        except json.JSONDecodeError:
                            pass
                    break
        start = text.find("{", start + 1)
    return None


def ask_json(entity, call_to_action: str) -> tuple[dict[str, Any] | None, str]:
    """Acts with a free-text spec, parses JSON; on failure retries once with a stricter instruction.
    Returns (parsed or None, raw text of the last attempt)."""
    raw = entity.act(entity_lib.free_action_spec(call_to_action=call_to_action))
    obj = extract_json(raw)
    if obj is not None:
        return obj, raw
    raw = entity.act(entity_lib.free_action_spec(call_to_action=call_to_action + prompts.retry_suffix()))
    return extract_json(raw), raw


def ask_text(entity, call_to_action: str) -> str:
    return entity.act(entity_lib.free_action_spec(call_to_action=call_to_action))
