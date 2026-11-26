
import pandas as pd
import ast
import math

from Calculations.angle import calculate_shot_angle
from Calculations.distance import calculate_shot_distance
from Calculations.entryToShot import calculate_entry_to_shot_time

from Calculations.pressure import (
    calculate_pressure,
    calculate_attack_pressure
)

from Calculations.shotLineCoverage import (
    calculate_shot_line_coverage
)

from Calculations.goaliePositioning import (
    calculate_goalie_positioning_score
)


WEIGHTS = {
    "D": 1.0,
    "A": 1.0,
    "V": 1.0,
    "T": 1.0,
    "P": 1.0,
    "C_L": 1.0,
    "G": 5.0
}

BEHIND_GOAL_SCORE = 5.0
PRESSURE_SENSITIVITY = 2.0


def normalize_id(value):
    if pd.isna(value):
        return None

    try:
        number = float(value)

        if number.is_integer():
            return str(int(number))

    except (ValueError, TypeError):
        pass

    return str(value).strip()


def parse_coordinate(coordinate):
    if coordinate is None:
        return None

    try:
        if pd.isna(coordinate):
            return None
    except (ValueError, TypeError):
        return None

    try:
        position = ast.literal_eval(str(coordinate))
        return float(position[0]), float(position[1])

    except (ValueError, TypeError, SyntaxError, IndexError):
        return None


def is_behind_goal(shooter_x, goal_x):
    direction = 1 if goal_x >= 0 else -1
    return shooter_x * direction >= abs(goal_x)


def get_target_goal_x(shooter_x, shooter_y):
    right_goal = (26, 0)
    left_goal = (-26, 0)

    distance_right = (
        (right_goal[0] - shooter_x) ** 2
        + (right_goal[1] - shooter_y) ** 2
    )

    distance_left = (
        (left_goal[0] - shooter_x) ** 2
        + (left_goal[1] - shooter_y) ** 2
    )

    return 26 if distance_right <= distance_left else -26


def get_opponent_positions(shot):
    shooter_team = shot["EventPrimaryTeam"]

    goalie_ids = {
        normalize_id(shot["HomeGoalieOnIce"]),
        normalize_id(shot["AwayGoalieOnIce"])
    }

    goalie_ids.discard(None)

    opponent_positions = []

    for i in range(1, 13):
        player_id = normalize_id(
            shot[f"StartPlayerId{i}"]
        )

        player_team = shot[f"StartPlayerTeam{i}"]
        coordinate = shot[f"StartPlayerCoordinates{i}"]

        if pd.isna(player_team) or pd.isna(coordinate):
            continue

        if player_id in goalie_ids:
            continue

        if str(player_team) == str(shooter_team):
            continue

        position = parse_coordinate(coordinate)

        if position is not None:
            opponent_positions.append(position)

    return opponent_positions


def get_shooter_slot(shot):
    event_position = parse_coordinate(
        shot["EventStartCoordinate"]
    )

    if event_position is None:
        return None

    event_x, event_y = event_position
    shooter_team = shot["EventPrimaryTeam"]

    best_slot = None
    best_distance = None

    for i in range(1, 13):
        player_team = shot[f"StartPlayerTeam{i}"]

        position = parse_coordinate(
            shot[f"StartPlayerCoordinates{i}"]
        )

        if pd.isna(player_team) or position is None:
            continue

        if str(player_team) != str(shooter_team):
            continue

        distance = (
            (position[0] - event_x) ** 2
            + (position[1] - event_y) ** 2
        )

        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_slot = i

    return best_slot


def get_shot_position(shot, shooter_slot=None):
    if shooter_slot is None:
        shooter_slot = get_shooter_slot(shot)

    if shooter_slot is not None:
        position = parse_coordinate(
            shot[f"StartPlayerCoordinates{shooter_slot}"]
        )

        if position is not None:
            return position

    return parse_coordinate(
        shot["EventStartCoordinate"]
    )


def calculate_shot_pressure(shot):
    """
    Berechnet den Pressure-Wert eines einzelnen Schusses.

    Beruecksichtigt die Position des Schuetzen und die
    Positionen der gegnerischen Feldspieler.
    """

    position = get_shot_position(shot)
    opponents = get_opponent_positions(shot)

    if position is None or not opponents:
        return None

    return calculate_pressure(
        position[0],
        position[1],
        opponents
    )


def calculate_pressure_factor(
    selected_shot,
    df,
    shooter_slot=None
):
    opponent_positions = get_opponent_positions(
        selected_shot
    )

    if not opponent_positions:
        return None

    shot_position = get_shot_position(
        selected_shot,
        shooter_slot=shooter_slot
    )

    if shot_position is None:
        return None

    pressure = calculate_pressure(
        shot_position[0],
        shot_position[1],
        opponent_positions
    )

    reference_shots = df[
        (df["EventType"] == "Shot")
        & (df.index != selected_shot.name)
    ]

    pressure_values = reference_shots.apply(
        calculate_shot_pressure,
        axis=1
    ).dropna()

    if pressure_values.empty:
        attack_pressure = (
            100 * math.exp(-PRESSURE_SENSITIVITY * pressure)
        )

    else:
        p_min = pressure_values.min()
        p_max = pressure_values.max()

        if p_max > p_min:
            attack_pressure = calculate_attack_pressure(
                pressure,
                p_min,
                p_max
            )

        else:
            attack_pressure = (
                100 * math.exp(-PRESSURE_SENSITIVITY * pressure)
            )

    attack_pressure = max(
        1.0,
        min(100.0, attack_pressure)
    )

    return attack_pressure


def calculate_attack_score(
    D,
    A,
    V,
    T,
    P,
    C_L,
    G,
    weights=None
):
    if weights is None:
        weights = WEIGHTS

    values = {
        "D": D,
        "A": A,
        "V": V,
        "T": T,
        "P": P,
        "C_L": C_L,
        "G": G
    }

    if any(
        value is None or pd.isna(value)
        for value in values.values()
    ):
        return None

    if any(weight < 0 for weight in weights.values()):
        raise ValueError("Weights cannot be negative.")

    total_weight = sum(
        weights[key]
        for key in values
    )

    if total_weight <= 0:
        raise ValueError("Total weight must be positive.")

    weighted_sum = sum(
        weights[key] * values[key]
        for key in values
    )

    return round(
        weighted_sum / total_weight,
        2
    )


def calculate_attack_score_for_shot(
    selected_shot,
    df,
    shooter_slot=None,
    goal_x=None,
    shot_speed=None
):
    """
    Berechnet den gesamten AttackScore eines Schusses.

    shot_speed:
        Optionaler simulierter Schussgeschwindigkeitswert.
        Falls None, wird die Originalgeschwindigkeit verwendet.
    """

    shot_position = get_shot_position(
        selected_shot,
        shooter_slot
    )

    if shot_position is None:
        return None

    shot_x, shot_y = shot_position

    if goal_x is None:
        goal_x = get_target_goal_x(
            shot_x,
            shot_y
        )

    if is_behind_goal(shot_x, goal_x):
        return BEHIND_GOAL_SCORE

    distance = calculate_shot_distance(
        shot_x,
        shot_y,
        goal_x=goal_x,
        goal_y=0
    )

    D = max(
        0,
        min(100, 100 * (1 - distance / 30))
    )

    angle = calculate_shot_angle(
        shot_x,
        shot_y,
        goal_x=goal_x,
        goal_y=0
    )

    A = max(
        0,
        min(100, 100 * (1 - angle / 90))
    )

    # Simulierte oder originale Schussgeschwindigkeit
    if shot_speed is None:
        shot_speed = selected_shot["ShotSpeed"]

    if pd.isna(shot_speed):
        return None

    V = max(
        0,
        min(100, float(shot_speed))
    )

    entry_to_shot = calculate_entry_to_shot_time(
        df,
        selected_shot.name
    )

    T = (
        max(0, min(100, 100 * (1 - entry_to_shot / 60)))
        if entry_to_shot is not None
        else None
    )

    attack_pressure = calculate_pressure_factor(
        selected_shot,
        df,
        shooter_slot=shooter_slot
    )

    opponent_positions = get_opponent_positions(
        selected_shot
    )

    if not opponent_positions:
        return None

    coverage_result = calculate_shot_line_coverage(
        shooter_x=shot_x,
        shooter_y=shot_y,
        defender_positions=opponent_positions,
        goal_x=goal_x,
        goal_y=0,
        r=0.4
    )

    coverage_factor = coverage_result["coverage_factor"]

    goalie_positions = []

    for slot in [1, 7]:
        position = parse_coordinate(
            selected_shot[f"StartPlayerCoordinates{slot}"]
        )

        if position is not None:
            goalie_positions.append({
                "slot": slot,
                "x": position[0],
                "y": position[1]
            })

    if len(goalie_positions) != 2:
        return None

    goalie = min(
        goalie_positions,
        key=lambda player: (
            (player["x"] - goal_x) ** 2
            + player["y"] ** 2
        )
    )

    goalie_score = calculate_goalie_positioning_score(
        puck=parse_coordinate(
            selected_shot["EventStartCoordinate"]
        ),
        goalie=(goalie["x"], goalie["y"]),
        goal=(goal_x, 0)
    )

    return calculate_attack_score(
        D=D,
        A=A,
        V=V,
        T=T,
        P=attack_pressure,
        C_L=coverage_factor,
        G=goalie_score
    )
