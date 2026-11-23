param(
    [string]$ResourceGroup = 'rg-rescate360',
    [string]$AppName = 'rescate360-api'
)

$ErrorActionPreference = 'Stop'
$env:AZURE_CORE_ONLY_SHOW_ERRORS = 'true'

az account show -o none

az containerapp update -n $AppName -g $ResourceGroup --min-replicas 0 --max-replicas 1 -o none

Write-Host 'API en scale-to-zero. La réplica puede tardar unos minutos en desaparecer.'
Write-Host 'PostgreSQL sigue encendido, dentro del free tier de 750 h/mes.'
