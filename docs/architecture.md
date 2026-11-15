# How Slipstream runs

Six diagrams covering the whole game: who owns what, the startup path, the
state machine, one frame of play, how the endless course is generated, and how
art and sound are found. A formatted OpenDocument version with the same diagrams is in
[architecture.odt](architecture.odt)
(rebuild it with `python tools/build_docs.py`).

- [Module map](#module-map)
- [Startup](#startup)
- [Game states](#game-states)
- [One frame of play](#one-frame-of-play)
- [Course generation](#course-generation)
- [Assets and resources](#assets-and-resources)
- [Tuning numbers](#tuning-numbers)

## Module map

*`app.py`, `world/__init__.py`*

`SlipstreamApp` owns everything. It splits the game into a 3D half (`World`,
which moves things and reports collisions) and a rules half (the app itself,
which turns those reports into health, sounds, HUD updates and saved records).
`World` knows nothing about health or scoring.

```mermaid
flowchart LR
  main["main.py<br/>parse args"] --> app["SlipstreamApp<br/>state machine + rules"]
  app --> save["SaveData<br/>save.json"]
  app --> res["Resources<br/>custom/ or assets/"]
  app --> snd["SoundManager<br/>SFX + crossfading music"]
  app --> ui["UI overlays<br/>HUD · StartMenu · Pause<br/>GameOver · About · Touch · SurfaceBand"]
  app --> world["World<br/>one per theme"]
  res --> gen["AssetBuilder<br/>procedural generators"]
  world --> env["Environment<br/>floor, cliffs, fog, decor"]
  world --> player["Player<br/>movement + bounces"]
  world --> course["Course<br/>walls, obstacles, rewards"]
  world --> trench["Trench<br/>cliff drift per run"]
  world --> aim["AimHelper<br/>ring + dots"]
  world --> fx["Bubbles"]
  world --> markers["DistanceMarkers<br/>Last Run / Best gates"]
  course --> walls["WallFactory → Wall"]
  course --> obs["Obstacle / Reward"]
  themes["themes.py<br/>THEMES"] -.-> app
  config["config.py<br/>tuning constants"] -.-> world
```

## Startup

*`SlipstreamApp.__init__`*

The save file is read before Panda3D is imported, because the last window size
must be set before the window opens. Missing assets are generated next, with a
progress message rendered frame by frame.

```mermaid
flowchart TD
  A["main.py: parse --width --height --fullscreen --fps --reset-save"] --> B["SaveData loads save.json<br/>(defaults if missing)"]
  B --> C["configure_panda: PRC settings<br/>window size and origin from save"]
  C --> D["ShowBase opens window<br/>load font, watch window events"]
  D --> E{"--reset-save?"}
  E -- yes --> E1["clear records"] --> F
  E -- no --> F["AssetBuilder"]
  F --> G{"version.json matches<br/>ASSET_VERSION?"}
  G -- no --> G1["delete generated folders<br/>(custom/ untouched)"] --> H
  G -- yes --> H["build: generate only missing files<br/>'Generating sea life... i/n'"]
  H --> I["Resources + window icon + SoundManager"]
  I --> J["bind keys: held keys go into self.keys,<br/>pressed keys call on_* handlers"]
  J --> K["create UI overlays"]
  K --> L["load_theme(last used theme)<br/>builds World, band, music"]
  L --> M["to_menu()"]
  M --> N["taskMgr.add(_task)<br/>runs every frame"]
```

## Game states

*`self.state`*

The app is a five-state machine. Key events call `on_*` methods that check the
current state before acting; `_task` then advances whichever state is active
each frame.

```mermaid
stateDiagram-v2
  [*] --> menu: startup
  menu --> about: ? key
  about --> menu: ? / Space / Esc
  menu --> play: Space → start_run()
  play --> paused: P
  paused --> play: P / Space
  play --> gameover: health ≤ 0 → game_over()
  gameover --> play: Space → start_run()
  play --> menu: Esc (run is still recorded)
  paused --> menu: Esc
  gameover --> menu: Esc
  menu --> [*]: Q / Esc → save + quit
  note right of menu
    T next theme · S sound
    R reset best · A aim helper
    B touch buttons
    fish swims by itself (attract mode)
  end note
```

- **menu / about:** `_update_attract` fakes key presses from slow sine waves so
  the fish weaves through open water.
- **play:** `_update_play` runs the rules (next diagram).
- **paused:** the world is not updated at all, so it stays frozen.
- **gameover:** the fish drifts forward at speed 2 with `active=False` (no
  collisions) behind the panel.

## One frame of play

*`_task` → `_update_play` → `World.update`*

Each frame, `dt` is capped at 1/20 s so a stall can't push the fish through a
wall in one step. The world moves everything and returns two lists: **events**
(bumped the floor or a cliff) and **hits** (hit, reward or passed). The app
turns those into game consequences.

```mermaid
flowchart TD
  T["_task(dt ≤ 0.05 s)"] --> T1["sound.update · hud.update · menu.update · band.update"]
  T1 --> S{"state"}
  S -- play --> P0["_input(): held keys → ix, iz, zoom"]
  S -- "menu / about" --> AT["_update_attract → world.update(active=False)"]
  S -- gameover --> GO["world.update(speed 2, active=False)"]
  S -- paused --> FZ["nothing moves"]
  P0 --> P1["run_time += dt<br/>speed = forward_speed(run_time)"]
  P1 --> W

  subgraph W["World.update"]
    direction TB
    W1["Player.update: ease velocity,<br/>sink when idle, clamp to trench,<br/>floor bounce, surface cap"] --> W2["Course.fill(y, difficulty)<br/>difficulty = y / 4000, max 1"]
    W2 --> W3["check objects within 4 units:<br/>reward touched → 'reward'<br/>wall/obstacle touched once → 'hit'<br/>behind and untouched → 'passed'"]
    W3 --> W4["Course.update: animate, despawn 25 behind"]
    W4 --> W5["markers, bubbles, camera lead + zoom"]
    W5 --> W6["sync sprites · AimHelper · _place_camera<br/>(tilt keeps fish and its shadow in view)"]
  end

  W --> R1["swim swish every 0.5 s while moving"]
  R1 --> R2{"events"}
  R2 -- floor --> R2a["bounce sound"]
  R2 -- "side, cooldown over" --> R2b["−5 health, 1 s cooldown, shake"]
  R2 --> R3{"each hit"}
  R3 -- "hit, not invulnerable" --> R3a["−25 wall / −14 obstacle<br/>0.9 s invulnerable, flash, shake"]
  R3 -- reward --> R3b["+6 / +12 / +18 / +30 health, chime"]
  R3 -- passed --> R3c["walls_passed++ · progress++<br/>music stage = progress ÷ 10"]
  R3 --> R4["regen +0.6 health/s, cap 100"]
  R4 --> R5["banners: passed last run · NEW BEST TIME"]
  R5 --> R6["hud.set_values"]
  R6 --> R7{"health ≤ 0?"}
  R7 -- yes --> R8["game_over(): save.finish_run,<br/>show panel, stop music"]
  R7 -- no --> NX["next frame"]
```

- **One hit per object.** Each wall or obstacle sets `hit = True` on first
  contact, and the 0.9 s invulnerability window stops brushing along a wall
  from costing several hits.
- **Score is time survived.** `run_time` is the score; the fish's `y` is the
  distance used for the Last Run and Best gates.
- **Wall collision is pixel exact.** A wall's hole mask is also its texture
  alpha; the fish's centre and 8 rim points are tested against it.

## Course generation

*`course.py`, `walls.py`, `pace.py`, `trench.py`*

The course is endless but fully determined by one random seed per run. It is
built one **segment** at a time (a wall, then rows of obstacles up to the next
wall) whenever the next wall comes within 165 units. The key guarantee: every
wall has an opening the player can reach in time from some opening of the
previous wall.

```mermaid
flowchart TD
  S0["start_run: seed = random<br/>Trench(seed) · Course(seed)"] --> F{"next_wall_y < player_y + 165?"}
  F -- no --> DONE["wait for next frame"]
  F -- yes --> SEG["_segment(difficulty d)"]
  SEG --> N["choose 1–3 openings<br/>(fewer 3s when d > 0.6)"]
  N --> RCH["pace.reach(prev wall, this wall):<br/>time between walls − 0.6 s reaction<br/>× 60% of top swim speed"]
  RCH --> MO["make_openings: place holes within reach<br/>of every anchor (previous openings),<br/>inside Trench.bounds at this y"]
  MO --> OK{"every anchor covered?"}
  OK -- "no, under 30 tries" --> MO
  OK -- "yes, or best of 30" --> WALL["Wall: lumpy holes from sine harmonics,<br/>radius shrinks with d · mask = texture = collision"]
  WALL --> ANC["anchors = this wall's openings"]
  ANC --> RW{"45% chance"}
  RW -- yes --> RW1["reward in front of an opening"]
  RW --> ROWS["rows from wall.back to next wall − 10<br/>spacing tightens with d"]
  RW1 --> ROWS
  ROWS --> ROW{"per row"}
  ROW -- "55% → 95% with d" --> OB["obstacle: half random x,<br/>half lined up with an opening<br/>(2nd side by side up to 50% at full d)"]
  ROW -- "else 70%" --> RR["reward: pearl 45% · shell 30%<br/>starfish 18% · gem 7%"]
  OB --> GAP
  RR --> GAP["next_wall_y += gap<br/>46–78 at start → 30–52 at full d"]
  GAP --> F
```

- **Speed.** Forward speed rises from 9 toward 19 units/s on an exponential
  curve (time constant 150 s). `time_at(y)` inverts the distance integral by
  bisection so generation knows how long the player has between walls.
- **Trench.** Each cliff drifts inward by up to 9.6 units using three long sine
  waves with random phases, clipped and faded in after the first 25 units.

## Assets and resources

*`assetgen/`, `resources.py`, `sound.py`*

Nothing binary ships in the repo. Generators draw every sprite, texture, effect
and tune with numpy and Pillow. At load time, files in `custom/` always win
over generated ones.

```mermaid
flowchart LR
  subgraph GEN["Generate (first launch)"]
    direction TB
    D{"frozen build?"} -- yes --> DB{"bundled assets current?"}
    DB -- yes --> BU["use bundled assets/"]
    DB -- no --> UD["user data dir/assets"]
    D -- no --> PR["project assets/<br/>(user dir if not writable)"]
    PR --> TASKS["tasks per file:<br/>sprites.py · textures.py · audio.py"]
    UD --> TASKS
    TASKS --> MISS["build only missing files"]
  end
  subgraph LOAD["Load (Resources)"]
    direction TB
    REQ["texture('obstacles', 'mine_0.png')"] --> C1{"in custom/ next to exe?"}
    C1 -- no --> C2{"in project/bundled custom/?<br/>any of png · jpg · jpeg"}
    C1 -- yes --> USE["load + cache"]
    C2 -- yes --> USE
    C2 -- no --> GENF["generated asset"] --> USE
  end
  GEN --> LOAD
  LOAD --> MUS["SoundManager: 8 tunes per theme,<br/>stage every 10 passes,<br/>after 8th cycles last 4,<br/>crossfade + preload next"]
```

## Tuning numbers

*`config.py`*

| Constant | Value | What it controls |
|---|---|---|
| `HEALTH_MAX` | 100 | Run ends at 0 |
| `WALL_DAMAGE` / `OBSTACLE_DAMAGE` | 25 / 14 | Health lost per hit |
| `CLIFF_DAMAGE` | 5 per 1 s | Scraping or being pushed by a side cliff |
| `HIT_INVULNERABLE` | 0.9 s | Grace period after a hit |
| `HEALTH_REGEN` | 0.6 /s | Slow natural healing |
| `FORWARD_SPEED_START` → `MAX` | 9 → 19 | Units/s, ramp constant 150 s |
| `DIFFICULTY_DISTANCE` | 4000 | Distance at which difficulty reaches 1 |
| `SPAWN_AHEAD` / `DESPAWN_BEHIND` | 165 / 25 | Course window around the fish |
| `MUSIC_STAGE_EVERY` | 10 | Walls and obstacles passed per tune change |
| `CAM_DIST_MIN` – `MAX` | 3 – 18 | A / Z zoom range |

Drawn from the source at commit ff32eb0. The diagrams simplify some detail; the
code is the reference.
