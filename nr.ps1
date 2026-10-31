# Run docker compose for a named newsroom instance.
#   .\nr.ps1 <name> up -d --build
#   .\nr.ps1 <name> logs collector --tail 20
#   .\nr.ps1 <name> down
#   .\nr.ps1 mine ps        ('mine' is your own newsroom: plain docker compose, exactly as before)
# Each instance gets its own containers and its own database volume (<name>_news-data).
# Note: no param() block on purpose, so options like -d are passed to docker instead of PowerShell.

if ($args.Count -lt 2) {
    Write-Host "Usage: .\nr.ps1 <instance> <docker compose command...>   e.g.  .\nr.ps1 <name> up -d --build"
    exit 1
}
Set-Location $PSScriptRoot
$Instance = $args[0]
$ComposeArgs = $args[1..($args.Count - 1)]

if ($Instance -eq 'mine') {
    docker compose @ComposeArgs
} else {
    $envFile = "instances/$Instance/.env"
    if (-not (Test-Path $envFile)) {
        Write-Error "Missing $envFile - create the instance folder first."
        exit 1
    }
    docker compose -p $Instance --env-file $envFile @ComposeArgs
}
