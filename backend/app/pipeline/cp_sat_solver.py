from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.data import Place


@dataclass(frozen=True)
class CpSatScheduleResult:
    available: bool
    feasible: bool
    status: str
    checked_slots: int
    objective_minutes: int | None
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class CpSatSelectionResult:
    available: bool
    selected_ids: tuple[str, ...]
    status: str
    candidate_count: int
    objective_score: int | None
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class CpSatOrderResult:
    available: bool
    ordered_ids: tuple[str, ...]
    status: str
    candidate_count: int
    objective_travel_minutes: int | None
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class CpSatDayScheduleResult:
    available: bool
    feasible: bool
    status: str
    selected_ids: tuple[str, ...]
    starts: dict[str, int]
    objective_score: int | None
    candidate_count: int
    blockers: tuple[str, ...] = ()


def _clock(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def select_places_with_cp_sat(
    candidates: list[Place],
    count: int,
    budget_per_person: int,
    scores: dict[str, int],
    *,
    max_candidates: int = 40,
) -> CpSatSelectionResult:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return CpSatSelectionResult(
            available=False,
            selected_ids=(),
            status="ortools_missing",
            candidate_count=0,
            objective_score=None,
            blockers=("OR-Tools is not installed",),
        )
    pool = candidates[:max_candidates]
    if count <= 0:
        return CpSatSelectionResult(True, (), "empty_request", len(pool), 0)
    if len(pool) < count:
        return CpSatSelectionResult(
            available=True,
            selected_ids=(),
            status="insufficient_candidates",
            candidate_count=len(pool),
            objective_score=None,
            blockers=("insufficient_candidates",),
        )
    model = cp_model.CpModel()
    selected = [model.NewBoolVar(f"select_{index}") for index, _place in enumerate(pool)]
    model.Add(sum(selected) == count)
    model.Add(sum(selected[index] * max(0, pool[index].cost) for index in range(len(pool))) <= budget_per_person)
    model.Maximize(sum(selected[index] * max(0, int(scores.get(pool[index].id, 0))) for index in range(len(pool))))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1.0
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return CpSatSelectionResult(
            available=True,
            selected_ids=(),
            status=solver.StatusName(status),
            candidate_count=len(pool),
            objective_score=None,
            blockers=("cp_sat_selection_infeasible",),
        )
    selected_ids = tuple(
        pool[index].id
        for index, variable in enumerate(selected)
        if solver.Value(variable)
    )
    return CpSatSelectionResult(
        available=True,
        selected_ids=selected_ids,
        status=solver.StatusName(status),
        candidate_count=len(pool),
        objective_score=int(solver.ObjectiveValue()),
    )


def optimize_order_with_cp_sat(
    places: list[Place],
    origin: tuple[float, float],
    travel_from_origin: Callable[[tuple[float, float], Place], int],
    travel_between: Callable[[Place, Place], int],
    *,
    max_places: int = 10,
) -> CpSatOrderResult:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return CpSatOrderResult(
            available=False,
            ordered_ids=(),
            status="ortools_missing",
            candidate_count=0,
            objective_travel_minutes=None,
            blockers=("OR-Tools is not installed",),
        )
    pool = places[:max_places]
    n = len(pool)
    if n <= 1:
        return CpSatOrderResult(True, tuple(place.id for place in pool), "trivial", n, 0)

    model = cp_model.CpModel()
    at = [[model.NewBoolVar(f"place_{i}_pos_{p}") for p in range(n)] for i in range(n)]
    for i in range(n):
        model.Add(sum(at[i][p] for p in range(n)) == 1)
    for p in range(n):
        model.Add(sum(at[i][p] for i in range(n)) == 1)

    objective_terms = []
    for i, place in enumerate(pool):
        objective_terms.append(at[i][0] * max(0, travel_from_origin(origin, place)))
    for p in range(n - 1):
        for i, left in enumerate(pool):
            for j, right in enumerate(pool):
                if i == j:
                    continue
                adjacent = model.NewBoolVar(f"edge_{p}_{i}_{j}")
                model.Add(adjacent <= at[i][p])
                model.Add(adjacent <= at[j][p + 1])
                model.Add(adjacent >= at[i][p] + at[j][p + 1] - 1)
                objective_terms.append(adjacent * max(0, travel_between(left, right)))
    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1.0
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return CpSatOrderResult(
            available=True,
            ordered_ids=(),
            status=solver.StatusName(status),
            candidate_count=n,
            objective_travel_minutes=None,
            blockers=("cp_sat_order_infeasible",),
        )
    ordered: list[Place] = []
    for p in range(n):
        for i, place in enumerate(pool):
            if solver.Value(at[i][p]):
                ordered.append(place)
                break
    return CpSatOrderResult(
        available=True,
        ordered_ids=tuple(place.id for place in ordered),
        status=solver.StatusName(status),
        candidate_count=n,
        objective_travel_minutes=int(solver.ObjectiveValue()),
    )


def optimize_day_schedule_with_cp_sat(
    candidates: list[Place],
    day_start_minute: int,
    day_end_minute: int,
    durations: dict[str, int],
    scores: dict[str, int],
    travel_between: Callable[[Place, Place], int],
    *,
    min_places: int,
    max_places: int,
    budget_per_person: int,
    max_candidates: int = 50,
) -> CpSatDayScheduleResult:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return CpSatDayScheduleResult(
            available=False,
            feasible=False,
            status="ortools_missing",
            selected_ids=(),
            starts={},
            objective_score=None,
            candidate_count=0,
            blockers=("OR-Tools is not installed",),
        )
    pool = candidates[:max_candidates]
    n = len(pool)
    if min_places <= 0 or max_places <= 0:
        return CpSatDayScheduleResult(True, True, "empty_request", (), {}, 0, n)
    if n < min_places:
        return CpSatDayScheduleResult(
            True,
            False,
            "insufficient_candidates",
            (),
            {},
            None,
            n,
            ("insufficient_candidates",),
        )

    model = cp_model.CpModel()
    selected = [model.NewBoolVar(f"select_{index}") for index in range(n)]
    starts = [
        model.NewIntVar(day_start_minute, day_end_minute, f"start_{index}")
        for index in range(n)
    ]
    ends = [
        model.NewIntVar(day_start_minute, day_end_minute, f"end_{index}")
        for index in range(n)
    ]

    model.Add(sum(selected) >= min_places)
    model.Add(sum(selected) <= min(max_places, n))
    model.Add(sum(selected[index] * max(0, pool[index].cost) for index in range(n)) <= budget_per_person)
    for index, place in enumerate(pool):
        duration = max(1, int(durations.get(place.id, place.duration_min or 60)))
        open_minute = max(day_start_minute, place.open_hour * 60)
        close_minute = min(day_end_minute, place.close_hour * 60)
        model.Add(starts[index] >= open_minute).OnlyEnforceIf(selected[index])
        model.Add(ends[index] == starts[index] + duration).OnlyEnforceIf(selected[index])
        model.Add(ends[index] <= close_minute).OnlyEnforceIf(selected[index])
        model.Add(starts[index] == day_start_minute).OnlyEnforceIf(selected[index].Not())
        model.Add(ends[index] == day_start_minute).OnlyEnforceIf(selected[index].Not())

    horizon = max(1, day_end_minute - day_start_minute + 24 * 60)
    for left_index, left in enumerate(pool):
        for right_index, right in enumerate(pool):
            if left_index >= right_index:
                continue
            left_before = model.NewBoolVar(f"before_{left_index}_{right_index}")
            right_before = model.NewBoolVar(f"before_{right_index}_{left_index}")
            both = model.NewBoolVar(f"both_{left_index}_{right_index}")
            model.AddBoolAnd([selected[left_index], selected[right_index]]).OnlyEnforceIf(both)
            model.AddBoolOr([selected[left_index].Not(), selected[right_index].Not()]).OnlyEnforceIf(both.Not())
            model.Add(left_before + right_before == 1).OnlyEnforceIf(both)
            model.Add(left_before == 0).OnlyEnforceIf(both.Not())
            model.Add(right_before == 0).OnlyEnforceIf(both.Not())
            model.Add(
                starts[right_index] >= ends[left_index] + max(0, travel_between(left, right)) - horizon * (1 - left_before)
            )
            model.Add(
                starts[left_index] >= ends[right_index] + max(0, travel_between(right, left)) - horizon * (1 - right_before)
            )

    objective = sum(selected[index] * max(0, int(scores.get(pool[index].id, 0))) for index in range(n))
    objective -= sum(starts[index] for index in range(n))
    model.Maximize(objective)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 2.0
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return CpSatDayScheduleResult(
            True,
            False,
            solver.StatusName(status),
            (),
            {},
            None,
            n,
            ("cp_sat_day_schedule_infeasible",),
        )
    chosen = [
        (pool[index], solver.Value(starts[index]))
        for index in range(n)
        if solver.Value(selected[index])
    ]
    chosen.sort(key=lambda item: (item[1], item[0].id))
    return CpSatDayScheduleResult(
        True,
        True,
        solver.StatusName(status),
        tuple(place.id for place, _start in chosen),
        {place.id: start for place, start in chosen},
        int(solver.ObjectiveValue()),
        n,
    )


def verify_fixed_schedule_with_cp_sat(
    plan: dict,
    by_id: dict[str, Place],
    travel_minutes: Callable[[Place, Place], int],
) -> CpSatScheduleResult:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return CpSatScheduleResult(
            available=False,
            feasible=False,
            status="ortools_missing",
            checked_slots=0,
            objective_minutes=None,
            blockers=("OR-Tools is not installed",),
        )

    model = cp_model.CpModel()
    starts: list[tuple[dict, Place, object, int, int]] = []
    blockers: list[str] = []
    for day in plan.get("ngay", []):
        day_slots = day.get("khoang_gio", [])
        previous: tuple[dict, Place, object, int, int] | None = None
        for slot in day_slots:
            place = by_id.get(slot.get("dia_diem_id"))
            if not place:
                blockers.append(f"missing_place:{slot.get('dia_diem_id')}")
                continue
            planned_start = _clock(slot["bat_dau"])
            planned_end = _clock(slot["ket_thuc"])
            duration = planned_end - planned_start
            if duration <= 0:
                blockers.append(f"invalid_duration:{place.id}")
                continue
            open_minute = place.open_hour * 60
            close_minute = place.close_hour * 60
            start = model.NewIntVar(planned_start, planned_start, f"start_{len(starts)}")
            end = model.NewIntVar(planned_end, planned_end, f"end_{len(starts)}")
            model.Add(end == start + duration)
            model.Add(start >= open_minute)
            model.Add(end <= close_minute)
            current = (slot, place, start, planned_start, planned_end)
            if previous:
                _, previous_place, _previous_start, _previous_planned_start, previous_planned_end = previous
                model.Add(start >= previous_planned_end + travel_minutes(previous_place, place))
            starts.append(current)
            previous = current

    if blockers:
        return CpSatScheduleResult(
            available=True,
            feasible=False,
            status="input_invalid",
            checked_slots=len(starts),
            objective_minutes=None,
            blockers=tuple(blockers),
        )
    if not starts:
        return CpSatScheduleResult(
            available=True,
            feasible=False,
            status="empty_schedule",
            checked_slots=0,
            objective_minutes=None,
            blockers=("empty_schedule",),
        )
    scheduled_minutes = sum(end - start for _slot, _place, _var, start, end in starts)
    model.Minimize(sum(var for _slot, _place, var, _start, _end in starts))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1.0
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return CpSatScheduleResult(
        available=True,
        feasible=feasible,
        status=solver.StatusName(status),
        checked_slots=len(starts),
        objective_minutes=scheduled_minutes if feasible else None,
        blockers=() if feasible else ("cp_sat_infeasible",),
    )
