"""TOML configuration file support for STM analysis parameters."""

import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        raise ImportError(
            "Python <3.11 requires 'tomli' for TOML support. "
            "Install with: pip install tomli"
        )

try:
    import tomli_w
except ImportError:
    tomli_w = None


_REQUIRED_SECTIONS = {"geometry", "material", "supports", "loads", "mesh", "beso"}

_GEOMETRY_KEYS = {"L", "h", "b"}
_MATERIAL_KEYS = {"E", "nu"}
_MESH_KEYS = {"max_edge", "max_AR"}
_BESO_KEYS = {"volfrac", "ER", "r_min", "max_iter", "tol", "Emin"}


def validate_config(config):
    """Validate a configuration dict has all required sections and keys."""
    missing = _REQUIRED_SECTIONS - set(config.keys())
    if missing:
        raise ValueError(f"Missing config sections: {missing}")

    geo = config["geometry"]
    missing_geo = _GEOMETRY_KEYS - set(geo.keys())
    if missing_geo:
        raise ValueError(f"Missing geometry keys: {missing_geo}")
    for k in ("L", "h", "b"):
        if geo[k] <= 0:
            raise ValueError(f"geometry.{k} must be positive, got {geo[k]}")

    mat = config["material"]
    missing_mat = _MATERIAL_KEYS - set(mat.keys())
    if missing_mat:
        raise ValueError(f"Missing material keys: {missing_mat}")
    if mat["E"] <= 0:
        raise ValueError(f"material.E must be positive, got {mat['E']}")

    if not isinstance(config["supports"], list) or len(config["supports"]) < 1:
        raise ValueError("At least one support is required")
    for i, support in enumerate(config["supports"]):
        for key in ("x", "y", "type"):
            if key not in support:
                raise ValueError(f"Support {i} missing key '{key}'")

    if not isinstance(config["loads"], list) or len(config["loads"]) < 1:
        raise ValueError("At least one load is required")
    for i, load in enumerate(config["loads"]):
        for key in ("x", "y", "Px", "Py"):
            if key not in load:
                raise ValueError(f"Load {i} missing key '{key}'")

    mesh = config["mesh"]
    missing_mesh = _MESH_KEYS - set(mesh.keys())
    if missing_mesh:
        raise ValueError(f"Missing mesh keys: {missing_mesh}")

    beso = config["beso"]
    missing_beso = _BESO_KEYS - set(beso.keys())
    if missing_beso:
        raise ValueError(f"Missing beso keys: {missing_beso}")


def load_config(path):
    """Load and validate an analysis configuration from a TOML file."""
    with open(path, "rb") as file:
        config = tomllib.load(file)
    validate_config(config)
    return config


def save_config(config, path):
    """Validate and save an analysis configuration to a TOML file."""
    if tomli_w is None:
        raise ImportError(
            "'tomli-w' is required to save TOML files. Install with: pip install tomli-w"
        )
    validate_config(config)
    with open(path, "wb") as file:
        tomli_w.dump(config, file)


def build_config(
    *, L, h, b, E, nu, supports, loads, max_edge, max_AR,
    volfrac, ER, r_min, max_iter, tol, Emin
):
    """Build and validate a configuration dict from individual parameters."""
    config = {
        "geometry": {"L": float(L), "h": float(h), "b": float(b)},
        "material": {"E": float(E), "nu": float(nu)},
        "supports": [
            {"x": float(s["x"]), "y": float(s["y"]), "type": s["type"]}
            for s in supports
        ],
        "loads": [
            {
                "x": float(load["x"]),
                "y": float(load["y"]),
                "Px": float(load["Px"]),
                "Py": float(load["Py"]),
            }
            for load in loads
        ],
        "mesh": {"max_edge": float(max_edge), "max_AR": float(max_AR)},
        "beso": {
            "volfrac": float(volfrac),
            "ER": float(ER),
            "r_min": float(r_min),
            "max_iter": int(max_iter),
            "tol": float(tol),
            "Emin": float(Emin),
        },
    }
    validate_config(config)
    return config


def unpack_config(config):
    """Flatten a configuration dict into individual analysis parameters."""
    flat = {}
    flat.update(config["geometry"])
    flat.update(config["material"])
    flat["supports"] = config["supports"]
    flat["loads"] = config["loads"]
    flat.update(config["mesh"])
    flat.update(config["beso"])
    return flat
