import game
from pygame.math import Vector2

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
        return game.key_just_pressed(self.key_shoot)