param(
    [string]$ResourceGroup = 'rg-rescate360',
    [string]$AppName = 'rescate360-api'
)

$ErrorActionPreference = 'Stop'
$env:AZURE_CORE_ONLY_SHOW_ERRORS = 'true'

az account show -o none

az containerapp update -n $AppName -g $ResourceGroup --min-replicas 1 --max-replicas 1 -o none

$fqdn = az containerapp show -n $AppName -g $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv
Write-Host "API encendida: https://$fqdn"
Write-Host 'Espera a que /health/ready devuelva ok antes de empezar la demo.'
