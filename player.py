from pygame.math import Vector2
import random
import math
import constant
import game
from actor import MyActor
from goal import Goal

class Player():
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
        speed = constant.PLAYER_DEFAULT_SPEED

        my_team = game.teams[self.team]
        pre_kickoff = game.kickoff_player != None
        i_am_kickoff_player = self == game.kickoff_player
        ball = game.ball

        if self == game.teams[self.team].active_control_player and my_team.human() and (not pre_kickoff or i_am_kickoff_player):
     
            if ball.owner == self:
                speed = constant.HUMAN_PLAYER_WITH_BALL_SPEED
            else:
                speed = constant.HUMAN_PLAYER_WITHOUT_BALL_SPEED

            target = self.vpos + my_team.controls.move(speed)

        elif ball.owner != None:
            if ball.owner == self:
              
                costs = [game.cost(self.vpos + game.angle_to_vec(self.dir + d) * 3, self.team, abs(d)) for d in range(-2, 3)]

                
                _, target = min(costs, key=lambda element: element[0])

                speed = constant.CPU_PLAYER_WITH_BALL_BASE_SPEED + game.difficulty.speed_boost

            elif ball.owner.team == self.team:
                if self.active():

                    direction = -1 if self.team == 0 else 1
                    target.x = (ball.vpos.x + target.x) / 2
                    target.y = (ball.vpos.y + 400 * direction + target.y) / 2
            else:
                if self.lead is not None:


                    target = ball.owner.vpos + game.angle_to_vec(ball.owner.dir) * self.lead

                    target.x = max(constant.AI_MIN_X, min(constant.AI_MAX_X, target.x))
                    target.y = max(constant.AI_MIN_Y, min(constant.AI_MAX_Y, target.y))

                    other_team = 1 if self.team == 0 else 0
                    speed = constant.LEAD_PLAYER_BASE_SPEED
                    if game.teams[other_team].human():
                        speed += game.difficulty.speed_boost

                elif self.mark.active():

                    if my_team.human():
          
                        target = Vector2(ball.vpos)
                    else:
                        vec, length = game.safe_normalise(ball.vpos - self.mark.vpos)

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

       
                while (target - self.vpos).length() > constant.PLAYER_INTERCEPT_BALL_SPEED * frame + constant.DRIBBLE_DIST_X and vel.length() > 0.5:
                    target += vel
                    vel *= constant.DRAG
                    frame += 1

                speed = constant.PLAYER_INTERCEPT_BALL_SPEED

            elif pre_kickoff:
   
                target.y = self.vpos.y


        vec, distance = game.safe_normalise(target - self.vpos)

        self.debug_target = Vector2(target)

        if distance > 0:
            distance = min(distance, speed)

            target_dir = game.vec_to_angle(vec)

            
            if game.allow_movement(self.vpos.x + vec.x * distance, self.vpos.y):
                self.vpos.x += vec.x * distance
            if game.allow_movement(self.vpos.x, self.vpos.y + vec.y * distance):
                self.vpos.y += vec.y * distance

            self.anim_frame = (self.anim_frame + max(distance, 1.5)) % 72
        else:
            target_dir = game.vec_to_angle(ball.vpos - self.vpos)
            self.anim_frame = -1


        dir_diff = (target_dir - self.dir)
        self.dir = (self.dir + [0, 1, 1, 1, 1, 7, 7, 7][dir_diff % 8]) % 8

        suffix = str(self.dir) + str((int(self.anim_frame) // 18) + 1) # todo

        self.image = "player" + str(self.team) + suffix
        self.shadow.image = "players" + suffix

        self.shadow.vpos = Vector2(self.vpos)