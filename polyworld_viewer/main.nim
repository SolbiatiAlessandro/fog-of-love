## Fog of Love — Love Town 3D replay viewer on the Polyworld renderer.
## Movement, seating and timing are staged deterministically from the
## recorded love-town-replay/1 facts; nothing else is invented.

import std/[json, math, os, strformat, strutils, times, algorithm]
import chroma, opengl, pixie, vmath, windy
import polyworld/[inputs, shapes, viewers]
import replay_model, town

when not defined(emscripten):
  import silky
  import polyworld/gameuis

when defined(emscripten):
  {.emit: "#include <emscripten.h>".}

const
  WindowTitle = "Fog of Love — Love Town (Polyworld)"
  UiHeight = 150.0'f32
  DaySeconds = 60.0'f32
  MorningEnd = 3.0'f32
  DayEnd = 26.0'f32
  AppEnd = 29.0'f32
  DateEnd = 51.0'f32
  VisitEnd = 55.0'f32
  DateWalkAllowance = 2.4'f32
  AutoSwitchSeconds = 30.0
  SceneHalf = 90.0'f32
  AvenueZ = 0.0'f32
  PromenadeZ = 4.6'f32

type
  Activity = enum
    actHome = "home", actWork = "work", actEat = "eating", actGames = "games",
    actTherapy = "therapy", actMeditate = "meditation", actApp = "app",
    actDate = "date", actVisit = "visit", actNight = "night"
  Anchor = object
    frame: Frame          ## the spot itself
    via: seq[Vec3]        ## route from the spot out to the avenue (last on z = 0)
  Stop = object
    start: float32        ## day-relative seconds when the agent sets off
    anchor: Anchor
    activity: Activity
    pose: Pose
    prop: Prop
    seat: int             ## table index for dates, else -1
    partner: int
    path: seq[Vec3]       ## route from wherever the agent was at `start`
    pathLength: float32
  Town = object
    houses: seq[Anchor]         ## per house slot: porch spot
    houseFrames: seq[Frame]     ## house body frames
    desks: seq[Anchor]
    tables: array[2, Vec3]
    tableSeats: array[2, array[2, Anchor]]
    stools: seq[Anchor]
    couch: seq[Anchor]
    cushions: seq[Anchor]
    workFrame, restaurantFrame, therapyFrame, gardenFrame: Frame
    lamps: seq[Vec3]
    trees: seq[Vec3]
  DayPlan = object
    stops: seq[seq[Stop]]       ## per agent
    dateRounds: int
    roundLength: float32
  AgentState = object
    position: Vec3
    yaw: float32
    pose: Pose
    prop: Prop
    activity: Activity
    walking: bool
    partner, seat: int
  ViewerOptions = object
    replayPath: string
    playing: bool
    speed: int
    seek: float32
    follow: string
    auto: bool
    trace: bool
    width, height: int32
    zoom: float32

var window: Window

proc parseOptions(): ViewerOptions =
  result.width = 1280
  result.height = 800
  result.speed = 1
  result.auto = true
  result.zoom = 1
  when defined(emscripten): result.replayPath = "/replay.json"
  let args = commandLineParams()
  var i = 0
  while i < args.len:
    case args[i]
    of "--play": result.playing = true
    of "--no-auto": result.auto = false
    of "--trace": result.trace = true
    of "--speed":
      inc i
      if i >= args.len: raise newException(ValueError, "--speed needs a value")
      result.speed = parseInt(args[i])
      if result.speed notin [1, 2, 4, 16]:
        raise newException(ValueError, "--speed must be 1, 2, 4, or 16")
    of "--seek":
      inc i
      if i >= args.len: raise newException(ValueError, "--seek needs seconds")
      result.seek = parseFloat(args[i]).float32
    of "--follow":
      inc i
      if i >= args.len: raise newException(ValueError, "--follow needs an agent id or name")
      result.follow = args[i]
    of "--zoom":
      inc i
      if i >= args.len: raise newException(ValueError, "--zoom needs a factor")
      result.zoom = parseFloat(args[i]).float32
    of "--windowSize":
      inc i
      if i >= args.len: raise newException(ValueError, "--windowSize needs WIDTHxHEIGHT")
      let fields = args[i].toLowerAscii.split('x')
      if fields.len != 2: raise newException(ValueError, "--windowSize needs WIDTHxHEIGHT")
      result.width = parseInt(fields[0]).int32
      result.height = parseInt(fields[1]).int32
    of "--help", "-h":
      echo "lovetown-polyworld REPLAY.json [--play] [--speed 1|2|4|16] [--seek SECONDS]"
      echo "  [--follow AGENT] [--no-auto] [--zoom F] [--windowSize WxH]"
      quit(0)
    else:
      if args[i].startsWith("-"): raise newException(ValueError, "unknown option: " & args[i])
      if result.replayPath.len > 0 and result.replayPath != "/replay.json":
        raise newException(ValueError, "only one replay path is allowed")
      result.replayPath = args[i]
    inc i

## Town layout

proc spotOf(anchor: Anchor, offset: Vec3): Anchor =
  ## The same route, standing a little off the anchor (guests, couples).
  result = anchor
  result.frame.origin = anchor.frame.world(offset)
  if result.via.len > 0:
    result.via[0] = result.frame.origin

proc buildTown(agentCount: int): Town =
  # Houses on four short streets running north from the avenue; slots fill
  # from the centre streets outward, three rows, both sides.
  const streetX = [-8.0'f32, 8.0, -23.0, 23.0]
  let slots = max(agentCount, 1)
  for i in 0 ..< slots:
    let
      street = streetX[(i div 6) mod streetX.len]
      row = (i mod 6) div 2
      side = if (i mod 2) == 0: -1'f32 else: 1'f32
      z = -7.0'f32 - row.float32 * 6.0'f32
      x = street + side * 5.2'f32
      yaw = if side < 0: PI.float32 / 2 else: -PI.float32 / 2
      body = frame(vec3(x, 0, z), yaw)
      porch = body.world(vec3(0, 0, 2.7))
    result.houseFrames.add body
    result.houses.add Anchor(frame: frame(porch, yaw),
      via: @[porch, vec3(street, 0, z), vec3(street, 0, AvenueZ)])
  # Workspace south-west of the avenue, open front facing north.
  result.workFrame = frame(vec3(-14.5, 0, 14.5), PI.float32)
  for i in 0 ..< 24:
    let column = i mod 6
    let row = i div 6
    let local = vec3(-7.5'f32 + column.float32 * 3.0'f32, 0, -3.5'f32 + row.float32 * 2.2'f32)
    let seat = result.workFrame.world(local)
    result.desks.add Anchor(frame: frame(seat, PI.float32),
      via: @[seat, vec3(seat.x, 0, PromenadeZ), vec3(seat.x, 0, AvenueZ)])
  # Restaurant south-centre with two patio tables and a bar counter.
  result.restaurantFrame = frame(vec3(4, 0, 15.5), PI.float32)
  result.tables = [vec3(0.4, 0, 8.6), vec3(7.6, 0, 8.6)]
  for t in 0 ..< 2:
    let table = result.tables[t]
    for s in 0 ..< 2:
      let side = if s == 0: 1'f32 else: -1'f32
      let seat = table + vec3(side * 1.35, 0, 0)
      let yaw = if s == 0: -PI.float32 / 2 else: PI.float32 / 2
      result.tableSeats[t][s] = Anchor(frame: frame(seat, yaw),
        via: @[seat, vec3(seat.x, 0, PromenadeZ), vec3(seat.x, 0, AvenueZ)])
  for i in 0 ..< 8:
    let seat = result.restaurantFrame.world(vec3(-3.8'f32 + i.float32 * 1.08'f32, 0, 2.05))
    result.stools.add Anchor(frame: frame(seat, PI.float32),
      via: @[seat, vec3(seat.x, 0, PromenadeZ), vec3(seat.x, 0, AvenueZ)])
  # Therapy office to the east, couch along the back wall.
  result.therapyFrame = frame(vec3(16.5, 0, 13), PI.float32)
  for i in 0 ..< 6:
    let seat = result.therapyFrame.world(vec3(-2.6'f32 + i.float32 * 1.05'f32, 0, -2.2))
    result.couch.add Anchor(frame: frame(seat, PI.float32),
      via: @[seat, vec3(seat.x, 0, PromenadeZ), vec3(seat.x, 0, AvenueZ)])
  # Meditation garden at the east end.
  result.gardenFrame = frame(vec3(26.5, 0, 9), PI.float32)
  for i in 0 ..< 12:
    let a = TAU.float32 * i.float32 / 12 + 0.26
    let seat = result.gardenFrame.origin + vec3(cos(a) * 3.6, 0, sin(a) * 3.6)
    let yaw = yawTowards(seat, result.gardenFrame.origin)
    result.cushions.add Anchor(frame: frame(seat, yaw),
      via: @[seat, vec3(25, 0, PromenadeZ), vec3(25, 0, AvenueZ)])
  for x in [-29'f32, -18, -13, -3, 3, 13, 18, 29]:
    result.lamps.add vec3(x, 0, -2.6)
    result.lamps.add vec3(x, 0, 2.6)
  for i, x in [-36'f32, -30, -24, -18, -12, -6, 0, 6, 12, 18, 24, 30, 36]:
    if i mod 2 == 0: result.trees.add vec3(x, 0, -27.5)
  for p in [vec3(-40, 0, 6), vec3(-40, 0, 18), vec3(-6, 0, 16), vec3(15, 0, 18),
      vec3(31, 0, 18), vec3(47, 0, 4), vec3(47, 0, 16), vec3(-44, 0, -8), vec3(44, 0, -8),
      vec3(-44, 0, -20), vec3(44, 0, -20), vec3(-18, 0, -27), vec3(18, 0, -27),
      vec3(0, 0, -30), vec3(-36, 0, -28), vec3(36, 0, -28)]:
    result.trees.add p

## Staging

proc homeSlot(replay: Replay, dayIndex, agent: int): int =
  ## The house an agent lives in at the start of a day: cohabiting pairs share
  ## the lower-indexed partner's house from the night they moved in.
  result = agent
  var index = dayIndex - 1
  while index >= 0:
    let day = replay.days[index]
    let night = day.nightFor(agent)
    if night >= 0:
      let state = day.nights[night]
      if state.status == "cohabiting" and state.partner >= 0:
        return min(agent, state.partner)
      return agent
    dec index

proc nightSlot(replay: Replay, dayIndex, agent: int): int =
  let day = replay.days[dayIndex]
  let night = day.nightFor(agent)
  if night >= 0:
    let state = day.nights[night]
    if state.status == "cohabiting" and state.partner >= 0:
      return min(agent, state.partner)
  agent

type Interval = object
  agent: int
  start, finish: float32

proc assignSeats(intervals: seq[Interval], seatCount: int): seq[int] =
  ## Greedy interval seating: the first seat whose previous occupant has left.
  ## Overflow gets a negative standing slot.
  result = newSeq[int](intervals.len)
  var order = newSeq[int](intervals.len)
  for i in 0 ..< order.len: order[i] = i
  order.sort(proc(a, b: int): int = cmp(intervals[a].start, intervals[b].start))
  var freeAt = newSeq[float32](max(seatCount, 1))
  var overflow = 0
  for k in order:
    var seat = -1
    for s in 0 ..< seatCount:
      if freeAt[s] <= intervals[k].start + 0.001:
        seat = s
        break
    if seat < 0:
      seat = -1 - (overflow mod 8)
      inc overflow
    else:
      freeAt[seat] = intervals[k].finish
    result[k] = seat

proc pathBetween(a, b: Anchor): seq[Vec3] =
  ## Route along the streets: out to the avenue, along it, in to the target.
  ## Venues south of the avenue share a promenade, so a walk between two of
  ## them stays on it instead of dropping to the avenue and back.
  var outbound = a.via
  var inbound = b.via
  if a.via.len >= 3 and b.via.len >= 3 and a.via[^2].z > 0 and
      abs(a.via[^2].z - b.via[^2].z) < 0.01:
    outbound = a.via[0 ..< ^1]
    inbound = b.via[0 ..< ^1]
  result = outbound
  for i in countdown(inbound.high, 0):
    if result.len == 0 or dist(result[^1], inbound[i]) > 0.05:
      result.add inbound[i]

proc polylineLength(points: seq[Vec3]): float32 =
  for i in 1 ..< points.len:
    result += dist(points[i - 1], points[i])

proc pointAlong(points: seq[Vec3], distanceAlong: float32):
    tuple[p: Vec3, yaw: float32, moving: bool] =
  if points.len == 0: return (vec3(0), 0'f32, false)
  var remaining = distanceAlong
  for i in 1 ..< points.len:
    let segment = dist(points[i - 1], points[i])
    if segment <= 0.0001: continue
    if remaining <= segment:
      let t = remaining / segment
      return (mix(points[i - 1], points[i], t), yawTowards(points[i - 1], points[i]), true)
    remaining -= segment
  (points[^1], (if points.len >= 2: yawTowards(points[^2], points[^1]) else: 0'f32), false)

proc standingSpot(near: Anchor, index: int): Anchor =
  ## Overflow visitors wait outside the venue in a short row.
  let spot = near.via[^2] + vec3(-2.2'f32 + index.float32 * 1.1'f32, 0, 1.2)
  Anchor(frame: frame(spot, PI.float32), via: @[spot, vec3(spot.x, 0, PromenadeZ), vec3(spot.x, 0, AvenueZ)])

proc venueSeat(town: Town, kind: Activity, seat: int): Anchor =
  case kind
  of actEat:
    if seat >= 0 and seat < town.stools.len: town.stools[seat]
    elif seat >= town.stools.len and seat < town.stools.len + 4:
      town.tableSeats[(seat - town.stools.len) div 2][(seat - town.stools.len) mod 2]
    else: standingSpot(town.stools[0], -1 - seat)
  of actTherapy:
    if seat >= 0 and seat < town.couch.len: town.couch[seat]
    else: standingSpot(town.couch[0], -1 - seat)
  of actMeditate:
    if seat >= 0 and seat < town.cushions.len: town.cushions[seat]
    else: standingSpot(town.cushions[0], -1 - seat)
  else: town.desks[max(seat, 0) mod town.desks.len]

type Segment = tuple[activity: Activity, hours: float32]

proc segmentLengths(list: seq[Segment], walkSeconds: seq[float32]): seq[float32] =
  ## Day time in proportion to the allocated hours, with a floor per segment
  ## of its walk there plus a moment of presence, so a one-hour activity is
  ## still reached and seen. Segments above their floor absorb the cost.
  const PresenceSeconds = 1.5'f32
  let span = DayEnd - MorningEnd
  var total = 0'f32
  for s in list: total += s.hours
  result = newSeq[float32](list.len)
  var floors = newSeq[float32](list.len)
  for i, s in list:
    result[i] = span * s.hours / max(total, 0.001)
    floors[i] = walkSeconds[i] + PresenceSeconds
  for _ in 0 ..< 4:
    var fixedSum = 0'f32
    var flexibleHours = 0'f32
    for i, s in list:
      if result[i] <= floors[i]:
        result[i] = floors[i]
        fixedSum += floors[i]
      else:
        flexibleHours += s.hours
    let remaining = span - fixedSum
    if remaining <= 0 or flexibleHours <= 0: break
    for i, s in list:
      if result[i] > floors[i]:
        result[i] = max(remaining * s.hours / flexibleHours, floors[i])
  var sum = 0'f32
  for value in result: sum += value
  if sum > span:
    for i in 0 ..< result.len: result[i] *= span / sum

proc planDay(replay: Replay, town: Town, dayIndex: int): DayPlan =
  let day = replay.days[dayIndex]
  let n = replay.agents.len
  result.stops = newSeq[seq[Stop]](n)
  var segments = newSeq[seq[Segment]](n)
  var walks = newSeq[seq[float32]](n)
  var eat, therapy, meditate: seq[Interval]
  var eatIndex = newSeq[int](n)
  var therapyIndex = newSeq[int](n)
  var meditateIndex = newSeq[int](n)
  for i in 0 ..< n:
    let a = day.allocationFor(i)
    var work, games, home, eatHours = 0'f32
    var hasTherapy, hasMeditation = false
    if a >= 0:
      let allocation = day.allocations[a]
      work = allocation.hours.work; games = allocation.hours.games
      home = allocation.hours.home; eatHours = allocation.hours.eat
      hasTherapy = allocation.therapy; hasMeditation = allocation.meditation
    let therapyHours = if hasTherapy: 1'f32 else: 0'f32
    let meditationHours = if hasMeditation: 1'f32 else: 0'f32
    var list: seq[Segment]
    template addSeg(kind: Activity, hours: float32) =
      if hours > 0: list.add((kind, hours))
    # Orders differ by agent so the restaurant and garden fill through the day.
    case i mod 3
    of 0:
      addSeg(actWork, work); addSeg(actEat, eatHours); addSeg(actTherapy, therapyHours)
      addSeg(actMeditate, meditationHours); addSeg(actGames, games); addSeg(actHome, home)
    of 1:
      addSeg(actEat, eatHours); addSeg(actWork, work); addSeg(actTherapy, therapyHours)
      addSeg(actMeditate, meditationHours); addSeg(actHome, home); addSeg(actGames, games)
    else:
      addSeg(actWork, work); addSeg(actTherapy, therapyHours); addSeg(actEat, eatHours)
      addSeg(actMeditate, meditationHours); addSeg(actGames, games); addSeg(actHome, home)
    if list.len == 0: list.add((actHome, 16'f32))
    segments[i] = list
    # Walk estimates use the venue's first seat; seats are booked below.
    var walkSeconds: seq[float32]
    var previous = town.houses[replay.homeSlot(dayIndex, i) mod town.houses.len]
    for s in list:
      let next = if s.activity in {actWork, actEat, actTherapy, actMeditate}:
          town.venueSeat(s.activity, (if s.activity == actWork: i else: 0))
        else: town.houses[replay.homeSlot(dayIndex, i) mod town.houses.len]
      walkSeconds.add polylineLength(pathBetween(previous, next)) / WalkSpeed
      previous = next
    walks[i] = walkSeconds
    var clock = MorningEnd
    eatIndex[i] = -1; therapyIndex[i] = -1; meditateIndex[i] = -1
    let lengths = segmentLengths(list, walkSeconds)
    for index, s in list:
      let length = lengths[index]
      case s.activity
      of actEat:
        eatIndex[i] = eat.len
        eat.add Interval(agent: i, start: clock, finish: clock + length)
      of actTherapy:
        therapyIndex[i] = therapy.len
        therapy.add Interval(agent: i, start: clock, finish: clock + length)
      of actMeditate:
        meditateIndex[i] = meditate.len
        meditate.add Interval(agent: i, start: clock, finish: clock + length)
      else: discard
      clock += length
  let eatSeats = assignSeats(eat, town.stools.len + 4)
  let therapySeats = assignSeats(therapy, town.couch.len)
  let meditateSeats = assignSeats(meditate, town.cushions.len)
  # Dates: rounds of two tables.
  result.dateRounds = max((day.dates.len + 1) div 2, 1)
  result.roundLength = (DateEnd - AppEnd) / result.dateRounds.float32
  var dateOf = newSeq[int](n)
  for i in 0 ..< n: dateOf[i] = -1
  for d, date in day.dates:
    if dateOf[date.a] < 0: dateOf[date.a] = d
    if dateOf[date.b] < 0: dateOf[date.b] = d
  # Visits: accepted invites, else the recorded night visit_with pairs.
  var visitHost = newSeq[int](n)
  for i in 0 ..< n: visitHost[i] = -1
  for invite in day.invites:
    if invite.accepted and visitHost[invite.guest] < 0 and invite.host != invite.guest:
      visitHost[invite.guest] = invite.host
  if day.invites.len == 0:
    for night in day.nights:
      if night.visitWith >= 0 and night.agent > night.visitWith and visitHost[night.agent] < 0:
        visitHost[night.agent] = night.visitWith
  for i in 0 ..< n:
    let home = replay.homeSlot(dayIndex, i)
    # Cohabiting residents share a porch, each on their own side of the door.
    let homeOffset = if home != i: (if i < home: -0.7'f32 else: 0.7'f32) else:
      (block:
        var shared = 0'f32
        for other in 0 ..< n:
          if other != i and replay.homeSlot(dayIndex, other) == home:
            shared = if i < other: -0.7'f32 else: 0.7'f32
        shared)
    let houseAnchor = town.houses[home mod town.houses.len].spotOf(vec3(homeOffset, 0, 0))
    var stops: seq[Stop]
    proc push(t: float32, where: Anchor, kind: Activity, p: Pose, pr: Prop,
        seatIndex = -1, other = -1) =
      stops.add Stop(start: t, anchor: where, activity: kind, pose: p, prop: pr,
        seat: seatIndex, partner: other)
    var clock = MorningEnd
    let lengths = segmentLengths(segments[i], walks[i])
    for index, s in segments[i]:
      let length = lengths[index]
      case s.activity
      of actWork: push(clock, town.desks[i mod town.desks.len], actWork, poseSit, propNone)
      of actEat:
        let seat = eatSeats[eatIndex[i]]
        push(clock, town.venueSeat(actEat, seat), actEat, (if seat >= 0: poseSit else: poseStand), propCup)
      of actTherapy:
        let seat = therapySeats[therapyIndex[i]]
        push(clock, town.venueSeat(actTherapy, seat), actTherapy, (if seat >= 0: poseLounge else: poseStand), propNone)
      of actMeditate:
        let seat = meditateSeats[meditateIndex[i]]
        push(clock, town.venueSeat(actMeditate, seat), actMeditate, (if seat >= 0: poseCrossLegged else: poseStand), propNone)
      of actGames: push(clock, houseAnchor, actGames, poseStand, propController)
      else: push(clock, houseAnchor, actHome, poseStand, propBook)
      clock += length
    # Evening on the app, at home.
    push(DayEnd, houseAnchor, actApp, poseStand, propPhone)
    if dateOf[i] >= 0:
      let d = dateOf[i]
      let date = day.dates[d]
      let table = d mod 2
      let seat = if date.a == i: 0 else: 1
      let other = if date.a == i: date.b else: date.a
      let roundStart = AppEnd + (d div 2).float32 * result.roundLength
      push(roundStart, town.tableSeats[table][seat], actDate, poseSit, propNone, table, other)
      push(roundStart + result.roundLength, houseAnchor, actHome, poseStand, propNone)
    if visitHost[i] >= 0:
      let hostAnchor = town.houses[replay.homeSlot(dayIndex, visitHost[i]) mod town.houses.len]
      push(DateEnd, hostAnchor.spotOf(vec3(-0.9, 0, 0.2)), actVisit, poseStand, propNone, -1, visitHost[i])
    else:
      var hosting = -1
      for guest in 0 ..< n:
        if visitHost[guest] == i: hosting = guest
      if hosting >= 0:
        push(DateEnd, houseAnchor.spotOf(vec3(0.9, 0, 0.2)), actVisit, poseStand, propNone, -1, hosting)
    let nightHome = replay.nightSlot(dayIndex, i)
    let nightAnchor = town.houses[nightHome mod town.houses.len]
    let nightOffset = if nightHome != i: (if i < nightHome: -0.7'f32 else: 0.7'f32) else:
      (block:
        var shared = 0'f32
        for other in 0 ..< n:
          if other != i and replay.nightSlot(dayIndex, other) == nightHome:
            shared = if i < other: -0.7'f32 else: 0.7'f32
        shared)
    push(VisitEnd, nightAnchor.spotOf(vec3(nightOffset, 0, 0)), actNight, poseStand, propNone)
    # Routes: each stop's path starts where the agent actually was when the
    # stop began (it may still have been walking).
    var position = houseAnchor.frame.origin
    var previous = houseAnchor
    var atRest = true
    for k in 0 ..< stops.len:
      let destination = stops[k].anchor.frame.origin
      var route: seq[Vec3]
      if dist(position, destination) < 0.05:
        route = @[destination]
      elif atRest:
        route = pathBetween(previous, stops[k].anchor)
      else:
        route = @[position, vec3(position.x, 0, AvenueZ)]
        for j in countdown(stops[k].anchor.via.high, 0):
          if dist(route[^1], stops[k].anchor.via[j]) > 0.05:
            route.add stops[k].anchor.via[j]
      stops[k].path = route
      stops[k].pathLength = polylineLength(route)
      let nextStart = if k + 1 < stops.len: stops[k + 1].start else: DaySeconds
      let travelled = (nextStart - stops[k].start) * WalkSpeed
      atRest = travelled >= stops[k].pathLength
      position = pointAlong(route, min(travelled, stops[k].pathLength)).p
      previous = stops[k].anchor
    result.stops[i] = stops

proc stateAt(plan: DayPlan, agent: int, s: float32): AgentState =
  let stops = plan.stops[agent]
  var k = 0
  for index in 0 ..< stops.len:
    if stops[index].start <= s: k = index
  let stop = stops[k]
  let travelled = (s - stop.start) * WalkSpeed
  let along = pointAlong(stop.path, min(travelled, stop.pathLength))
  result.activity = stop.activity
  result.partner = stop.partner
  result.seat = stop.seat
  if travelled < stop.pathLength and stop.pathLength > 0.05:
    result.position = along.p
    result.yaw = along.yaw
    result.pose = poseWalk
    result.walking = true
    result.prop = propNone
  else:
    result.position = stop.anchor.frame.origin
    result.yaw = stop.anchor.frame.yaw
    result.pose = stop.pose
    result.prop = stop.prop

proc hourAt(s: float32): float32 =
  if s < MorningEnd: 6.5'f32 + s / MorningEnd * 0.5'f32
  elif s < DayEnd: 7'f32 + (s - MorningEnd) / (DayEnd - MorningEnd) * 11'f32
  elif s < AppEnd: 18'f32 + (s - DayEnd) / (AppEnd - DayEnd)
  elif s < DateEnd: 19'f32 + (s - AppEnd) / (DateEnd - AppEnd) * 2.5'f32
  elif s < VisitEnd: 21.5'f32 + (s - DateEnd) / (VisitEnd - DateEnd) * 1.5'f32
  else: 23'f32 + (s - VisitEnd) / (DaySeconds - VisitEnd)

proc phaseAt(s: float32): string =
  if s < MorningEnd: "morning"
  elif s < DayEnd: "day"
  elif s < AppEnd: "app"
  elif s < DateEnd: "date"
  elif s < VisitEnd: "visit"
  else: "night"

proc smoothstep(t: float32): float32 =
  let x = clamp(t, 0, 1)
  x * x * (3 - 2 * x)

proc screenPosition(p: Vec3, matrix: Mat4, size: IVec2): Vec2 =
  let clip = matrix * vec4(p.x, p.y, p.z, 1)
  if clip.w <= 0: return vec2(-10000)
  vec2((clip.x / clip.w * 0.5 + 0.5) * size.x.float32, (0.5 - clip.y / clip.w * 0.5) * size.y.float32)

proc normalizedPosition(p: Vec3, matrix: Mat4): tuple[x, y: float32, visible: bool] =
  let clip = matrix * vec4(p.x, p.y, p.z, 1)
  if clip.w <= 0: return (-1'f32, -1'f32, false)
  result.x = clip.x / clip.w * 0.5 + 0.5
  result.y = 0.5 - clip.y / clip.w * 0.5
  result.visible = result.x >= 0 and result.x <= 1 and result.y >= 0 and result.y <= 1

proc shortMoney(value: float64): string =
  if abs(value) >= 1_000_000: &"${value / 1_000_000:.1f}M"
  elif abs(value) >= 10_000: &"${value / 1_000:.1f}K"
  else: &"${value:.2f}"

## Bridge

var commandQueue: seq[string]
var latestState = "{}"

proc lovetownCommand(cmd: cstring) {.exportc: "lovetownCommand", cdecl.} =
  ## Queues one command: play | pause | toggle | speed <1|2|4|16> |
  ## seek <seconds> | day <n> | follow <agentId|name|none> | auto <0|1>.
  commandQueue.add $cmd

proc lovetownState(): cstring {.exportc: "lovetownState", cdecl.} =
  ## The latest per-frame state as JSON (see publishState).
  latestState.cstring

when defined(emscripten):
  proc takeBrowserCommand(): cstring =
    {.emit: """
    `result` = (char*)EM_ASM_PTR({
      var q = Module.lovetownCommand;
      if (!Array.isArray(q) || !q.length) return 0;
      var c = q.shift();
      if (c && typeof c === 'object') {
        var t = c.type || c.cmd || '';
        var v = c.value !== undefined ? c.value : (c.speed !== undefined ? c.speed :
          c.t !== undefined ? c.t : c.seconds !== undefined ? c.seconds :
          c.agentId !== undefined ? c.agentId : c.agent !== undefined ? c.agent :
          c.day !== undefined ? c.day : c.enabled !== undefined ? (c.enabled ? 1 : 0) : '');
        c = (t + ' ' + v).trim();
      }
      return stringToNewUTF8(String(c));
    });
    """.}
  proc freeBrowserString(p: cstring) =
    {.emit: "free((void*)`p`);".}
  proc publishReady(agentCount, days: int32) =
    {.emit: """
    EM_ASM({ if (Module.lovetownReady) Module.lovetownReady({schema: 'love-town-replay/1', agents: $0, days: $1, daySeconds: 60}); }, `agentCount`, `days`);
    """.}
  proc publishState(payload: cstring) =
    {.emit: """
    EM_ASM({ if (typeof Module.lovetownState === 'function') { try { Module.lovetownState(JSON.parse(UTF8ToString($0))); } catch (error) { if (!Module.lovetownBridgeError) { Module.lovetownBridgeError = true; console.error('Love Town bridge callback failed', error); } } } }, `payload`);
    """.}

## Native HUD text

when not defined(emscripten):
  proc drawTinyText(sk: Silky, text: string, origin: Vec2, color: ColorRGBX,
      scale = 2.0'f32, maxChars = 0, maxLines = 1) =
    let advance = 6 * scale
    var x, line = 0
    for ch in text:
      if ch == '\n' or (maxChars > 0 and x >= maxChars):
        inc line
        x = 0
        if line >= maxLines: break
        if ch == '\n': continue
      let rows = glyphRows(ch)
      for row in 0 ..< 7:
        for column in 0 ..< 5:
          if rows[row][column] == '1':
            sk.drawRect(origin + vec2(x.float32 * advance + column.float32 * scale,
              line.float32 * 9 * scale + row.float32 * scale), vec2(scale), color)
      inc x

proc main() =
  let options = parseOptions()
  let replay = loadReplay(options.replayPath)
  let n = replay.agents.len
  let town = buildTown(n)
  var plans: seq[DayPlan]
  for d in 0 ..< replay.numDays:
    plans.add planDay(replay, town, d)
  let totalSeconds = replay.numDays.float32 * DaySeconds
  var looks = newSeq[Look](n)
  for i in 0 ..< n: looks[i] = lookFor(i)
  # House colours per slot.
  const walls = [c(244, 214, 190), c(214, 228, 200), c(240, 236, 210), c(206, 220, 236),
    c(238, 206, 214), c(226, 222, 236)]
  const roofs = [c(176, 82, 74), c(96, 112, 140), c(150, 96, 70), c(88, 128, 104), c(130, 84, 110)]

  when not defined(emscripten):
    let atlasPath = getTempDir() / "lovetown-polyworld-atlas.png"
    let atlas = newAtlasBuilder(32, 1)
    atlas.write(atlasPath)
  window = newWindow(WindowTitle, ivec2(options.width, options.height), vsync = true)
  window.makeContextCurrent()
  loadExtensions()
  when not defined(emscripten):
    let sk = newSilky(window, atlasPath)
  var renderer = initShapeRenderer()

  var
    playing = options.playing
    speed = options.speed
    clock = clamp(options.seek, 0, totalSeconds - 0.001)
    followed = 0
    autoFollow = options.auto
    sinceSwitch = 0.0
    cameraYaw = 0.6'f32
    cameraTarget = vec3(0, 1.1, 0)
    cameraDistance = 7.5'f32
    cameraPitch = 0.42'f32
    cameraZoom = options.zoom
    lastFrame = epochTime()
    screenshotFrame = 0
    smoothed = newSeq[Vec3](n)
    smoothedYaw = newSeq[float32](n)
    wallClock = 0.0
    cameraSnap = 2   ## frames left in which the camera jumps to its target
  if options.follow.len > 0:
    let index = replay.agentIndex(options.follow)
    if index >= 0: followed = index
  for i in 0 ..< n:
    let state = plans[0].stateAt(i, 0)
    smoothed[i] = state.position
    smoothedYaw[i] = state.yaw

  proc dayIndexAt(t: float32): int = clamp(int(t / DaySeconds), 0, replay.numDays - 1)

  proc pickNextAgent() =
    ## Prefer someone on a date, then someone walking, then round-robin.
    let d = dayIndexAt(clock)
    let s = clock - d.float32 * DaySeconds
    var candidates: seq[int]
    for i in 0 ..< n:
      if i != followed and plans[d].stateAt(i, s).activity == actDate: candidates.add i
    if candidates.len == 0:
      for i in 0 ..< n:
        if i != followed and plans[d].stateAt(i, s).walking: candidates.add i
    if candidates.len == 0:
      followed = (followed + 1) mod n
    else:
      followed = candidates[(int(clock) + followed) mod candidates.len]

  proc applyCommand(command: string) =
    let parts = command.strip.split(' ', 1)
    if parts.len == 0: return
    let argument = if parts.len > 1: parts[1].strip else: ""
    case parts[0].toLowerAscii
    of "play": playing = true
    of "pause": playing = false
    of "toggle": playing = not playing
    of "speed":
      try:
        let value = parseInt(argument)
        if value in [1, 2, 4, 16]: speed = value
      except ValueError: discard
    of "seek":
      try:
        clock = clamp(parseFloat(argument).float32, 0, totalSeconds - 0.001)
        cameraSnap = 2
      except ValueError: discard
    of "day":
      try:
        clock = clamp((parseInt(argument) - 1).float32 * DaySeconds, 0, totalSeconds - 0.001)
        cameraSnap = 2
      except ValueError: discard
    of "follow":
      if argument.toLowerAscii in ["none", ""]:
        discard
      elif argument.toLowerAscii == "next":
        pickNextAgent()
        sinceSwitch = 0
      else:
        let index = replay.agentIndex(argument)
        if index >= 0:
          followed = index
          sinceSwitch = 0
    of "auto":
      autoFollow = argument in ["1", "true", "on"]
      sinceSwitch = 0
    else: discard

  when defined(emscripten):
    publishReady(n.int32, replay.numDays.int32)

  if options.trace:
    let d0 = dayIndexAt(clock)
    let s0 = clock - d0.float32 * DaySeconds
    stderr.writeLine(&"trace: {replay.agents[followed].name} day {d0 + 1} s {s0:.2f}")
    for stop in plans[d0].stops[followed]:
      stderr.writeLine(&"  stop start {stop.start:.2f} {stop.activity} at ({stop.anchor.frame.origin.x:.1f}, {stop.anchor.frame.origin.z:.1f}) path {stop.pathLength:.1f} via {stop.path.len} points")
    let st = plans[d0].stateAt(followed, s0)
    stderr.writeLine(&"  state {st.activity} walking {st.walking} pose {st.pose} at ({st.position.x:.1f}, {st.position.z:.1f})")

  window.onFrame = proc() =
    let dt = frameDelta(lastFrame)
    wallClock += dt
    when defined(emscripten):
      for _ in 0 ..< 16:
        let raw = takeBrowserCommand()
        if raw == nil: break
        let command = $raw
        freeBrowserString(raw)
        applyCommand(command)
    for command in commandQueue: applyCommand(command)
    commandQueue.setLen(0)

    if playing:
      clock += dt * speed.float32
      if clock >= totalSeconds:
        clock = totalSeconds - 0.001
        playing = false
    if autoFollow:
      sinceSwitch += dt
      if sinceSwitch >= AutoSwitchSeconds:
        sinceSwitch = 0
        pickNextAgent()

    let d = dayIndexAt(clock)
    let day = replay.days[d]
    let plan = plans[d]
    let s = clock - d.float32 * DaySeconds
    let hour = hourAt(s)
    let night = hour >= 19.2 or hour < 6.8
    let phase = phaseAt(s)
    dayTint = paletteHighlight(hour)

    var states = newSeq[AgentState](n)
    for i in 0 ..< n:
      states[i] = plan.stateAt(i, s)
      let factor = 1 - exp(-dt * 9)
      if dist(smoothed[i], states[i].position) > 6:
        smoothed[i] = states[i].position
        smoothedYaw[i] = states[i].yaw
      else:
        smoothed[i] += (states[i].position - smoothed[i]) * factor
        var delta = states[i].yaw - smoothedYaw[i]
        while delta > PI: delta -= TAU
        while delta < -PI: delta += TAU
        smoothedYaw[i] += delta * (1 - exp(-dt * 8))

    # Garments: the validated morning `wear` until the app phase, the
    # recorded night state afterwards (purchases happen at the market).
    var wearing = newSeq[string](n)
    for i in 0 ..< n:
      wearing[i] = if s < DayEnd: replay.wearingDuring(d, i) else: replay.wearingAtNight(d, i)

    # Active date round and bubble.
    var bubbleAgent = -1
    var bubbleText = ""
    var bubbleTurn = -1
    var activeDates: seq[tuple[index, table, turn: int, speaker: int, text: string]]
    if s >= AppEnd and s < DateEnd:
      let round = min(int((s - AppEnd) / plan.roundLength), plan.dateRounds - 1)
      for k in 0 ..< 2:
        let index = round * 2 + k
        if index >= day.dates.len: continue
        let date = day.dates[index]
        let roundStart = AppEnd + round.float32 * plan.roundLength
        let talkStart = roundStart + DateWalkAllowance
        let talkLength = max(plan.roundLength - DateWalkAllowance - 0.4, 0.5)
        var turn = -1
        var speaker = -1
        var text = ""
        if date.turns.len > 0 and s >= talkStart:
          turn = min(int((s - talkStart) / talkLength * date.turns.len.float32), date.turns.len - 1)
          speaker = date.turns[turn].speaker
          text = date.turns[turn].text
        activeDates.add((index, k, turn, speaker, text))
        if speaker >= 0 and (bubbleAgent < 0 or speaker == followed or
            (bubbleAgent != followed and date.a == followed or date.b == followed)):
          bubbleAgent = speaker
          bubbleText = text
          bubbleTurn = turn

    # Hearts: matches during the app phase, relationship changes at the end
    # of the pair's date round or at night, cohabiting at night.
    type Effect = tuple[agent: int, broken: bool, age: float32]
    var effects: seq[Effect]
    if s >= DayEnd and s < AppEnd:
      for match in day.matches:
        effects.add((match.a, false, s - DayEnd))
        effects.add((match.b, false, s - DayEnd))
    for change in day.relationships:
      var shown = false
      for index, date in day.dates:
        if (date.a == change.a and date.b == change.b) or (date.a == change.b and date.b == change.a):
          let roundEnd = AppEnd + ((index div 2) + 1).float32 * plan.roundLength
          if s >= roundEnd - 3.5'f32 and s < roundEnd:
            effects.add((change.a, change.toStatus == "single", s - (roundEnd - 3.5'f32)))
            effects.add((change.b, change.toStatus == "single", s - (roundEnd - 3.5'f32)))
          shown = true
          break
      if not shown and s >= VisitEnd:
        effects.add((change.a, change.toStatus == "single", s - VisitEnd))
        effects.add((change.b, change.toStatus == "single", s - VisitEnd))

    # Camera: three-quarter follow of one agent; frame the table on a date.
    let me = states[followed]
    var desiredTarget = smoothed[followed] + vec3(0, 1.05, 0)
    var desiredDistance = 7.2'f32
    var desiredYaw = smoothedYaw[followed] + 0.65'f32
    var desiredPitch = 0.42'f32
    if me.activity == actDate and not me.walking and me.seat >= 0:
      # Both diners in profile from the patio side.
      desiredTarget = town.tables[me.seat] + vec3(0, 1.0, 0)
      desiredDistance = 7.6
      desiredYaw = PI.float32 + 0.42'f32
      desiredPitch = 0.34
    elif me.activity in {actWork, actEat, actTherapy, actMeditate} and not me.walking:
      desiredYaw = smoothedYaw[followed] + 0.75'f32
      desiredDistance = 6.4
    elif me.activity in {actHome, actGames, actApp, actNight, actVisit} and not me.walking:
      # Porches face a narrow street: stay close and high, off to the side.
      desiredYaw = smoothedYaw[followed] + 0.95'f32
      desiredDistance = 5.6
      desiredPitch = 0.5
    var yawDelta = desiredYaw - cameraYaw
    while yawDelta > PI: yawDelta -= TAU
    while yawDelta < -PI: yawDelta += TAU
    if window.scrollDelta.y != 0:
      cameraZoom = clamp(cameraZoom * pow(0.92'f32, window.scrollDelta.y / 3), 0.55, 2.6)
    if cameraSnap > 0:
      dec cameraSnap
      cameraYaw = desiredYaw
      cameraTarget = desiredTarget
      cameraDistance = desiredDistance * cameraZoom
      cameraPitch = desiredPitch
    else:
      cameraYaw += yawDelta * (1 - exp(-dt * 2.2))
      cameraTarget += (desiredTarget - cameraTarget) * (1 - exp(-dt * 5))
      cameraDistance += (desiredDistance * cameraZoom - cameraDistance) * (1 - exp(-dt * 3))
      cameraPitch += (desiredPitch - cameraPitch) * (1 - exp(-dt * 2.5))
    let pitch = cameraPitch
    let eye = cameraTarget + vec3(sin(cameraYaw) * cos(pitch), sin(pitch), cos(cameraYaw) * cos(pitch)) * cameraDistance
    let aspect = window.size.x.float32 / max(window.size.y.float32, 1)
    let view = lookAt(eye, cameraTarget, vec3(0, 1, 0))
    let projection = perspective(40'f32, aspect, 0.1'f32, 260'f32)
    let viewProjection = projection * view
    let billboardYaw = cameraYaw

    glViewport(0, 0, window.size.x.GLsizei, window.size.y.GLsizei)
    let sky = skyColor(hour)
    glClearColor(sky.x, sky.y, sky.z, 1)
    glClear(GL_COLOR_BUFFER_BIT or GL_DEPTH_BUFFER_BIT)
    renderer.clear()

    # Ground, avenue, side streets, paths.
    renderer.addQuad(vec3(-SceneHalf, 0, -SceneHalf), vec3(SceneHalf, 0, -SceneHalf),
      vec3(SceneHalf, 0, SceneHalf), vec3(-SceneHalf, 0, SceneHalf), lit(c(96, 160, 92)))
    for z in 0 ..< 12:
      for x in 0 ..< 16:
        if (x * 5 + z * 3) mod 4 != 0:
          let p = vec3(-SceneHalf + 6 + x.float32 * 11, 0.004, -SceneHalf + 6 + z.float32 * 14)
          renderer.addQuad(p, p + vec3(10, 0, 0), p + vec3(10, 0, 12), p + vec3(0, 0, 12),
            lit(if (x + z) mod 2 == 0: c(102, 168, 96) else: c(90, 152, 88)))
    renderer.addQuad(vec3(-46, 0.01, -2.2), vec3(46, 0.01, -2.2), vec3(46, 0.01, 2.2), vec3(-46, 0.01, 2.2), lit(c(196, 186, 168)))
    for i in 0 ..< 23:
      let x = -45'f32 + i.float32 * 4
      renderer.addQuad(vec3(x, 0.014, -0.08), vec3(x + 2, 0.014, -0.08), vec3(x + 2, 0.014, 0.08), vec3(x, 0.014, 0.08), lit(c(226, 220, 200)))
    for street in [-8'f32, 8, -23, 23]:
      renderer.addQuad(vec3(street - 1.4, 0.012, -24), vec3(street + 1.4, 0.012, -24),
        vec3(street + 1.4, 0.012, 0), vec3(street - 1.4, 0.012, 0), lit(c(204, 194, 176)))
    for house in town.houses:
      renderer.addQuad(house.via[0] + vec3(-0.5, 0.013, -0.5), house.via[1] + vec3(-0.5, 0.013, -0.5),
        house.via[1] + vec3(0.5, 0.013, 0.5), house.via[0] + vec3(0.5, 0.013, 0.5), lit(c(214, 204, 184)))
    renderer.addQuad(vec3(-25, 0.011, PromenadeZ - 1.1), vec3(34, 0.011, PromenadeZ - 1.1),
      vec3(34, 0.011, PromenadeZ + 1.1), vec3(-25, 0.011, PromenadeZ + 1.1), lit(c(210, 200, 180)))
    for anchor in [town.desks[2], town.stools[3], town.couch[2], town.cushions[0]]:
      let a = anchor.via[^2]
      let b = anchor.via[^1]
      renderer.addQuad(vec3(a.x - 1.2, 0.013, a.z), vec3(a.x + 1.2, 0.013, a.z),
        vec3(b.x + 1.2, 0.013, b.z), vec3(b.x - 1.2, 0.013, b.z), lit(c(214, 204, 184)))
    renderer.addQuad(vec3(-5, 0.012, 4.6), vec3(13, 0.012, 4.6), vec3(13, 0.012, 11.5), vec3(-5, 0.012, 11.5), lit(c(206, 190, 168)))

    # Buildings.
    renderer.addWorkspace(town.workFrame, (block:
      var frames: seq[Frame]
      for anchor in town.desks: frames.add anchor.frame
      frames), night)
    renderer.addRestaurant(town.restaurantFrame, night)
    for t in 0 ..< 2:
      var active = false
      for date in activeDates:
        if date.table == t: active = true
      renderer.addTable(frame(town.tables[t]), active)
    for stool in town.stools: renderer.addStool(stool.frame)
    renderer.addTherapyOffice(town.therapyFrame, (block:
      var frames: seq[Frame]
      for anchor in town.couch: frames.add anchor.frame
      frames), night)
    renderer.addGarden(town.gardenFrame, (block:
      var frames: seq[Frame]
      for anchor in town.cushions: frames.add anchor.frame
      frames), night)
    for slot, house in town.houseFrames:
      var glowAmount = 0'f32
      for i in 0 ..< n:
        if states[i].activity == actGames and not states[i].walking and
            replay.homeSlot(d, i) mod town.houses.len == slot:
          glowAmount = 1
      if night and glowAmount == 0:
        for i in 0 ..< n:
          if states[i].activity in {actNight, actVisit, actHome, actApp} and not states[i].walking and
              dist(states[i].position, town.houses[slot].frame.origin) < 2.5:
            glowAmount = 0.5
      renderer.addHouse(house, walls[slot mod walls.len], roofs[(slot * 7 + slot div 4) mod roofs.len], glowAmount, night)
    for i, tree in town.trees: renderer.addTree(tree, i)
    for lamp in town.lamps: renderer.addLamp(lamp, night)
    for i, p in [vec3(-5, 0, 3.4), vec3(13.5, 0, 3.4), vec3(-29, 0, 3.4), vec3(-8, 0, -3.4), vec3(36, 0, 3.4)]:
      renderer.addFlowerBed(p, i)
    for p in [vec3(-13, 0, -3.3), vec3(13, 0, -3.3), vec3(34, 0, 3.6)]:
      renderer.addBench(frame(p, 0))

    # Agents.
    for i in 0 ..< n:
      let state = states[i]
      var ch = Character(frame: frame(smoothed[i], smoothedYaw[i]), garment: garmentOf(wearing[i]),
        look: looks[i], pose: state.pose, prop: state.prop, highlight: i == followed)
      ch.phase = if state.walking: wallClock.float32 * 9 + i.float32 else: wallClock.float32 + i.float32
      ch.talking = i == bubbleAgent
      if state.walking: ch.prop = propNone
      renderer.addCharacter(ch)
    if bubbleAgent >= 0:
      let balloonLift = if states[bubbleAgent].pose in {poseSit, poseLounge}: 2.4'f32 else: 2.75'f32
      renderer.addBalloon(smoothed[bubbleAgent] + vec3(0, balloonLift, 0), billboardYaw, 1.1)
    for effect in effects:
      let lift = 2.5'f32 + effect.age * 0.25 + sin(effect.age * 3) * 0.08
      let color = if effect.broken: rgbx(120, 110, 130, 254) else: rgbx(240, 70, 110, 254)
      renderer.addHeart(smoothed[effect.agent] + vec3(0.35, lift, 0), 0.22, color, billboardYaw, effect.broken)
    renderer.draw(viewProjection)

    # Click to follow.
    let sceneBottom = when defined(emscripten): window.size.y.float32 else: window.size.y.float32 - UiHeight
    if window.mousePressed(MouseLeft) and window.mousePos.y.float32 < sceneBottom and window.mousePos.y > 56:
      var closest = 40'f32
      for i in 0 ..< n:
        let distanceToClick = length(screenPosition(smoothed[i] + vec3(0, 1.1, 0), viewProjection, window.size) - window.mousePos.vec2)
        if distanceToClick < closest:
          closest = distanceToClick
          followed = i
          sinceSwitch = 0

    # State for the HTML layer (also readable natively through lovetownState).
    block:
      var agentNodes = newJArray()
      for i in 0 ..< n:
        let head = normalizedPosition(smoothed[i] + vec3(0, 2.3, 0), viewProjection)
        let nightIndex = day.nightFor(i)
        var status = ""
        var partner = ""
        if nightIndex >= 0:
          status = day.nights[nightIndex].status
          partner = replay.agentId(day.nights[nightIndex].partner)
        agentNodes.add(%* {"id": replay.agents[i].id, "name": replay.agents[i].name,
          "x": smoothed[i].x, "y": smoothed[i].y, "z": smoothed[i].z,
          "sx": head.x, "sy": head.y, "visible": head.visible,
          "wearing": wearing[i], "tier": replay.goodTier(wearing[i]),
          "activity": $states[i].activity, "walking": states[i].walking,
          "status": status, "partner": partner,
          "partnerNow": replay.agentId(states[i].partner),
          "followed": i == followed})
      var tableNodes = newJArray()
      for t in 0 ..< 2:
        let top = normalizedPosition(town.tables[t] + vec3(0, 1.4, 0), viewProjection)
        tableNodes.add(%* {"index": t, "x": town.tables[t].x, "y": 0, "z": town.tables[t].z,
          "sx": top.x, "sy": top.y, "visible": top.visible})
      var houseNodes = newJArray()
      for slot, house in town.houses:
        let top = normalizedPosition(town.houseFrames[slot].origin + vec3(0, 4.6, 0), viewProjection)
        houseNodes.add(%* {"slot": slot, "agent": replay.agentId(slot),
          "x": house.frame.origin.x, "y": 0, "z": house.frame.origin.z,
          "sx": top.x, "sy": top.y, "visible": top.visible})
      proc placeNode(name: string, p: Vec3): JsonNode =
        let top = normalizedPosition(p, viewProjection)
        %* {"name": name, "x": p.x, "y": p.y, "z": p.z, "sx": top.x, "sy": top.y, "visible": top.visible}
      var dateNodes = newJArray()
      for date in activeDates:
        let record = day.dates[date.index]
        dateNodes.add(%* {"index": date.index, "a": replay.agentId(record.a), "b": replay.agentId(record.b),
          "table": date.table, "turn": date.turn, "turns": record.turns.len,
          "speaker": replay.agentId(date.speaker), "text": date.text})
      var effectNodes = newJArray()
      for effect in effects:
        effectNodes.add(%* {"agent": replay.agentId(effect.agent), "kind": (if effect.broken: "broken-heart" else: "heart")})
      var bubble = newJNull()
      if bubbleAgent >= 0:
        let anchor = normalizedPosition(smoothed[bubbleAgent] + vec3(0, 3.1, 0), viewProjection)
        bubble = %* {"agent": replay.agentId(bubbleAgent), "text": bubbleText, "turn": bubbleTurn,
          "sx": anchor.x, "sy": anchor.y, "visible": anchor.visible}
      let state = %* {"schema": ReplaySchema, "t": clock, "day": d + 1, "days": replay.numDays,
        "daySeconds": DaySeconds, "dayTime": s, "phase": phase, "hour": hour,
        "playing": playing, "speed": speed, "auto": autoFollow,
        "followed": replay.agents[followed].id, "followedIndex": followed,
        "width": window.size.x, "height": window.size.y,
        "agents": agentNodes,
        "anchors": {"tables": tableNodes, "houses": houseNodes,
          "workspace": placeNode("workspace", town.workFrame.origin + vec3(0, 5.2, -5.5)),
          "restaurant": placeNode("restaurant", town.restaurantFrame.origin + vec3(0, 3.4, -1.9)),
          "therapy": placeNode("therapy", town.therapyFrame.origin + vec3(0, 4.0, -3.4)),
          "garden": placeNode("garden", town.gardenFrame.origin + vec3(0, 3.0, -7.4))},
        "dates": dateNodes, "bubble": bubble, "effects": effectNodes}
      latestState = $state
      when defined(emscripten):
        publishState(latestState.cstring)

    when not defined(emscripten):
      glDisable(GL_DEPTH_TEST); glDisable(GL_CULL_FACE); glDisable(GL_BLEND)
      sk.beginUi(window, window.size)
      let width = window.size.x.float32
      sk.drawRect(vec2(0, 0), vec2(width, 52), rgbx(24, 20, 34, 236))
      sk.drawTinyText("FOG OF LOVE  LOVE TOWN", vec2(16, 14), rgbx(250, 214, 224, 255), 2.5)
      let hourLabel = &"{int(hour):02}:{int((hour - floor(hour)) * 60):02}"
      sk.drawTinyText(&"DAY {d + 1}/{replay.numDays}  {phase.toUpperAscii}  {hourLabel}  " &
        (if autoFollow: "AUTO" else: "MANUAL"), vec2(max(width - 440, 420), 16), rgbx(214, 204, 230, 255), 2)
      # Speech bubble text above the speaker.
      if bubbleAgent >= 0 and bubbleText.len > 0:
        let anchor = screenPosition(smoothed[bubbleAgent] + vec3(0, 3.3, 0), viewProjection, window.size)
        let origin = vec2(clamp(anchor.x - 190, 8, width - 388), clamp(anchor.y - 84, 60, sceneBottom - 80))
        let bubble = GameUiPanel(origin: origin, size: vec2(380, 70))
        sk.drawRect(bubble.origin, bubble.size, rgbx(252, 248, 236, 244))
        sk.drawTinyText((replay.agentName(bubbleAgent) & ": " & bubbleText).toUpperAscii,
          bubble.origin + vec2(10, 9), rgbx(40, 34, 44, 255), 1.45, 42, 3)
      # Name tags for everyone in view.
      for i in 0 ..< n:
        let tag = screenPosition(smoothed[i] + vec3(0, 2.35, 0), viewProjection, window.size)
        if tag.x < -100 or tag.x > width + 100 or tag.y < 62 or tag.y > sceneBottom: continue
        if dist(smoothed[i], cameraTarget) > 15: continue
        let label = replay.agents[i].name.split(' ')[0].toUpperAscii
        let tagWidth = label.len.float32 * 6 * 1.5 + 8
        sk.drawRect(tag - vec2(tagWidth * 0.5, 8), vec2(tagWidth, 16),
          if i == followed: rgbx(250, 200, 90, 230) else: rgbx(20, 18, 28, 170))
        sk.drawTinyText(label, tag - vec2(tagWidth * 0.5 - 4, 5),
          if i == followed: rgbx(30, 24, 20, 255) else: rgbx(240, 236, 230, 255), 1.5)
      # Transport and the followed agent's card.
      let bottom = window.size.y.float32 - UiHeight
      sk.drawRect(vec2(0, bottom), vec2(width, UiHeight), rgbx(22, 18, 30, 246))
      proc button(panel: GameUiPanel, label: string, active = false): bool =
        let hovered = panel.contains(sk.mousePos)
        sk.drawRect(panel.origin, panel.size, if active: rgbx(176, 70, 110, 255)
          elif hovered: rgbx(70, 56, 80, 255) else: rgbx(46, 38, 58, 255))
        sk.drawTinyText(label, panel.origin + vec2(9, 10), rgbx(240, 232, 236, 255), 2)
        window.mousePressed(MouseLeft) and hovered
      var x = 14'f32
      if button(GameUiPanel(origin: vec2(x, bottom + 12), size: vec2(94, 32)),
          (if playing: "PAUSE" else: "PLAY"), playing): playing = not playing
      x += 104
      if button(GameUiPanel(origin: vec2(x, bottom + 12), size: vec2(52, 32)), "<"):
        applyCommand("day " & $d)
      x += 62
      if button(GameUiPanel(origin: vec2(x, bottom + 12), size: vec2(52, 32)), ">"):
        applyCommand("day " & $(d + 2))
      x += 70
      for value in [1, 2, 4, 16]:
        if button(GameUiPanel(origin: vec2(x, bottom + 12), size: vec2(52, 32)), $value & "X", speed == value):
          speed = value
        x += 60
      if button(GameUiPanel(origin: vec2(x, bottom + 12), size: vec2(76, 32)), "AUTO", autoFollow):
        autoFollow = not autoFollow
        sinceSwitch = 0
      x += 86
      if button(GameUiPanel(origin: vec2(x, bottom + 12), size: vec2(76, 32)), "NEXT"):
        applyCommand("follow next")
      let timeline = GameUiPanel(origin: vec2(14, bottom + 56), size: vec2(max(width * 0.55 - 28, 220), 20))
      sk.drawRect(timeline.origin, timeline.size, rgbx(52, 44, 64, 255))
      sk.drawRect(timeline.origin, vec2(timeline.size.x * clock / totalSeconds, timeline.size.y), rgbx(214, 96, 140, 255))
      for k in 1 ..< replay.numDays:
        let tx = timeline.origin.x + timeline.size.x * k.float32 / replay.numDays.float32
        sk.drawRect(vec2(tx, timeline.origin.y), vec2(2, timeline.size.y), rgbx(240, 230, 240, 200))
      if window.mouseDown(MouseLeft) and timeline.contains(sk.mousePos):
        playing = false
        clock = clamp((sk.mousePos.x - timeline.origin.x) / timeline.size.x * totalSeconds, 0, totalSeconds - 0.001)
      var caption = case phase
        of "morning": "MORNING: EVERYONE LEAVES HOME"
        of "day": "DAY: WORK, MEALS, THERAPY, MEDITATION, GAMES AND HOME HOURS AS ALLOCATED"
        of "app": "EVENING: ON THE DATING APP AT HOME"
        of "date": "DATES AT THE RESTAURANT TABLES"
        of "visit": "VISITS: GUESTS WALK TO THEIR HOST'S HOUSE"
        else: "NIGHT: EVERYONE HOME"
      if phase == "date" and activeDates.len > 0:
        caption = ""
        for date in activeDates:
          let record = day.dates[date.index]
          caption.add &"TABLE {date.table + 1}: {replay.agentName(record.a)} + {replay.agentName(record.b)}  "
      sk.drawTinyText(caption, vec2(14, bottom + 88), rgbx(230, 224, 232, 255), 1.7,
        max(int(width * 0.55 / 10), 20), 3)
      let infoX = width * 0.57
      sk.drawRect(vec2(infoX, bottom + 8), vec2(width - infoX - 12, UiHeight - 16), rgbx(38, 30, 48, 255))
      let agent = replay.agents[followed]
      let nightIndex = day.nightFor(followed)
      sk.drawTinyText(agent.name.toUpperAscii, vec2(infoX + 12, bottom + 18), rgbx(250, 214, 140, 255), 2)
      let tier = replay.goodTier(wearing[followed])
      sk.drawTinyText(("WEARING  " & wearing[followed] & (if tier.len > 0: "  (" & tier & ")" else: "")).toUpperAscii,
        vec2(infoX + 12, bottom + 44), rgbx(236, 180, 210, 255), 1.7)
      var line = $states[followed].activity
      if states[followed].walking: line = "walking to " & line
      if states[followed].partner >= 0: line.add " with " & replay.agentName(states[followed].partner)
      sk.drawTinyText(line.toUpperAscii, vec2(infoX + 12, bottom + 66), rgbx(200, 220, 210, 255), 1.6)
      if nightIndex >= 0:
        let stateNow = day.nights[nightIndex]
        var relation = stateNow.status
        if stateNow.partner >= 0: relation.add " with " & replay.agentName(stateNow.partner)
        sk.drawTinyText(("STATUS " & relation & "  CASH " & shortMoney(stateNow.cash)).toUpperAscii,
          vec2(infoX + 12, bottom + 88), rgbx(200, 200, 220, 255), 1.5, max(int((width - infoX - 28) / 9), 18), 1)
        sk.drawTinyText(stateNow.sentence.toUpperAscii, vec2(infoX + 12, bottom + 108), rgbx(190, 184, 200, 255), 1.4,
          max(int((width - infoX - 28) / 8.4), 18), 2)
      else:
        sk.drawTinyText(("CASH " & shortMoney(agent.cash)).toUpperAscii, vec2(infoX + 12, bottom + 88), rgbx(200, 200, 220, 255), 1.5)
      sk.endUi()
    reportReplayFrame(int32(clock), 0)
    captureScreenshot(window, screenshotFrame, 12, getTempDir() / "lovetown-polyworld.png")
    window.presentFrame()

  when not defined(emscripten):
    window.onButtonPress = proc(key: Button) =
      case key
      of KeySpace: playing = not playing
      of KeyLeft: applyCommand("day " & $dayIndexAt(clock))
      of KeyRight: applyCommand("day " & $(dayIndexAt(clock) + 2))
      of KeyTab: applyCommand("follow next")
      of KeyA: applyCommand("auto " & (if autoFollow: "0" else: "1"))
      of Key1: speed = 1
      of Key2: speed = 2
      of Key4: speed = 4
      of Key5: speed = 16
      of KeyEscape: window.closeRequested = true
      else: discard
  while not window.closeRequested: pollEvents()

when isMainModule:
  try: main()
  except CatchableError as error:
    stderr.writeLine("Love Town Polyworld viewer: " & error.msg)
    quit(1)
