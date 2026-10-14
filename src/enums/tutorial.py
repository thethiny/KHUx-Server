"""
Tutorial progression (action 62 `progression`, login.progression). On a relaunch the client resumes at the screen
for the stored step (sub_67F3C0): 1 invitation / download, 2 download, 3 name, 4 avatar, 5 union, 6 the tutorial
battle; any other value shows the EULA. The guided tutorial after that is tracked by /tutorial/status phases.
"""
from enum import IntEnum


class TutorialProgression(IntEnum):
    START = 0               # EULA shown, full flow
    POST_BIRTHDAY = 1       # EULA accepted, download step
    POST_BIRTHDAY_CONF = 2  # Birthday confirmed
    POST_DOWNLOAD = 3       # Download done, name entry
    POST_NAME = 4           # Name entered, avatar creation
    POST_AVATAR = 5         # Avatar set, union select
    POST_UNION = 6          # Union selected, battle
    COMPLETE = 995          # Tutorial finished
