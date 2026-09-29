## Procedural Love Town geometry drawn with the engine's ShapeRenderer:
## dressed characters (Track B garments), houses, workspace, restaurant,
## therapy office, meditation garden, props and effects. Everything here is
## presentation only; nothing reads replay facts.

import std/[math, strutils]
import chroma, vmath
import polyworld/shapes

const
  WalkSpeed* = 10.0'f32
  CharacterHeight* = 1.95'f32

var dayTint* = vec3(1, 1, 1)
  ## Multiplied into every lit colour. Follows the engine's toon palette
  ## highlight for the current hour (see `paletteHighlight`).

## Toon palette. Copied from polyworld/toon.nim (ToonPalettes and DayCycle)
## so the browser build does not pull the glTF renderer in through that
## module; values are the engine's.
type Palette = tuple[hour: float32, highlight: Vec3]

proc rgb(hex: string): Vec3 =
  let c = parseHtmlColor("#" & hex)
  vec3(c.r, c.g, c.b)

let dayCycle: seq[Palette] = @[
  (0.0'f32, rgb("879EB5")), (4.0'f32, rgb("879EB5")), (6.0'f32, rgb("A19AA3")),
  (8.0'f32, rgb("F0EAE3")), (11.0'f32, rgb("FFFFFF")), (15.0'f32, rgb("FFFFFF")),
  (17.0'f32, rgb("D8C37F")), (19.0'f32, rgb("8D8C9A")), (20.5'f32, rgb("A19AA3")),
  (22.0'f32, rgb("879EB5")), (24.0'f32, rgb("879EB5"))]

proc paletteHighlight*(hour: float32): Vec3 =
  ## The engine's toon highlight colour for an hour of the day.
  let h = ((hour mod 24) + 24) mod 24
  for i in 0 ..< dayCycle.len - 1:
    let (h0, c0) = dayCycle[i]
    let (h1, c1) = dayCycle[i + 1]
    if h <= h1:
      let t = if h1 > h0: (h - h0) / (h1 - h0) else: 0'f32
      return mix(c0, c1, t)
  dayCycle[^1].highlight

proc skyColor*(hour: float32): Vec3 =
  ## Clear colour for the hour: dawn, day, sunset, night.
  const stops = [
    (0.0'f32, vec3(0.07, 0.09, 0.19)), (5.0'f32, vec3(0.07, 0.09, 0.19)),
    (7.0'f32, vec3(0.88, 0.66, 0.55)), (9.0'f32, vec3(0.60, 0.80, 0.93)),
    (16.0'f32, vec3(0.58, 0.78, 0.92)), (18.5'f32, vec3(0.95, 0.66, 0.45)),
    (20.5'f32, vec3(0.32, 0.24, 0.42)), (22.0'f32, vec3(0.07, 0.09, 0.19)),
    (24.0'f32, vec3(0.07, 0.09, 0.19))]
  let h = ((hour mod 24) + 24) mod 24
  for i in 0 ..< stops.len - 1:
    if h <= stops[i + 1][0]:
      let t = (h - stops[i][0]) / max(stops[i + 1][0] - stops[i][0], 0.001)
      return mix(stops[i][1], stops[i + 1][1], t)
  stops[^1][1]

## Colours

proc c*(r, g, b: int): ColorRGBX = rgbx(r.uint8, g.uint8, b.uint8, 254)

proc scaled(color: ColorRGBX, factor: float32, tint = true): ColorRGBX =
  let t = if tint: dayTint else: vec3(1)
  rgbx(
    clamp(color.r.float32 * factor * t.x, 0, 255).uint8,
    clamp(color.g.float32 * factor * t.y, 0, 255).uint8,
    clamp(color.b.float32 * factor * t.z, 0, 255).uint8,
    color.a)

proc lit*(color: ColorRGBX): ColorRGBX = scaled(color, 1)

proc glow*(color: ColorRGBX): ColorRGBX = color
  ## Emissive colours ignore the day tint.

## Frames

type Frame* = object
  origin*: Vec3
  yaw*: float32

proc rotY(v: Vec3, a: float32): Vec3 =
  let s = sin(a)
  let k = cos(a)
  vec3(v.x * k + v.z * s, v.y, -v.x * s + v.z * k)

proc rotX(v: Vec3, a: float32): Vec3 =
  let s = sin(a)
  let k = cos(a)
  vec3(v.x, v.y * k - v.z * s, v.y * s + v.z * k)

proc frame*(origin: Vec3, yaw = 0'f32): Frame = Frame(origin: origin, yaw: yaw)

proc world*(f: Frame, local: Vec3): Vec3 = f.origin + rotY(local, f.yaw)

proc forward*(f: Frame): Vec3 = rotY(vec3(0, 0, 1), f.yaw)

proc yawTowards*(a, b: Vec3): float32 = arctan2(b.x - a.x, b.z - a.z)

## Primitives

proc addBoxF*(r: var ShapeRenderer, f: Frame, center, size: Vec3,
    color: ColorRGBX, pitch = 0'f32, pivot = vec3(0), tint = true) =
  ## An axis-aligned box in the frame's local space, optionally pitched
  ## around a local pivot (limbs). Faces take flat toon shades.
  let h = size * 0.5'f32
  var corner: array[8, Vec3]
  for i in 0 ..< 8:
    var p = center + vec3(
      (if (i and 1) != 0: h.x else: -h.x),
      (if (i and 2) != 0: h.y else: -h.y),
      (if (i and 4) != 0: h.z else: -h.z))
    if pitch != 0:
      p = pivot + rotX(p - pivot, pitch)
    corner[i] = f.world(p)
  template q(a, b, cc, d: int, shade: float32) =
    r.addQuad(corner[a], corner[b], corner[cc], corner[d], scaled(color, shade, tint))
  q(2, 3, 7, 6, 1.12)  # top
  q(0, 4, 5, 1, 0.55)  # bottom
  q(4, 6, 7, 5, 1.0)   # front (+z)
  q(1, 3, 2, 0, 0.78)  # back
  q(0, 2, 6, 4, 0.86)  # left (-x)
  q(5, 7, 3, 1, 0.9)   # right (+x)

proc addPrismF*(r: var ShapeRenderer, f: Frame, base: Vec3, bottomRadius,
    topRadius, height: float32, sides: int, color: ColorRGBX,
    tint = true, capBottom = false) =
  ## A truncated cone with its axis along local Y, toon-shaded per side.
  let top = scaled(color, 1.12, tint)
  for i in 0 ..< sides:
    let
      a = TAU.float32 * i.float32 / sides.float32
      b = TAU.float32 * (i + 1).float32 / sides.float32
      mid = (a + b) * 0.5'f32 + f.yaw
      light = cos(mid - 0.7'f32)  # light from the upper front-left
      shade = if light > 0.35: 1.0'f32 elif light > -0.3: 0.88'f32 else: 0.76'f32
      p0 = f.world(base + vec3(cos(a) * bottomRadius, 0, sin(a) * bottomRadius))
      p1 = f.world(base + vec3(cos(b) * bottomRadius, 0, sin(b) * bottomRadius))
      p2 = f.world(base + vec3(cos(b) * topRadius, height, sin(b) * topRadius))
      p3 = f.world(base + vec3(cos(a) * topRadius, height, sin(a) * topRadius))
    r.addQuad(p0, p1, p2, p3, scaled(color, shade, tint))
    if topRadius > 0:
      r.addTriangle(f.world(base + vec3(0, height, 0)), p3, p2, top)
    if capBottom:
      r.addTriangle(f.world(base), p1, p0, scaled(color, 0.6, tint))

proc addWedgeF*(r: var ShapeRenderer, f: Frame, a, b, cc: Vec3,
    color: ColorRGBX, thickness = 0.03'f32) =
  ## A thin triangular slab (lapels, collars) with both faces.
  let n = normalize(cross(b - a, cc - a)) * thickness
  r.addTriangle(f.world(a + n), f.world(b + n), f.world(cc + n), scaled(color, 1.0))
  r.addTriangle(f.world(cc - n), f.world(b - n), f.world(a - n), scaled(color, 0.8))

proc addDisc*(r: var ShapeRenderer, center: Vec3, radius: float32,
    color: ColorRGBX, sides = 20, tint = true) =
  r.addPolygon(center, radius, sides, scaled(color, 1.0, tint))

## Block-letter signs and the HUD glyph table (5x7 bitmap font)

proc glyphRows*(ch: char): array[7, string] =
  case ch.toUpperAscii
  of 'A': ["01110","10001","10001","11111","10001","10001","10001"]
  of 'B': ["11110","10001","10001","11110","10001","10001","11110"]
  of 'C': ["01111","10000","10000","10000","10000","10000","01111"]
  of 'D': ["11110","10001","10001","10001","10001","10001","11110"]
  of 'E': ["11111","10000","10000","11110","10000","10000","11111"]
  of 'F': ["11111","10000","10000","11110","10000","10000","10000"]
  of 'G': ["01111","10000","10000","10111","10001","10001","01111"]
  of 'H': ["10001","10001","10001","11111","10001","10001","10001"]
  of 'I': ["11111","00100","00100","00100","00100","00100","11111"]
  of 'J': ["00111","00010","00010","00010","10010","10010","01100"]
  of 'K': ["10001","10010","10100","11000","10100","10010","10001"]
  of 'L': ["10000","10000","10000","10000","10000","10000","11111"]
  of 'M': ["10001","11011","10101","10101","10001","10001","10001"]
  of 'N': ["10001","11001","10101","10011","10001","10001","10001"]
  of 'O': ["01110","10001","10001","10001","10001","10001","01110"]
  of 'P': ["11110","10001","10001","11110","10000","10000","10000"]
  of 'Q': ["01110","10001","10001","10001","10101","10010","01101"]
  of 'R': ["11110","10001","10001","11110","10100","10010","10001"]
  of 'S': ["01111","10000","10000","01110","00001","00001","11110"]
  of 'T': ["11111","00100","00100","00100","00100","00100","00100"]
  of 'U': ["10001","10001","10001","10001","10001","10001","01110"]
  of 'V': ["10001","10001","10001","10001","10001","01010","00100"]
  of 'W': ["10001","10001","10001","10101","10101","10101","01010"]
  of 'X': ["10001","10001","01010","00100","01010","10001","10001"]
  of 'Y': ["10001","10001","01010","00100","00100","00100","00100"]
  of 'Z': ["11111","00001","00010","00100","01000","10000","11111"]
  of '0': ["01110","10001","10011","10101","11001","10001","01110"]
  of '1': ["00100","01100","00100","00100","00100","00100","01110"]
  of '2': ["01110","10001","00001","00010","00100","01000","11111"]
  of '3': ["11110","00001","00001","01110","00001","00001","11110"]
  of '4': ["00010","00110","01010","10010","11111","00010","00010"]
  of '5': ["11111","10000","10000","11110","00001","00001","11110"]
  of '6': ["01110","10000","10000","11110","10001","10001","01110"]
  of '7': ["11111","00001","00010","00100","01000","01000","01000"]
  of '8': ["01110","10001","10001","01110","10001","10001","01110"]
  of '9': ["01110","10001","10001","01111","00001","00001","11110"]
  of '-': ["00000","00000","00000","11111","00000","00000","00000"]
  of '+': ["00000","00100","00100","11111","00100","00100","00000"]
  of '.': ["00000","00000","00000","00000","00000","01100","01100"]
  of ',': ["00000","00000","00000","00000","00000","00100","01000"]
  of ':': ["00000","01100","01100","00000","01100","01100","00000"]
  of '/': ["00001","00010","00010","00100","01000","01000","10000"]
  of '$': ["00100","01111","10100","01110","00101","11110","00100"]
  of '%': ["11001","11010","00010","00100","01000","01011","10011"]
  of '?': ["01110","10001","00001","00010","00100","00000","00100"]
  of '!': ["00100","00100","00100","00100","00100","00000","00100"]
  of '\'': ["00100","00100","00000","00000","00000","00000","00000"]
  of '<': ["00010","00100","01000","10000","01000","00100","00010"]
  of '>': ["01000","00100","00010","00001","00010","00100","01000"]
  of '(': ["00010","00100","01000","01000","01000","00100","00010"]
  of ')': ["01000","00100","00010","00010","00010","00100","01000"]
  else: ["00000","00000","00000","00000","00000","00000","00000"]

proc addSign*(r: var ShapeRenderer, f: Frame, text: string, cell: float32,
    color: ColorRGBX, tint = false) =
  ## Block letters standing in the frame's XY plane, centred on the origin.
  let width = text.len.float32 * 6 * cell - cell
  for index, ch in text:
    let rows = glyphRows(ch)
    for row in 0 ..< 7:
      for column in 0 ..< 5:
        if rows[row][column] == '1':
          let x = -width * 0.5'f32 + index.float32 * 6 * cell + column.float32 * cell
          let y = (6 - row).float32 * cell
          r.addBoxF(f, vec3(x + cell * 0.5'f32, y + cell * 0.5'f32, 0),
            vec3(cell, cell, cell * 0.5'f32), color, tint = tint)

## Characters

type
  Garment* = enum
    gNone = "no garment", gTee = "Plain Tee", gHoodie = "Thrift Hoodie",
    gLinen = "Linen Shirt", gLeather = "Leather Jacket",
    gCoat = "Designer Coat", gSuit = "Tailored Suit"
  Pose* = enum
    poseStand, poseWalk, poseSit, poseCrossLegged, poseLounge
  Prop* = enum
    propNone, propPhone, propController, propCup, propBook
  Look* = object
    skin*, hair*: ColorRGBX
    hairStyle*: int
  Character* = object
    frame*: Frame
    garment*: Garment
    look*: Look
    pose*: Pose
    phase*: float32   ## walk cycle or idle time
    prop*: Prop
    talking*: bool
    highlight*: bool

proc garmentOf*(goodId: string): Garment =
  for g in Garment:
    if g != gNone and cmpIgnoreCase($g, goodId) == 0:
      return g
  gNone

proc lookFor*(index: int): Look =
  const skins = [c(232, 190, 150), c(200, 150, 110), c(150, 104, 70),
    c(246, 214, 186), c(112, 74, 50), c(224, 172, 128)]
  const hairs = [c(48, 34, 30), c(24, 22, 24), c(140, 64, 34), c(214, 176, 92),
    c(96, 66, 44), c(178, 120, 70), c(60, 44, 70), c(230, 226, 214)]
  Look(skin: skins[index mod skins.len], hair: hairs[(index * 5 + index div 6) mod hairs.len],
    hairStyle: index mod 6)

type GarmentPalette = object
  top, topShade, accent, trousers, shoes, under: ColorRGBX

proc paletteOf(g: Garment): GarmentPalette =
  case g
  of gTee: GarmentPalette(top: c(172, 226, 196), topShade: c(150, 204, 176),
    accent: c(255, 255, 255), trousers: c(76, 98, 146), shoes: c(240, 240, 236), under: c(172, 226, 196))
  of gHoodie: GarmentPalette(top: c(146, 130, 164), topShade: c(118, 104, 136),
    accent: c(232, 228, 236), trousers: c(104, 104, 112), shoes: c(70, 70, 76), under: c(146, 130, 164))
  of gLinen: GarmentPalette(top: c(240, 228, 198), topShade: c(216, 202, 170),
    accent: c(90, 70, 50), trousers: c(190, 160, 118), shoes: c(120, 84, 58), under: c(240, 228, 198))
  of gLeather: GarmentPalette(top: c(56, 42, 46), topShade: c(78, 60, 64),
    accent: c(206, 210, 216), trousers: c(46, 54, 76), shoes: c(30, 28, 30), under: c(240, 240, 240))
  of gCoat: GarmentPalette(top: c(172, 30, 64), topShade: c(126, 20, 46),
    accent: c(236, 194, 82), trousers: c(32, 30, 38), shoes: c(24, 22, 26), under: c(250, 236, 226))
  of gSuit: GarmentPalette(top: c(38, 54, 100), topShade: c(58, 78, 130),
    accent: c(216, 172, 60), trousers: c(38, 54, 100), shoes: c(26, 26, 30), under: c(250, 250, 250))
  of gNone: GarmentPalette(top: c(150, 150, 150), topShade: c(120, 120, 120),
    accent: c(150, 150, 150), trousers: c(110, 110, 120), shoes: c(60, 60, 60), under: c(150, 150, 150))

proc addHair(r: var ShapeRenderer, f: Frame, look: Look, headY: float32) =
  let hair = look.hair
  # Cap on every style.
  r.addBoxF(f, vec3(0, headY + 0.19, -0.02), vec3(0.42, 0.14, 0.42), hair)
  case look.hairStyle
  of 0:  # short crop
    r.addBoxF(f, vec3(0, headY + 0.05, -0.16), vec3(0.42, 0.28, 0.12), hair)
  of 1:  # bob
    r.addBoxF(f, vec3(0, headY - 0.02, -0.1), vec3(0.46, 0.4, 0.3), hair)
    r.addBoxF(f, vec3(0, headY + 0.13, 0.15), vec3(0.44, 0.1, 0.12), hair)
  of 2:  # bun
    r.addBoxF(f, vec3(0, headY + 0.02, -0.15), vec3(0.4, 0.3, 0.14), hair)
    r.addPrismF(f, vec3(0, headY + 0.2, -0.16), 0.12, 0.09, 0.16, 8, hair)
  of 3:  # long
    r.addBoxF(f, vec3(0, headY - 0.22, -0.14), vec3(0.44, 0.7, 0.16), hair)
    r.addBoxF(f, vec3(-0.2, headY - 0.05, 0.02), vec3(0.08, 0.5, 0.3), hair)
    r.addBoxF(f, vec3(0.2, headY - 0.05, 0.02), vec3(0.08, 0.5, 0.3), hair)
  of 4:  # spiky
    for i in 0 ..< 4:
      r.addPrismF(f, vec3(-0.15 + i.float32 * 0.1, headY + 0.24, -0.05 + (i mod 2).float32 * 0.08),
        0.07, 0.0, 0.16, 4, hair)
    r.addBoxF(f, vec3(0, headY + 0.05, -0.16), vec3(0.42, 0.26, 0.1), hair)
  else:  # side-swept
    r.addBoxF(f, vec3(-0.08, headY + 0.13, 0.15), vec3(0.3, 0.12, 0.14), hair)
    r.addBoxF(f, vec3(0.16, headY + 0.02, -0.08), vec3(0.12, 0.34, 0.3), hair)
    r.addBoxF(f, vec3(0, headY + 0.03, -0.17), vec3(0.42, 0.3, 0.1), hair)

proc addCharacter*(r: var ShapeRenderer, ch: Character) =
  ## A dressed figure about 1.95 units tall, feet at the frame origin,
  ## facing local +z.
  let
    f = ch.frame
    p = paletteOf(ch.garment)
    skin = ch.look.skin
    walking = ch.pose == poseWalk
    seated = ch.pose in {poseSit, poseLounge}
    crossed = ch.pose == poseCrossLegged
    swing = if walking: sin(ch.phase) * 0.6'f32 else: 0'f32
    bob = if walking: abs(sin(ch.phase)) * 0.03'f32 else: 0'f32
    drop = if seated: 0.36'f32 elif crossed: 0.66'f32 else: 0'f32
    hipY = 0.82'f32 - drop + bob
    torsoTop = hipY + 0.68'f32
    headY = torsoTop + 0.28'f32
    longCoat = ch.garment == gCoat
    baggy = ch.garment in {gHoodie, gLeather}
    torsoW = if baggy: 0.64'f32 else: 0.56'f32
    torsoD = if baggy: 0.38'f32 else: 0.32'f32
  if ch.highlight:
    r.addDisc(f.origin + vec3(0, 0.02, 0), 0.62, rgbx(255, 214, 120, 120), tint = false)
  # Legs and shoes
  if seated:
    for x in [-0.14'f32, 0.14'f32]:
      r.addBoxF(f, vec3(x, hipY - 0.06, 0.26), vec3(0.2, 0.2, 0.56), p.trousers)
      r.addBoxF(f, vec3(x, hipY - 0.36, 0.5), vec3(0.2, 0.5, 0.2), p.trousers)
      r.addBoxF(f, vec3(x, 0.05, 0.56), vec3(0.2, 0.1, 0.3), p.shoes)
  elif crossed:
    r.addBoxF(f, vec3(-0.12, 0.12, 0.2), vec3(0.5, 0.18, 0.24), p.trousers, pitch = 0, pivot = vec3(0))
    r.addBoxF(f, vec3(0.12, 0.1, 0.32), vec3(0.5, 0.16, 0.22), p.trousers)
    r.addBoxF(f, vec3(-0.3, 0.1, 0.34), vec3(0.16, 0.1, 0.24), p.shoes)
    r.addBoxF(f, vec3(0.3, 0.1, 0.2), vec3(0.16, 0.1, 0.24), p.shoes)
  else:
    for i, x in [-0.14'f32, 0.14'f32]:
      let pitch = if i == 0: swing else: -swing
      let pivot = vec3(x, hipY, 0)
      r.addBoxF(f, vec3(x, hipY - 0.42, 0), vec3(0.2, 0.8, 0.22), p.trousers, pitch, pivot)
      r.addBoxF(f, vec3(x, hipY - 0.78, 0.05), vec3(0.2, 0.1, 0.32), p.shoes, pitch, pivot)
  # Torso
  r.addBoxF(f, vec3(0, hipY + 0.34, 0), vec3(torsoW, 0.68, torsoD), p.top)
  # Arms: upper arm in the garment colour (or skin for the tee), forearm
  # per garment sleeve length.
  let sleeveFull = ch.garment notin {gTee, gLinen}
  for i, x in [-(torsoW * 0.5 + 0.1), torsoW * 0.5 + 0.1]:
    let pitch = if walking: (if i == 0: -swing else: swing) * 0.7'f32 else: 0'f32
    let armPitch = if ch.prop != propNone and i == 1: -1.3'f32
      elif ch.talking and i == 0: -0.9'f32 - sin(ch.phase * 5) * 0.2'f32
      elif seated: -1.2'f32 else: pitch
    let pivot = vec3(x, torsoTop - 0.05, 0)
    let upper = if ch.garment == gTee: p.top else: p.top
    r.addBoxF(f, vec3(x, torsoTop - 0.2, 0), vec3(0.17, 0.32, 0.18), upper, armPitch, pivot)
    let forearmColor = if sleeveFull: p.topShade elif ch.garment == gLinen: p.top else: skin
    let forearmSize = if ch.garment == gLinen: vec3(0.19, 0.3, 0.2) else: vec3(0.15, 0.3, 0.16)
    if ch.garment == gLinen:
      r.addBoxF(f, vec3(x, torsoTop - 0.45, 0), vec3(0.15, 0.2, 0.16), skin, armPitch, pivot)
      r.addBoxF(f, vec3(x, torsoTop - 0.35, 0), forearmSize, forearmColor, armPitch, pivot)
    else:
      r.addBoxF(f, vec3(x, torsoTop - 0.5, 0), forearmSize, forearmColor, armPitch, pivot)
    if ch.garment in {gLeather, gCoat, gSuit}:
      r.addBoxF(f, vec3(x, torsoTop - 0.63, 0), vec3(0.18, 0.06, 0.19), p.accent, armPitch, pivot)
    r.addBoxF(f, vec3(x, torsoTop - 0.7, 0), vec3(0.14, 0.12, 0.14), skin, armPitch, pivot)
    # Hand props on the right hand.
    if i == 1 and ch.prop != propNone:
      let hand = vec3(x, torsoTop - 0.76, 0)
      case ch.prop
      of propPhone:
        r.addBoxF(f, hand + vec3(0, 0.02, 0.06), vec3(0.1, 0.18, 0.02), c(30, 30, 34), armPitch, pivot)
        r.addBoxF(f, hand + vec3(0, 0.02, 0.075), vec3(0.08, 0.15, 0.01), c(140, 220, 255), armPitch, pivot, tint = false)
      of propController:
        r.addBoxF(f, hand + vec3(-0.1, 0, 0.06), vec3(0.34, 0.08, 0.14), c(240, 240, 240), armPitch, pivot)
        r.addBoxF(f, hand + vec3(0, 0.05, 0.06), vec3(0.06, 0.03, 0.06), c(220, 60, 80), armPitch, pivot)
      of propCup:
        r.addPrismF(f, hand + vec3(0, -0.02, 0.1), 0.05, 0.06, 0.12, 8, c(250, 250, 246))
      of propBook:
        r.addBoxF(f, hand + vec3(0, 0, 0.1), vec3(0.22, 0.04, 0.16), c(190, 90, 70), armPitch, pivot)
      else: discard
  # Garment details
  case ch.garment
  of gTee:
    r.addBoxF(f, vec3(0, hipY + 0.5, torsoD * 0.5 + 0.005), vec3(0.34, 0.06, 0.01), p.accent)
  of gHoodie:
    r.addBoxF(f, vec3(0, headY + 0.02, -0.28), vec3(0.5, 0.42, 0.22), p.topShade)
    r.addBoxF(f, vec3(0, torsoTop - 0.02, -0.12), vec3(0.62, 0.14, 0.34), p.topShade)
    r.addBoxF(f, vec3(0, hipY + 0.16, torsoD * 0.5 + 0.02), vec3(0.4, 0.2, 0.05), p.topShade)
    for x in [-0.07'f32, 0.07'f32]:
      r.addBoxF(f, vec3(x, torsoTop - 0.28, torsoD * 0.5 + 0.02), vec3(0.02, 0.3, 0.02), p.accent)
  of gLinen:
    let z = torsoD * 0.5 + 0.005
    r.addBoxF(f, vec3(0, hipY + 0.34, z), vec3(0.08, 0.66, 0.012), p.topShade)
    for i in 0 ..< 4:
      r.addBoxF(f, vec3(0, hipY + 0.14 + i.float32 * 0.14, z + 0.01), vec3(0.035, 0.035, 0.012), p.accent)
    r.addWedgeF(f, vec3(-0.04, torsoTop + 0.02, z), vec3(-0.22, torsoTop - 0.14, z), vec3(-0.06, torsoTop - 0.2, z), c(252, 246, 230))
    r.addWedgeF(f, vec3(0.04, torsoTop + 0.02, z), vec3(0.06, torsoTop - 0.2, z), vec3(0.22, torsoTop - 0.14, z), c(252, 246, 230))
    r.addBoxF(f, vec3(0, hipY + 0.03, 0), vec3(torsoW + 0.06, 0.08, torsoD + 0.04), p.top)
  of gLeather:
    let z = torsoD * 0.5 + 0.005
    r.addBoxF(f, vec3(0, torsoTop - 0.22, z), vec3(0.2, 0.42, 0.012), p.under)
    r.addBoxF(f, vec3(0, hipY + 0.3, z + 0.012), vec3(0.025, 0.6, 0.012), p.accent, tint = false)
    r.addWedgeF(f, vec3(-0.08, torsoTop + 0.02, z), vec3(-0.3, torsoTop - 0.06, z), vec3(-0.1, torsoTop - 0.3, z), p.topShade)
    r.addWedgeF(f, vec3(0.08, torsoTop + 0.02, z), vec3(0.1, torsoTop - 0.3, z), vec3(0.3, torsoTop - 0.06, z), p.topShade)
    r.addBoxF(f, vec3(0, hipY + 0.03, 0), vec3(torsoW + 0.04, 0.1, torsoD + 0.03), p.topShade)
    r.addBoxF(f, vec3(0, hipY + 0.03, z + 0.02), vec3(0.08, 0.08, 0.02), p.accent, tint = false)
  of gCoat:
    let z = torsoD * 0.5 + 0.005
    if not seated and not crossed:
      r.addPrismF(f, vec3(0, hipY - 0.55, 0), 0.5, 0.3, 0.6, 10, p.top)
    else:
      r.addPrismF(f, vec3(0, hipY - 0.2, 0.1), 0.42, 0.3, 0.26, 10, p.top)
    r.addBoxF(f, vec3(0, hipY + 0.06, 0), vec3(torsoW + 0.05, 0.1, torsoD + 0.05), p.accent, tint = false)
    r.addBoxF(f, vec3(0, hipY + 0.06, z + 0.03), vec3(0.1, 0.1, 0.03), c(255, 236, 160), tint = false)
    r.addBoxF(f, vec3(0, hipY + 0.42, z), vec3(0.14, 0.5, 0.012), p.under)
    r.addWedgeF(f, vec3(-0.06, torsoTop + 0.04, z), vec3(-0.34, torsoTop - 0.08, z + 0.02), vec3(-0.1, torsoTop - 0.34, z), p.topShade, 0.04)
    r.addWedgeF(f, vec3(0.06, torsoTop + 0.04, z), vec3(0.1, torsoTop - 0.34, z), vec3(0.34, torsoTop - 0.08, z + 0.02), p.topShade, 0.04)
    r.addBoxF(f, vec3(0, torsoTop + 0.02, -0.08), vec3(0.6, 0.12, 0.26), p.topShade)
  of gSuit:
    let z = torsoD * 0.5 + 0.005
    r.addBoxF(f, vec3(0, torsoTop - 0.2, z), vec3(0.2, 0.42, 0.012), p.under)
    r.addBoxF(f, vec3(0, torsoTop - 0.24, z + 0.014), vec3(0.06, 0.34, 0.012), p.accent, tint = false)
    r.addWedgeF(f, vec3(-0.06, torsoTop + 0.02, z), vec3(-0.26, torsoTop - 0.08, z), vec3(-0.08, torsoTop - 0.34, z), p.topShade)
    r.addWedgeF(f, vec3(0.06, torsoTop + 0.02, z), vec3(0.08, torsoTop - 0.34, z), vec3(0.26, torsoTop - 0.08, z), p.topShade)
    r.addBoxF(f, vec3(-0.18, torsoTop - 0.16, z + 0.01), vec3(0.08, 0.03, 0.012), p.under)
    r.addBoxF(f, vec3(0, hipY + 0.03, 0), vec3(torsoW + 0.02, 0.06, torsoD + 0.02), p.topShade)
  of gNone: discard
  # Neck and head
  r.addBoxF(f, vec3(0, torsoTop + 0.05, 0), vec3(0.16, 0.12, 0.16), skin)
  r.addPrismF(f, vec3(0, headY - 0.22, 0), 0.22, 0.2, 0.44, 10, skin)
  r.addBoxF(f, vec3(0, headY + 0.2, 0), vec3(0.36, 0.06, 0.36), skin)
  for x in [-0.09'f32, 0.09'f32]:
    r.addBoxF(f, vec3(x, headY + 0.02, 0.2), vec3(0.06, 0.07, 0.03), c(36, 32, 34))
    r.addBoxF(f, vec3(x, headY + 0.09, 0.2), vec3(0.09, 0.02, 0.02), ch.look.hair)
  let mouthH = if ch.talking: 0.05'f32 + abs(sin(ch.phase * 9)) * 0.04'f32 else: 0.025'f32
  r.addBoxF(f, vec3(0, headY - 0.12, 0.2), vec3(0.12, mouthH, 0.02), c(150, 78, 74))
  r.addHair(f, ch.look, headY)

## Effects

proc addHeart*(r: var ShapeRenderer, center: Vec3, size: float32,
    color: ColorRGBX, yaw: float32, broken = false) =
  ## A flat heart facing `yaw`; a broken heart splits with a dark crack.
  let f = frame(center, yaw)
  let gap = if broken: size * 0.12 else: 0'f32
  for side in [-1'f32, 1'f32]:
    let offset = vec3(side * (size * 0.5 + gap), (if broken and side > 0: -size * 0.15 else: 0), 0)
    for i in 0 ..< 10:
      let a = TAU.float32 * i.float32 / 10
      let b = TAU.float32 * (i + 1).float32 / 10
      r.addTriangle(f.world(offset), f.world(offset + vec3(cos(a) * size * 0.5, sin(a) * size * 0.5, 0)),
        f.world(offset + vec3(cos(b) * size * 0.5, sin(b) * size * 0.5, 0)), color)
      r.addTriangle(f.world(offset), f.world(offset + vec3(cos(b) * size * 0.5, sin(b) * size * 0.5, 0)),
        f.world(offset + vec3(cos(a) * size * 0.5, sin(a) * size * 0.5, 0)), color)
    let tip = vec3(side * gap, -size * 1.2, 0)
    let inner = vec3(side * gap, 0, 0)
    let outer = offset + vec3(side * size * 0.5, -size * 0.1, 0)
    r.addTriangle(f.world(inner), f.world(outer), f.world(tip), color)
    r.addTriangle(f.world(tip), f.world(outer), f.world(inner), color)

proc addBalloon*(r: var ShapeRenderer, center: Vec3, yaw: float32, width = 1.2'f32) =
  ## A speech balloon with a tail, facing the camera yaw.
  let f = frame(center, yaw)
  r.addBoxF(f, vec3(0, 0, 0), vec3(width, 0.5, 0.06), c(252, 248, 236), tint = false)
  r.addBoxF(f, vec3(0, 0, 0.02), vec3(width - 0.1, 0.4, 0.04), c(252, 248, 236), tint = false)
  for i in 0 ..< 3:
    r.addBoxF(f, vec3(-width * 0.32 + i.float32 * width * 0.32, 0, 0.05), vec3(0.08, 0.08, 0.02), c(90, 84, 80), tint = false)
  r.addWedgeF(f, vec3(-0.18, -0.24, 0), vec3(0.06, -0.24, 0), vec3(-0.14, -0.46, 0), c(252, 248, 236), 0.03)

## Buildings and props

proc addHouse*(r: var ShapeRenderer, f: Frame, wall, roof: ColorRGBX,
    windowGlow: float32, night: bool) =
  ## A small house whose door faces local +z, with a porch slab in front.
  r.addBoxF(f, vec3(0, 1.4, 0), vec3(4.4, 2.8, 4.0), wall)
  r.addPrismF(f, vec3(0, 2.8, 0), 3.4, 0.2, 1.7, 4, roof)
  r.addBoxF(f, vec3(0, 0.05, 2.6), vec3(3.4, 0.1, 1.3), c(196, 176, 150))
  r.addBoxF(f, vec3(0, 1.0, 2.01), vec3(0.9, 2.0, 0.06), c(96, 66, 46))
  r.addBoxF(f, vec3(0.28, 1.0, 2.05), vec3(0.08, 0.08, 0.04), c(230, 190, 90), tint = false)
  let glass = if windowGlow > 0: mix(vec3(1.0, 0.86, 0.5), vec3(0.6, 0.9, 1.0), 1 - windowGlow)
    elif night: vec3(0.3, 0.32, 0.4) else: vec3(0.68, 0.86, 0.96)
  let glassColor = rgbx((glass.x * 255).uint8, (glass.y * 255).uint8, (glass.z * 255).uint8, 254)
  for x in [-1.3'f32, 1.3'f32]:
    r.addBoxF(f, vec3(x, 1.5, 2.01), vec3(1.0, 1.0, 0.05), glassColor, tint = windowGlow <= 0)
    r.addBoxF(f, vec3(x, 1.5, 2.04), vec3(0.06, 1.0, 0.03), c(250, 250, 250))
    r.addBoxF(f, vec3(x, 1.5, 2.04), vec3(1.0, 0.06, 0.03), c(250, 250, 250))
  r.addBoxF(f, vec3(0, 2.62, 2.5), vec3(1.6, 0.1, 1.1), roof)
  r.addBoxF(f, vec3(-0.7, 1.3, 2.9), vec3(0.12, 2.6, 0.12), c(230, 226, 214))
  r.addBoxF(f, vec3(0.7, 1.3, 2.9), vec3(0.12, 2.6, 0.12), c(230, 226, 214))
  r.addBoxF(f, vec3(1.5, 3.9, -1.0), vec3(0.5, 1.2, 0.5), c(150, 140, 136))

proc addWorkspace*(r: var ShapeRenderer, f: Frame, desks: seq[Frame], night: bool) =
  ## An open-fronted office: floor slab, pillars, flat roof, glass back wall.
  r.addBoxF(f, vec3(0, 0.1, 0), vec3(19, 0.2, 11), c(214, 210, 200))
  r.addBoxF(f, vec3(0, 2.6, -5.3), vec3(19, 5.2, 0.4), c(120, 150, 170))
  for x in [-9.2'f32, -4.6, 0, 4.6, 9.2]:
    r.addBoxF(f, vec3(x, 2.6, 5.2), vec3(0.4, 5.2, 0.4), c(230, 226, 216))
    r.addBoxF(f, vec3(x, 2.6, -5.3), vec3(0.5, 5.2, 0.5), c(230, 226, 216))
  for x in [-9.5'f32, 9.5'f32]:
    r.addBoxF(f, vec3(x, 2.6, 0), vec3(0.3, 5.2, 11), c(178, 196, 208))
  r.addBoxF(f, vec3(0, 5.4, 0), vec3(20, 0.4, 12), c(96, 112, 128))
  r.addBoxF(f, vec3(0, 5.8, 0), vec3(17, 0.4, 9), c(112, 128, 144))
  for desk in desks:
    r.addBoxF(desk, vec3(0, 0.75, 0.55), vec3(1.5, 0.08, 0.8), c(196, 160, 120))
    r.addBoxF(desk, vec3(-0.65, 0.4, 0.55), vec3(0.08, 0.7, 0.7), c(120, 100, 84))
    r.addBoxF(desk, vec3(0.65, 0.4, 0.55), vec3(0.08, 0.7, 0.7), c(120, 100, 84))
    r.addBoxF(desk, vec3(0, 1.05, 0.8), vec3(0.6, 0.42, 0.05), c(40, 44, 50))
    r.addBoxF(desk, vec3(0, 1.05, 0.77), vec3(0.54, 0.36, 0.02),
      (if night: c(60, 66, 80) else: c(150, 220, 240)), tint = false)
    r.addBoxF(desk, vec3(0, 0.45, 0), vec3(0.6, 0.08, 0.6), c(70, 80, 96))
    r.addBoxF(desk, vec3(0, 0.22, 0), vec3(0.1, 0.44, 0.1), c(50, 54, 60))
  r.addSign(frame(f.world(vec3(0, 6.1, 5.6)), f.yaw), "WORKSPACE", 0.16, c(250, 250, 250))

proc addTable*(r: var ShapeRenderer, f: Frame, active: bool) =
  ## A round patio table with a chair on each side (local +z and -z).
  if active:
    r.addDisc(f.origin + vec3(0, 0.03, 0), 2.2, rgbx(255, 200, 140, 90), tint = false)
  r.addPrismF(f, vec3(0, 0, 0), 0.14, 0.12, 0.76, 8, c(80, 70, 66))
  r.addPrismF(f, vec3(0, 0.76, 0), 0.9, 0.9, 0.08, 14, c(236, 224, 200))
  r.addPrismF(f, vec3(0, 0.84, 0), 0.32, 0.3, 0.16, 8, c(240, 236, 226))
  r.addPrismF(f, vec3(0, 0.84, 0), 0.06, 0.05, 0.36, 6, c(80, 130, 90))
  r.addPrismF(f, vec3(0, 1.18, 0), 0.14, 0.02, 0.14, 8, c(240, 110, 130))
  for side in [-1'f32, 1'f32]:
    let z = side * 1.35
    r.addBoxF(f, vec3(0, 0.42, z), vec3(0.6, 0.08, 0.6), c(120, 76, 56))
    r.addBoxF(f, vec3(0, 0.7, z + side * 0.28), vec3(0.6, 0.6, 0.08), c(120, 76, 56))
    for x in [-0.25'f32, 0.25'f32]:
      r.addBoxF(f, vec3(x, 0.2, z - side * 0.25), vec3(0.06, 0.4, 0.06), c(90, 60, 46))
      r.addBoxF(f, vec3(x, 0.2, z + side * 0.25), vec3(0.06, 0.4, 0.06), c(90, 60, 46))

proc addStool*(r: var ShapeRenderer, f: Frame) =
  r.addPrismF(f, vec3(0, 0, 0), 0.06, 0.06, 0.44, 6, c(70, 66, 64))
  r.addPrismF(f, vec3(0, 0.44, 0), 0.26, 0.26, 0.06, 10, c(190, 96, 70))

proc addRestaurant*(r: var ShapeRenderer, f: Frame, night: bool) =
  ## The restaurant building with an awning, a bar counter in front and a
  ## patio apron; tables are placed by the caller.
  r.addBoxF(f, vec3(0, 0.06, 2.5), vec3(16, 0.12, 9), c(206, 190, 168))
  r.addBoxF(f, vec3(0, 1.9, -2.5), vec3(12, 3.8, 5), c(240, 200, 150))
  r.addPrismF(f, vec3(0, 3.8, -2.5), 8.2, 1.0, 1.6, 4, c(190, 78, 70))
  r.addBoxF(f, vec3(0, 1.3, 0.02), vec3(1.4, 2.6, 0.08), c(90, 60, 48))
  for x in [-4'f32, 4'f32]:
    r.addBoxF(f, vec3(x, 2.0, 0.02), vec3(2.6, 1.6, 0.06),
      (if night: c(255, 214, 140) else: c(170, 220, 240)), tint = not night)
  for s in 0 ..< 10:
    let x = -6'f32 + s.float32 * 1.2'f32 + 0.6'f32
    let stripe = if s mod 2 == 0: c(206, 66, 70) else: c(250, 244, 226)
    r.addBoxF(f, vec3(x, 2.85, 0.9), vec3(1.2, 0.1, 1.8), stripe)
    r.addBoxF(f, vec3(x, 2.7, 1.8), vec3(1.2, 0.3, 0.08), stripe)
  for x in [-5.9'f32, 5.9'f32]:
    r.addBoxF(f, vec3(x, 1.4, 1.75), vec3(0.12, 2.8, 0.12), c(230, 226, 214))
  # Bar counter for solo diners, along the front, with the stools placed by
  # the caller.
  r.addBoxF(f, vec3(0, 0.5, 1.2), vec3(9, 1.0, 0.6), c(120, 80, 56))
  r.addBoxF(f, vec3(0, 1.02, 1.2), vec3(9.4, 0.08, 0.9), c(230, 214, 190))
  for i in 0 ..< 5:
    r.addPrismF(f, vec3(-3.6 + i.float32 * 1.8, 1.06, 1.15), 0.1, 0.1, 0.1, 8, c(250, 250, 250))
  r.addSign(frame(f.world(vec3(0, 3.0, 1.9)), f.yaw), "RESTAURANT", 0.14, c(250, 250, 250))

proc addTherapyOffice*(r: var ShapeRenderer, f: Frame, couch: seq[Frame], night: bool) =
  ## A calm office: an open front, a long couch and an armchair.
  r.addBoxF(f, vec3(0, 0.08, 0), vec3(9, 0.16, 7), c(200, 196, 186))
  r.addBoxF(f, vec3(0, 1.7, -3.3), vec3(9, 3.4, 0.4), c(184, 206, 190))
  for x in [-4.4'f32, 4.4'f32]:
    r.addBoxF(f, vec3(x, 1.7, 0), vec3(0.3, 3.4, 7), c(184, 206, 190))
  r.addPrismF(f, vec3(0, 3.4, 0), 6.5, 0.3, 1.4, 4, c(110, 140, 120))
  r.addBoxF(f, vec3(0, 2.0, -3.1), vec3(3, 1.4, 0.06),
    (if night: c(255, 220, 150) else: c(180, 224, 240)), tint = not night)
  for seat in couch:
    r.addBoxF(seat, vec3(0, 0.25, 0), vec3(1.0, 0.5, 0.9), c(96, 120, 150))
    r.addBoxF(seat, vec3(0, 0.7, -0.4), vec3(1.0, 0.5, 0.2), c(84, 106, 136))
  r.addBoxF(f, vec3(3.2, 0.3, 1.2), vec3(0.9, 0.6, 0.9), c(150, 100, 80))
  r.addBoxF(f, vec3(3.2, 0.8, 0.8), vec3(0.9, 0.6, 0.2), c(140, 92, 72))
  r.addPrismF(f, vec3(-3.2, 0, 1.6), 0.4, 0.3, 0.6, 8, c(190, 120, 90))
  r.addPrismF(f, vec3(-3.2, 0.6, 1.6), 0.8, 0.3, 1.2, 8, c(90, 150, 100))
  r.addSign(frame(f.world(vec3(0, 3.7, 3.4)), f.yaw), "THERAPY", 0.14, c(250, 250, 250))

proc addGarden*(r: var ShapeRenderer, f: Frame, cushions: seq[Frame], night: bool) =
  ## Gravel circle, stones, a lantern and meditation cushions.
  r.addDisc(f.origin + vec3(0, 0.02, 0), 7.0, c(214, 206, 186), 28)
  r.addDisc(f.origin + vec3(0, 0.03, 0), 6.0, c(226, 218, 198), 28)
  for i in 0 ..< 12:
    let a = TAU.float32 * i.float32 / 12
    r.addPrismF(f, vec3(cos(a) * 6.5, 0, sin(a) * 6.5), 0.45, 0.3, 0.45 + (i mod 3).float32 * 0.12, 6, c(150, 146, 140))
  r.addPrismF(f, vec3(0, 0, 0), 0.5, 0.5, 0.3, 6, c(120, 116, 110))
  r.addBoxF(f, vec3(0, 0.75, 0), vec3(0.5, 0.9, 0.5), (if night: c(255, 200, 110) else: c(240, 230, 200)), tint = not night)
  r.addPrismF(f, vec3(0, 1.2, 0), 0.5, 0.05, 0.35, 4, c(80, 60, 50))
  for cushion in cushions:
    r.addPrismF(cushion, vec3(0, 0, 0), 0.5, 0.42, 0.18, 8, c(184, 96, 84))
  r.addPrismF(f, vec3(-4.5, 0, -4.5), 0.25, 0.18, 2.4, 7, c(100, 70, 46))
  r.addPrismF(f, vec3(-4.5, 1.7, -4.5), 1.6, 0.3, 2.0, 9, c(230, 140, 170))
  r.addSign(frame(f.world(vec3(0, 2.8, 7.4)), f.yaw), "MEDITATION", 0.12, c(250, 250, 250))

proc addTree*(r: var ShapeRenderer, p: Vec3, variant: int) =
  let f = frame(p, variant.float32 * 0.7)
  r.addPrismF(f, vec3(0), 0.24, 0.16, 2.2, 7, c(96, 66, 42))
  case variant mod 3
  of 0:
    r.addPrismF(f, vec3(0, 1.5, 0), 1.3, 0.4, 2.3, 8, c(66, 138, 82))
    r.addPrismF(f, vec3(0, 2.7, 0), 0.9, 0.1, 1.6, 8, c(78, 156, 92))
  of 1:
    r.addPrismF(f, vec3(0, 1.8, 0), 1.2, 0.9, 1.2, 8, c(88, 152, 78))
    r.addPrismF(f, vec3(0, 3.0, 0), 0.9, 0.0, 1.2, 8, c(100, 168, 90))
  else:
    r.addPrismF(f, vec3(0, 1.6, 0), 1.0, 0.7, 1.4, 6, c(214, 128, 96))
    r.addPrismF(f, vec3(0, 3.0, 0), 0.7, 0.0, 1.0, 6, c(226, 150, 110))

proc addLamp*(r: var ShapeRenderer, p: Vec3, on: bool) =
  let f = frame(p)
  r.addPrismF(f, vec3(0), 0.14, 0.1, 3.0, 8, c(60, 66, 70))
  r.addBoxF(f, vec3(0, 3.08, 0), vec3(0.6, 0.16, 0.6), c(64, 70, 74))
  r.addPrismF(f, vec3(0, 3.16, 0), 0.3, 0.2, 0.44, 8,
    (if on: c(255, 220, 130) else: c(220, 214, 190)), tint = not on)
  if on:
    r.addDisc(p + vec3(0, 0.025, 0), 2.4, rgbx(255, 214, 120, 46), tint = false)

proc addBench*(r: var ShapeRenderer, f: Frame) =
  r.addBoxF(f, vec3(0, 0.45, 0), vec3(1.8, 0.08, 0.5), c(150, 108, 72))
  r.addBoxF(f, vec3(0, 0.75, -0.25), vec3(1.8, 0.5, 0.08), c(150, 108, 72))
  for x in [-0.75'f32, 0.75'f32]:
    r.addBoxF(f, vec3(x, 0.2, 0), vec3(0.1, 0.4, 0.44), c(70, 66, 62))

proc addFlowerBed*(r: var ShapeRenderer, p: Vec3, variant: int) =
  let f = frame(p)
  r.addBoxF(f, vec3(0, 0.2, 0), vec3(1.6, 0.4, 0.7), c(140, 92, 60))
  const petals = [c(242, 111, 127), c(245, 191, 72), c(157, 115, 205), c(250, 250, 250)]
  for i in 0 ..< 5:
    let q = vec3(-0.6 + i.float32 * 0.3, 0.4, 0)
    r.addPrismF(f, q, 0.05, 0.04, 0.3, 5, c(70, 140, 80))
    r.addPrismF(f, q + vec3(0, 0.26, 0), 0.14, 0.03, 0.16, 6, petals[(i + variant) mod petals.len])
