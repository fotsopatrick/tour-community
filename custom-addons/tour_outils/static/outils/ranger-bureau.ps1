<#
    Tour de controle - Rangeur de Bureau
    ------------------------------------
    Le Bureau Windows sert de boite de reception : notes .txt jetees a la volee,
    captures d'ecran, PDF administratifs, installeurs, exports. Rien n'en sort
    tout seul. Ce script fait la partie mecanique du rangement - classer,
    dedoublonner, archiver - et laisse a un humain (ou a Claude Code) la partie
    qui demande de LIRE : transformer les notes en taches dans la tour.

    Trois regles non negociables :
      1. On ne supprime JAMAIS. On deplace, et on ecrit ou.
      2. Les fichiers de secrets sont detectes, signales, et laisses en place.
         Leur contenu n'est ni lu, ni recopie, ni envoye nulle part.
      3. Par defaut, le script SIMULE. Il faut -Appliquer pour qu'il bouge un
         fichier.

    Usage :
        .\ranger-bureau.ps1                       # simulation + plan de rangement
        .\ranger-bureau.ps1 -Appliquer            # range pour de vrai
        .\ranger-bureau.ps1 -Appliquer -Destination D:\Bureau-archive
        .\ranger-bureau.ps1 -RangerRaccourcis     # embarque aussi les .lnk / .url
#>
[CmdletBinding()]
param(
    [string] $Bureau = [Environment]::GetFolderPath('Desktop'),
    [string] $Destination,
    [switch] $Appliquer,
    [switch] $RangerRaccourcis,
    [switch] $RangerDossiers,
    [int]    $JoursRecents = 3,
    [string[]] $Epargner = @()
)

$ErrorActionPreference = 'Stop'

# Le Bureau vit sur C:. Quand la machine sera reinstallee, C: sera efface :
# l'archive va donc sur un autre disque si la machine en a un.
if (-not $Destination) {
    $autre = Get-PSDrive -PSProvider FileSystem |
        Where-Object { $_.Name -ne 'C' -and $_.Free -gt 5GB } | Select-Object -First 1
    $Destination = if ($autre) { Join-Path $autre.Root 'Bureau-archive' }
    else { Join-Path $Bureau 'Bureau-archive' }
}

# ------------------------------------------------------------- classification
# L'ordre compte : « secret » l'emporte sur tout le reste.
$CATEGORIES = @(
    @{ Nom = 'Secrets'; Test = { param($f) $f.Name -match '(?i)(mot.?de.?passe|password|acces|access|token|jeton|secret|credential|identifiant|\.env$|\.pem$|\.ppk$|id_rsa)' } }
    @{ Nom = 'Notes'; Test = { param($f) $f.Extension -in '.txt', '.md', '.rtf' } }
    @{ Nom = 'Captures'; Test = { param($f) $f.Extension -in '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp' } }
    @{ Nom = 'Administratif'; Test = { param($f) $f.Extension -in '.pdf', '.docx', '.doc', '.odt', '.xlsx', '.xls', '.csv' } }
    @{ Nom = 'Installeurs'; Test = { param($f) $f.Extension -in '.exe', '.msi', '.msix', '.appx' } }
    @{ Nom = 'Archives'; Test = { param($f) $f.Extension -in '.zip', '.7z', '.rar', '.tar', '.gz', '.iso' } }
    @{ Nom = 'Code et donnees'; Test = { param($f) $f.Extension -in '.json', '.xml', '.yml', '.yaml', '.ps1', '.sh', '.py', '.sql', '.html', '.css', '.js' } }
    @{ Nom = 'Raccourcis'; Test = { param($f) $f.Extension -in '.lnk', '.url' } }
    @{ Nom = 'Medias'; Test = { param($f) $f.Extension -in '.mp4', '.mkv', '.avi', '.mp3', '.wav', '.mov' } }
)

function Test-ContenuSensible {
    <#
        Le nom d'un fichier ment. « ──Sur ta question le paiement… .txt » ne
        ressemble a rien de dangereux et contient pourtant un mot de passe en
        clair. On regarde donc DANS les fichiers texte - mais on ne retient que
        le fait qu'il y a un secret, jamais le secret lui-meme : cette fonction
        rend $true ou $false, et rien d'autre ne sort d'ici.
    #>
    param($Fichier)
    if ($Fichier.Extension -notin '.txt', '.md', '.json', '.env', '.yml', '.yaml', '.ini', '.cfg') { return $false }
    if ($Fichier.Length -gt 2MB) { return $false }
    try { $lignes = Get-Content -LiteralPath $Fichier.FullName -ErrorAction Stop } catch { return $false }
    foreach ($l in $lignes) {
        # 1. Les jetons qui s'annoncent : leur seule forme suffit.
        if ($l -match '(sk-ant-|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|xox[baprs]-|eyJ[A-Za-z0-9_-]{20,}\.)') { return $true }
        # 2. Un mot qui annonce un secret, ET sur la meme ligne une chaine qui
        #    ressemble a une valeur (longue, melangee). Les deux, sinon toute
        #    phrase parlant de mots de passe serait signalee.
        if ($l -match '(?i)(mot de passe|mots de passe|password|passwd|\bmdp\b|secret|token|jeton|cl[ée] api|api.?key)') {
            foreach ($m in [regex]::Matches($l, '[A-Za-z0-9+/=_\-\.]{12,}')) {
                $v = $m.Value
                if ($v -match '[0-9]' -and $v -match '[A-Z]' -and $v -match '[a-z]' -and $v -notmatch '^(https?|www)') { return $true }
            }
        }
    }
    return $false
}

function Get-CategorieFichier {
    param($Fichier)
    # Le nom d'abord (c'est gratuit), le contenu ensuite, et SEULEMENT ensuite
    # les categories ordinaires : une note reste une note, mais une note qui
    # porte un mot de passe est d'abord un secret.
    if (& $CATEGORIES[0].Test $Fichier) { return 'Secrets' }
    if (Test-ContenuSensible $Fichier) { return 'Secrets' }
    foreach ($c in $CATEGORIES) {
        if (& $c.Test $Fichier) { return $c.Nom }
    }
    return 'Divers'
}

# ------------------------------------------------------------------ collecte
$aIgnorer = @('desktop.ini', 'Bureau-archive') + $Epargner
$limite = (Get-Date).AddDays(-$JoursRecents)

$plan = New-Object System.Collections.Generic.List[object]
foreach ($item in (Get-ChildItem -LiteralPath $Bureau -Force)) {
    if ($item.Name -in $aIgnorer) { continue }
    if ($item.Attributes -band [IO.FileAttributes]::System) { continue }

    if ($item.PSIsContainer) {
        if (-not $RangerDossiers) { continue }
        $cat = 'Dossiers'
        $taille = 0
    } else {
        $cat = Get-CategorieFichier $item
        $taille = $item.Length
    }
    if ($cat -eq 'Raccourcis' -and -not $RangerRaccourcis) { continue }

    # Un fichier touche il y a deux heures est encore en cours d'usage.
    $recent = $item.LastWriteTime -gt $limite
    $action = 'Deplacer'
    if ($cat -eq 'Secrets') { $action = 'Laisser (secret)' }
    elseif ($recent) { $action = 'Laisser (recent)' }

    $plan.Add([pscustomobject]@{
            Nom       = $item.Name
            Categorie = $cat
            TailleMo  = [math]::Round($taille / 1MB, 2)
            Modifie   = $item.LastWriteTime
            Action    = $action
            Source    = $item.FullName
            Cible     = Join-Path (Join-Path $Destination $cat) $item.Name
            Doublon   = $null
        })
}

# ------------------------------------------------------- doublons a l'octet
# Deux fichiers de meme taille ET de meme empreinte sont le meme fichier. On
# n'en supprime aucun : on range le premier, et on ecrit que le second le
# repete - a l'utilisateur de trancher.
$parTaille = $plan | Where-Object { $_.TailleMo -gt 0 } | Group-Object TailleMo | Where-Object Count -gt 1
foreach ($g in $parTaille) {
    $vus = @{}
    foreach ($f in $g.Group) {
        try { $h = (Get-FileHash -LiteralPath $f.Source -Algorithm SHA256).Hash } catch { continue }
        if ($vus.ContainsKey($h)) { $f.Doublon = $vus[$h] } else { $vus[$h] = $f.Nom }
    }
}

# ------------------------------------------------------------------ rapport
$horodatage = Get-Date -Format 'yyyy-MM-dd_HHmm'
$md = New-Object System.Text.StringBuilder
$null = $md.AppendLine("# Rangement du Bureau - $(Get-Date -Format 'dd/MM/yyyy HH:mm')")
$null = $md.AppendLine()
$null = $md.AppendLine("Bureau : ``$Bureau``")
$null = $md.AppendLine("Archive : ``$Destination``")
$null = $md.AppendLine("Mode : " + $(if ($Appliquer) { '**applique**' } else { 'simulation (rien n''a bouge)' }))
$null = $md.AppendLine()
$null = $md.AppendLine('Ce fichier est le seul moyen de retrouver un fichier deplace. Il reste dans l''archive.')
$null = $md.AppendLine()

foreach ($g in ($plan | Group-Object Categorie | Sort-Object Name)) {
    $null = $md.AppendLine("## $($g.Name) ($($g.Count))")
    $null = $md.AppendLine()
    foreach ($f in ($g.Group | Sort-Object Nom)) {
        $bits = @($f.Action)
        if ($f.TailleMo -ge 0.01) { $bits += "$($f.TailleMo) Mo" }
        $bits += $f.Modifie.ToString('dd/MM/yyyy')
        if ($f.Doublon) { $bits += "DOUBLON de $($f.Doublon)" }
        $null = $md.AppendLine("- ``$($f.Nom)`` - " + ($bits -join ' | '))
    }
    $null = $md.AppendLine()
}

# ---------------------------------------------------------------- execution
$deplaces = 0
if ($Appliquer) {
    foreach ($f in ($plan | Where-Object Action -eq 'Deplacer')) {
        $dossier = Split-Path $f.Cible -Parent
        if (-not (Test-Path $dossier)) { New-Item -ItemType Directory -Path $dossier -Force | Out-Null }
        $cible = $f.Cible
        # Jamais d'ecrasement silencieux : un homonyme prend un suffixe.
        if (Test-Path -LiteralPath $cible) {
            $b = [IO.Path]::GetFileNameWithoutExtension($cible)
            $e = [IO.Path]::GetExtension($cible)
            $n = 2
            while (Test-Path -LiteralPath $cible) { $cible = Join-Path $dossier "$b ($n)$e"; $n++ }
        }
        Move-Item -LiteralPath $f.Source -Destination $cible
        $deplaces++
    }
    if (-not (Test-Path $Destination)) { New-Item -ItemType Directory -Path $Destination -Force | Out-Null }
}

$journal = Join-Path $Destination "_rangement-$horodatage.md"
if ($Appliquer -or -not (Test-Path $Destination)) {
    if (-not (Test-Path $Destination)) { New-Item -ItemType Directory -Path $Destination -Force | Out-Null }
}
if (-not $Appliquer) { $journal = Join-Path $Bureau "plan-de-rangement-$horodatage.md" }
[IO.File]::WriteAllText($journal, $md.ToString(), (New-Object Text.UTF8Encoding $false))

$plan | Group-Object Categorie | Sort-Object Name |
    Select-Object @{n = 'Categorie'; e = { $_.Name } }, Count | Format-Table -AutoSize

$secrets = @($plan | Where-Object Categorie -eq 'Secrets')
if ($secrets.Count) {
    Write-Host ''
    Write-Host "ATTENTION - $($secrets.Count) fichier(s) de secrets laisse(s) en place :" -ForegroundColor Yellow
    $secrets | ForEach-Object { Write-Host "  $($_.Nom)" -ForegroundColor Yellow }
    Write-Host '  Leur contenu n''a pas ete lu. A passer au Coffre de la tour.' -ForegroundColor Yellow
}

Write-Host ''
if ($Appliquer) { Write-Host "$deplaces fichier(s) deplaces vers $Destination" -ForegroundColor Green }
else { Write-Host 'Simulation : rien n''a bouge. Relancer avec -Appliquer.' -ForegroundColor Cyan }
Write-Host "Journal : $journal" -ForegroundColor Green
