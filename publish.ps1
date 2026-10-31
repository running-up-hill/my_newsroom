# Publish a generated page: commit and push it if anything changed.
#   .\publish.ps1               your own newsroom (the docs folder in this repo)
#   .\publish.ps1 -Instance <name>    that instance's page (its own git repo in instances\<name>\pages)
# If scripts are blocked, run it as:  powershell -ExecutionPolicy Bypass -File .\publish.ps1 -Instance <name>
param([string]$Instance = 'mine')

if ($Instance -eq 'mine') {
    Set-Location $PSScriptRoot
    $target = 'docs'
} else {
    $pages = Join-Path $PSScriptRoot "instances/$Instance/pages"
    if (-not (Test-Path (Join-Path $pages '.git'))) {
        Write-Error "$pages is not a git repository yet - follow the setup steps for this instance first."
        exit 1
    }
    Set-Location $pages
    $target = '.'
}

git add $target
if (git status --porcelain $target) {
    git commit -m "Update digests $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    git push
    Write-Host "Published. GitHub Pages usually updates within a minute or two."
} else {
    Write-Host "Nothing new to publish."
}
