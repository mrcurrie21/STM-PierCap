"""Typed pier-cap inputs, persistence, and analysis orchestration."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


def _positive_finite(value, name):
    value = float(value)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be a positive finite value")
    return value


def _finite(value, name):
    value = float(value)
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True)
class PierCapGeometry:
    """Longitudinal geometry and reinforcement centrelines, in inches."""

    depth: float
    top_tie_y: float
    bottom_tie_y: float
    length: float = None
    width: float = None

    def __post_init__(self):
        depth = _positive_finite(self.depth, "depth")
        top = _finite(self.top_tie_y, "top_tie_y")
        bottom = _finite(self.bottom_tie_y, "bottom_tie_y")
        if not 0.0 <= bottom < top <= depth:
            raise ValueError("Require 0 <= bottom_tie_y < top_tie_y <= depth")
        if self.length is not None:
            _positive_finite(self.length, "length")
        if self.width is not None:
            _positive_finite(self.width, "width")

    def contains(self, x, y):
        """Return whether a longitudinal point lies inside the cap envelope."""
        x = _finite(x, "x")
        y = _finite(y, "y")
        return (
            0.0 <= y <= self.depth
            and (self.length is None or 0.0 <= x <= self.length)
        )


@dataclass(frozen=True)
class LoadPointForce:
    """Force contribution at a stable physical load-point ID."""

    id: str
    x: float
    y: float
    py: float
    px: float = 0.0

    def __post_init__(self):
        if not str(self.id).strip():
            raise ValueError("LoadPointForce.id must be nonempty")
        _finite(self.x, "LoadPointForce.x")
        _finite(self.y, "LoadPointForce.y")
        _finite(self.px, "LoadPointForce.px")
        _finite(self.py, "LoadPointForce.py")


@dataclass(frozen=True)
class LoadComponent:
    """Named collection of compatible load-point force contributions."""

    name: str
    loads: tuple

    def __post_init__(self):
        object.__setattr__(self, "loads", tuple(self.loads))
        if not str(self.name).strip():
            raise ValueError("LoadComponent.name must be nonempty")
        if not self.loads:
            raise ValueError("LoadComponent requires at least one load")
        if not all(isinstance(item, LoadPointForce) for item in self.loads):
            raise TypeError("LoadComponent.loads must contain LoadPointForce objects")
        identifiers = [item.id for item in self.loads]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(f"Duplicate load-point ID in component {self.name}")


@dataclass(frozen=True)
class LoadCombination:
    """Named factors applied to load components."""

    name: str
    factors: dict

    def __post_init__(self):
        if not str(self.name).strip():
            raise ValueError("LoadCombination.name must be nonempty")
        if not self.factors:
            raise ValueError("LoadCombination requires at least one factor")
        for component, factor in self.factors.items():
            if not str(component).strip():
                raise ValueError("LoadCombination component names must be nonempty")
            _finite(factor, f"LoadCombination factor for {component}")


class PierCapLoadSet:
    """Validated components and combinations sharing stable load-point geometry."""

    def __init__(self, components, combinations, face_widths):
        self.components = tuple(components)
        self.combinations = tuple(combinations)
        self.face_widths = dict(face_widths)
        if not self.components or not self.combinations:
            raise ValueError("At least one load component and combination are required")
        if not all(isinstance(item, LoadComponent) for item in self.components):
            raise TypeError("components must contain LoadComponent objects")
        if not all(isinstance(item, LoadCombination) for item in self.combinations):
            raise TypeError("combinations must contain LoadCombination objects")
        component_names = [item.name for item in self.components]
        combination_names = [item.name for item in self.combinations]
        if len(set(component_names)) != len(component_names):
            raise ValueError("Load component names must be unique")
        if len(set(combination_names)) != len(combination_names):
            raise ValueError("Load combination names must be unique")
        known_components = set(component_names)
        for combination in self.combinations:
            unknown = set(combination.factors) - known_components
            if unknown:
                raise ValueError(
                    f"Combination {combination.name} uses unknown components "
                    f"{sorted(unknown)}"
                )
        locations = {}
        for component in self.components:
            for load in component.loads:
                location = (float(load.x), float(load.y))
                if load.id in locations and locations[load.id] != location:
                    raise ValueError(
                        f"Load point {load.id} changes location between components"
                    )
                locations[load.id] = location
        missing_widths = set(locations) - set(self.face_widths)
        extra_widths = set(self.face_widths) - set(locations)
        if missing_widths or extra_widths:
            raise ValueError(
                f"face_widths must match load points; missing={sorted(missing_widths)}, "
                f"extra={sorted(extra_widths)}"
            )
        for load_id, width in self.face_widths.items():
            _positive_finite(width, f"face width for {load_id}")
        self._locations = locations

    def assemble(self, combination_name):
        """Assemble a combination into finite-face bearing resultants."""
        combination = next(
            (item for item in self.combinations if item.name == combination_name), None
        )
        if combination is None:
            raise KeyError(f"Unknown load combination: {combination_name}")
        component_map = {item.name: item for item in self.components}
        totals = {}
        for component_name, factor in combination.factors.items():
            for load in component_map[component_name].loads:
                force = totals.setdefault(load.id, [0.0, 0.0])
                force[0] += float(factor) * float(load.px)
                force[1] += float(factor) * float(load.py)
        return tuple(
            BearingLoad(
                load_id, *self._locations[load_id], totals[load_id][1],
                self.face_widths[load_id], px=totals[load_id][0],
            )
            for load_id in sorted(totals)
        )

    def assemble_all(self):
        return {item.name: self.assemble(item.name) for item in self.combinations}

    def validate_envelope(self, geometry):
        outside = [
            load_id for load_id, (x, y) in self._locations.items()
            if not geometry.contains(x, y)
        ]
        if outside:
            raise ValueError(f"Load points outside the cap envelope: {outside}")


@dataclass(frozen=True)
class BearingLoad:
    """Applied resultant at the centroid of a finite bearing face."""

    id: str
    x: float
    y: float
    py: float
    face_width: float
    px: float = 0.0

    def __post_init__(self):
        if not str(self.id).strip():
            raise ValueError("BearingLoad.id must be nonempty")
        _finite(self.x, "BearingLoad.x")
        _finite(self.y, "BearingLoad.y")
        _finite(self.px, "BearingLoad.px")
        _finite(self.py, "BearingLoad.py")
        _positive_finite(self.face_width, "BearingLoad.face_width")

    def to_solver_dict(self):
        return {
            "id": self.id, "x": float(self.x), "y": float(self.y),
            "Px": float(self.px), "Py": float(self.py),
            "face_width": float(self.face_width),
        }


@dataclass(frozen=True)
class FoundationSupport:
    """Pile or shaft resultant and its finite cap-contact face."""

    id: str
    x: float
    y: float
    face_width: float
    restraint: str = "roller"
    foundation_type: str = "pile"

    def __post_init__(self):
        if not str(self.id).strip():
            raise ValueError("FoundationSupport.id must be nonempty")
        _finite(self.x, "FoundationSupport.x")
        _finite(self.y, "FoundationSupport.y")
        _positive_finite(self.face_width, "FoundationSupport.face_width")
        if self.restraint.lower() not in ("pin", "fixed", "roller"):
            raise ValueError("restraint must be 'pin', 'fixed', or 'roller'")
        if self.foundation_type.lower() not in ("pile", "shaft"):
            raise ValueError("foundation_type must be 'pile' or 'shaft'")

    def to_solver_dict(self):
        return {
            "id": self.id, "x": float(self.x), "y": float(self.y),
            "face_width": float(self.face_width), "type": self.restraint.lower(),
            "foundation_type": self.foundation_type.lower(),
        }


@dataclass(frozen=True)
class PierCapModel:
    """Validated input model for one pier-cap load case."""

    geometry: PierCapGeometry
    loads: tuple
    supports: tuple
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "loads", tuple(self.loads))
        object.__setattr__(self, "supports", tuple(self.supports))
        if not self.loads:
            raise ValueError("PierCapModel requires at least one bearing load")
        if not self.supports:
            raise ValueError("PierCapModel requires at least one foundation support")
        if not all(isinstance(item, BearingLoad) for item in self.loads):
            raise TypeError("loads must contain BearingLoad objects")
        if not all(isinstance(item, FoundationSupport) for item in self.supports):
            raise TypeError("supports must contain FoundationSupport objects")
        identifiers = [item.id for item in self.loads] + [item.id for item in self.supports]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Load and support IDs must be unique")
        load_locations = [(float(item.x), float(item.y)) for item in self.loads]
        support_locations = [(float(item.x), float(item.y)) for item in self.supports]
        if len(set(load_locations)) != len(load_locations):
            raise ValueError("Bearing load locations must be unique")
        if len(set(support_locations)) != len(support_locations):
            raise ValueError("Foundation support locations must be unique")
        outside = [
            item.id for item in self.loads + self.supports
            if not self.geometry.contains(item.x, item.y)
        ]
        if outside:
            raise ValueError(f"Loads or supports outside the cap envelope: {outside}")
        if self.geometry.length is not None:
            faces_outside = [
                item.id for item in self.loads + self.supports
                if item.x - 0.5 * item.face_width < 0.0
                or item.x + 0.5 * item.face_width > self.geometry.length
            ]
            if faces_outside:
                raise ValueError(
                    f"Finite external faces extend outside the cap: {faces_outside}"
                )

    def to_solver_inputs(self):
        """Return compatibility dictionaries for the ground-structure solver."""
        return (
            [item.to_solver_dict() for item in self.loads],
            [item.to_solver_dict() for item in self.supports],
        )

    def solve(self, **options):
        """Run the current ground-structure solver from validated inputs."""
        from .ground_structure import optimize_pier_cap

        loads, supports = self.to_solver_inputs()
        options.setdefault("top_tie_y", self.geometry.top_tie_y)
        options.setdefault("bottom_tie_y", self.geometry.bottom_tie_y)
        return optimize_pier_cap(loads, supports, **options)

    def input_records(self):
        """Return stable tabular records suitable for DataFrames or export."""
        return {
            "loads": [item.to_solver_dict() for item in self.loads],
            "supports": [item.to_solver_dict() for item in self.supports],
            "geometry": [{
                "depth": self.geometry.depth,
                "top_tie_y": self.geometry.top_tie_y,
                "bottom_tie_y": self.geometry.bottom_tie_y,
                "length": self.geometry.length,
                "width": self.geometry.width,
            }],
        }

    def to_dict(self):
        """Return a JSON-serializable representation of one analysis case."""
        loads, supports = self.to_solver_inputs()
        return {
            "schema_version": 1,
            "geometry": {
                "depth": self.geometry.depth,
                "top_tie_y": self.geometry.top_tie_y,
                "bottom_tie_y": self.geometry.bottom_tie_y,
                "length": self.geometry.length,
                "width": self.geometry.width,
            },
            "loads": loads,
            "supports": supports,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data):
        """Construct a model from its versioned serialized representation."""
        if data.get("schema_version") != 1:
            raise ValueError("Unsupported pier-cap model schema_version")
        geometry = PierCapGeometry(**data["geometry"])
        loads = tuple(
            BearingLoad(
                item["id"], item["x"], item["y"], item["Py"],
                item["face_width"], px=item.get("Px", 0.0),
            )
            for item in data["loads"]
        )
        supports = tuple(
            FoundationSupport(
                item["id"], item["x"], item["y"], item["face_width"],
                restraint=item.get("type", "roller"),
                foundation_type=item.get("foundation_type", "pile"),
            )
            for item in data["supports"]
        )
        return cls(geometry, loads, supports, metadata=data.get("metadata", {}))


def save_pier_cap_model(model, path):
    """Write a versioned pier-cap model JSON file."""
    if not isinstance(model, PierCapModel):
        raise TypeError("model must be a PierCapModel")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(model.to_dict(), stream, indent=2, sort_keys=True)
        stream.write("\n")


def load_pier_cap_model(path):
    """Read and validate a versioned pier-cap model JSON file."""
    with Path(path).open(encoding="utf-8") as stream:
        return PierCapModel.from_dict(json.load(stream))
