## Read-only projection of `love-town-replay/1`, the JSON that
## tools/export_polyworld_replay.py derives from a run's events.jsonl.
##
## Shape the viewer reads (everything else is passed through untouched for the
## HTML layer via `root`):
##
## {
##   "schema": "love-town-replay/1",
##   "source": {"path": "...", "sha256": "..."},                  optional
##   "run": {"name": "...", "days": N, "seed": s, "model": "..."},
##   "agents": [{"id", "name", "persona", "cash", "wearing"}],
##   "goods":  [{"id", "category", "tier", "list_price"}],
##   "days": [{
##     "day": 1,
##     "allocations": [{"agent", "hours": {"work","games","home","eat"},
##                      "therapy", "meditation", "wear", "shopping": [...],
##                      "invite", "accept_invite", "accept_move_in",
##                      "breakup", "profile_text"}],
##     "invites": [{"host", "guest", "accepted"}],
##     "market": {...},                                            passthrough
##     "profiles": [...], "swipes": [...],                         passthrough
##     "matches": [{"a", "b"}],
##     "dates": [{"a", "b", "scene", "turns": [{"speaker", "text"}],
##                "outcomes": [{"agent", "partner", "rating", "choice", "reason"}]}],
##     "relationships": [{"a", "b", "from", "to"}],
##     "gossip": [{"text", "about": [...]}],
##     "nights": [{"agent", "cash", "inventory": {...}, "wearing", "partner",
##                 "status", "sentence", "U", "U_hat", "visit_with"}],
##     "cost": {"calls", "usd"}
##   }],
##   "standings": [...]                                            optional
## }
##
## Agent references ("agent", "a", "b", "host", "guest", "partner",
## "speaker", "visit_with") may be an agent id or an agent name.

import std/[json, os, strutils, tables]

const ReplaySchema* = "love-town-replay/1"

type
  ReplayError* = object of CatchableError
  Agent* = object
    id*, name*, persona*: string
    cash*: float64
    wearing*: string
  Good* = object
    id*, category*, tier*: string
    listPrice*: float64
  Hours* = object
    work*, games*, home*, eat*: float32
  Allocation* = object
    agent*: int
    hours*: Hours
    therapy*, meditation*: bool
    wear*: string
    invite*, acceptInvite*: int
    acceptMoveIn*, breakup*: bool
    profileText*: string
  Invite* = object
    host*, guest*: int
    accepted*: bool
  Match* = object
    a*, b*: int
  DateTurn* = object
    speaker*: int
    text*: string
  DateOutcome* = object
    agent*, partner*: int
    rating*: float64
    choice*, reason*: string
  DateRecord* = object
    a*, b*: int
    scene*: string
    turns*: seq[DateTurn]
    outcomes*: seq[DateOutcome]
  RelationshipChange* = object
    a*, b*: int
    fromStatus*, toStatus*: string
  NightState* = object
    agent*: int
    cash*: float64
    inventory*: JsonNode
    wearing*, partnerName*, status*, sentence*: string
    partner*, visitWith*: int
    utility*, utilityHat*: float64
  Day* = object
    day*: int
    allocations*: seq[Allocation]
    invites*: seq[Invite]
    matches*: seq[Match]
    dates*: seq[DateRecord]
    relationships*: seq[RelationshipChange]
    gossip*: seq[string]
    nights*: seq[NightState]
  Replay* = object
    root*: JsonNode
    path*, run*, model*: string
    seed*, numDays*: int
    agents*: seq[Agent]
    goods*: seq[Good]
    days*: seq[Day]
    lookup: Table[string, int]

proc fail(message: string) {.noreturn.} =
  raise newException(ReplayError, message)

proc field(node: JsonNode, names: varargs[string]): JsonNode =
  if node == nil or node.kind != JObject:
    return nil
  for name in names:
    if node.hasKey(name) and node[name].kind != JNull:
      return node[name]

proc strField(node: JsonNode, names: varargs[string]): string =
  let value = node.field(names)
  if value != nil and value.kind == JString:
    result = value.getStr()

proc intField(node: JsonNode, names: varargs[string]; fallback = 0): int =
  let value = node.field(names)
  if value == nil:
    return fallback
  case value.kind
  of JInt: value.getInt()
  of JFloat: int(value.getFloat())
  else: fallback

proc floatField(node: JsonNode, names: varargs[string]): float64 =
  let fallback = 0.0
  let value = node.field(names)
  if value == nil:
    return fallback
  case value.kind
  of JInt: value.getInt().float64
  of JFloat: value.getFloat()
  else: fallback

proc boolField(node: JsonNode, names: varargs[string]): bool =
  let value = node.field(names)
  value != nil and value.kind == JBool and value.getBool()

proc items(node: JsonNode, name: string): seq[JsonNode] =
  let value = node.field(name)
  if value != nil and value.kind == JArray:
    for item in value:
      result.add item

proc agentIndex*(replay: Replay, reference: string): int =
  ## Resolves an agent id or name; -1 when unknown or empty.
  if reference.len == 0:
    return -1
  replay.lookup.getOrDefault(reference.toLowerAscii, -1)

proc agentRef(replay: Replay, node: JsonNode, names: varargs[string]): int =
  replay.agentIndex(node.strField(names))

proc agentName*(replay: Replay, index: int): string =
  if index >= 0 and index < replay.agents.len: replay.agents[index].name else: ""

proc agentId*(replay: Replay, index: int): string =
  if index >= 0 and index < replay.agents.len: replay.agents[index].id else: ""

proc goodTier*(replay: Replay, goodId: string): string =
  for good in replay.goods:
    if cmpIgnoreCase(good.id, goodId) == 0:
      return good.tier
  if goodId.len > 0: "Unknown" else: ""

proc parseHours(node: JsonNode): Hours =
  result.work = node.floatField("work").float32
  result.games = node.floatField("games").float32
  result.home = node.floatField("home").float32
  result.eat = node.floatField("eat", "eating").float32

proc parseDay(replay: Replay, node: JsonNode, expected: int): Day =
  result.day = node.intField("day", fallback = expected)
  for item in node.items("allocations"):
    var allocation = Allocation(
      agent: replay.agentRef(item, "agent", "name"),
      hours: parseHours(item.field("hours")),
      therapy: item.boolField("therapy"),
      meditation: item.boolField("meditation"),
      wear: item.strField("wear"),
      invite: replay.agentRef(item, "invite"),
      acceptInvite: replay.agentRef(item, "accept_invite"),
      acceptMoveIn: item.boolField("accept_move_in"),
      breakup: item.boolField("breakup"),
      profileText: item.strField("profile_text")
    )
    if allocation.agent >= 0:
      result.allocations.add allocation
  for item in node.items("invites"):
    let invite = Invite(
      host: replay.agentRef(item, "host", "name"),
      guest: replay.agentRef(item, "guest", "target"),
      accepted: item.boolField("accepted")
    )
    if invite.host >= 0 and invite.guest >= 0:
      result.invites.add invite
  for item in node.items("matches"):
    let match = Match(a: replay.agentRef(item, "a"), b: replay.agentRef(item, "b"))
    if match.a >= 0 and match.b >= 0:
      result.matches.add match
  for item in node.items("dates"):
    var date = DateRecord(
      a: replay.agentRef(item, "a"),
      b: replay.agentRef(item, "b"),
      scene: item.strField("scene", "text")
    )
    if date.a < 0 or date.b < 0:
      continue
    for turn in item.items("turns"):
      date.turns.add DateTurn(
        speaker: replay.agentRef(turn, "speaker"),
        text: turn.strField("text")
      )
    for outcome in item.items("outcomes"):
      date.outcomes.add DateOutcome(
        agent: replay.agentRef(outcome, "agent", "name"),
        partner: replay.agentRef(outcome, "partner"),
        rating: outcome.floatField("rating"),
        choice: outcome.strField("choice"),
        reason: outcome.strField("reason")
      )
    result.dates.add date
  for item in node.items("relationships"):
    let change = RelationshipChange(
      a: replay.agentRef(item, "a"),
      b: replay.agentRef(item, "b"),
      fromStatus: item.strField("from"),
      toStatus: item.strField("to")
    )
    if change.a >= 0 and change.b >= 0:
      result.relationships.add change
  for item in node.items("gossip"):
    let text = item.strField("text")
    if text.len > 0:
      result.gossip.add text
  for item in node.items("nights"):
    let night = NightState(
      agent: replay.agentRef(item, "agent", "name"),
      cash: item.floatField("cash"),
      inventory: item.field("inventory"),
      wearing: item.strField("wearing"),
      partnerName: item.strField("partner"),
      status: item.strField("status"),
      sentence: item.strField("sentence"),
      partner: replay.agentRef(item, "partner"),
      visitWith: replay.agentRef(item, "visit_with"),
      utility: item.floatField("U"),
      utilityHat: item.floatField("U_hat")
    )
    if night.agent >= 0:
      result.nights.add night

proc loadReplay*(path: string): Replay =
  if path.len == 0:
    fail("supply a love-town replay JSON path")
  if not fileExists(path):
    fail("replay not found: " & path)
  result.path = path
  try:
    result.root = parseFile(path)
  except JsonParsingError as error:
    fail("invalid replay JSON: " & error.msg)
  if result.root.kind != JObject or result.root.strField("schema") != ReplaySchema:
    fail("expected schema " & ReplaySchema)
  let run = result.root.field("run")
  result.run = run.strField("name")
  result.model = run.strField("model")
  result.seed = run.intField("seed")
  let agents = result.root.field("agents")
  if agents == nil or agents.kind != JArray or agents.len == 0:
    fail("replay has no agents")
  for node in agents:
    var agent = Agent(
      id: node.strField("id"),
      name: node.strField("name"),
      persona: node.strField("persona", "persona_summary"),
      cash: node.floatField("cash"),
      wearing: node.strField("wearing")
    )
    if agent.name.len == 0:
      agent.name = agent.id
    if agent.id.len == 0:
      agent.id = agent.name.toLowerAscii.replace(' ', '-')
    if agent.id.len == 0:
      fail("agent ids and names must be non-empty")
    if agent.id.toLowerAscii in result.lookup:
      fail("duplicate agent id: " & agent.id)
    result.lookup[agent.id.toLowerAscii] = result.agents.len
    if agent.name.toLowerAscii notin result.lookup:
      result.lookup[agent.name.toLowerAscii] = result.agents.len
    result.agents.add agent
  for node in result.root.items("goods"):
    result.goods.add Good(
      id: node.strField("id", "name"),
      category: node.strField("category"),
      tier: node.strField("tier"),
      listPrice: node.floatField("list_price", "base_price")
    )
  let days = result.root.field("days")
  if days == nil or days.kind != JArray or days.len == 0:
    fail("replay has no days array")
  for index, node in days.elems:
    result.days.add result.parseDay(node, index + 1)
  result.numDays = run.intField("days", fallback = result.days.len)
  if result.numDays > result.days.len:
    result.numDays = result.days.len

proc allocationFor*(day: Day, agent: int): int =
  for index, allocation in day.allocations:
    if allocation.agent == agent:
      return index
  -1

proc nightFor*(day: Day, agent: int): int =
  for index, night in day.nights:
    if night.agent == agent:
      return index
  -1

proc wearingBefore*(replay: Replay, dayIndex, agent: int): string =
  ## The garment on the agent's back at the start of a day: the previous
  ## recorded night, else the setup state.
  var index = dayIndex - 1
  while index >= 0:
    let night = replay.days[index].nightFor(agent)
    if night >= 0 and replay.days[index].nights[night].wearing.len > 0:
      return replay.days[index].nights[night].wearing
    dec index
  replay.agents[agent].wearing

proc wearingDuring*(replay: Replay, dayIndex, agent: int): string =
  ## The morning `wear` decision as validated by the engine, else the
  ## previous night's garment.
  let day = replay.days[dayIndex]
  let allocation = day.allocationFor(agent)
  if allocation >= 0 and day.allocations[allocation].wear.len > 0:
    return day.allocations[allocation].wear
  replay.wearingBefore(dayIndex, agent)

proc wearingAtNight*(replay: Replay, dayIndex, agent: int): string =
  ## The recorded night state, which reflects purchases made at the market.
  let day = replay.days[dayIndex]
  let night = day.nightFor(agent)
  if night >= 0 and day.nights[night].wearing.len > 0:
    return day.nights[night].wearing
  replay.wearingDuring(dayIndex, agent)
