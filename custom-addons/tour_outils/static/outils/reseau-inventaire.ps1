<#
    Tour de controle - Inventaire du reseau local
    ---------------------------------------------
    Repond a UNE question : qu'est-ce qui est connecte a mon reseau ?

    Il liste les appareils presents, tente de les nommer, identifie leur
    fabricant, et signale ceux qu'il ne connait pas. Il enregistre l'inventaire
    pour que la prochaine execution puisse dire << celui-la est nouveau >>.

    CE QU'IL NE FAIT PAS, ET C'EST VOLONTAIRE.
    Il ne regarde pas ce que les appareils font. Pas les sites visites, pas le
    contenu des echanges. Sur son propre reseau, on a le droit de savoir QUI est
    connecte - c'est de l'administration. Intercepter les communications
    d'autrui, meme chez soi, est une autre affaire : en France, l'atteinte au
    secret des correspondances est un delit (art. 226-15 du code penal), et le
    fait que la box vous appartienne n'y change rien.

    La bonne reponse a << il y a quelqu'un sur mon wifi >> n'est donc pas de
    l'espionner : c'est de le mettre dehors. Ce script sert a le reperer.

    Usage :
        .\reseau-inventaire.ps1                 # scanne et compare au dernier passage
        .\reseau-inventaire.ps1 -Rapide         # table ARP seulement (2 secondes)
        .\reseau-inventaire.ps1 -Nommer "a4:83:e7:11:22:33=iPhone de Patrick"
#>
[CmdletBinding()]
param(
    [switch]   $Rapide,
    [string[]] $Nommer = @(),
    [string]   $Fichier = (Join-Path $env:USERPROFILE ".tour-reseau.json"),
    [int]      $Timeout = 250
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Prefixes MAC des fabricants qu'on croise dans un logement. Volontairement
# court : le but est de reconnaitre l'ordinaire d'un coup d'oeil, pas de tenir
# a jour le registre mondial des 50 000 prefixes.
$FABRICANTS = @{
    '00:1A:11' = 'Google'; '3C:5A:B4' = 'Google'; 'F4:F5:D8' = 'Google'
    'AC:DE:48' = 'Apple';  'A4:83:E7' = 'Apple';  'F0:18:98' = 'Apple'
    '00:1B:63' = 'Apple';  '3C:07:54' = 'Apple';  '04:D3:B0' = 'Apple'
    '00:1D:D8' = 'Microsoft'; '7C:1E:52' = 'Microsoft'; '00:50:F2' = 'Microsoft'
    '00:04:4B' = 'NVIDIA'; 'B4:0A:D8' = 'Sony (PlayStation)'; '00:D9:D1' = 'Sony'
    'FC:0F:E6' = 'Sony (PlayStation)'; '00:15:5D' = 'Hyper-V (machine virtuelle)'
    '64:16:66' = 'Nest';   '18:B4:30' = 'Nest';   'D8:0F:99' = 'Xiaomi'
    '28:6C:07' = 'Xiaomi'; '64:CC:2E' = 'Xiaomi'; '50:EC:50' = 'Xiaomi (Mi TV)'
    '00:24:D4' = 'Bouygues (Bbox)'; '68:A3:78' = 'Bouygues (Bbox)'
    'E0:B9:E5' = 'Bouygues (Bbox)'; '00:1E:74' = 'Sagemcom (box)'
    'DC:A6:32' = 'Raspberry Pi'; 'B8:27:EB' = 'Raspberry Pi'; 'E4:5F:01' = 'Raspberry Pi'
    '00:0C:29' = 'VMware'; '08:00:27' = 'VirtualBox'
}

function Fabricant {
    param([string]$Mac)
    if (-not $Mac) { return '' }
    $p = ($Mac -replace '-', ':').ToUpper()
    if ($p.Length -lt 8) { return '' }
    $cle = $p.Substring(0, 8)
    if ($FABRICANTS.ContainsKey($cle)) { return $FABRICANTS[$cle] }
    return ''
}

# ------------------------------------------------------ le reseau courant
$carte = Get-NetIPConfiguration |
    Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } |
    Select-Object -First 1
if (-not $carte) { throw "Aucune connexion reseau active." }

$monIp = $carte.IPv4Address.IPAddress
$passerelle = $carte.IPv4DefaultGateway.NextHop
$prefixe = ($monIp -split '\.')[0..2] -join '.'

Write-Host "Reseau      : $prefixe.0/24" -ForegroundColor Cyan
Write-Host "Cette machine : $monIp   |   Box : $passerelle" -ForegroundColor Cyan
Write-Host ''

# ------------------------------------------------------------- balayage
# Un ping sur chaque adresse force la box a remplir la table ARP. Sans ca,
# on ne voit que les appareils qui ont parle recemment - et un intrus discret
# est justement celui qui parle peu.
if (-not $Rapide) {
    Write-Host 'Balayage des 254 adresses...' -ForegroundColor DarkGray
    $taches = 1..254 | ForEach-Object {
        $ip = "$prefixe.$_"
        (New-Object System.Net.NetworkInformation.Ping).SendPingAsync($ip, $Timeout)
    }
    [Threading.Tasks.Task]::WaitAll($taches)
}

$table = Get-NetNeighbor -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.State -in 'Reachable', 'Stale', 'Permanent' -and
                   $_.IPAddress -like "$prefixe.*" -and
                   $_.LinkLayerAddress -notmatch '^(00-00-00|FF-FF-FF)' }

# ------------------------------------------------ inventaire precedent
$connus = @{}
if (Test-Path $Fichier) {
    try {
        (Get-Content $Fichier -Raw -Encoding UTF8 | ConvertFrom-Json) |
            ForEach-Object { $connus[$_.mac] = $_ }
    } catch { }
}
foreach ($n in $Nommer) {
    $m, $nom = $n -split '=', 2
    $m = ($m -replace '-', ':').ToUpper()
    if ($connus.ContainsKey($m)) { $connus[$m].nom = $nom }
    else { $connus[$m] = [pscustomobject]@{ mac = $m; nom = $nom; ip = ''; vu = '' } }
}

# ----------------------------------------------------------- resultats
$resultats = New-Object System.Collections.Generic.List[object]

# La machine qui scanne n'apparait pas dans sa propre table ARP : on ne demande
# pas son adresse a soi-meme. Sans cette ligne, le compte est faux et on cherche
# un appareil manquant qui est celui devant lequel on est assis.
$maMac = ($carte.NetAdapter.MacAddress -replace '-', ':').ToUpper()
$resultats.Add([pscustomobject]@{
        IP = $monIp; MAC = $maMac; Nom = $env:COMPUTERNAME
        Fabricant = Fabricant $maMac; Etat = 'CETTE MACHINE'
    })

foreach ($e in $table) {
    $mac = ($e.LinkLayerAddress -replace '-', ':').ToUpper()
    $ip = $e.IPAddress
    $nom = ''
    try { $nom = ([Net.Dns]::GetHostEntry($ip)).HostName } catch { }

    $etiquette = ''
    $nouveau = $true
    if ($connus.ContainsKey($mac)) {
        $etiquette = $connus[$mac].nom
        $nouveau = $false
    }

    $resultats.Add([pscustomobject]@{
            IP        = $ip
            MAC       = $mac
            Nom       = if ($etiquette) { $etiquette } elseif ($nom) { $nom } else { '' }
            Fabricant = Fabricant $mac
            Etat      = if ($ip -eq $passerelle) { 'BOX' }
                        elseif ($ip -eq $monIp) { 'CETTE MACHINE' }
                        elseif ($nouveau) { 'NOUVEAU' } else { 'connu' }
        })
}

$resultats = $resultats | Sort-Object { [version](($_.IP -replace '^(\d+)\.(\d+)\.(\d+)\.(\d+)$', '$1.$2.$3.$4')) }

$resultats | Format-Table -AutoSize IP, MAC, Nom, Fabricant, Etat | Out-String -Width 130

$nouveaux = @($resultats | Where-Object Etat -eq 'NOUVEAU')
Write-Host "$($resultats.Count) appareil(s) present(s), dont $($nouveaux.Count) jamais vu(s)." -ForegroundColor Green
if ($nouveaux.Count) {
    Write-Host ''
    Write-Host 'APPAREILS INCONNUS :' -ForegroundColor Yellow
    $nouveaux | ForEach-Object {
        Write-Host ("  {0,-15} {1}  {2}" -f $_.IP, $_.MAC, $_.Fabricant) -ForegroundColor Yellow
    }
    Write-Host ''
    Write-Host "  Nommez ceux que vous reconnaissez :" -ForegroundColor DarkGray
    Write-Host "    .\reseau-inventaire.ps1 -Nommer `"$($nouveaux[0].MAC)=Mon appareil`"" -ForegroundColor DarkGray
    Write-Host "  Ceux que vous ne reconnaissez pas : changez le mot de passe du wifi." -ForegroundColor DarkGray
}

# On enregistre l'inventaire : sans memoire, tout serait << nouveau >> a
# chaque passage, et l'alerte deviendrait du bruit.
$aGarder = @()
foreach ($r in $resultats) {
    $nom = $r.Nom
    if ($connus.ContainsKey($r.MAC) -and $connus[$r.MAC].nom) { $nom = $connus[$r.MAC].nom }
    $aGarder += [pscustomobject]@{
        mac = $r.MAC; nom = $nom; ip = $r.IP
        vu  = (Get-Date -Format 'yyyy-MM-dd HH:mm')
    }
}
foreach ($k in $connus.Keys) {
    if (-not ($aGarder.mac -contains $k)) { $aGarder += $connus[$k] }
}
[IO.File]::WriteAllText($Fichier, ($aGarder | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding $false))
Write-Host ''
Write-Host "Inventaire enregistre : $Fichier" -ForegroundColor DarkGray
