# Pier Cap STM project instructions

- Treat `notebooks/pier_cap_design.ipynb` and `stm_solver/` as production code. Ask the user before changing production analysis behavior during validation work.
- Put durable validation inputs, executed notebooks, HTML reports, reference publications, and comparison results under the applicable `validation/<case>/v<version>/` folder.
- Run notebooks with `scripts/run_validation_notebook.ps1`; do not create notebook or PDF-rendering scratch folders in the repository.
- Use `SESSION_HANDOFF.md` for current project decisions and resumable state. Consult `TODO.md` when planning future work; do not read either file for unrelated, narrowly scoped edits.
- Keep generated caches and scratch artifacts out of Git. The ignored `tmp/`, `output/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`, and `pytest-cache-files-*/` paths are disposable.
- When validation identifies a possible production-analysis defect, document the evidence and ask the user before implementing a production change.
