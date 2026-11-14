"""Global tuning constants for Slipstream.

World coordinates (Panda3D convention):
    X = left/right, Y = forward (into the screen), Z = up.
The sea floor is at z = 0 and the water surface at z = WORLD_H.
"""

TITLE = "Slipstream"
ASSET_VERSION = 6          # bump to force regeneration of procedural assets

# --- World geometry -------------------------------------------------------
WORLD_H = 10.0             # height of the water column (floor -> surface)
HALF_W = 24.0              # half width of the swimmable corridor
WALL_EXTRA = 2.0           # walls extend this far into the side cliffs
PPU = 16                   # wall texture pixels per world unit
SPAWN_AHEAD = 120.0        # how far ahead of the player things are created
DESPAWN_BEHIND = 25.0      # how far behind the player things are removed
FOG_NEAR = 4.0
FOG_FAR = 118.0

# --- Player ---------------------------------------------------------------
FISH_RADIUS = 0.45         # collision radius
FISH_SIZE = 1.8            # sprite size in world units
LATERAL_SPEED = 9.5
VERTICAL_SPEED = 6.0
SINK_SPEED = 1.1           # drift down when no vertical input
ACCEL = 7.0                # velocity smoothing factor
FLOOR_BOUNCE = 2.6
SIDE_BOUNCE = 0.55

# Forward speed ramps from START to MAX over time.
FORWARD_SPEED_START = 9.0
FORWARD_SPEED_MAX = 19.0
FORWARD_SPEED_RAMP = 150.0  # seconds (time constant)

# --- Camera ---------------------------------------------------------------
CAM_DIST_DEFAULT = 10.0
CAM_DIST_MIN = 3.0
CAM_DIST_MAX = 18.0
CAM_VFOV = 58.0            # vertical field of view (degrees)
CAM_ZOOM_SPEED = 7.0        # units per second while A/Z is held
CAM_LEAD = 0.08             # how far the fish leads the camera (s * velocity)
CAM_LEAD_MAX = 0.7
CAM_LEAD_RELAX = 0.6        # how slowly that offset relaxes once you stop (per second)

# --- Health ---------------------------------------------------------------
HEALTH_MAX = 100.0
HEALTH_REGEN = 0.6          # per second
WALL_DAMAGE = 22.0
OBSTACLE_DAMAGE = 14.0
HIT_INVULNERABLE = 0.9      # seconds

# --- Progression ----------------------------------------------------------
MUSIC_STAGE_EVERY = 10      # walls/obstacles passed per music change
DIFFICULTY_DISTANCE = 4000.0

# --- Audio ----------------------------------------------------------------
SAMPLE_RATE = 22050
MUSIC_VOLUME = 0.55
SFX_VOLUME = 0.9
