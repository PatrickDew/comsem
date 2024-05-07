import pgzero, pgzrun, pygame  # Importing necessary libraries for the game
import math, sys, random  # Importing additional libraries for mathematical operations, system functionality, and random number generation
from enum import Enum  # Importing Enum for defining symbolic names for constants
from pygame.math import Vector2  # Importing Vector2 class from pygame.math for vector operations

# Extracting major version of pgzero for version checking
pgzero_version = [int(s) if s.isnumeric() else s for s in pgzero.__version__.split('.')]
# Exiting if pgzero version is less than 1.2
if pgzero_version < [1,2]:
    sys.exit()

# Defining screen dimensions
WIDTH = 800
HEIGHT = 480
TITLE = "Soccer"

# Calculating half of window width
HALF_WINDOW_W = WIDTH / 2

# Defining level dimensions
LEVEL_W = 1000
LEVEL_H = 1400
HALF_LEVEL_W = LEVEL_W // 2
HALF_LEVEL_H = LEVEL_H // 2

# Calculating half of pitch dimensions
HALF_PITCH_W = 442
HALF_PITCH_H = 622

# Defining goal dimensions
GOAL_WIDTH = 186
GOAL_DEPTH = 20
HALF_GOAL_W = GOAL_WIDTH // 2

# Defining boundaries for pitch and goal
PITCH_BOUNDS_X = (HALF_LEVEL_W - HALF_PITCH_W, HALF_LEVEL_W + HALF_PITCH_W)
PITCH_BOUNDS_Y = (HALF_LEVEL_H - HALF_PITCH_H, HALF_LEVEL_H + HALF_PITCH_H)

GOAL_BOUNDS_X = (HALF_LEVEL_W - HALF_GOAL_W, HALF_LEVEL_W + HALF_GOAL_W)
GOAL_BOUNDS_Y = (HALF_LEVEL_H - HALF_PITCH_H - GOAL_DEPTH,
                 HALF_LEVEL_H + HALF_PITCH_H + GOAL_DEPTH)

# Creating rectangles for pitch and goals
PITCH_RECT = pygame.rect.Rect(PITCH_BOUNDS_X[0], PITCH_BOUNDS_Y[0], HALF_PITCH_W * 2, HALF_PITCH_H * 2)
GOAL_0_RECT = pygame.rect.Rect(GOAL_BOUNDS_X[0], GOAL_BOUNDS_Y[0], GOAL_WIDTH, GOAL_DEPTH)
GOAL_1_RECT = pygame.rect.Rect(GOAL_BOUNDS_X[0], GOAL_BOUNDS_Y[1] - GOAL_DEPTH, GOAL_WIDTH, GOAL_DEPTH)

# Defining AI movement boundaries
AI_MIN_X = 78
AI_MAX_X = LEVEL_W - 78
AI_MIN_Y = 98
AI_MAX_Y = LEVEL_H - 98

# Defining starting positions for players
PLAYER_START_POS = [(350, 550), (650, 450), (200, 850), (500, 750), (800, 950), (350, 1250), (650, 1150)]

# Defining distances used for player movement
LEAD_DISTANCE_1 = 10
LEAD_DISTANCE_2 = 50

DRIBBLE_DIST_X, DRIBBLE_DIST_Y = 18, 16

# Defining player speeds
PLAYER_DEFAULT_SPEED = 2
CPU_PLAYER_WITH_BALL_BASE_SPEED = 2.6
PLAYER_INTERCEPT_BALL_SPEED = 2.75
LEAD_PLAYER_BASE_SPEED = 2.9
HUMAN_PLAYER_WITH_BALL_SPEED = 3
HUMAN_PLAYER_WITHOUT_BALL_SPEED = 3.3

# Debug flags
DEBUG_SHOW_LEADS = False
DEBUG_SHOW_TARGETS = False
DEBUG_SHOW_PEERS = False
DEBUG_SHOW_SHOOT_TARGET = False
DEBUG_SHOW_COSTS = False

# Class for defining difficulty levels
class Difficulty:
    def __init__(self, goalie_enabled, second_lead_enabled, speed_boost, holdoff_timer):
        # Initializing attributes for each difficulty level
        self.goalie_enabled = goalie_enabled
        self.second_lead_enabled = second_lead_enabled
        self.speed_boost = speed_boost
        self.holdoff_timer = holdoff_timer

# Defining difficulty levels
DIFFICULTY = [Difficulty(False, False, 0, 120), Difficulty(False, True, 0.1, 90), Difficulty(True, True, 0.2, 60)]

# Defining sine function
def sin(x):
    return math.sin(x*math.pi/4)

# Defining cosine function
def cos(x):
    return sin(x+2)

# Converting vector to angle
def vec_to_angle(vec):
    return int(4 * math.atan2(vec.x, -vec.y) / math.pi + 8.5) % 8

# Converting angle to vector
def angle_to_vec(angle):
    return Vector2(sin(angle), -cos(angle))

# Key function for sorting by distance
def dist_key(pos):
    return lambda p: (p.vpos - pos).length()

# Safely normalizing a vector
def safe_normalise(vec):
    length = vec.length()
    if length == 0:
        return Vector2(0,0), 0
    else:
        return vec.normalize(), length

class MyActor(Actor):
    def __init__(self, img, x=0, y=0, anchor=None):
        # Initialize MyActor class inheriting from Actor class with additional parameters
        super().__init__(img, (0, 0), anchor=anchor)
        self.vpos = Vector2(x, y)  # Set the virtual position of the actor

    def draw(self, offset_x, offset_y):
        # Draw method for MyActor class with offset parameters
        self.pos = (self.vpos.x - offset_x, self.vpos.y - offset_y)  # Set the position with respect to the offset
        super().draw()  # Call the draw method of the superclass

KICK_STRENGTH = 11.5  # Define the kick strength constant
DRAG = 0.98  # Define the drag constant for ball physics

def ball_physics(pos, vel, bounds):
    # Function for simulating ball physics
    pos += vel  # Update ball position based on velocity

    # Check if ball is out of bounds and apply rebound
    if pos < bounds[0] or pos > bounds[1]:
        pos, vel = pos - vel, -vel  # Reverse velocity upon collision with bounds

    return pos, vel * DRAG  # Return updated position and velocity with drag applied

def steps(distance):
    # Function to calculate steps based on distance
    steps, vel = 0, KICK_STRENGTH  # Initialize steps and velocity

    # Iterate until distance is zero or velocity is too low
    while distance > 0 and vel > 0.25:
        distance, steps, vel = distance - vel, steps + 1, vel * DRAG  # Update distance, steps, and velocity

    return steps  # Return the calculated steps

class Goal(MyActor):
    def __init__(self, team):
        # Initialize Goal class inheriting from MyActor class with team parameter
        x = HALF_LEVEL_W  # Set x-coordinate to half of level width
        y = 0 if team == 0 else LEVEL_H  # Set y-coordinate based on team
        super().__init__("goal" + str(team), x, y)  # Call superclass constructor with image, x, and y

        self.team = team  # Set the team attribute for the goal

    def active(self):
        # Method to check if the goal is active
        return abs(game.ball.vpos.y - self.vpos.y) < 500  # Check if the ball is close to the goal vertically

def targetable(target, source):
    # Function to check if a target is targetable by a source
    v0, d0 = safe_normalise(target.vpos - source.vpos)  # Calculate normalized vector and distance to target

    # Check if source is not human-controlled and if other players are in the way
    if not game.teams[source.team].human():
        for p in game.players:
            v1, d1 = safe_normalise(p.vpos - source.vpos)
            if p.team != target.team and d1 > 0 and d1 < d0 and v0*v1 > 0.8:
                return False  # Return False if other players are in the way

    # Return True if target is on the same team, within range, and not blocked by teammates
    return target.team == source.team and d0 > 0 and d0 < 300 and v0 * angle_to_vec(source.dir) > 0.8

def avg(a, b):
    # Function to calculate average of two numbers
    return b if abs(b-a) < 1 else (a+b)/2  # Return b if difference is negligible, otherwise return average

def on_pitch(x, y):
    # Function to check if a point is on the pitch
    return PITCH_RECT.collidepoint(x,y) \
           or GOAL_0_RECT.collidepoint(x,y) \
           or GOAL_1_RECT.collidepoint(x,y)  # Return True if point is within pitch or goal boundaries

class Ball(MyActor):
    def __init__(self):
        # Initialize Ball class inheriting from MyActor class
        super().__init__("ball", HALF_LEVEL_W, HALF_LEVEL_H)  # Call superclass constructor with image and position
        self.vel = Vector2(0, 0)  # Initialize velocity vector for the ball

        self.owner = None  # Initialize owner of the ball
        self.timer = 0  # Initialize timer for ball possession

        self.shadow = MyActor("balls")  # Create shadow actor for the ball

    def collide(self, p):
        # Method to check if the ball collides with a player
        return p.timer < 0 and (p.vpos - self.vpos).length() <= DRIBBLE_DIST_X  # Return True if player is close enough to dribble

    def update(self):
        # Method to update ball state
        self.timer -= 1  # Decrease possession timer

        if self.owner:
            # If ball has an owner
            new_x = avg(self.vpos.x, self.owner.vpos.x + DRIBBLE_DIST_X * sin(self.owner.dir))
            new_y = avg(self.vpos.y, self.owner.vpos.y - DRIBBLE_DIST_Y * cos(self.owner.dir))

            if on_pitch(new_x, new_y):
                # If new position is on the pitch, update ball position
                self.vpos = Vector2(new_x, new_y)
            else:
                # If new position is off the pitch, reset possession timer and shoot the ball
                self.owner.timer = 60
                self.vel = angle_to_vec(self.owner.dir) * 3
                self.owner = None
        else:
            # If ball has no owner
            if abs(self.vpos.y - HALF_LEVEL_H) > HALF_PITCH_H:
                bounds_x = GOAL_BOUNDS_X
            else:
                bounds_x = PITCH_BOUNDS_X

            if abs(self.vpos.x - HALF_LEVEL_W) < HALF_GOAL_W:
                bounds_y = GOAL_BOUNDS_Y
            else:
                bounds_y = PITCH_BOUNDS_Y

            # Simulate ball physics for x and y directions
            self.vpos.x, self.vel.x = ball_physics(self.vpos.x, self.vel.x, bounds_x)
            self.vpos.y, self.vel.y = ball_physics(self.vpos.y, self.vel.y, bounds_y)

        self.shadow.vpos = Vector2(self.vpos)  # Update shadow position to match ball position

        for target in game.players:
            # Iterate through players to check for ball collisions
            if (not self.owner or self.owner.team != target.team) and self.collide(target):
                # If there is no owner or the owner is not on the same team and the ball collides with a player
                if self.owner:
                    # If ball has an owner, reset possession timer
                    self.owner.timer = 60

                self.timer = game.difficulty.holdoff_timer  # Set possession timer to difficulty holdoff timer

                game.teams[target.team].active_control_player = self.owner = target  # Set player as ball owner

        if self.owner:
            # If ball has an owner
            team = game.teams[self.owner.team]  # Get the team of the ball owner

            # Find targetable players for shooting
            targetable_players = [p for p in game.players + game.goals if p.team == self.owner.team and targetable(p, self.owner)]

            if len(targetable_players) > 0:
                # If there are targetable players
                target = min(targetable_players, key=dist_key(self.owner.vpos))  # Choose the closest target
                game.debug_shoot_target = target.vpos  # Set debug shoot target to the chosen target
            else:
                target = None  # If no targetable players, set target to None

            if team.human():
                # If the team is human-controlled
                do_shoot = team.controls.shoot()  # Check if shoot action is triggered
            else:
                # If the team is AI-controlled
                do_shoot = self.timer <= 0 and target and cost(target.vpos, self.owner.team) < cost(self.owner.vpos, self.owner.team)
                # Check if it's time to shoot and if shooting is beneficial

            if do_shoot:
                # If shooting action is triggered
                game.play_sound("kick", 4)  # Play kick sound effect

                if target:
                    # If there is a target
                    r = 0  # Initialize shoot distance

                    iterations = 8 if team.human() and isinstance(target, Player) else 1
                    # Set number of iterations for shooting

                    for i in range(iterations):
                        # Iterate through shooting iterations
                        t = target.vpos + angle_to_vec(self.owner.dir) * r  # Calculate target position

                        vec, length = safe_normalise(t - self.vpos)  # Calculate vector and length to target

                        r = HUMAN_PLAYER_WITHOUT_BALL_SPEED * steps(length)  # Calculate shoot distance

                else:
                    # If there is no target
                    vec = angle_to_vec(self.owner.dir)  # Calculate shoot direction vector

                    target = min([p for p in game.players if p.team == self.owner.team],
                                 key=dist_key(self.vpos + (vec * 250)))  # Find closest teammate

                if isinstance(target, Player):
                    # If target is a player
                    game.teams[self.owner.team].active_control_player = target  # Set player as active control player

                self.owner.timer = 10  # Reset possession timer
                self.vel = vec * KICK_STRENGTH  # Set ball velocity for shooting

                self.owner = None  # Reset ball owner

def allow_movement(x, y):
    # Function to check if movement is allowed at a given point
    if abs(x - HALF_LEVEL_W) > HALF_LEVEL_W:
        return False  # Return False if x-coordinate is out of bounds

    elif abs(x - HALF_LEVEL_W) < HALF_GOAL_W + 20:
        return abs(y - HALF_LEVEL_H) < HALF_PITCH_H  # Return True if point is within goal area

    else:
        return abs(y - HALF_LEVEL_H) < HALF_LEVEL_H  # Return True if point is within pitch area

def cost(pos, team, handicap=0):
    # Function to calculate cost of moving to a position
    own_goal_pos = Vector2(HALF_LEVEL_W, 78 if team == 1 else LEVEL_H - 78)  # Calculate position of own goal
    inverse_own_goal_distance = 3500 / (pos - own_goal_pos).length()  # Calculate inverse distance to own goal

    # Calculate total cost based on distance to own goal, distance to opponents, position, and handicap
    result = inverse_own_goal_distance \
            + sum([4000 / max(24, (p.vpos - pos).length()) for p in game.players if p.team != team]) \
            + ((pos.x - HALF_LEVEL_W)**2 / 200 \
            - pos.y * (4 * team - 2)) \
            + handicap

    return result, pos  # Return the calculated cost and position

class Player(MyActor):
    # Define Player class inheriting from MyActor class
    ANCHOR = (25,37)  # Define anchor point for player sprites

    def __init__(self, x, y, team):
        # Initialize Player instance with position and team
        kickoff_y = (y / 2) + 550 - (team * 400)  # Calculate kickoff position based on team
        super().__init__("blank", x, kickoff_y, Player.ANCHOR)  # Call superclass constructor with initial parameters

        self.home = Vector2(x, y)  # Set home position of the player
        self.team = team  # Set team of the player
        self.dir = 0  # Initialize direction of the player
        self.anim_frame = -1  # Initialize animation frame
        self.timer = 0  # Initialize timer
        self.shadow = MyActor("blank", 0, 0, Player.ANCHOR)  # Create shadow actor for the player
        self.debug_target = Vector2(0, 0)  # Initialize debug target position

    def active(self):
        # Method to check if the player is active based on proximity to the ball
        return abs(game.ball.vpos.y - self.home.y) < 400  # Return True if player is close to the ball vertically

    def update(self):
        # Method to update player state
        self.timer -= 1  # Decrease timer

        target = Vector2(self.home)  # Set default target position to home position
        speed = PLAYER_DEFAULT_SPEED  # Set default movement speed

        my_team = game.teams[self.team]  # Get player's team
        pre_kickoff = game.kickoff_player != None  # Check if it's pre-kickoff
        i_am_kickoff_player = self == game.kickoff_player  # Check if the player is the kickoff player
        ball = game.ball  # Get the ball instance

        if self == game.teams[self.team].active_control_player and my_team.human() and (not pre_kickoff or i_am_kickoff_player):
            # If the player is active control player and human-controlled and it's not pre-kickoff or the player is the kickoff player
            if ball.owner == self:
                # If the ball is owned by the player
                speed = HUMAN_PLAYER_WITH_BALL_SPEED  # Set movement speed with the ball
            else:
                speed = HUMAN_PLAYER_WITHOUT_BALL_SPEED  # Set movement speed without the ball
            target = self.vpos + my_team.controls.move(speed)  # Update target position based on player's input

        elif ball.owner != None:
            # If the ball is owned by a player
            if ball.owner == self:
                # If the ball is owned by the player
                costs = [cost(self.vpos + angle_to_vec(self.dir + d) * 3, self.team, abs(d)) for d in range(-2, 3)]
                # Calculate costs for possible directions to move
                _, target = min(costs, key=lambda element: element[0])  # Choose the direction with minimum cost
                speed = CPU_PLAYER_WITH_BALL_BASE_SPEED + game.difficulty.speed_boost  # Set movement speed with the ball

            elif ball.owner.team == self.team:
                # If the ball is owned by a teammate
                if self.active():
                    # If the player is active
                    direction = -1 if self.team == 0 else 1  # Calculate direction towards the ball
                    target.x = (ball.vpos.x + target.x) / 2  # Update target x-coordinate towards the ball
                    target.y = (ball.vpos.y + 400 * direction + target.y) / 2  # Update target y-coordinate towards the ball
            else:
                # If the ball is owned by an opponent
                if self.lead is not None:
                    # If the player has a lead
                    target = ball.owner.vpos + angle_to_vec(ball.owner.dir) * self.lead  # Set target towards ball owner
                    target.x = max(AI_MIN_X, min(AI_MAX_X, target.x))  # Ensure target x-coordinate is within bounds
                    target.y = max(AI_MIN_Y, min(AI_MAX_Y, target.y))  # Ensure target y-coordinate is within bounds
                    other_team = 1 if self.team == 0 else 0  # Get the opponent team
                    speed = LEAD_PLAYER_BASE_SPEED  # Set lead player movement speed
                    if game.teams[other_team].human():
                        speed += game.difficulty.speed_boost  # Increase speed based on difficulty for human opponents

                elif self.mark.active():
                    # If the player is marking an opponent
                    if my_team.human():
                        target = Vector2(ball.vpos)  # Set target position as the ball position for human-controlled teams
                    else:
                        vec, length = safe_normalise(ball.vpos - self.mark.vpos)  # Calculate vector and length to mark
                        if isinstance(self.mark, Goal):
                            length = min(150, length)  # Limit length if marking the goal
                        else:
                            length /= 2  # Reduce length for other marks
                        target = self.mark.vpos + vec * length  # Update target position based on mark position
        else:
            # If the ball is free
            if (pre_kickoff and i_am_kickoff_player) or (not pre_kickoff and self.active()):
                # If it's pre-kickoff and the player is the kickoff player or it's not pre-kickoff and the player is active
                target = Vector2(ball.vpos)  # Set target position towards the ball
                vel = Vector2(ball.vel)  # Get ball velocity
                frame = 0  # Initialize frame counter

                # Simulate ball movement to predict interception position
                while (target - self.vpos).length() > PLAYER_INTERCEPT_BALL_SPEED * frame + DRIBBLE_DIST_X and vel.length() > 0.5:
                    target += vel  # Update target position based on ball velocity
                    vel *= DRAG  # Apply drag to ball velocity
                    frame += 1  # Increment frame counter

                speed = PLAYER_INTERCEPT_BALL_SPEED  # Set movement speed for ball interception

            elif pre_kickoff:
                # If it's pre-kickoff
                target.y = self.vpos.y  # Keep target y-coordinate same as player y-coordinate

        vec, distance = safe_normalise(target - self.vpos)  # Calculate normalized vector and distance to target

        self.debug_target = Vector2(target)  # Update debug target position

        if distance > 0:
            # If there is a distance to move
            distance = min(distance, speed)  # Limit distance to move within speed
            target_dir = vec_to_angle(vec)  # Calculate target direction based on vector

            # Check if movement is allowed in x and y directions and update position accordingly
            if allow_movement(self.vpos.x + vec.x * distance, self.vpos.y):
                self.vpos.x += vec.x * distance  # Update x-coordinate
            if allow_movement(self.vpos.x, self.vpos.y + vec.y * distance):
                self.vpos.y += vec.y * distance  # Update y-coordinate

            self.anim_frame = (self.anim_frame + max(distance, 1.5)) % 72  # Update animation frame based on movement
        else:
            target_dir = vec_to_angle(ball.vpos - self.vpos)  # Calculate target direction towards the ball
            self.anim_frame = -1  # Reset animation frame

        dir_diff = (target_dir - self.dir)  # Calculate direction difference
        self.dir = (self.dir + [0, 1, 1, 1, 1, 7, 7, 7][dir_diff % 8]) % 8  # Update direction based on difference

        suffix = str(self.dir) + str((int(self.anim_frame) // 18) + 1)  # Calculate sprite suffix based on direction and frame

        self.image = "player" + str(self.team) + suffix  # Update player sprite
        self.shadow.image = "players" + suffix  # Update player shadow sprite

        self.shadow.vpos = Vector2(self.vpos)  # Update shadow position to match player position

class Team:
    def __init__(self, controls):
        # Initialize a Team instance with controls
        self.controls = controls
        # Set the active controlled player to None
        self.active_control_player = None
        # Initialize score to 0
        self.score = 0

    def human(self):
        # Check if the team has human controls
        return self.controls != None


class Game:
    def __init__(self, p1_controls=None, p2_controls=None, difficulty=2):
        # Initialize a Game instance with player controls and difficulty level
        self.teams = [Team(p1_controls), Team(p2_controls)]
        # Set game difficulty based on input or default to 2
        self.difficulty = DIFFICULTY[difficulty]

        try:
            # If first team is human, adjust sound settings
            if self.teams[0].human():
                music.fadeout(1)
                sounds.crowd.play(-1)
                sounds.start.play()
            else:
                # If not human, play theme music and stop crowd sound
                music.play("theme")
                sounds.crowd.stop()
        except Exception:
            pass

        # Initialize score timer and scoring team
        self.score_timer = 0
        self.scoring_team = 1   

        # Reset the game
        self.reset()

    def reset(self):
        # Reset game state

        # Generate players with random positions
        self.players = []
        random_offset = lambda x: x + random.randint(-32, 32)
        for pos in PLAYER_START_POS:
            self.players.append(Player(random_offset(pos[0]), random_offset(pos[1]), 0))
            self.players.append(Player(random_offset(LEVEL_W - pos[0]), random_offset(LEVEL_H - pos[1]), 1))

        # Link players with their peers
        for a, b in zip(self.players, self.players[::-1]):
            a.peer = b

        # Create goal objects
        self.goals = [Goal(i) for i in range(2)]

        # Set active control player for each team
        self.teams[0].active_control_player = self.players[0]
        self.teams[1].active_control_player = self.players[1]

        # Determine kickoff player and position
        other_team = 1 if self.scoring_team == 0 else 0
        self.kickoff_player = self.players[other_team]
        self.kickoff_player.vpos = Vector2(HALF_LEVEL_W - 30 + other_team * 60, HALF_LEVEL_H)

        # Create a ball object
        self.ball = Ball()

        # Set camera focus to ball position
        self.camera_focus = Vector2(self.ball.vpos)

        # Initialize debug shoot target
        self.debug_shoot_target = None

    def update(self):
        # Update game state

        # Decrease score timer
        self.score_timer -= 1

        # Check if it's time to reset the game
        if self.score_timer == 0:
            self.reset()

        # Check if there's a goal scored
        elif self.score_timer < 0 and abs(self.ball.vpos.y - HALF_LEVEL_H) > HALF_PITCH_H:
            game.play_sound("goal", 2)
            # Determine scoring team and update score
            self.scoring_team = 0 if self.ball.vpos.y < HALF_LEVEL_H else 1
            self.teams[self.scoring_team].score += 1
            # Set score timer for reset delay
            self.score_timer = 60     

        # Reset player marks and debug targets
        for b in self.players:
            b.mark = b.peer
            b.lead = None
            b.debug_target = None

        self.debug_shoot_target = None

        if self.ball.owner:
            # Update player behavior based on ball possession
            o = self.ball.owner
            pos, team = o.vpos, o.team
            owners_target_goal = game.goals[team]
            other_team = 1 if team == 0 else 0

            if self.difficulty.goalie_enabled:
                # Find nearest player to own goal for goalie behavior
                nearest = min([p for p in self.players if p.team != team], key=dist_key(owners_target_goal.vpos))
                o.peer.mark = nearest.mark
                nearest.mark = owners_target_goal

            # Update player behaviors for attacking or defending
            l = sorted([p for p in self.players
                        if p.team != team
                        and p.timer <= 0
                        and (not self.teams[other_team].human() or p != self.teams[other_team].active_control_player)
                        and not isinstance(p.mark, Goal)],
                       key=dist_key(pos))

            a = [p for p in l if (p.vpos.y > pos.y if team == 0 else p.vpos.y < pos.y)]
            b = [p for p in l if p not in a]
            NONE2 = [None] * 2
            zipped = [s for t in zip(a + NONE2, b + NONE2) for s in t if s]
            zipped[0].lead = LEAD_DISTANCE_1
            if self.difficulty.second_lead_enabled:
                zipped[1].lead = LEAD_DISTANCE_2

            self.kickoff_player = None

        # Update player and ball objects
        for obj in self.players + [self.ball]:
            obj.update()

        # Update camera focus to track the ball
        owner = self.ball.owner
        for team_num in range(2):
            team_obj = self.teams[team_num]

            if team_obj.human() and team_obj.controls.shoot():
                # Update active controlled player based on shoot command
                def dist_key_weighted(p):
                    dist_to_ball = (p.vpos - self.ball.vpos).length()
                    goal_dir = (2 * team_num - 1)
                    if owner and (p.vpos.y - self.ball.vpos.y) * goal_dir < 0:
                        return dist_to_ball / 2
                    else:
                        return dist_to_ball

                self.teams[team_num].active_control_player = min([p for p in game.players if p.team == team_num],
                                                                 key=dist_key_weighted)

        # Update camera focus based on ball position
        camera_ball_vec, distance = safe_normalise(self.camera_focus - self.ball.vpos)
        if distance > 0:
            self.camera_focus -= camera_ball_vec * min(distance, 8)

    def draw(self):
        # Draw game objects on the screen

        # Calculate screen offset based on camera focus
        offset_x = max(0, min(LEVEL_W - WIDTH, self.camera_focus.x - WIDTH / 2))
        offset_y = max(0, min(LEVEL_H - HEIGHT, self.camera_focus.y - HEIGHT / 2))
        offset = Vector2(offset_x, offset_y)

        # Draw pitch background
        screen.blit("pitch", (-offset_x, -offset_y))

        # Prepare objects to draw
        objects = sorted([self.ball] + self.players, key=lambda obj: obj.y)
        objects = objects + [obj.shadow for obj in objects]
        objects = [self.goals[0]] + objects + [self.goals[1]]

        # Draw objects on the screen
        for obj in objects:
            obj.draw(offset_x, offset_y)

        # Draw control arrows for human players
        for t in range(2):
            if self.teams[t].human():
                arrow_pos = self.teams[t].active_control_player.vpos - offset - Vector2(11, 45)
                screen.blit("arrow" + str(t), arrow_pos)

        # Draw debug information if enabled
        if DEBUG_SHOW_LEADS:
            for p in self.players:
                if game.ball.owner and p.lead:
                    line_start = game.ball.owner.vpos - offset
                    line_end = p.vpos - offset
                    pygame.draw.line(screen.surface, (0, 0, 0), line_start, line_end)

        if DEBUG_SHOW_TARGETS:
            for p in self.players:
                line_start = p.debug_target - offset
                line_end = p.vpos - offset
                pygame.draw.line(screen.surface, (255, 0, 0), line_start, line_end)

        if DEBUG_SHOW_PEERS:
            for p in self.players:
                line_start = p.peer.vpos - offset
                line_end = p.vpos - offset
                pygame.draw.line(screen.surface, (0, 0, 255), line_start, line_end)

        if DEBUG_SHOW_SHOOT_TARGET:
            if self.debug_shoot_target and self.ball.owner:
                line_start = self.ball.owner.vpos - offset
                line_end = self.debug_shoot_target - offset
                pygame.draw.line(screen.surface, (255, 0, 255), line_start, line_end)
        
        if DEBUG_SHOW_COSTS and self.ball.owner:
            for x in range(0, LEVEL_W, 60):
                for y in range(0, LEVEL_H, 26):
                    c = cost(Vector2(x, y), self.ball.owner.team)[0]
                    screen_pos = Vector2(x, y) - offset
                    screen_pos = (screen_pos.x, screen_pos.y)    
                    screen.draw.text("{0:.0f}".format(c), center=screen_pos)

    def play_sound(self, name, c):
        # Play a sound effect from the sounds module
        if state != State.MENU:
            try:
                getattr(sounds, name + str(random.randint(0, c - 1))).play()
            except:
                pass

key_status = {}

def key_just_pressed(key):
    # Check if a key was just pressed
    result = False

    # Get previous key status
    prev_status = key_status.get(key, False)

    # Check if key was not pressed before and is pressed now
    if not prev_status and keyboard[key]:
        result = True

    # Update key status
    key_status[key] = keyboard[key]

    return result

class Controls:
    def __init__(self, player_num):
        # Initialize Controls class for a player with specific controls based on player number
        if player_num == 0:
            # Player 1 controls
            self.key_up = keys.UP
            self.key_down = keys.DOWN
            self.key_left = keys.LEFT
            self.key_right = keys.RIGHT
            self.key_shoot = keys.SPACE
        else:
            # Player 2 controls
            self.key_up = keys.W
            self.key_down = keys.S
            self.key_left = keys.A
            self.key_right = keys.D
            self.key_shoot = keys.LSHIFT

    def move(self, speed):
        # Calculate movement direction based on pressed keys
        dx, dy = 0, 0
        if keyboard[self.key_left]:
            dx = -1
        elif keyboard[self.key_right]:
            dx = 1
        if keyboard[self.key_up]:
            dy = -1
        elif keyboard[self.key_down]:
            dy = 1
        return Vector2(dx, dy) * speed

    def shoot(self):
        # Check if shoot key is just pressed
        return key_just_pressed(self.key_shoot)


class State(Enum):
    # Define game states
    MENU = 0
    PLAY = 1
    GAME_OVER = 2

class MenuState(Enum):
    # Define menu states
    NUM_PLAYERS = 0
    DIFFICULTY = 1

def update():
    global state, game, menu_state, menu_num_players, menu_difficulty

    if state == State.MENU:
        # Update game state when in menu
        if key_just_pressed(keys.SPACE):
            # Proceed to next menu state or start game
            if menu_state == MenuState.NUM_PLAYERS:
                if menu_num_players == 1:
                    menu_state = MenuState.DIFFICULTY
                else:
                    state = State.PLAY
                    menu_state = None
                    game = Game(Controls(0), Controls(1))
            else:
                state = State.PLAY
                menu_state = None
                game = Game(Controls(0), None, menu_difficulty)
        else:
            # Handle menu navigation
            selection_change = 0
            if key_just_pressed(keys.DOWN):
                selection_change = 1
            elif key_just_pressed(keys.UP):
                selection_change = -1
            if selection_change != 0:
                try:
                    sounds.move.play()
                except Exception:
                    pass
                if menu_state == MenuState.NUM_PLAYERS:
                    menu_num_players = 2 if menu_num_players == 1 else 1
                else:
                    menu_difficulty = (menu_difficulty + selection_change) % 3

        game.update()

    elif state == State.PLAY:
        # Update game state when playing
        if max([team.score for team in game.teams]) == 9 and game.score_timer == 1:
            state = State.GAME_OVER
        else:
            game.update()

    elif state == State.GAME_OVER:
        # Update game state when game over
        if key_just_pressed(keys.SPACE):
            # Return to menu on space press
            state = State.MENU
            menu_state = MenuState.NUM_PLAYERS
            game = Game()

def draw():
    # Draw game elements on the screen
    game.draw()

    if state == State.MENU:
        # Draw menu if in menu state
        if menu_state == MenuState.NUM_PLAYERS:
            image = "menu0" + str(menu_num_players)
        else:
            image = "menu1" + str(menu_difficulty)
        screen.blit(image, (0, 0))

    elif state == State.PLAY:
        # Draw score and goal indication during gameplay
        screen.blit("bar", (HALF_WINDOW_W - 176, 0))
        for i in range(2):
            screen.blit("s" + str(game.teams[i].score), (HALF_WINDOW_W + 7 - 39 * i, 6))
        if game.score_timer > 0:
            screen.blit("goal", (HALF_WINDOW_W - 300, HEIGHT / 2 - 88))

    elif state == State.GAME_OVER:
        # Draw game over screen with results
        img = "over" + str(int(game.teams[1].score > game.teams[0].score))
        screen.blit(img, (0, 0))
        for i in range(2):
            img = "l" + str(i) + str(game.teams[i].score)
            screen.blit(img, (HALF_WINDOW_W + 25 - 125 * i, 144))

try:
    # Initialize and configure pygame mixer
    pygame.mixer.quit()
    pygame.mixer.init(44100, -16, 2, 1024)
except Exception:
    pass

# Set initial game state and menu state
state = State.MENU
menu_state = MenuState.NUM_PLAYERS
menu_num_players = 1
menu_difficulty = 0

# Initialize game
game = Game()

# Run the game loop
pgzrun.go()