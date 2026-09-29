# Assets used by the Polyworld 3D viewer

## Character clothing: Track B (procedural), not Track A

The spec's Track A asked for the Quaternius "Ultimate Modular Characters" pack,
on the condition that the page's license text is CC0 and the download needs no
form.

Checked 2026-09-28 (PDT):

- Pack page: <https://quaternius.com/packs/ultimatemodularcharacters.html>.
  The page title is "Ultimate Modular Men Pack" (February 2022, 11 characters,
  24 animations, FBX/OBJ/glTF/Blend). The pack card prints the words
  "License CC0".
- The page's "License" button links to <https://quaternius.com/license.html>,
  which now states: "Quaternius Asset License (QAL) v1.0, Last updated:
  8/28/2026". The QAL allows free personal, educational and commercial use
  with no credit, but section 3(a) says "You may not resell or redistribute
  the Assets themselves ... whether for free or for payment ... regardless of
  how much the Assets have been modified." Committing the raw model files to a
  public repository (this repo publishes `docs/` through GitHub Pages) would
  be redistribution of the assets themselves.
- The download button opens a Google Drive folder
  (`drive.google.com/drive/folders/1USAAquX2JJWuA2m6zol0KUkFe3UkZ8zX`); no
  form, but not a direct file link either.

Because the linked license text is not CC0 (the card label and the license
page disagree, and the license page is the governing text), Track A was
stopped before downloading anything, per the spec's stop rule. No Quaternius
file is in this repository.

The viewer therefore uses **Track B**: procedural garments built from the
engine's `ShapeRenderer` (boxes, prisms, wedges) in `polyworld_viewer/main.nim`.
The six clothing goods in the runs each have their own silhouette and palette:

| Good | Tier | Silhouette |
| --- | --- | --- |
| Plain Tee | Low | short torso, short sleeves, flat mint, blue jeans |
| Thrift Hoodie | Low | baggy torso, hood behind the head, kangaroo pocket, drawstrings, grey sweatpants |
| Linen Shirt | Mid | cream shirt with collar wedges, button placket, rolled sleeves, beige chinos |
| Leather Jacket | Mid | dark wide torso, lapels, silver zip and cuffs, white tee in the V, dark jeans |
| Designer Coat | High | crimson long flared coat to mid-calf, wide collar, gold belt, black trousers and boots |
| Tailored Suit | High | navy jacket with lighter lapels, white shirt, gold tie, pocket square, navy trousers, black shoes |

Hair style and colour and skin tone vary per agent. No third-party art is
bundled for the characters.

## Everything else

Buildings, trees, lamps, tables, hearts and speech balloons are also
procedural `ShapeRenderer` geometry. The toon day palette comes from the
engine's `polyworld/toon.nim` (`paletteAtHour`). The native HUD's tiny bitmap
font is the same hand-written 5x7 glyph table the Concordia viewer used. No
files under `assets/` are required by the build at the moment.
