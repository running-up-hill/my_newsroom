# Back up newsroom databases to dated files under backups\<name>\ (keep backups\ out of git).
#   .\backup.ps1                  back up every newsroom: yours, plus each folder in instances\
#   .\backup.ps1 -Instance <name>   back up just one ('mine' is your own newsroom)
# Needs Docker running and the newsroom-mcp image built. Safe while the collector is running.
# If scripts are blocked, use backup.cmd instead.
param([string]$Instance = '')

Set-Location $PSScriptRoot
$stamp = Get-Date -Format 'yyyy-MM-dd_HHmm'
$keep = 14                                   # newest backups to keep per newsroom
$helper = Join-Path $PSScriptRoot 'tools\backup_db.py'
if (-not (Test-Path $helper)) { Write-Error "Missing $helper"; exit 1 }

# newsroom name -> docker volume that holds its database
$targets = [ordered]@{}
if ($Instance -eq '' -or $Instance -eq 'mine') {
    $targets['mine'] = (Split-Path $PSScriptRoot -Leaf).ToLower() + '_news-data'
}
if ($Instance -eq '') {
    Get-ChildItem 'instances' -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $targets[$_.Name] = "$($_.Name)_news-data"
    }
} elseif ($Instance -ne 'mine') {
    $targets[$Instance] = "${Instance}_news-data"
}

$failed = 0
foreach ($name in $targets.Keys) {
    $volume = $targets[$name]
    docker volume inspect $volume *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[$name] skipped: Docker volume '$volume' not found (not started yet?)"
        continue
    }

    $dir = Join-Path $PSScriptRoot "backups\$name"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $dest = Join-Path $dir "news-$stamp.db"
    $container = "nr-backup-$name"

    docker rm -f $container *> $null
    # Make the copy inside a throwaway container, then copy the file out to Windows.
    docker run --name $container -v "${volume}:/data" -v "${helper}:/backup_db.py:ro" newsroom-mcp python /backup_db.py /data/news.db /tmp/backup.db
    $ok = ($LASTEXITCODE -eq 0)
    if ($ok) {
        docker cp "${container}:/tmp/backup.db" $dest
        $ok = ($LASTEXITCODE -eq 0)
    }
    docker rm -f $container *> $null

    if ($ok) {
        Write-Host "[$name] saved $dest"
        Get-ChildItem $dir -Filter 'news-*.db' | Sort-Object Name -Descending |
            Select-Object -Skip $keep | Remove-Item
    } else {
        Write-Warning "[$name] backup FAILED, nothing was saved"
        $failed++
    }
}
if ($failed -gt 0) { exit 1 }
