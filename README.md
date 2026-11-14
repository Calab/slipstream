# Slipstream

A third-person underwater game written in Python with
[Panda3D](https://www.panda3d.org/). You swim from behind your fish (or submarine)
through irregular openings in walls that get closer and closer, dodge obstacles,
and collect rewards that restore health.

All art, textures, sound effects and music are **generated procedurally** with
numpy + Pillow on first launch. The game ships with no binary assets.

## Running

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py                     # --fullscreen, --width/--height, --fps
```

The window reopens at the size and position you last left it.

The first launch takes a few seconds to generate assets into `./assets`.
`python tools/generate_assets.py --force` rebuilds them.

Works on Linux, Windows and macOS (Python 3.9+). Saves and best times are stored in
`~/.local/share/slipstream` (Linux), `%APPDATA%\Slipstream` (Windows) or
`~/Library/Application Support/Slipstream` (macOS).

## Controls

| Key | Start screen | In game |
|---|---|---|
| Arrow keys | | Swim up / down / left / right |
| A / Z | | Camera closer / further |
| Space | Start | Swim again (after game over) |
| T | Next theme | |
| S | Sound on/off | |
| R | Reset best time for the theme | |
| A | Aim helper on/off | |
| B | Touch buttons on/off | Touch buttons on/off |
| P | | Pause |
| Q / Esc | Quit | Esc: back to the menu |

Every start-screen key also has an on-screen button. The touch buttons (on-screen arrows plus A/Z)
is meant for tablets and phones, and also works with a mouse.

## Gameplay

* When you stop swimming the fish slowly sinks. It bounces off the sea floor in a
  puff of bubbles. You can't swim around the ends of a wall or over its top.
* The side cliffs drift in and out by up to 9.6 units each as you go (at its
  narrowest the trench is 60% of its full width), so it narrows and widens and
  the rock can creep up on a fish sitting near one side. Scraping a cliff (or
  being pushed by one) costs 5 health, at most once a second.
* Openings glow softly around their edges and show bright water through them,
  so they stand out even from far away.
* Each wall has 1–3 irregular openings, anywhere from the sea floor (an arch)
  up to just under the surface. Every wall has an opening you can reach in time
  from any opening of the previous wall. Hitting a wall or an obstacle splats you
  and costs health. Health also comes back slowly over time.
* Rewards: pearl +6, shell +12, starfish +18, gem +30.
* The camera tilts to keep the fish's shadow on the sea floor in view. Compare
  the shadow with the base of the next wall to judge how far away it is.
  (When zoomed right in, keeping the fish in view takes priority.)
* **Aim helper** (toggle with A on the start screen): a ring on the next wall
  shows where the fish arrives if it holds its course. It is green for an opening
  and red for a splat, and it moves onto any obstacle that is in the way. Dots
  between the fish and the ring crowd together as the wall gets closer.
* Obstacles get more frequent over time. Rows come closer together, and later
  on two obstacles can appear side by side.
* Each theme has 8 different nautical tunes, alternating jigs and hornpipes.
  The music moves to the next, busier and faster tune every 10 walls/obstacles
  passed. After the eighth it keeps cycling through the last four.
* A glowing gate marks where your **last run** ended (gold) and how far your
  **best** run got (green). A banner shows when you beat your best time.
* Forward speed and difficulty (narrower openings, closer walls) ramp up over time.

## Themes

| Theme | Player | Walls | Obstacles | Boat |
|---|---|---|---|---|
| Coral Reef | Clownfish | coral, seaweed | chest, boulder, octopus, Neptune, jellyfish, fish hook | sailboat |
| Shipwreck Deep | Submarine | sunken hull planks, rock | mine, anchor, chest, barrel, boulder, octopus, iceberg | warship |
| Kelp Forest | Mermaid | kelp, rock | net, jellyfish, octopus, boulder, Neptune, anchor, galleon hull | trawler |

## Using your own art and sounds

Put replacement files in `custom/`, using the same folder and file name as the
generated asset. For example, `custom/obstacles/neptune_0.png` replaces Neptune.
The game checks `custom/` first and never modifies it, so commit it with your
project. See [custom/README.md](custom/README.md) for every file name, size and
format.

To add a theme, add a `Theme(...)` entry in `slipstream/themes.py`. If it uses new
sprites or materials, add a generator for each to `slipstream/assetgen/` and bump
`ASSET_VERSION` in `config.py`.

## Project layout

```
main.py                     launcher / command-line options
slipstream/
  app.py                    window, input, game states, scoring
  config.py                 tuning constants (speeds, damage, sizes…)
  themes.py                 theme definitions, obstacle & reward tables
  save.py                   settings + per-theme records (JSON)
  sound.py                  sound effects, cross-fading stage music
  resources.py              texture/sound loading
  assetgen/                 procedural generators
    sprites.py              fish/sub rear views, obstacles, rewards, boats, bg layers
    textures.py             floor, cliffs, surface, wall materials
    audio.py                synthesised SFX and nautical music
  world/
    environment.py          floor, cliffs, surface, parallax background, fog, light rays
    terrain.py              bumpy floor and cliff meshes
    trench.py               how far each side cliff has drifted in at any distance
    player.py               player movement, sinking, bounce, animation, shadow
    walls.py                walls with irregular openings (mask = visuals = collision)
    obstacles.py            obstacles (some moving) and rewards
    course.py               spawning/despawning, last/best distance markers
    effects.py              bubbles
    aim.py                  aim helper (target ring + distance dots)
  ui/                       HUD, surface band (waves + boat), menus, touch buttons
  fonts/                    Some Time Later font + licence
tools/generate_assets.py    pre-generate / rebuild assets
custom/                     your replacement art & sounds (overrides assets/)
```

## Credits

Text uses the [Some Time Later](https://github.com/ctrlcctrlv/some-time-later) font
by Fredrick R. Brennan, under the SIL Open Font License 1.1
(`slipstream/fonts/LICENSE-SomeTimeLater.txt`).

## Android

Panda3D has experimental Android support (`build_apps` with the Android
platform tag in Panda3D 1.11). The game already includes the pieces it would
need: the touch buttons, assets that are generated rather than bundled, and a
writable-directory fallback for the asset cache. A packaging setup would still
have to be added.
