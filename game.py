import pgzero, pgzrun, pygame
from enum import Enum
from pygame.math import Vector2
import random
import sys
import math

# Import other game components
from player import Player
from ball import Ball
from goal import Goal
from team import Team
from controls import Controls
from state import State, MenuState
from difficulty import Difficulty
import constant 

# Define constants for the game window size and title
WIDTH = 800
HEIGHT = 480
TITLE = "Soccer"

# Check the version of pgzero and exit if it's older than 1.2
pgzero_version = [int(s) if s.isnumeric() else s for s in pgzero.__version__.split('.')]
if pgzero_version < [1, 2]:
    sys.exit()


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

def ball_physics(pos, vel, bounds):
    pos += vel

    if pos < bounds[0] or pos > bounds[1]:
        pos, vel = pos - vel, -vel

    return pos, vel * constant.DRAG

def steps(distance):
    steps, vel = 0, constant.KICK_STRENGTH

    while distance > 0 and vel > 0.25:
        distance, steps, vel = distance - vel, steps + 1, vel * constant.DRAG

    return steps

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

    return constant.PITCH_RECT.collidepoint(x,y) \
           or constant.GOAL_0_RECT.collidepoint(x,y) \
           or constant.GOAL_1_RECT.collidepoint(x,y)

def allow_movement(x, y):
    if abs(x - constant.HALF_LEVEL_W) > constant.HALF_LEVEL_W:
        return False

    elif abs(x - constant.HALF_LEVEL_W) < constant.HALF_GOAL_W + 20:
        return abs(y - constant.HALF_LEVEL_H) < constant.HALF_PITCH_H

    else:
        return abs(y - constant.HALF_LEVEL_H) < constant.HALF_LEVEL_H


def cost(pos, team, handicap=0):

    own_goal_pos = Vector2(constant.HALF_LEVEL_W, 78 if team == 1 else constant.LEVEL_H - 78)
    inverse_own_goal_distance = 3500 / (pos - own_goal_pos).length()

    result = inverse_own_goal_distance \
            + sum([4000 / max(24, (p.vpos - pos).length()) for p in game.players if p.team != team]) \
            + ((pos.x - constant.HALF_LEVEL_W)**2 / 200 \
            - pos.y * (4 * team - 2)) \
            + handicap

    return result, pos




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
        for pos in constant.PLAYER_START_POS:
     
            self.players.append(Player(random_offset(pos[0]), random_offset(pos[1]), 0))
            self.players.append(Player(random_offset(constant.LEVEL_W - pos[0]), random_offset(constant.LEVEL_H - pos[1]), 1))

    
        for a, b in zip(self.players, self.players[::-1]):
            a.peer = b

        self.goals = [Goal(i) for i in range(2)]


        self.teams[0].active_control_player = self.players[0]
        self.teams[1].active_control_player = self.players[1]

        other_team = 1 if self.scoring_team == 0 else 0


        self.kickoff_player = self.players[other_team]

        self.kickoff_player.vpos = Vector2(constant.HALF_LEVEL_W - 30 + other_team * 60, constant.HALF_LEVEL_H)

        self.ball = Ball()

        self.camera_focus = Vector2(self.ball.vpos)

        self.debug_shoot_target = None

    def update(self):
        self.score_timer -= 1

        if self.score_timer == 0:
            self.reset()

        elif self.score_timer < 0 and abs(self.ball.vpos.y - constant.HALF_LEVEL_H) > constant.HALF_PITCH_H:
            game.play_sound("goal", 2)

            self.scoring_team = 0 if self.ball.vpos.y < constant.HALF_LEVEL_H else 1
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


            zipped[0].lead = constant.LEAD_DISTANCE_1
            if self.difficulty.second_lead_enabled:
                zipped[1].lead = constant.LEAD_DISTANCE_2

       
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
        offset_x = max(0, min(constant.LEVEL_W - WIDTH, self.camera_focus.x - WIDTH / 2))
        offset_y = max(0, min(constant.LEVEL_H - HEIGHT, self.camera_focus.y - HEIGHT / 2))
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

        if constant.DEBUG_SHOW_LEADS:
            for p in self.players:
                if game.ball.owner and p.lead:
                    line_start = game.ball.owner.vpos - offset
                    line_end = p.vpos - offset
                    pygame.draw.line(screen.surface, (0,0,0), line_start, line_end)

        if constant.DEBUG_SHOW_TARGETS:
            for p in self.players:
                line_start = p.debug_target - offset
                line_end = p.vpos - offset
                pygame.draw.line(screen.surface, (255,0,0), line_start, line_end)

        if constant.DEBUG_SHOW_PEERS:
            for p in self.players:
                line_start = p.peer.vpos - offset
                line_end = p.vpos - offset
                pygame.draw.line(screen.surface, (0,0,255), line_start, line_end)

        if constant.DEBUG_SHOW_SHOOT_TARGET:
            if self.debug_shoot_target and self.ball.owner:
                line_start = self.ball.owner.vpos - offset
                line_end = self.debug_shoot_target - offset
                pygame.draw.line(screen.surface, (255,0,255), line_start, line_end)
        
        if constant.DEBUG_SHOW_COSTS and self.ball.owner:
            for x in range(0,constant.LEVEL_W,60):
                for y in range(0, constant.LEVEL_H, 26):
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
        screen.blit("bar", (constant.HALF_WINDOW_W - 176, 0))

        for i in range(2):
            screen.blit("s" + str(game.teams[i].score), (constant.HALF_WINDOW_W + 7 - 39 * i, 6))

        if game.score_timer > 0:
            screen.blit("goal", (constant.HALF_WINDOW_W - 300, HEIGHT / 2 - 88))

    elif state == State.GAME_OVER:
        img = "over" + str(int(game.teams[1].score > game.teams[0].score))
        screen.blit(img, (0, 0))

        for i in range(2):
            img = "l" + str(i) + str(game.teams[i].score)
            screen.blit(img, (constant.HALF_WINDOW_W + 25 - 125 * i, 144))

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
