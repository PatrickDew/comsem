import pgzero, pgzrun, pygame
import math, sys, random
from enum import Enum
from pygame.math import Vector2

pgzero_version = [int(s) if s.isnumeric() else s for s in pgzero.__version__.split('.')]
if pgzero_version < [1,2]:
    print("This game requires at least version 1.2 of Pygame Zero. You have version {0}. Please upgrade using the command 'pip3 install --upgrade pgzero'".format(pgzero.__version__))
    sys.exit()

WIDTH = 800
HEIGHT = 480
TITLE = "Soccer"

HALF_WINDOW_W = WIDTH / 2

LEVEL_W = 1000
LEVEL_H = 1400
HALF_LEVEL_W = LEVEL_W // 2
HALF_LEVEL_H = LEVEL_H // 2

HALF_PITCH_W = 442
HALF_PITCH_H = 622

GOAL_WIDTH = 186
GOAL_DEPTH = 20
HALF_GOAL_W = GOAL_WIDTH // 2

PITCH_BOUNDS_X = (HALF_LEVEL_W - HALF_PITCH_W, HALF_LEVEL_W + HALF_PITCH_W)
PITCH_BOUNDS_Y = (HALF_LEVEL_H - HALF_PITCH_H, HALF_LEVEL_H + HALF_PITCH_H)

GOAL_BOUNDS_X = (HALF_LEVEL_W - HALF_GOAL_W, HALF_LEVEL_W + HALF_GOAL_W)
GOAL_BOUNDS_Y = (HALF_LEVEL_H - HALF_PITCH_H - GOAL_DEPTH,
                 HALF_LEVEL_H + HALF_PITCH_H + GOAL_DEPTH)

PITCH_RECT = pygame.rect.Rect(PITCH_BOUNDS_X[0], PITCH_BOUNDS_Y[0], HALF_PITCH_W * 2, HALF_PITCH_H * 2)
GOAL_0_RECT = pygame.rect.Rect(GOAL_BOUNDS_X[0], GOAL_BOUNDS_Y[0], GOAL_WIDTH, GOAL_DEPTH)
GOAL_1_RECT = pygame.rect.Rect(GOAL_BOUNDS_X[0], GOAL_BOUNDS_Y[1] - GOAL_DEPTH, GOAL_WIDTH, GOAL_DEPTH)

AI_MIN_X = 78
AI_MAX_X = LEVEL_W - 78
AI_MIN_Y = 98
AI_MAX_Y = LEVEL_H - 98

PLAYER_START_POS = [(350, 550), (650, 450), (200, 850), (500, 750), (800, 950), (350, 1250), (650, 1150)]

LEAD_DISTANCE_1 = 10
LEAD_DISTANCE_2 = 50

DRIBBLE_DIST_X, DRIBBLE_DIST_Y = 18, 16

PLAYER_DEFAULT_SPEED = 2
CPU_PLAYER_WITH_BALL_BASE_SPEED = 2.6
PLAYER_INTERCEPT_BALL_SPEED = 2.75
LEAD_PLAYER_BASE_SPEED = 2.9
HUMAN_PLAYER_WITH_BALL_SPEED = 3
HUMAN_PLAYER_WITHOUT_BALL_SPEED = 3.3

DEBUG_SHOW_LEADS = False
DEBUG_SHOW_TARGETS = False
DEBUG_SHOW_PEERS = False
DEBUG_SHOW_SHOOT_TARGET = False
DEBUG_SHOW_COSTS = False

class Difficulty:
    def __init__(self, goalie_enabled, second_lead_enabled, speed_boost, holdoff_timer):
        self.goalie_enabled = goalie_enabled

        self.second_lead_enabled = second_lead_enabled

        self.speed_boost = speed_boost

        self.holdoff_timer = holdoff_timer

DIFFICULTY = [Difficulty(False, False, 0, 120), Difficulty(False, True, 0.1, 90), Difficulty(True, True, 0.2, 60)]

def sin(x):
    return math.sin(x*math.pi/4)

def cos(x):
    return sin(x+2)


def vec_to_angle(vec):

    return int(4 * math.atan2(vec.x, -vec.y) / math.pi + 8.5) % 8


def angle_to_vec(angle):
    return Vector2(sin(angle), -cos(angle))


def dist_key(pos):
    return lambda p: (p.vpos - pos).length()


def safe_normalise(vec):
    length = vec.length()
    if length == 0:
        return Vector2(0,0), 0
    else:
        return vec.normalize(), length


class MyActor(Actor):
    def __init__(self, img, x=0, y=0, anchor=None):
        super().__init__(img, (0, 0), anchor=anchor)
        self.vpos = Vector2(x, y)

    def draw(self, offset_x, offset_y):
        self.pos = (self.vpos.x - offset_x, self.vpos.y - offset_y)
        super().draw()

KICK_STRENGTH = 11.5
DRAG = 0.98


def ball_physics(pos, vel, bounds):
    pos += vel

    if pos < bounds[0] or pos > bounds[1]:
        pos, vel = pos - vel, -vel

    return pos, vel * DRAG

def steps(distance):
    steps, vel = 0, KICK_STRENGTH

    while distance > 0 and vel > 0.25:
        distance, steps, vel = distance - vel, steps + 1, vel * DRAG

    return steps

class Goal(MyActor):
    def __init__(self, team):
        x = HALF_LEVEL_W
        y = 0 if team == 0 else LEVEL_H
        super().__init__("goal" + str(team), x, y)

        self.team = team

    def active(self):
        return abs(game.ball.vpos.y - self.vpos.y) < 500

def targetable(target, source):
    v0, d0 = safe_normalise(target.vpos - source.vpos)


    if not game.teams[source.team].human():
        for p in game.players:
            v1, d1 = safe_normalise(p.vpos - source.vpos)
            if p.team != target.team and d1 > 0 and d1 < d0 and v0*v1 > 0.8:
                return False

    return target.team == source.team and d0 > 0 and d0 < 300 and v0 * angle_to_vec(source.dir) > 0.8

def avg(a, b):
    return b if abs(b-a) < 1 else (a+b)/2

def on_pitch(x, y):

    return PITCH_RECT.collidepoint(x,y) \
           or GOAL_0_RECT.collidepoint(x,y) \
           or GOAL_1_RECT.collidepoint(x,y)

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

            if abs(self.vpos.x - HALF_LEVEL_W) < HALF_GOAL_W:
                bounds_y = GOAL_BOUNDS_Y
            else:
                bounds_y = PITCH_BOUNDS_Y

            self.vpos.x, self.vel.x = ball_physics(self.vpos.x, self.vel.x, bounds_x)
            self.vpos.y, self.vel.y = ball_physics(self.vpos.y, self.vel.y, bounds_y)

        self.shadow.vpos = Vector2(self.vpos)

        for target in game.players:

            if (not self.owner or self.owner.team != target.team) and self.collide(target):
                if self.owner:

                    self.owner.timer = 60

                self.timer = game.difficulty.holdoff_timer

                game.teams[target.team].active_control_player = self.owner = target

        if self.owner:
            team = game.teams[self.owner.team]


            targetable_players = [p for p in game.players + game.goals if p.team == self.owner.team and targetable(p, self.owner)]

            if len(targetable_players) > 0:

                target = min(targetable_players, key=dist_key(self.owner.vpos))
                game.debug_shoot_target = target.vpos
            else:
                target = None

            if team.human():
                do_shoot = team.controls.shoot()
            else:

                do_shoot = self.timer <= 0 and target and cost(target.vpos, self.owner.team) < cost(self.owner.vpos, self.owner.team)

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

                if isinstance(target, Player):
                    game.teams[self.owner.team].active_control_player = target

                self.owner.timer = 10  

                self.vel = vec * KICK_STRENGTH

                self.owner = None

def allow_movement(x, y):
    if abs(x - HALF_LEVEL_W) > HALF_LEVEL_W:
        return False

    elif abs(x - HALF_LEVEL_W) < HALF_GOAL_W + 20:
        return abs(y - HALF_LEVEL_H) < HALF_PITCH_H

    else:
        return abs(y - HALF_LEVEL_H) < HALF_LEVEL_H


def cost(pos, team, handicap=0):

    own_goal_pos = Vector2(HALF_LEVEL_W, 78 if team == 1 else LEVEL_H - 78)
    inverse_own_goal_distance = 3500 / (pos - own_goal_pos).length()

    result = inverse_own_goal_distance \
            + sum([4000 / max(24, (p.vpos - pos).length()) for p in game.players if p.team != team]) \
            + ((pos.x - HALF_LEVEL_W)**2 / 200 \
            - pos.y * (4 * team - 2)) \
            + handicap

    return result, pos

class Player(MyActor):
    ANCHOR = (25,37)

    def __init__(self, x, y, team):
        
        kickoff_y = (y / 2) + 550 - (team * 400)

        super().__init__("blank", x, kickoff_y, Player.ANCHOR)

        self.home = Vector2(x, y)

        self.team = team

        self.dir = 0

        self.anim_frame = -1

        self.timer = 0

        self.shadow = MyActor("blank", 0, 0, Player.ANCHOR)

        self.debug_target = Vector2(0, 0)

    def active(self):

        return abs(game.ball.vpos.y - self.home.y) < 400

    def update(self):
        self.timer -= 1

        target = Vector2(self.home)     
        speed = PLAYER_DEFAULT_SPEED

        my_team = game.teams[self.team]
        pre_kickoff = game.kickoff_player != None
        i_am_kickoff_player = self == game.kickoff_player
        ball = game.ball

        if self == game.teams[self.team].active_control_player and my_team.human() and (not pre_kickoff or i_am_kickoff_player):
     
            if ball.owner == self:
                speed = HUMAN_PLAYER_WITH_BALL_SPEED
            else:
                speed = HUMAN_PLAYER_WITHOUT_BALL_SPEED

            target = self.vpos + my_team.controls.move(speed)

        elif ball.owner != None:
            if ball.owner == self:
              
                costs = [cost(self.vpos + angle_to_vec(self.dir + d) * 3, self.team, abs(d)) for d in range(-2, 3)]

                
                _, target = min(costs, key=lambda element: element[0])

                speed = CPU_PLAYER_WITH_BALL_BASE_SPEED + game.difficulty.speed_boost

            elif ball.owner.team == self.team:
                if self.active():

                    direction = -1 if self.team == 0 else 1
                    target.x = (ball.vpos.x + target.x) / 2
                    target.y = (ball.vpos.y + 400 * direction + target.y) / 2
            else:
                if self.lead is not None:


                    target = ball.owner.vpos + angle_to_vec(ball.owner.dir) * self.lead

                    target.x = max(AI_MIN_X, min(AI_MAX_X, target.x))
                    target.y = max(AI_MIN_Y, min(AI_MAX_Y, target.y))

                    other_team = 1 if self.team == 0 else 0
                    speed = LEAD_PLAYER_BASE_SPEED
                    if game.teams[other_team].human():
                        speed += game.difficulty.speed_boost

                elif self.mark.active():

                    if my_team.human():
          
                        target = Vector2(ball.vpos)
                    else:
                        vec, length = safe_normalise(ball.vpos - self.mark.vpos)

                        if isinstance(self.mark, Goal):

                            length = min(150, length)
                        else:
                            length /= 2

                        target = self.mark.vpos + vec * length
        else:

            if (pre_kickoff and i_am_kickoff_player) or (not pre_kickoff and self.active()):
               
                target = Vector2(ball.vpos)     #
                vel = Vector2(ball.vel)         # 
                frame = 0

       
                while (target - self.vpos).length() > PLAYER_INTERCEPT_BALL_SPEED * frame + DRIBBLE_DIST_X and vel.length() > 0.5:
                    target += vel
                    vel *= DRAG
                    frame += 1

                speed = PLAYER_INTERCEPT_BALL_SPEED

            elif pre_kickoff:
   
                target.y = self.vpos.y


        vec, distance = safe_normalise(target - self.vpos)

        self.debug_target = Vector2(target)

        if distance > 0:
            distance = min(distance, speed)

            target_dir = vec_to_angle(vec)

            
            if allow_movement(self.vpos.x + vec.x * distance, self.vpos.y):
                self.vpos.x += vec.x * distance
            if allow_movement(self.vpos.x, self.vpos.y + vec.y * distance):
                self.vpos.y += vec.y * distance

            self.anim_frame = (self.anim_frame + max(distance, 1.5)) % 72
        else:
            target_dir = vec_to_angle(ball.vpos - self.vpos)
            self.anim_frame = -1


        dir_diff = (target_dir - self.dir)
        self.dir = (self.dir + [0, 1, 1, 1, 1, 7, 7, 7][dir_diff % 8]) % 8

        suffix = str(self.dir) + str((int(self.anim_frame) // 18) + 1) # todo

        self.image = "player" + str(self.team) + suffix
        self.shadow.image = "players" + suffix

        self.shadow.vpos = Vector2(self.vpos)


class Team:
    def __init__(self, controls):
        self.controls = controls
        self.active_control_player = None
        self.score = 0

    def human(self):
        return self.controls != None


class Game:
    def __init__(self, p1_controls=None, p2_controls=None, difficulty=2):
        self.teams = [Team(p1_controls), Team(p2_controls)]
        self.difficulty = DIFFICULTY[difficulty]

        try:
            if self.teams[0].human():
                music.fadeout(1)
                sounds.crowd.play(-1)
                sounds.start.play()
            else:
                music.play("theme")
                sounds.crowd.stop()
        except Exception:
            pass

        self.score_timer = 0
        self.scoring_team = 1   

        self.reset()

    def reset(self):

        self.players = []
        random_offset = lambda x: x + random.randint(-32, 32)
        for pos in PLAYER_START_POS:
     
            self.players.append(Player(random_offset(pos[0]), random_offset(pos[1]), 0))
            self.players.append(Player(random_offset(LEVEL_W - pos[0]), random_offset(LEVEL_H - pos[1]), 1))

    
        for a, b in zip(self.players, self.players[::-1]):
            a.peer = b

        self.goals = [Goal(i) for i in range(2)]


        self.teams[0].active_control_player = self.players[0]
        self.teams[1].active_control_player = self.players[1]

        other_team = 1 if self.scoring_team == 0 else 0


        self.kickoff_player = self.players[other_team]

        self.kickoff_player.vpos = Vector2(HALF_LEVEL_W - 30 + other_team * 60, HALF_LEVEL_H)

        self.ball = Ball()

        self.camera_focus = Vector2(self.ball.vpos)

        self.debug_shoot_target = None

    def update(self):
        self.score_timer -= 1

        if self.score_timer == 0:
            self.reset()

        elif self.score_timer < 0 and abs(self.ball.vpos.y - HALF_LEVEL_H) > HALF_PITCH_H:
            game.play_sound("goal", 2)

            self.scoring_team = 0 if self.ball.vpos.y < HALF_LEVEL_H else 1
            self.teams[self.scoring_team].score += 1
            self.score_timer = 60     

        for b in self.players:
            b.mark = b.peer
            b.lead = None
            b.debug_target = None

        self.debug_shoot_target = None

        if self.ball.owner:
        
            o = self.ball.owner
            pos, team = o.vpos, o.team
            owners_target_goal = game.goals[team]
            other_team = 1 if team == 0 else 0

            if self.difficulty.goalie_enabled:
                nearest = min([p for p in self.players if p.team != team], key = dist_key(owners_target_goal.vpos))

                o.peer.mark = nearest.mark
                nearest.mark = owners_target_goal

        
            l = sorted([p for p in self.players
                        if p.team != team
                        and p.timer <= 0
                        and (not self.teams[other_team].human() or p != self.teams[other_team].active_control_player)
                        and not isinstance(p.mark, Goal)],
                       key = dist_key(pos))

          
            a = [p for p in l if (p.vpos.y > pos.y if team == 0 else p.vpos.y < pos.y)]
            b = [p for p in l if p not in a]

            
            NONE2 = [None] * 2
            zipped = [s for t in zip(a+NONE2, b+NONE2) for s in t if s]


            zipped[0].lead = LEAD_DISTANCE_1
            if self.difficulty.second_lead_enabled:
                zipped[1].lead = LEAD_DISTANCE_2

       
            self.kickoff_player = None

        for obj in self.players + [self.ball]:
            obj.update()

        owner = self.ball.owner

        for team_num in range(2):
            team_obj = self.teams[team_num]

            if team_obj.human() and team_obj.controls.shoot():
              
                def dist_key_weighted(p):
                    dist_to_ball = (p.vpos - self.ball.vpos).length()
                    
                    goal_dir = (2 * team_num - 1)
                    if owner and (p.vpos.y - self.ball.vpos.y) * goal_dir < 0:
                        return dist_to_ball / 2
                    else:
                        return dist_to_ball

                self.teams[team_num].active_control_player = min([p for p in game.players if p.team == team_num],
                                                                 key = dist_key_weighted)

        camera_ball_vec, distance = safe_normalise(self.camera_focus - self.ball.vpos)
        if distance > 0:
            self.camera_focus -= camera_ball_vec * min(distance, 8)

    def draw(self):
        offset_x = max(0, min(LEVEL_W - WIDTH, self.camera_focus.x - WIDTH / 2))
        offset_y = max(0, min(LEVEL_H - HEIGHT, self.camera_focus.y - HEIGHT / 2))
        offset = Vector2(offset_x, offset_y)

        screen.blit("pitch", (-offset_x, -offset_y))

        
        objects = sorted([self.ball] + self.players, key = lambda obj: obj.y)
        objects = objects + [obj.shadow for obj in objects]
        objects = [self.goals[0]] + objects + [self.goals[1]]

        for obj in objects:
            obj.draw(offset_x, offset_y)

        for t in range(2):
            if self.teams[t].human():
                arrow_pos = self.teams[t].active_control_player.vpos - offset - Vector2(11, 45)
                screen.blit("arrow" + str(t), arrow_pos)

        if DEBUG_SHOW_LEADS:
            for p in self.players:
                if game.ball.owner and p.lead:
                    line_start = game.ball.owner.vpos - offset
                    line_end = p.vpos - offset
                    pygame.draw.line(screen.surface, (0,0,0), line_start, line_end)

        if DEBUG_SHOW_TARGETS:
            for p in self.players:
                line_start = p.debug_target - offset
                line_end = p.vpos - offset
                pygame.draw.line(screen.surface, (255,0,0), line_start, line_end)

        if DEBUG_SHOW_PEERS:
            for p in self.players:
                line_start = p.peer.vpos - offset
                line_end = p.vpos - offset
                pygame.draw.line(screen.surface, (0,0,255), line_start, line_end)

        if DEBUG_SHOW_SHOOT_TARGET:
            if self.debug_shoot_target and self.ball.owner:
                line_start = self.ball.owner.vpos - offset
                line_end = self.debug_shoot_target - offset
                pygame.draw.line(screen.surface, (255,0,255), line_start, line_end)
        
        if DEBUG_SHOW_COSTS and self.ball.owner:
            for x in range(0,LEVEL_W,60):
                for y in range(0, LEVEL_H, 26):
                    c = cost(Vector2(x,y), self.ball.owner.team)[0]
                    screen_pos = Vector2(x,y)-offset
                    screen_pos = (screen_pos.x,screen_pos.y)    
                    screen.draw.text("{0:.0f}".format(c), center=screen_pos)

    def play_sound(self, name, c):
        if state != State.MENU:
            try:
                getattr(sounds, name+str(random.randint(0, c-1))).play()
            except:
                
                pass


key_status = {}

def key_just_pressed(key):
    result = False


    prev_status = key_status.get(key, False)

    if not prev_status and keyboard[key]:
        result = True


    key_status[key] = keyboard[key]

    return result

class Controls:
    def __init__(self, player_num):
        if player_num == 0:
            self.key_up = keys.UP
            self.key_down = keys.DOWN
            self.key_left = keys.LEFT
            self.key_right = keys.RIGHT
            self.key_shoot = keys.SPACE
        else:
            self.key_up = keys.W
            self.key_down = keys.S
            self.key_left = keys.A
            self.key_right = keys.D
            self.key_shoot = keys.LSHIFT

    def move(self, speed):
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
        return key_just_pressed(self.key_shoot)


class State(Enum):
    MENU = 0
    PLAY = 1
    GAME_OVER = 2

class MenuState(Enum):
    NUM_PLAYERS = 0
    DIFFICULTY = 1

def update():
    global state, game, menu_state, menu_num_players, menu_difficulty

    if state == State.MENU:
        if key_just_pressed(keys.SPACE):
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
        if max([team.score for team in game.teams]) == 9 and game.score_timer == 1:
            state = State.GAME_OVER
        else:
            game.update()

    elif state == State.GAME_OVER:
        if key_just_pressed(keys.SPACE):
            state = State.MENU
            menu_state = MenuState.NUM_PLAYERS
            game = Game()

def draw():
    game.draw()

    if state == State.MENU:
  
        if menu_state == MenuState.NUM_PLAYERS:
            image = "menu0" + str(menu_num_players)
        else:
            image = "menu1" + str(menu_difficulty)
        screen.blit(image, (0, 0))

    elif state == State.PLAY:
        screen.blit("bar", (HALF_WINDOW_W - 176, 0))

        for i in range(2):
            screen.blit("s" + str(game.teams[i].score), (HALF_WINDOW_W + 7 - 39 * i, 6))

        if game.score_timer > 0:
            screen.blit("goal", (HALF_WINDOW_W - 300, HEIGHT / 2 - 88))

    elif state == State.GAME_OVER:
        img = "over" + str(int(game.teams[1].score > game.teams[0].score))
        screen.blit(img, (0, 0))

        for i in range(2):
            img = "l" + str(i) + str(game.teams[i].score)
            screen.blit(img, (HALF_WINDOW_W + 25 - 125 * i, 144))

try:
    pygame.mixer.quit()
    pygame.mixer.init(44100, -16, 2, 1024)
except Exception:
    pass

state = State.MENU

menu_state = MenuState.NUM_PLAYERS
menu_num_players = 1
menu_difficulty = 0

game = Game()

pgzrun.go()