"""STM-TrussSolver: BESO topology optimization for strut-and-tie model generation."""

from stm_solver.config import build_config, load_config, save_config, unpack_config
from stm_solver.ground_structure import (
    ExternalFace,
    build_pier_cap_external_faces,
    find_member_crossings,
    optimize_pier_cap,
    optimize_pier_cap_load_cases,
)
from stm_solver.pier_cap import (
    BearingLoad,
    FoundationSupport,
    LoadCombination,
    LoadComponent,
    LoadPointForce,
    PierCapGeometry,
    PierCapLoadSet,
    PierCapModel,
    load_pier_cap_model,
    save_pier_cap_model,
)
from stm_solver.versioning import TOOL_VERSION as __version__

__all__ = [
    "build_config",
    "build_pier_cap_external_faces",
    "BearingLoad",
    "ExternalFace",
    "find_member_crossings",
    "FoundationSupport",
    "LoadCombination",
    "LoadComponent",
    "LoadPointForce",
    "load_config",
    "optimize_pier_cap",
    "optimize_pier_cap_load_cases",
    "PierCapGeometry",
    "PierCapLoadSet",
    "PierCapModel",
    "load_pier_cap_model",
    "save_pier_cap_model",
    "save_config",
    "unpack_config",
    "__version__",
]
