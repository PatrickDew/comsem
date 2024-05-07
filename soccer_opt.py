# Import necessary libraries
import pgzero, pgzrun, pygame
import math, sys, random
from enum import Enum
from pygame.math import Vector2

# Check Pygame Zero version
pgzero_version = [int(s) if s.isnumeric() else s for s in pgzero.__version__.split('.')]
if pgzero_version < [1,2]:
    print("This game requires at least version 1.2 of Pygame Zero. You have version {0}. Please upgrade using the command 'pip3 install --upgrade pgzero'".format(pgzero.__version__))
    sys.exit()

# Define game window dimensions and title
WIDTH = 800
HEIGHT = 480
TITLE = "Soccer"

# Calculate half window width
HALF_WINDOW_W = WIDTH / 2

# Define level dimensions
LEVEL_W = 1000
LEVEL_H = 1400
HALF_LEVEL_W = LEVEL_W // 2
HALF_LEVEL_H = LEVEL_H // 2

# Define pitch dimensions
HALF_PITCH_W = 442
HALF_PITCH_H = 622

# Define goal dimensions
GOAL_WIDTH = 186
GOAL_DEPTH = 20
HALF_GOAL_W = GOAL_WIDTH // 2

# Define pitch and goal boundaries
PITCH_BOUNDS_X = (HALF_LEVEL_W - HALF_PITCH_W, HALF_LEVEL_W + HALF_PITCH_W)
PITCH_BOUNDS_Y = (HALF_LEVEL_H - HALF_PITCH_H, HALF_LEVEL_H + HALF_PITCH_H)
GOAL_BOUNDS_X = (HALF_LEVEL_W - HALF_GOAL_W, HALF_LEVEL_W + HALF_GOAL_W)
GOAL_BOUNDS_Y = (HALF_LEVEL_H - HALF_PITCH_H - GOAL_DEPTH, HALF_LEVEL_H + HALF_PITCH_H + GOAL_DEPTH)

# Define pitch and goal rectangles
PITCH_RECT = pygame.rect.Rect(PITCH_BOUNDS_X[0], PITCH_BOUNDS_Y[0], HALF_PITCH_W * 2, HALF_PITCH_H * 2)
GOAL_0_RECT = pygame.rect.Rect(GOAL_BOUNDS_X[0], GOAL_BOUNDS_Y[0], GOAL_WIDTH, GOAL_DEPTH)
GOAL_1_RECT = pygame.rect.Rect(GOAL_BOUNDS_X[0], GOAL_BOUNDS_Y[1] - GOAL_DEPTH, GOAL_WIDTH, GOAL_DEPTH)

# Define AI player movement boundaries
AI_MIN_X = 78
AI_MAX_X = LEVEL_W - 78
AI_MIN_Y = 98
AI_MAX_Y = LEVEL_H - 98

# Define starting positions for players
PLAYER_START_POS = [(350, 550), (650, 450), (200, 850), (500, 750), (800, 950), (350, 1250), (650, 1150)]

# Define lead distances for players
LEAD_DISTANCE_1 = 10
LEAD_DISTANCE_2 = 50

# Define dribble distances
DRIBBLE_DIST_X, DRIBBLE_DIST_Y = 18, 16

# Define speeds for different player actions
PLAYER_DEFAULT_SPEED = 2
CPU_PLAYER_WITH_BALL_BASE_SPEED = 2.6
PLAYER_INTERCEPT_BALL_SPEED = 2.75
LEAD_PLAYER_BASE_SPEED = 2.9
HUMAN_PLAYER_WITH_BALL_SPEED = 3
HUMAN_PLAYER_WITHOUT_BALL_SPEED = 3.3

# Define debug flags
DEBUG_SHOW_LEADS = False
DEBUG_SHOW_TARGETS = False
DEBUG_SHOW_PEERS = False
DEBUG_SHOW_SHOOT_TARGET = False
DEBUG_SHOW_COSTS = False

# Define class for difficulty settings
class Difficulty:
    def __init__(self, goalie_enabled, second_lead_enabled, speed_boost, holdoff_timer):
        self.goalie_enabled = goalie_enabled
        self.second_lead_enabled = second_lead_enabled
        self.speed_boost = speed_boost
        self.holdoff_timer = holdoff_timer

# Define difficulty levels
DIFFICULTY = [Difficulty(False, False, 0, 120), Difficulty(False, True, 0.1, 90), Difficulty(True, True, 0.2, 60)]

# Define custom sine function
def sin(x):
    return math.sin(x*math.pi/4)

# Define custom cosine function
def cos(x):
    return sin(x+2)

# Convert vector to angle
def vec_to_angle(vec):
    return int(4 * math.atan2(vec.x, -vec.y) / math.pi + 8.5) % 8

# Convert angle to vector
def angle_to_vec(angle):
    return Vector2(sin(angle), -cos(angle))

# Define key function for sorting based on distance
def dist_key(pos):
    return lambda p: (p.vpos - pos).length()

def safe_normalise(vec):
    length = vec.length()
    if length == 0:
        return Vector2(0,0), 0
    else:
        return vec.normalize(), length

# This function safely normalizes a vector. It returns a tuple containing the normalized vector and its length. 
# If the length of the input vector is 0, it returns a zero vector and 0 as length.

class MyActor(Actor):
    def __init__(self, img, x=0, y=0, anchor=None):
        super().__init__(img, (0, 0), anchor=anchor)
        self.vpos = Vector2(x, y)

    def draw(self, offset_x, offset_y):
        self.pos = (self.vpos.x - offset_x, self.vpos.y - offset_y)
        super().draw()

# This is a custom actor class that extends Pygame's Actor class. It initializes an actor object with a given image and position.
# The draw method is overridden to draw the actor at its virtual position (vpos) adjusted by the offset.

KICK_STRENGTH = 11.5
DRAG = 0.98

# Constants representing the kick strength of the ball and the drag factor affecting its velocity.

def ball_physics(pos, vel, bounds):
    pos += vel

    if pos < bounds[0] or pos > bounds[1]:
        pos, vel = pos - vel, -vel

    return pos, vel * DRAG

# This function simulates the physics of the ball's movement. It updates the position and velocity of the ball based on its current velocity and position,
# and ensures that the ball bounces off the boundaries defined by the 'bounds' parameter.

def steps(distance):
    steps, vel = 0, KICK_STRENGTH

    while distance > 0 and vel > 0.25:
        distance, steps, vel = distance - vel, steps + 1, vel * DRAG

    return steps

# This function calculates the number of steps needed for the ball to travel a given distance based on its kick strength and drag.

class Goal(MyActor):
    def __init__(self, team):
        x = HALF_LEVEL_W
        y = 0 if team == 0 else LEVEL_H
        super().__init__("goal" + str(team), x, y)

        self.team = team

    def active(self):
        return abs(game.ball.vpos.y - self.vpos.y) < 500

# This class represents a goal post. It extends the MyActor class and initializes a goal post object with its position based on the team (0 or 1).
# The active method checks if the goal post is actively involved in the game based on the position of the ball.

def targetable(target, source):
    v0, d0 = safe_normalise(target.vpos - source.vpos)

    if not game.teams[source.team].human():
        for p in game.players:
            v1, d1 = safe_normalise(p.vpos - source.vpos)
            if p.team != target.team and d1 > 0 and d1 < d0 and v0*v1 > 0.8:
                return False

    return target.team == source.team and d0 > 0 and d0 < 300 and v0 * angle_to_vec(source.dir) > 0.8

# This function determines if a target (player or ball) is targetable by a source player. It calculates the angle and distance between the target and source,
# and checks if the target is obstructed by other players. It returns True if the target is targetable, False otherwise.

def avg(a, b):
    return b if abs(b-a) < 1 else (a+b)/2

# This function calculates the average of two numbers with a tolerance of 1.

def on_pitch(x, y):
    return PITCH_RECT.collidepoint(x,y) \
           or GOAL_0_RECT.collidepoint(x,y) \
           or GOAL_1_RECT.collidepoint(x,y)

# This function checks if a given point (x, y) is within the pitch boundaries or collides with the goal posts.

class Ball(MyActor):
    def __init__(self):
        super().__init__("ball", HALF_LEVEL_W, HALF_LEVEL_H)
        self.vel = Vector2(0, 0)

        self.owner = None
        self.timer = 0

        self.shadow = MyActor("balls")

    def collide(self, p):
        return p.timer < 0 and (p.vpos - self.vpos).length() <= DRIBBLE_DIST_X

    def update(self):
        self.timer -= 1

        if self.owner:
            new_x = avg(self.vpos.x, self.owner.vpos.x + DRIBBLE_DIST_X * sin(self.owner.dir))
            new_y = avg(self.vpos.y, self.owner.vpos.y - DRIBBLE_DIST_Y * cos(self.owner.dir))

            if on_pitch(new_x, new_y):
                self.vpos = Vector2(new_x, new_y)
            else:
                self.owner.timer = 60
                self.vel = angle_to_vec(self.owner.dir) * 3
                self.owner = None
        else:
            if abs(self.vpos.y - HALF_LEVEL_H) > HALF_PITCH_H:
                bounds_x = GOAL_BOUNDS_X
            else:
                bounds_x = PITCH_BOUNDS_X
            # Calculate vertical boundary for the ball based on its position relative to the goal and pitch
            if abs(self.vpos.x - HALF_LEVEL_W) < HALF_GOAL_W:
                bounds_y = GOAL_BOUNDS_Y
            else:
                bounds_y = PITCH_BOUNDS_Y

            # Apply ball physics to update ball position and velocity in both horizontal and vertical directions
            self.vpos.x, self.vel.x = ball_physics(self.vpos.x, self.vel.x, bounds_x)
            self.vpos.y, self.vel.y = ball_physics(self.vpos.y, self.vel.y, bounds_y)

        # Update shadow position of the ball to match its position
        self.shadow.vpos = Vector2(self.vpos)

        # Iterate over all players in the game
        for target in game.players:

            # Check for collision between ball and player and assign ownership if conditions are met
            if (not self.owner or self.owner.team != target.team) and self.collide(target):
                if self.owner:
                    self.owner.timer = 60
                self.timer = game.difficulty.holdoff_timer
                game.teams[target.team].active_control_player = self.owner = target

        # If the ball has an owner, determine shooting target and execute shooting behavior
        if self.owner:
            team = game.teams[self.owner.team]

            # Find targetable players for shooting
            targetable_players = [p for p in game.players + game.goals if p.team == self.owner.team and targetable(p, self.owner)]

            # Select shooting target and update debug shoot target
            if len(targetable_players) > 0:
                target = min(targetable_players, key=dist_key(self.owner.vpos))
                game.debug_shoot_target = target.vpos
            else:
                target = None

            # Decide whether to shoot based on game conditions and player type
            if team.human():
                do_shoot = team.controls.shoot()
            else:
                do_shoot = self.timer <= 0 and target and cost(target.vpos, self.owner.team) < cost(self.owner.vpos, self.owner.team)

            # If shooting is allowed, execute shooting behavior
            if do_shoot:
                game.play_sound("kick", 4)
                if target:
                    r = 0
                    iterations = 8 if team.human() and isinstance(target, Player) else 1
                    for i in range(iterations):
                        t = target.vpos + angle_to_vec(self.owner.dir) * r
                        vec, length = safe_normalise(t - self.vpos)
                        r = HUMAN_PLAYER_WITHOUT_BALL_SPEED * steps(length)
                else:
                    vec = angle_to_vec(self.owner.dir)
                    target = min([p for p in game.players if p.team == self.owner.team],
                                key=dist_key(self.vpos + (vec * 250)))

                # Assign active control player for the team if shooting at a player, reset owner's timer, update ball velocity for shooting, and clear owner
                if isinstance(target, Player):
                    game.teams[self.owner.team].active_control_player = target
                self.owner.timer = 10
                self.vel = vec * KICK_STRENGTH
                self.owner = None

# Check if movement is allowed based on position
def allow_movement(x, y):
    if abs(x - HALF_LEVEL_W) > HALF_LEVEL_W:
        return False
    elif abs(x - HALF_LEVEL_W) < HALF_GOAL_W + 20:
        return abs(y - HALF_LEVEL_H) < HALF_PITCH_H
    else:
        return abs(y - HALF_LEVEL_H) < HALF_LEVEL_H

# Calculate cost of a position for a team considering various factors
def cost(pos, team, handicap=0):
    own_goal_pos = Vector2(HALF_LEVEL_W, 78 if team == 1 else LEVEL_H - 78)
    inverse_own_goal_distance = 3500 / (pos - own_goal_pos).length()

    result = inverse_own_goal_distance \
            + sum([4000 / max(24, (p.vpos - pos).length()) for p in game.players if p.team != team]) \
            + ((pos.x - HALF_LEVEL_W)**2 / 200 \
            - pos.y * (4 * team - 2)) \
            + handicap

    return result, pos

# Define Player class inheriting from MyActor
class Player(MyActor):
    ANCHOR = (25,37)  # Anchor point for player sprite
