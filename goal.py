
import constant
import game

class Goal():
    def __init__(self, team):
        x = constant.HALF_LEVEL_W
        y = 0 if team == 0 else constant.LEVEL_H
        super().__init__("goal" + str(team), x, y)

        self.team = team

    def active(self):
        return abs(game.ball.vpos.y - self.vpos.y) < 500