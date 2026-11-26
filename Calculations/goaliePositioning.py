import math


GOALIE_SLOTS = [1, 7]
GOALIE_ALIGNMENT_MAX_DISTANCE = 3.0


def calculate_distance_to_goal(player_position, goal_x):
    x, y = player_position

    distance = math.sqrt(
        (x - goal_x) ** 2 + y ** 2
    )

    return distance


def find_goalie(players, goal_x):

    possible_goalies = [
        player
        for player in players
        if player["slot"] in GOALIE_SLOTS
    ]

    if len(possible_goalies) != 2:
        return None

    goalie = min(
        possible_goalies,
        key=lambda player: calculate_distance_to_goal(
            (player["x"], player["y"]),
            goal_x
        )
    )

    return goalie


def calculate_goalie_alignment(puck, goalie, goal):
    px, py = puck
    gx, gy = goalie
    tx, ty = goal

    vx = tx - px
    vy = ty - py

    wx = gx - px
    wy = gy - py

    denominator = math.sqrt(
        vx ** 2 + vy ** 2
    )

    if denominator == 0:
        return None

    distance = abs(
        vx * wy - vy * wx
    ) / denominator

    return distance


def is_goalie_between_puck_and_goal(puck, goalie, goal):

    px, py = puck
    gx, gy = goalie
    tx, ty = goal

    vx = tx - px
    vy = ty - py

    wx = gx - px
    wy = gy - py

    denominator = vx ** 2 + vy ** 2

    if denominator == 0:
        return False

    projection = (
        wx * vx + wy * vy
    ) / denominator

    return 0 < projection < 1


def calculate_goalie_score(
    alignment_distance,
    max_distance=GOALIE_ALIGNMENT_MAX_DISTANCE,
    goalie_between=True
):

    if alignment_distance is None or max_distance <= 0:
        return None

    if not goalie_between:
        return 100.0

    score = min(
        100,
        max(
            0,
            100 * alignment_distance / max_distance
        )
    )

    return round(score, 2)


def calculate_goalie_positioning_score(
    puck,
    goalie,
    goal,
    max_distance=GOALIE_ALIGNMENT_MAX_DISTANCE
):
    if puck is None or goalie is None or goal is None:
        return None

    alignment_distance = calculate_goalie_alignment(
        puck,
        goalie,
        goal
    )

    goalie_between = is_goalie_between_puck_and_goal(
        puck,
        goalie,
        goal
    )

    return calculate_goalie_score(
        alignment_distance,
        max_distance=max_distance,
        goalie_between=goalie_between
    )
