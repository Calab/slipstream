"""Global tuning constants for Slipstream.

World coordinates (Panda3D convention):
    X = left/right, Y = forward (into the screen), Z = up.
The sea floor is at z = 0 and the water surface at z = WORLD_H.
The fish starts at y = 0 and swims towards +y forever; its y is the
"distance" shown for the last-run / best markers.

Distances are in world units (the fish sprite is FISH_SIZE units tall),
speeds in units per second and times in seconds unless noted otherwise.
Changing a number here is the easiest way to tune how the game feels.
"""

TITLE = "Slipstream"
ASSET_VERSION = 10          # bump to force regeneration of procedural assets

# --- World geometry -------------------------------------------------------
WORLD_H = 10.0             # height of the water column (floor -> surface)
HALF_W = 24.0              # half width of the swimmable corridor (x runs -HALF_W..+HALF_W)
WALL_EXTRA = 2.0           # walls extend this far into the side cliffs
PPU = 16                   # wall texture pixels per world unit (also the collision
                           # resolution of the holes in walls)
SPAWN_AHEAD = 165.0        # how far ahead of the player things are created
DESPAWN_BEHIND = 25.0      # how far behind the player things are removed
FOG_NEAR = 10.0            # fog starts this far from the camera...
FOG_FAR = 165.0            # ...and is solid water colour here (walls emerge from the
                           # haze this far ahead)

# --- Player ---------------------------------------------------------------
FISH_RADIUS = 0.45         # collision radius
FISH_SIZE = 1.8            # sprite size in world units
LATERAL_SPEED = 9.5        # top left/right swimming speed
VERTICAL_SPEED = 6.0       # top up/down swimming speed
SINK_SPEED = 1.1           # drift down when no vertical input
ACCEL = 7.0                # velocity smoothing factor (higher = snappier controls)
FLOOR_BOUNCE = 2.6         # upward speed given when the fish bumps the sea floor
SIDE_BOUNCE = 0.55         # fraction of sideways speed kept when bouncing off a cliff

# Forward speed ramps from START to MAX over time.
FORWARD_SPEED_START = 9.0
FORWARD_SPEED_MAX = 19.0
FORWARD_SPEED_RAMP = 150.0  # seconds (time constant: ~63% of the way to MAX after
                            # this long, ~86% after twice as long; see world/pace.py)

# --- Camera ---------------------------------------------------------------
CAM_DIST_DEFAULT = 10.0     # how far behind the fish the camera sits
CAM_DIST_MIN = 3.0          # closest zoom (A key)
CAM_DIST_MAX = 18.0         # furthest zoom (Z key)
CAM_VFOV = 58.0            # vertical field of view (degrees)
CAM_ZOOM_SPEED = 7.0        # units per second while A/Z is held
CAM_LEAD = 0.08             # how far the fish leads the camera (s * velocity)
CAM_LEAD_MAX = 0.7          # ...but never more than this many units
CAM_LEAD_RELAX = 0.6        # how slowly that offset relaxes once you stop (per second)

# --- Health ---------------------------------------------------------------
HEALTH_MAX = 100.0          # the run ends when health reaches 0
HEALTH_REGEN = 0.6          # per second
WALL_DAMAGE = 25.0          # health lost for hitting the solid part of a wall
OBSTACLE_DAMAGE = 14.0      # health lost for hitting an obstacle
HIT_INVULNERABLE = 0.9      # seconds after a hit during which further hits are free
CLIFF_DAMAGE = 5.0          # scraping against a side cliff
CLIFF_COOLDOWN = 1.0        # seconds between cliff hits (so being pinned doesn't drain you)

# --- Progression ----------------------------------------------------------
MUSIC_STAGE_EVERY = 10      # walls/obstacles passed per music change
DIFFICULTY_DISTANCE = 4000.0  # distance at which the course reaches full difficulty
                              # (smaller holes, more obstacles); it ramps up linearly

# --- Audio ----------------------------------------------------------------
SAMPLE_RATE = 22050         # samples per second (for reference only: the generators
                            # use their own copy, SR in assetgen/audio.py)
MUSIC_VOLUME = 0.55         # 0..1
SFX_VOLUME = 0.9            # 0..1
