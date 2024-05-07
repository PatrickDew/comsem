from pygame.math import Vector2
import constant
import game
from actor import MyActor
from player import Player

class Ball(MyActor):
    def __init__(self):
        super().__init__("ball", constant.HALF_LEVEL_W, constant.HALF_LEVEL_H)
        self.vel = Vector2(0, 0)

        self.owner = None
        self.timer = 0

        self.shadow = MyActor("balls")

    def collide(self, p):
        return p.timer < 0 and (p.vpos - self.vpos).length() <= constant.DRIBBLE_DIST_X

    def update(self):
        self.timer -= 1

        if self.owner:
            new_x = game.avg(self.vpos.x, self.owner.vpos.x + constant.DRIBBLE_DIST_X * game.sin(self.owner.dir))
            new_y = game.avg(self.vpos.y, self.owner.vpos.y - constant.DRIBBLE_DIST_Y * game.cos(self.owner.dir))

            if game.on_pitch(new_x, new_y):
                self.vpos = Vector2(new_x, new_y)
            else:
                self.owner.timer = 60

                self.vel = game.angle_to_vec(self.owner.dir) * 3

                self.owner = None
        else:
            if abs(self.vpos.y - constant.HALF_LEVEL_H) > constant.HALF_PITCH_H:
                bounds_x = constant.GOAL_BOUNDS_X
            else:
                bounds_x = constant.PITCH_BOUNDS_X

            if abs(self.vpos.x - constant.HALF_LEVEL_W) < constant.HALF_GOAL_W:
                bounds_y = constant.GOAL_BOUNDS_Y
            else:
                bounds_y = constant.PITCH_BOUNDS_Y

            self.vpos.x, self.vel.x = game.ball_physics(self.vpos.x, self.vel.x, bounds_x)
            self.vpos.y, self.vel.y = game.ball_physics(self.vpos.y, self.vel.y, bounds_y)

        self.shadow.vpos = Vector2(self.vpos)

        for target in game.players:

            if (not self.owner or self.owner.team != target.team) and self.collide(target):
                if self.owner:

                    self.owner.timer = 60

                self.timer = game.difficulty.holdoff_timer

                game.teams[target.team].active_control_player = self.owner = target

        if self.owner:
            team = game.teams[self.owner.team]


            targetable_players = [p for p in game.players + game.goals if p.team == self.owner.team and game.targetable(p, self.owner)]

            if len(targetable_players) > 0:

                target = min(targetable_players, key=game.dist_key(self.owner.vpos))
                game.debug_shoot_target = target.vpos
            else:
                target = None

            if team.human():
                do_shoot = team.controls.shoot()
            else:

                do_shoot = self.timer <= 0 and target and game.cost(target.vpos, self.owner.team) < game.cost(self.owner.vpos, self.owner.team)

            if do_shoot:

                game.play_sound("kick", 4)

                if target:
           
                    r = 0

                    iterations = 8 if team.human() and isinstance(target, Player) else 1

                    for i in range(iterations):
                        t = target.vpos + game.angle_to_vec(self.owner.dir) * r

                        vec, length = game.safe_normalise(t - self.vpos)

                        r = constant.HUMAN_PLAYER_WITHOUT_BALL_SPEED * game.steps(length)
                else:

                    vec = game.ngle_to_vec(self.owner.dir)

                    target = min([p for p in game.players if p.team == self.owner.team],
                                 key=game.dist_key(self.vpos + (vec * 250)))

                if isinstance(target, Player):
                    game.teams[self.owner.team].active_control_player = target

                self.owner.timer = 10  

                self.vel = vec * constant.KICK_STRENGTH

                self.owner = None