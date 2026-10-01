"""Deterministic route usage: one activity visit per crossed grid cell."""
from dataclasses import dataclass
from math import floor, inf, isfinite, isclose


@dataclass(frozen=True)
class RouteDensityParameters:
    cell_size: float = 10.0
    sigma: float = 20.0
    tile_size: int = 256
    algorithm: str = "route-visits-v1"

    def __post_init__(self):
        if not isfinite(self.cell_size) or self.cell_size <= 0:
            raise ValueError("Heatmap cell size must be positive and finite")
        if not isfinite(self.sigma) or self.sigma < 0:
            raise ValueError("Heatmap smoothing must be nonnegative and finite")
        if self.tile_size < 16 or self.tile_size & (self.tile_size - 1) or self.sigma * 3 >= self.cell_size * self.tile_size:
            raise ValueError("Heatmap tiles must fit the smoothing halo")


class HeatmapCancelled(Exception):
    pass


def check_cancelled(cancelled):
    if cancelled():
        raise HeatmapCancelled()


def segment_cells(start, end, cell_size):
    """Walk a segment on an origin-anchored grid, independent of vertex spacing."""
    x0, y0 = start[0] / cell_size, start[1] / cell_size
    x1, y1 = end[0] / cell_size, end[1] / cell_size
    if not all(isfinite(v) for v in (x0, y0, x1, y1)):
        raise ValueError("Heatmap track contains nonfinite coordinates")
    col, row = floor(x0), floor(y0)
    end_col, end_row = floor(x1), floor(y1)
    dx, dy = x1 - x0, y1 - y0
    step_x, step_y = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
    delta_x, delta_y = (abs(1 / dx) if dx else inf), (abs(1 / dy) if dy else inf)
    next_x = ((col + 1 - x0) / dx if dx > 0 else (col - x0) / dx) if dx else inf
    next_y = ((row + 1 - y0) / dy if dy > 0 else (row - y0) / dy) if dy else inf
    yield col, row
    while (col, row) != (end_col, end_row):
        if col == end_col:
            next_x = inf
        if row == end_row:
            next_y = inf
        if isclose(next_x, next_y, rel_tol=1e-12, abs_tol=1e-12):
            col += step_x
            row += step_y
            next_x += delta_x
            next_y += delta_y
        elif next_x < next_y:
            col += step_x
            next_x += delta_x
        else:
            row += step_y
            next_y += delta_y
        yield col, row


def activity_cells(parts, parameters, cancelled=lambda: False, max_cells=2_000_000):
    """Deduplicate repeats, multipart overlaps and stationary samples per activity."""
    visited = set()
    work = 0
    for points in parts:
        for start, end in zip(points, points[1:]):
            for cell in segment_cells(start, end, parameters.cell_size):
                work += 1
                if work % 1024 == 0:
                    check_cancelled(cancelled)
                visited.add(cell)
                if len(visited) > max_cells:
                    raise ValueError("A heatmap activity exceeds the safe cell budget")
    check_cancelled(cancelled)
    return visited


def tile_cell(cell, tile_size):
    col, row = cell
    return (col // tile_size, row // tile_size), (row % tile_size, col % tile_size)
