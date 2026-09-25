[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string] $Notebook,

    [ValidateRange(1, 86400)]
    [int] $TimeoutSeconds = 900
)

$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$notebookPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Notebook))
$repoPrefix = $repoRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar

if (-not $notebookPath.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Notebook must be inside the repository: $repoRoot"
}
if (-not (Test-Path -LiteralPath $notebookPath -PathType Leaf)) {
    throw "Notebook not found: $notebookPath"
}
if ([System.IO.Path]::GetExtension($notebookPath) -ne '.ipynb') {
    throw "Expected an .ipynb file: $notebookPath"
}

$notebookDirectory = [System.IO.Path]::GetDirectoryName($notebookPath)
$notebookBaseName = [System.IO.Path]::GetFileNameWithoutExtension($notebookPath)
$scratchRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("pier-cap-stm-jupyter-" + [guid]::NewGuid().ToString('N'))
$runtimeDirectory = Join-Path $scratchRoot 'runtime'
$ipythonDirectory = Join-Path $scratchRoot 'ipython'
$jupyterDataDirectory = Join-Path $scratchRoot 'data'
$matplotlibDirectory = Join-Path $scratchRoot 'matplotlib'

$savedEnvironment = @{
    JUPYTER_RUNTIME_DIR = $env:JUPYTER_RUNTIME_DIR
    JUPYTER_DATA_DIR = $env:JUPYTER_DATA_DIR
    IPYTHONDIR = $env:IPYTHONDIR
    MPLCONFIGDIR = $env:MPLCONFIGDIR
    PYTHONPATH = $env:PYTHONPATH
}

try {
    New-Item -ItemType Directory -Path $runtimeDirectory, $ipythonDirectory, $jupyterDataDirectory, $matplotlibDirectory -Force | Out-Null
    $env:JUPYTER_RUNTIME_DIR = $runtimeDirectory
    $env:JUPYTER_DATA_DIR = $jupyterDataDirectory
    $env:IPYTHONDIR = $ipythonDirectory
    $env:MPLCONFIGDIR = $matplotlibDirectory
    $env:PYTHONPATH = if ($savedEnvironment.PYTHONPATH) { "$repoRoot$([System.IO.Path]::PathSeparator)$($savedEnvironment.PYTHONPATH)" } else { $repoRoot }

    Push-Location $repoRoot
    try {
        & python -m jupyter nbconvert --to notebook --execute --inplace `
            "--ExecutePreprocessor.timeout=$TimeoutSeconds" `
            $notebookPath
        if ($LASTEXITCODE -ne 0) {
            throw "Notebook execution failed with exit code $LASTEXITCODE"
        }

        & python -m jupyter nbconvert --to html `
            --output $notebookBaseName `
            --output-dir $notebookDirectory `
            $notebookPath
        if ($LASTEXITCODE -ne 0) {
            throw "HTML export failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }

    Write-Host "Executed notebook: $notebookPath"
    Write-Host "Exported HTML: $(Join-Path $notebookDirectory ($notebookBaseName + '.html'))"
}
finally {
    $env:JUPYTER_RUNTIME_DIR = $savedEnvironment.JUPYTER_RUNTIME_DIR
    $env:JUPYTER_DATA_DIR = $savedEnvironment.JUPYTER_DATA_DIR
    $env:IPYTHONDIR = $savedEnvironment.IPYTHONDIR
    $env:MPLCONFIGDIR = $savedEnvironment.MPLCONFIGDIR
    $env:PYTHONPATH = $savedEnvironment.PYTHONPATH

    if (Test-Path -LiteralPath $scratchRoot) {
        $resolvedScratch = [System.IO.Path]::GetFullPath($scratchRoot)
        $tempPrefix = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
        if (-not $resolvedScratch.StartsWith($tempPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove scratch directory outside system temp: $resolvedScratch"
        }
        Remove-Item -LiteralPath $resolvedScratch -Recurse -Force
    }
}
