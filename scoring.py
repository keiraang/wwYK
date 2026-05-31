"""
scoring.py — XP and Points math for "What Would YOU Know?"

XP = knowledge/experience points tied to skills.
  - XP only goes down when a player FAILS a refresher challenge.
  - Earned by adding skills, winning or surviving challenges.

Points = competitive currency earned through challenges.
  - Can be transferred between players as challenge stakes.
"""

# ---------------------------------------------------------------------------
# XP constants — change these to tune the feel of the game
# ---------------------------------------------------------------------------

XP_ADD_SKILL = 20          # Base XP for adding a new skill to your profile
XP_PASS_CHALLENGE = 25     # Opponent passes a challenge they were tested on
XP_BLUFF_CALLED = -20      # Opponent FAILS when challenger called their bluff (lost XP)
XP_BLUFF_SURVIVES = 15     # Opponent passes when their claimed skill was challenged
XP_REFRESHER_FAIL = -15    # Player fails a refresher on their own skill
XP_REFRESHER_PASS = 10     # Player passes a refresher (keep skill sharp)
XP_NEITHER_PASS = 30       # Both players studied + both scored above threshold
XP_NEITHER_FAIL = 0        # Studied but didn't hit the threshold — no gain, no loss

# Score threshold (0–100) needed to earn XP in a "neither knows" challenge
NEITHER_PASS_THRESHOLD = 60

# ---------------------------------------------------------------------------
# Points constants
# ---------------------------------------------------------------------------

POINTS_CHALLENGE_WIN = 15  # Default points bonus for winning a challenge
POINTS_CHALLENGE_LOSE = 0  # Default points change for the loser

# ---------------------------------------------------------------------------
# XP functions
# ---------------------------------------------------------------------------

def xp_for_adding_skill() -> int:
    """Return XP awarded when a player adds a new skill."""
    return XP_ADD_SKILL


def xp_for_challenge_result(
    challenge_type: str,
    role: str,
    passed: bool,
) -> int:
    """
    Calculate the XP delta for one player after a challenge.

    challenge_type:
        "challenger_knows"  — challenger tests opponent on a skill challenger has
        "opponent_knows"    — challenger calls bluff on opponent's claimed skill
        "neither_knows"     — both studied; scored by passing threshold

    role:
        "challenger"  — the person who issued the challenge
        "opponent"    — the person being challenged

    passed:
        True if the relevant player met the success condition.

    Returns a positive or negative integer to be added to the player's XP.
    """
    if challenge_type == "challenger_knows":
        # Challenger tests opponent.
        # Opponent passes → opponent earns XP; challenger unaffected here.
        # Opponent fails → challenger's superiority confirmed, challenger earns XP.
        if role == "opponent":
            return XP_PASS_CHALLENGE if passed else 0
        if role == "challenger":
            return XP_PASS_CHALLENGE if not passed else 0  # rewarded when opponent fails

    elif challenge_type == "opponent_knows":
        # Challenger calls the opponent's bluff.
        # Opponent passes → bluff wasn't a bluff; opponent earns XP.
        # Opponent fails → bluff called correctly; challenger earns XP, opponent loses XP.
        if role == "opponent":
            return XP_BLUFF_SURVIVES if passed else XP_BLUFF_CALLED
        if role == "challenger":
            return POINTS_CHALLENGE_WIN if not passed else 0  # challenger wins when opponent fails

    elif challenge_type == "neither_knows":
        # Both studied; XP awarded based on individual score vs threshold.
        return XP_NEITHER_PASS if passed else XP_NEITHER_FAIL

    return 0


def xp_for_refresher(passed: bool) -> int:
    """
    Return XP delta for a refresher challenge on the player's own skill.
    This is the only way XP goes down outside of a bluff-call loss.
    """
    return XP_REFRESHER_PASS if passed else XP_REFRESHER_FAIL


# ---------------------------------------------------------------------------
# Points functions
# ---------------------------------------------------------------------------

def points_for_challenge(
    won: bool,
    stakes_points: int = 0,
) -> int:
    """
    Return the points delta for a player after a challenge.

    won         — True if this player won the challenge.
    stakes_points — extra points the loser agreed to give the winner.

    The winner receives POINTS_CHALLENGE_WIN + stakes_points.
    The loser receives -(stakes_points) if stakes were set, else 0.
    """
    if won:
        return POINTS_CHALLENGE_WIN + stakes_points
    else:
        return -stakes_points  # 0 if no stakes, negative if points were wagered


# ---------------------------------------------------------------------------
# Level helper — purely cosmetic title based on total XP
# ---------------------------------------------------------------------------

LEVEL_THRESHOLDS = [
    (0,   "Novice"),
    (50,  "Apprentice"),
    (100, "Journeyman"),
    (200, "Expert"),
    (350, "Master"),
    (500, "Grandmaster"),
]


def level_title(total_xp: int) -> str:
    """Return a cosmetic title string based on total accumulated XP."""
    title = LEVEL_THRESHOLDS[0][1]
    for threshold, name in LEVEL_THRESHOLDS:
        if total_xp >= threshold:
            title = name
    return title


def xp_to_next_level(total_xp: int) -> tuple[int, int]:
    """
    Return (current_level_floor, next_level_threshold).
    Useful for drawing a progress bar.
    Returns (current_floor, None) if at max level.
    """
    floor = 0
    for i, (threshold, _) in enumerate(LEVEL_THRESHOLDS):
        if total_xp >= threshold:
            floor = threshold
            if i + 1 < len(LEVEL_THRESHOLDS):
                next_t = LEVEL_THRESHOLDS[i + 1][0]
            else:
                next_t = None
    return floor, next_t
