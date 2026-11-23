param(
    [string]$ResourceGroup = 'rg-rescate360',
    [string]$Location = 'eastus',
    [string]$AcrName = 'acrrescate360',
    [string]$ImageName = 'rescate360-api',
    [string]$EnvironmentName = 'env-rescate360',
    [string]$AppName = 'rescate360-api'
)

$ErrorActionPreference = 'Stop'
$env:AZURE_CORE_ONLY_SHOW_ERRORS = 'true'

function Comprobar-ExitCode([string]$mensaje) {
    if ($LASTEXITCODE -ne 0) {
        throw $mensaje
    }
}

az account show -o none
Comprobar-ExitCode 'No se pudo autenticar con Azure. Ejecuta az login.'

$valores = @{}
$envFile = Join-Path (Get-Location) '.env.azure'
if (Test-Path -LiteralPath $envFile) {
    foreach ($linea in Get-Content -LiteralPath $envFile) {
        if ($linea -match '^\s*#' -or -not $linea.Trim()) {
            continue
        }
        $partes = $linea -split '=', 2
        if ($partes.Count -eq 2) {
            $valores[$partes[0].Trim()] = $partes[1].Trim()
        }
    }
}

function Obtener-Valor([string]$nombre, [string]$valorDelEntorno) {
    if ($valorDelEntorno) {
        return $valorDelEntorno
    }
    if ($valores.ContainsKey($nombre)) {
        return $valores[$nombre]
    }
    return ''
}

function Convertir-A-Json([string]$valor) {
    if ($null -eq $valor) {
        $valor = ''
    }
    return ($valor | ConvertTo-Json -Compress)
}

$databaseUrl = Obtener-Valor 'DATABASE_URL' $env:DATABASE_URL
$jwtSecret = Obtener-Valor 'JWT_SECRET' $env:JWT_SECRET
$storageBucket = Obtener-Valor 'STORAGE_BUCKET' $env:STORAGE_BUCKET
$storageConnection = Obtener-Valor 'AZURE_STORAGE_CONNECTION_STRING' $env:AZURE_STORAGE_CONNECTION_STRING
$storageAccount = Obtener-Valor 'AZURE_STORAGE_ACCOUNT_NAME' $env:AZURE_STORAGE_ACCOUNT_NAME
$cors = Obtener-Valor 'CORS_ORIGINS' $env:CORS_ORIGINS
if (-not $cors) {
    $cors = '[]'
}

$geminiApiKey = Obtener-Valor 'GEMINI_API_KEY' $env:GEMINI_API_KEY
$firebaseCredentialsPath = Obtener-Valor 'FIREBASE_CREDENTIALS_PATH' $env:FIREBASE_CREDENTIALS_PATH
$twilioAccountSid = Obtener-Valor 'TWILIO_ACCOUNT_SID' $env:TWILIO_ACCOUNT_SID
$twilioAuthToken = Obtener-Valor 'TWILIO_AUTH_TOKEN' $env:TWILIO_AUTH_TOKEN
$twilioFromNumber = Obtener-Valor 'TWILIO_FROM_NUMBER' $env:TWILIO_FROM_NUMBER

$opcionales = @(
    @{ EnvName = 'GEMINI_API_KEY'; SecretName = 'gemini-api-key'; Value = $geminiApiKey },
    @{ EnvName = 'FIREBASE_CREDENTIALS_PATH'; SecretName = 'firebase-credentials-path'; Value = $firebaseCredentialsPath },
    @{ EnvName = 'TWILIO_ACCOUNT_SID'; SecretName = 'twilio-account-sid'; Value = $twilioAccountSid },
    @{ EnvName = 'TWILIO_AUTH_TOKEN'; SecretName = 'twilio-auth-token'; Value = $twilioAuthToken },
    @{ EnvName = 'TWILIO_FROM_NUMBER'; SecretName = 'twilio-from-number'; Value = $twilioFromNumber }
)

$envOpcional = @()
$secretOpcional = @()
foreach ($opcional in $opcionales) {
    if ($opcional.Value) {
        $envOpcional += '          - name: {0}' -f $opcional.EnvName
        $envOpcional += '            secretRef: {0}' -f $opcional.SecretName
        $secretOpcional += '      - name: {0}' -f $opcional.SecretName
        $secretOpcional += '        value: {0}' -f (Convertir-A-Json $opcional.Value)
    }
}

if (-not $databaseUrl -or -not $jwtSecret -or -not $storageBucket -or -not $storageConnection -or -not $storageAccount) {
    throw 'Faltan secretos. Ejecuta provision.ps1 desde la raíz del backend o exporta DATABASE_URL, JWT_SECRET, STORAGE_BUCKET, AZURE_STORAGE_CONNECTION_STRING y AZURE_STORAGE_ACCOUNT_NAME.'
}

$loginServer = az acr show -n $AcrName --query loginServer -o tsv
Comprobar-ExitCode "No se encontró el ACR $AcrName. Revisa el nombre y la región."

az acr update -n $AcrName --admin-enabled true -o none
Comprobar-ExitCode "No se pudo habilitar el administrador del ACR $AcrName."

$acrCred = az acr credential show -n $AcrName -o json | ConvertFrom-Json
Comprobar-ExitCode "No se pudieron obtener credenciales del ACR $AcrName."

az acr login -n $AcrName
Comprobar-ExitCode "No se pudo iniciar sesión en el ACR $AcrName con Docker."

docker build -t "${ImageName}:latest" .
Comprobar-ExitCode 'No se pudo construir la imagen local con Docker.'

docker tag "${ImageName}:latest" "$loginServer/${ImageName}:latest"
Comprobar-ExitCode 'No se pudo etiquetar la imagen para el ACR.'

$preferenciaPush = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    $pushSalida = docker push "$loginServer/${ImageName}:latest" 2>&1
} finally {
    $ErrorActionPreference = $preferenciaPush
}
Comprobar-ExitCode 'No se pudo subir la imagen al ACR.'

$digest = $null
foreach ($linea in $pushSalida) {
    if ("$linea" -match 'digest:\s*(sha256:[0-9a-f]{64})') {
        $digest = $Matches[1]
    }
}
if (-not $digest) {
    throw 'No se pudo obtener el digest de la imagen subida al ACR.'
}
$image = "$loginServer/${ImageName}@$digest"
$environmentId = az containerapp env show -n $EnvironmentName -g $ResourceGroup --query id -o tsv
Comprobar-ExitCode "No se encontró el entorno $EnvironmentName en $ResourceGroup."

$template = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'containerapp.yaml.tpl')
$reemplazos = [ordered]@{
    '__LOCATION__'                        = (Convertir-A-Json $Location).Trim('"')
    '__APP_NAME__'                        = (Convertir-A-Json $AppName).Trim('"')
    '__ENVIRONMENT_ID__'                  = (Convertir-A-Json $environmentId).Trim('"')
    '__IMAGE__'                           = (Convertir-A-Json $image).Trim('"')
    '__DATABASE_URL__'                    = Convertir-A-Json $databaseUrl
    '__JWT_SECRET__'                      = Convertir-A-Json $jwtSecret
    '__STORAGE_BUCKET__'                  = Convertir-A-Json $storageBucket
    '__AZURE_STORAGE_CONNECTION_STRING__' = Convertir-A-Json $storageConnection
    '__AZURE_STORAGE_ACCOUNT_NAME__'      = Convertir-A-Json $storageAccount
    '__CORS_ORIGINS__'                    = Convertir-A-Json $cors
    '__OPTIONAL_ENV__'                    = ($envOpcional -join "`n")
    '__OPTIONAL_SECRETS__'                = ($secretOpcional -join "`n")
    '__ACR_SERVER__'   = $loginServer
    '__ACR_USERNAME__' = $acrCred.username
    '__ACR_PASSWORD__' = Convertir-A-Json $acrCred.passwords[0].value
}
foreach ($clave in $reemplazos.Keys) {
    $template = $template.Replace($clave, $reemplazos[$clave])
}

$directorio = Join-Path (Get-Location) '.deploy'
New-Item -ItemType Directory -Path $directorio -Force | Out-Null
$yaml = Join-Path $directorio 'containerapp.yaml'
Set-Content -LiteralPath $yaml -Value $template -Encoding utf8

$query = "[?name=='$AppName'].name"
$preferencia = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    $existe = az containerapp list -g $ResourceGroup --query $query -o tsv 2>$null
} finally {
    $ErrorActionPreference = $preferencia
}
if ($existe) {
    az containerapp update -n $AppName -g $ResourceGroup --yaml $yaml -o none
} else {
    az containerapp create -n $AppName -g $ResourceGroup --yaml $yaml -o none
}
Comprobar-ExitCode 'No se pudo crear o actualizar el Container App.'

$fqdn = az containerapp show -n $AppName -g $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv
Comprobar-ExitCode 'No se pudo obtener el FQDN del Container App.'
Write-Host "API desplegada: https://$fqdn"
Write-Host "YAML generado en $yaml (contiene secretos; no subirlo)."
