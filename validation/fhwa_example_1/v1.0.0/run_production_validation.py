"""Execute the FHWA copy of the production notebook from the repository root."""

import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
NOTEBOOK = PACKAGE / "fhwa_example_1_production_validation.ipynb"
HTML = PACKAGE / "fhwa_example_1_production_validation.html"
RUNTIME = PACKAGE / "runtime"
RUNTIME.mkdir(exist_ok=True)

# The managed Windows environment cannot apply Jupyter's normal ACL helper.
# Connection files remain inside this validation package's local runtime folder.
os.environ["JUPYTER_RUNTIME_DIR"] = str(RUNTIME)
os.environ["JUPYTER_ALLOW_INSECURE_WRITES"] = "1"

import nbformat  # noqa: E402
from nbclient import NotebookClient  # noqa: E402
from nbconvert import HTMLExporter  # noqa: E402
from nbconvert.writers import FilesWriter  # noqa: E402

document = nbformat.read(NOTEBOOK, as_version=4)
client = NotebookClient(
    document,
    timeout=600,
    kernel_name="python3",
    resources={"metadata": {"path": str(ROOT)}},
)
client.execute(cwd=str(ROOT))
nbformat.write(document, NOTEBOOK)

exporter = HTMLExporter(template_name="lab")
body, resources = exporter.from_notebook_node(document)
writer = FilesWriter(build_directory=str(PACKAGE))
writer.write(body, resources, notebook_name=HTML.stem)
print(NOTEBOOK)
print(HTML)
