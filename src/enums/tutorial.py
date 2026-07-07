"""
Tutorial progression enum — mapped from action 62 payloads and login flag testing.
See claude_sessions/login_flags_matrix.md for full test results.
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


# Valid resume points for login progression.
# Other values crash or black screen on resume.
VALID_RESUME_POINTS = {
    TutorialProgression.START,
    TutorialProgression.POST_BIRTHDAY,
    TutorialProgression.POST_AVATAR,
    TutorialProgression.POST_UNION,
}


def clamp_progression(prog: int) -> int:
    """Clamp a stored progression to a safe resume point.
    0 stays 0 (full flow). 1-4 clamp to 1 (download). 5 stays 5 (union). 6+ clamps to 6 (battle)."""
    if prog <= 0:
        return TutorialProgression.START
    if prog < 5:
        return TutorialProgression.POST_BIRTHDAY
    if prog == 5:
        return TutorialProgression.POST_AVATAR
    if prog >= 6:
        return TutorialProgression.POST_UNION
    return prog
