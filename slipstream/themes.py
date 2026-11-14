"""Theme definitions.

Each theme describes the player sprite, the boat on the surface, wall
materials, obstacle/reward mix, colours and the music style.  Everything a
theme needs is generated procedurally by :mod:`slipstream.assetgen`.

To add a theme: add an entry to THEMES, and (if it uses new sprite or
material names) add generators for those in assetgen/sprites.py or
assetgen/textures.py.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    blurb: str
    player: str                      # sprite family name ("fish_clown", "sub", ...)
    boat: str                        # boat sprite name
    floor: str                       # floor material
    cliff: str                       # side cliff material
    wall_materials: tuple            # wall material names
    obstacles: tuple                 # obstacle kinds
    rewards: tuple = ("pearl", "shell", "starfish", "gem")
    water: tuple = (0.10, 0.35, 0.50)        # fog / background colour
    surface: tuple = (0.55, 0.85, 0.95)      # underside of the waves
    bg_tints: tuple = ((0.2, 0.45, 0.58), (0.14, 0.34, 0.45), (0.09, 0.24, 0.33))
    sky_top: tuple = (70, 140, 220)
    sky_bottom: tuple = (190, 225, 245)
    wave_colors: tuple = ((40, 110, 170), (30, 95, 150), (20, 80, 130))
    decor: tuple = ("weed0", "coral0")
    music: dict = field(default_factory=dict)


THEMES = [
    Theme(
        key="reef",
        name="Coral Reef",
        blurb="A clownfish dodging coral and kelp in warm shallows.",
        player="fish_clown",
        boat="sailboat",
        floor="sand",
        cliff="reefrock",
        wall_materials=("coral", "seaweed", "coral"),
        obstacles=("chest", "boulder", "octopus", "neptune", "jellyfish"),
        water=(0.10, 0.42, 0.55),
        surface=(0.60, 0.90, 0.95),
        bg_tints=((0.22, 0.52, 0.62), (0.15, 0.40, 0.50), (0.10, 0.30, 0.38)),
        sky_top=(60, 140, 230),
        sky_bottom=(200, 235, 250),
        wave_colors=((70, 170, 210), (40, 140, 190), (25, 115, 165)),
        decor=("coral0", "coral1", "coral2", "weed0"),
        music=dict(root=62, scale="major", bpm=112, seed=11, lead="whistle",
                   progression=(0, 3, 0, 4, 0, 3, 4, 0)),
    ),
    Theme(
        key="wreck",
        name="Shipwreck Deep",
        blurb="A little submarine threading through sunken hulls and mines.",
        player="sub",
        boat="warship",
        floor="gravel",
        cliff="darkrock",
        wall_materials=("ship", "rock", "ship"),
        obstacles=("mine", "anchor", "chest", "barrel", "boulder", "octopus"),
        water=(0.05, 0.17, 0.30),
        surface=(0.30, 0.55, 0.70),
        bg_tints=((0.12, 0.25, 0.38), (0.08, 0.18, 0.29), (0.05, 0.12, 0.21)),
        sky_top=(55, 70, 105),
        sky_bottom=(150, 165, 185),
        wave_colors=((60, 90, 120), (45, 72, 100), (32, 58, 85)),
        decor=("weed1", "weed1", "weed0", "coral1"),
        music=dict(root=57, scale="minor", bpm=100, seed=23, lead="accordion",
                   progression=(0, 6, 0, 4, 0, 5, 6, 0)),
    ),
    Theme(
        key="kelp",
        name="Kelp Forest",
        blurb="A mermaid racing a trawler through towering kelp.",
        player="mermaid",
        boat="trawler",
        floor="mud",
        cliff="kelprock",
        wall_materials=("seaweed", "rock", "seaweed"),
        obstacles=("net", "jellyfish", "octopus", "boulder", "neptune", "anchor"),
        water=(0.08, 0.30, 0.25),
        surface=(0.55, 0.80, 0.60),
        bg_tints=((0.18, 0.40, 0.32), (0.12, 0.30, 0.24), (0.07, 0.21, 0.17)),
        sky_top=(110, 160, 200),
        sky_bottom=(225, 225, 205),
        wave_colors=((70, 140, 130), (50, 118, 110), (35, 95, 90)),
        decor=("weed0", "weed1", "weed0", "coral2"),
        music=dict(root=60, scale="dorian", bpm=124, seed=37, lead="marimba",
                   progression=(0, 6, 3, 0, 0, 6, 4, 0)),
    ),
]

THEME_BY_KEY = {t.key: t for t in THEMES}

# Reward kind -> (health restored, sprite size)
REWARD_INFO = {
    "pearl": (6, 1.4),
    "shell": (12, 1.7),
    "starfish": (18, 1.8),
    "gem": (30, 1.6),
}

# Obstacle kind -> dict(size, floating, moves, frames)
OBSTACLE_INFO = {
    "chest":     dict(size=4.3, floating=False, moves=False),
    "boulder":   dict(size=4.8, floating=False, moves=False),
    "anchor":    dict(size=4.6, floating=False, moves=False),
    "barrel":    dict(size=3.8, floating=False, moves=False),
    "octopus":   dict(size=3.6, floating=True, moves=True),
    "neptune":   dict(size=4.2, floating=True, moves=True),
    "jellyfish": dict(size=2.9, floating=True, moves=True),
    "mine":      dict(size=2.8, floating=True, moves=False, tether=True),
    "net":       dict(size=4.0, floating=True, moves=True),
}
