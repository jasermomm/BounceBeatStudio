from __future__ import annotations

"""Shared collision geometry for the Pymunk and deterministic backends.

BounceBeat uses screen coordinates: +X points right and +Y points down. Positive
project rotations therefore appear clockwise on screen. Keeping all angle and arc
construction here prevents the preview, fallback physics, and Pymunk physics from
drifting apart.
"""

import math
from dataclasses import dataclass
from typing import Iterable

Vec2 = tuple[float, float]
_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class ArcSegment:
    start: Vec2
    end: Vec2
    previous: Vec2
    following: Vec2


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def add(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] + b[0], a[1] + b[1])


def subtract(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] - b[0], a[1] - b[1])


def multiply(vector: Vec2, scalar: float) -> Vec2:
    return (vector[0] * scalar, vector[1] * scalar)


def dot(a: Vec2, b: Vec2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def length(vector: Vec2) -> float:
    return math.hypot(vector[0], vector[1])


def normalized(vector: Vec2, fallback: Vec2 = (1.0, 0.0)) -> Vec2:
    magnitude = length(vector)
    if magnitude <= _EPSILON:
        return fallback
    return (vector[0] / magnitude, vector[1] / magnitude)


def rotate_screen(point: Vec2, degrees: float) -> Vec2:
    """Rotate in screen coordinates; positive degrees appear clockwise."""

    radians = math.radians(degrees)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    return (
        point[0] * cosine - point[1] * sine,
        point[0] * sine + point[1] * cosine,
    )


def transform_point(local: Vec2, position: Vec2, rotation_degrees: float) -> Vec2:
    return add(position, rotate_screen(local, rotation_degrees))


def angular_velocity_at(point: Vec2, center: Vec2, degrees_per_second: float) -> Vec2:
    """Linear velocity of a point on a clockwise-positive rotating body."""

    relative = subtract(point, center)
    omega = math.radians(degrees_per_second)
    return (-omega * relative[1], omega * relative[0])


def normalize_degrees(angle: float) -> float:
    return angle % 360.0


def signed_angle_delta(angle: float, center: float) -> float:
    return (angle - center + 180.0) % 360.0 - 180.0


def screen_angle_degrees(vector: Vec2) -> float:
    return normalize_degrees(math.degrees(math.atan2(vector[1], vector[0])))


def point_is_in_ring_opening(
    point: Vec2,
    center: Vec2,
    opening_center_degrees: float,
    opening_angle_degrees: float,
    angular_padding_degrees: float = 0.0,
) -> bool:
    opening = clamp(opening_angle_degrees, 0.0, 359.999)
    if opening <= 0.0:
        return False
    angle = screen_angle_degrees(subtract(point, center))
    return abs(signed_angle_delta(angle, opening_center_degrees)) <= opening / 2.0 + max(0.0, angular_padding_degrees)


def ring_arc_points(radius: float, opening_angle_degrees: float, segments: int) -> tuple[list[Vec2], bool]:
    """Return exact local points for the solid portion of a ring.

    The opening is centered on local +X. For an open ring, the first and last
    points sit exactly on the two opening boundaries. For a closed ring, points
    are unique and callers close the final edge back to point zero.
    """

    safe_radius = max(0.001, float(radius))
    requested_segments = max(12, int(segments))
    opening = clamp(float(opening_angle_degrees), 0.0, 359.999)
    is_closed = opening <= 1e-7

    if is_closed:
        points = [
            (math.cos(index / requested_segments * math.tau) * safe_radius,
             math.sin(index / requested_segments * math.tau) * safe_radius)
            for index in range(requested_segments)
        ]
        return points, True

    solid_degrees = 360.0 - opening
    arc_segments = max(1, math.ceil(requested_segments * solid_degrees / 360.0))
    start_degrees = opening / 2.0
    points = []
    for index in range(arc_segments + 1):
        angle = math.radians(start_degrees + solid_degrees * index / arc_segments)
        points.append((math.cos(angle) * safe_radius, math.sin(angle) * safe_radius))
    return points, False


def ring_arc_segments(radius: float, opening_angle_degrees: float, segments: int) -> list[ArcSegment]:
    points, closed = ring_arc_points(radius, opening_angle_degrees, segments)
    if len(points) < 2:
        return []

    result: list[ArcSegment] = []
    count = len(points) if closed else len(points) - 1
    for index in range(count):
        end_index = (index + 1) % len(points)
        if closed:
            previous = points[(index - 1) % len(points)]
            following = points[(index + 2) % len(points)]
        else:
            previous = points[index - 1] if index > 0 else points[index]
            following = points[index + 2] if index + 2 < len(points) else points[end_index]
        result.append(ArcSegment(points[index], points[end_index], previous, following))
    return result


def qt_ring_arc_degrees(screen_clockwise_rotation: float, opening_angle_degrees: float) -> tuple[float, float]:
    """Convert project ring rotation to QPainter's counter-clockwise arc angles."""

    opening = clamp(opening_angle_degrees, 0.0, 359.999)
    qt_opening_center = -screen_clockwise_rotation
    return qt_opening_center + opening / 2.0, 360.0 - opening


def closest_point_on_segment(point: Vec2, start: Vec2, end: Vec2) -> tuple[Vec2, float]:
    edge = subtract(end, start)
    denominator = dot(edge, edge)
    if denominator <= _EPSILON:
        return start, 0.0
    amount = clamp(dot(subtract(point, start), edge) / denominator, 0.0, 1.0)
    return add(start, multiply(edge, amount)), amount


def point_in_polygon(point: Vec2, vertices: Iterable[Vec2]) -> bool:
    points = list(vertices)
    if len(points) < 3:
        return False
    inside = False
    previous = points[-1]
    for current in points:
        y_crosses = (current[1] > point[1]) != (previous[1] > point[1])
        if y_crosses:
            denominator = previous[1] - current[1]
            if abs(denominator) <= _EPSILON:
                denominator = _EPSILON
            x_intersection = (previous[0] - current[0]) * (point[1] - current[1]) / denominator + current[0]
            if point[0] < x_intersection:
                inside = not inside
        previous = current
    return inside


def polygon_world_vertices(vertices: Iterable[Vec2], position: Vec2, rotation_degrees: float) -> list[Vec2]:
    return [transform_point(vertex, position, rotation_degrees) for vertex in vertices]


def minimum_polygon_half_width(vertices: Iterable[Vec2]) -> float:
    points = list(vertices)
    if not points:
        return 8.0
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return max(1.0, min(max(xs) - min(xs), max(ys) - min(ys)) / 2.0)
