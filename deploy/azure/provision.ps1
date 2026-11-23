param(
    [string]$ResourceGroup = 'rg-rescate360',
    [string]$Location = 'westus2',
    [string]$AcrName = 'acrrescate360',
    [string]$PostgresName = 'psql-rescate360',
    [string]$StorageAccountName = 'strescate360',
    [string]$ContainerName = 'evidencias',
    [string]$EnvironmentName = 'env-rescate360',
    [string]$DatabaseName = 'rescate360',
    [string]$AdminUser = 'rescateadmin',
    [string]$AdminPassword = ''
)

$ErrorActionPreference = 'Stop'
$env:AZURE_CORE_ONLY_SHOW_ERRORS = 'true'

az account show -o none
if (-not $AdminPassword) {
    $AdminPassword = 'Rc' + [guid]::NewGuid().ToString('N') + '!'
}

az group create -n $ResourceGroup -l $Location -o none
az acr create -n $AcrName -g $ResourceGroup --sku Standard --admin-enabled true -o none

az postgres flexible-server create `
    -n $PostgresName -g $ResourceGroup -l $Location `
    --admin-user $AdminUser --admin-password $AdminPassword `
    --sku-name B1ms --storage-size 32 --version 16 `
    --public-access 0.0.0.0 -o none

az postgres flexible-server parameter set `
    -g $ResourceGroup -s $PostgresName --name azure.extensions --value POSTGIS,UNACCENT -o none

az postgres flexible-server db create `
    -g $ResourceGroup -s $PostgresName -d $DatabaseName -o none

az postgres flexible-server firewall-rule create `
    -g $ResourceGroup -s $PostgresName -n AllowAzure `
    --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 -o none

az storage account create `
    -n $StorageAccountName -g $ResourceGroup -l $Location `
    --sku Standard_LRS --kind StorageV2 -o none

az storage account update `
    -n $StorageAccountName -g $ResourceGroup --allow-blob-public-access true -o none

az storage container create `
    -n $ContainerName --account-name $StorageAccountName --public-access blob -o none

$connectionString = az storage account show-connection-string `
    -n $StorageAccountName -g $ResourceGroup --query connectionString -o tsv
$databaseUrl = 'postgresql+psycopg2://{0}:{1}@{2}.postgres.database.azure.com:5432/{3}?sslmode=require' -f `
    $AdminUser, [uri]::EscapeDataString($AdminPassword), $PostgresName, $DatabaseName

az containerapp env create `
    -n $EnvironmentName -g $ResourceGroup -l $Location -o none

$envFile = Join-Path (Get-Location) '.env.azure'
@"
DATABASE_URL=$databaseUrl
JWT_SECRET=$([guid]::NewGuid().ToString('N'))$([guid]::NewGuid().ToString('N'))
STORAGE_BUCKET=$ContainerName
AZURE_STORAGE_ACCOUNT_NAME=$StorageAccountName
AZURE_STORAGE_CONNECTION_STRING=$connectionString
"@ | Set-Content -LiteralPath $envFile -Encoding utf8

Write-Host "Recursos creados. Secretos en $envFile (no subir al repo)."
Write-Host 'Añade tu IP al firewall si necesitas ejecutar Alembic o el script de migración desde tu PC:'
Write-Host "az postgres flexible-server firewall-rule create -g $ResourceGroup -s $PostgresName -n AllowMiIP --start-ip-address <TU_IP> --end-ip-address <TU_IP>"
