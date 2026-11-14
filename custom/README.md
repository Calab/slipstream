# Custom assets

Put your own images and sounds here to replace the generated ones. The game
looks in `custom/` first and falls back to the generated file in `assets/` when
there is no override. The game never changes or deletes anything in this folder.

Use the **same sub-folder and file name** as the asset you're replacing. For
example, to replace Neptune, save your picture as:

    custom/obstacles/neptune_0.png

Restart the game to see changes. To compare with the originals, look at the
matching file in `assets/` (created on first run).

- **Images:** PNG works best because it supports transparency. `.jpg` / `.jpeg`
  also work for textures with no transparent areas.
- **Sounds:** `.wav`, `.ogg`, `.mp3` or `.flac`. Keep the name and change only
  the extension, e.g. `custom/sfx/splat.ogg`.

## Animated sprites (`_0`, `_1`, … frames)

Players and some obstacles are animations: `name_0.png`, `name_1.png`, … played
in order and looped. If `custom/` has a `name_0` file, **only your frames are
used**, so you can supply any number, even just `name_0.png` for a still image.
Number them without gaps.

## Sprites

Square PNGs with a transparent background. The artwork should fill most of
the square. The sizes listed are what the generator makes; bigger works too.

| Folder | Files | Size | Notes |
|---|---|---|---|
| `player/` | `fish_clown_N`, `sub_N`, `mermaid_N`, `fish_tang_N` (unused) | 256×256, 8 frames | Seen **from behind**, as the camera follows the player. Coral Reef, Shipwreck Deep and Kelp Forest themes in that order. |
| `obstacles/` | `chest_0`, `boulder_0`, `anchor_0`, `barrel_0` | 256×256 | Sit on the sea floor, so the artwork must **touch the bottom edge** of the image. |
| `obstacles/` | `neptune_0`, `mine_0`, `net_0` | 256×256 | Float in the water. Mines get a chain drawn to the floor automatically. |
| `obstacles/` | `octopus_0`…`octopus_5`, `jellyfish_0`…`jellyfish_5` | 256×256, 6 frames | Floating and animated. |
| `rewards/` | `pearl`, `shell`, `starfish`, `gem` | 256×256 | A soft glow around the item helps them stand out. |
| `boats/` | `sailboat`, `warship`, `trawler` | 256×160 | Side view, waterline near the bottom edge. |
| `decor/` | `coral0`–`coral2`, `weed0`, `weed1` | 128×128 | Scenery on the sea floor (doesn't collide). Should touch the bottom edge. |

Collision sizes come from `slipstream/themes.py` (`OBSTACLE_INFO`), not from
the image, so keep each object roughly filling its square.

## Textures

| Folder | Files | Size | Notes |
|---|---|---|---|
| `textures/` | `wall_coral`, `wall_seaweed`, `wall_ship`, `wall_rock` | 832×160 | The face of a wall (a 52×10-unit slab). Other sizes are stretched to fit. Holes are cut automatically. Should tile left-to-right. |
| `textures/` | `floor_sand`, `floor_gravel`, `floor_mud` | 512×512 | Sea floor, seen from above. **Must tile** seamlessly in both directions. |
| `textures/` | `cliff_reefrock`, `cliff_darkrock`, `cliff_kelprock` | 512×256 | Side cliffs. Must tile. |
| `textures/` | `surface` | 256×256 | Underside of the waves. Must tile. |
| `bg/` | `far`, `mid`, `near` | 1024×256 | Parallax background silhouettes. Draw them **white/grey on transparent**, because each theme tints them. Must tile left-to-right. |
| `band/` | `<theme>_sky`, `<theme>_wave0`–`wave2` | 4×64, 512×64 | Sky strip and rolling waves at the top of the screen. Waves must tile left-to-right. `<theme>` is `reef`, `wreck` or `kelp`. |
| `fx/` | `bubble`, `shadow`, `aim`, `dot`, `arrow`, `marker_last`, `marker_best`, `light_ray`, `caustics` | various | Effects. `aim`, `dot` and `arrow` should be white, because they're tinted in game. |

## Sounds

| Folder | Files | Notes |
|---|---|---|
| `sfx/` | `swish0`, `swish1` | Swimming (alternated). |
| `sfx/` | `splat` | Hitting a wall or obstacle. |
| `sfx/` | `chime0`–`chime3` | Rewards: pearl, shell, starfish, gem. |
| `sfx/` | `bounce`, `fanfare`, `gameover`, `click` | Floor/side bounce, new best time, game over, menu click. |
| `music/` | `<theme>_0` … `<theme>_4` | Looping music. Stage 0 plays first, and the music moves up a stage every 10 walls/obstacles. After stage 4 it alternates between stages 3 and 4. Tracks should loop seamlessly. |
