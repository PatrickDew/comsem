class Team:
    def __init__(self, controls):
        self.controls = controls
        self.active_control_player = None
        self.score = 0

    def human(self):
        return self.controls != None