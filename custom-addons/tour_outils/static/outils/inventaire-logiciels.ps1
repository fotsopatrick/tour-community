<#
    Tour de controle - Inventaire des logiciels du poste
    ----------------------------------------------------
    Recense TOUT ce qui est installe sur la machine, classe par categorie,
    et le depose dans la tour (note ou fiche du Depot) si on lui donne un acces.

    Pourquoi : avant de reinstaller Windows, on veut savoir ce qu'on avait.
    Le registre seul ne suffit pas - il ignore le Microsoft Store, les
    applications portables posees sur un autre disque, et les jeux Steam.

    Usage :
        .\inventaire-logiciels.ps1                          # rapport sur le Bureau
        .\inventaire-logiciels.ps1 -Sortie C:\tmp\inv.md
        .\inventaire-logiciels.ps1 -Json                    # + fichier .json a cote
        .\inventaire-logiciels.ps1 -DossiersSupplementaires D:\Logiciels,D:\JEUX
        .\inventaire-logiciels.ps1 -TourUrl https://tour.exemple.fr -TourBase tour `
                                   -TourLogin moi@exemple.fr -TourMdp '...'

    Ne modifie RIEN sur la machine : lecture seule.
#>
[CmdletBinding()]
param(
    [string]   $Sortie = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'inventaire-logiciels.md'),
    [switch]   $Json,
    [string[]] $DossiersSupplementaires = @(),
    [string]   $TourUrl,
    [string]   $TourBase = 'tour',
    [string]   $TourLogin,
    [string]   $TourMdp,
    [ValidateSet('note', 'depot')]
    [string]   $TourCible = 'note',
    [string]   $TourTitre
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ---------------------------------------------------------------- categories
# Regles lues dans l'ordre : la premiere qui matche gagne. Volontairement
# deterministe (aucun appel a une IA) : un inventaire doit etre reproductible
# et gratuit.
$REGLES = @(
    @{ Cat = 'Systeme Windows'; Motif = '^(Microsoft (Visual C\+\+|\.NET|Windows Desktop Runtime|Edge(WebView)?|OneDrive|Update|Server|Application Error)|Windows (SDK|Kits|Software Development|Assessment|Driver|App|PC Health))|Update for Microsoft|Kit de developpement|Runtime|Redistributable|MSI Development' }
    @{ Cat = 'Metier et gestion'; Motif = '(GALSS|Cryptographiques CPS|Carte de Professionnel|CPS v|Vitale|Tour de contr)' }
    @{ Cat = 'Pilotes et constructeur'; Motif = '(Driver|Pilote|NVIDIA|AMD (Software|Chipset|Radeon)|Realtek|Intel\(R\)|Synaptics|Conexant|Killer|Dell |HP |Lenovo|Logitech|Razer|Corsair|MSI (Center|Afterburner)|ASUS|Armoury|AURA (Creator|Sync)|GHelper|G-Helper|Dolby|Brother|Canon|Epson|Elan|Alps|Bluetooth|Chipset|Audio Driver)' }
    @{ Cat = 'Developpement'; Motif = '(Visual Studio|VS Code|Code - |JetBrains|IntelliJ|PyCharm|WebStorm|Rider|DataGrip|Android Studio|Eclipse|NetBeans|Git|GitHub|Node\.js|npm|Python|Anaconda|Miniconda|Java|JDK|JRE|OpenJDK|\.NET SDK|Docker|Podman|Kubernetes|WSL|Windows Subsystem|Sous-systeme Windows pour Linux|Sous-système Windows pour Linux|Debian|Ubuntu|Rust|Cargo|Golang|PHP|Composer|Ruby|Perl|Flutter|Dart|Unity|Godot|Unreal|UDK|WINDEV|WEBDEV|PC SOFT|PCSOFT|HFSQL|Postman|Insomnia|DBeaver|pgAdmin|MySQL|MariaDB|PostgreSQL|SQL Server|SQLite|MongoDB|Redis|Notepad\+\+|Sublime|Vim|Neovim|Cursor|Windsurf|Claude|Copilot|opencode|stripe|CMake|LLVM|Clang|MinGW|Arduino|Fiddler|Wireshark|USBPcap|WinMerge|Beyond Compare|Sourcetree|TortoiseGit|TortoiseSVN|Supabase|Firebase|ngrok|Terraform|Ansible|Vagrant|VirtualBox|VMware|Hyper-V|scoop|Chocolatey|WezTerm|Cmder|MobaXterm|ApacheDirectoryStudio|Apache)' }
    # « Ninja » (l'outil de build) est volontairement absent : trop de jeux le
    # portent dans leur titre, et un jeu classe en Developpement fait douter de
    # tout le reste du tableau.
    @{ Cat = 'Reseau et serveur'; Motif = '(WinSCP|FileZilla|PuTTY|OpenSSH|OpenVPN|VPN|WireGuard|Tailscale|TeamViewer|AnyDesk|RustDesk|Remote Desktop|Bureau a distance|Nmap|Advanced IP|Netlimiter|Rclone|Syncthing|qBittorrent|uTorrent|Transmission|Plex|Jellyfin|Emby|XAMPP|WAMP|Laragon|Nginx|IIS)' }
    @{ Cat = 'Navigateurs'; Motif = '(Google Chrome|Chromium|Mozilla Firefox|Microsoft Edge$|Opera|Brave|Vivaldi|Tor Browser|Safari)' }
    @{ Cat = 'Bureautique et documents'; Motif = '(Microsoft (Office|365|Word|Excel|PowerPoint|Outlook|Access|Publisher|Visio|Project|OneNote)|LibreOffice|OpenOffice|WPS|Adobe (Acrobat|Reader)|Foxit|PDF|Sumatra|Stirling|Notion|Obsidian|Evernote|Joplin|Zotero|Mendeley|Scribus|Calibre|Thunderbird|Mailbird|eM Client)' }
    @{ Cat = 'Multimedia et creation'; Motif = '(VLC|MPC|Media Player|PotPlayer|Kodi|Spotify|Deezer|iTunes|Apple Music|Audacity|Reaper|FL Studio|Ableton|OBS|Streamlabs|Handbrake|FFmpeg|ShareX|Greenshot|Lightshot|Snagit|Photoshop|Illustrator|Premiere|After Effects|Adobe|GIMP|Inkscape|Krita|Paint\.NET|Blender|DaVinci|Shotcut|Kdenlive|Figma|Canva|IrfanView|XnView|FastStone|Camtasia|Capture)' }
    @{ Cat = 'Communication'; Motif = '(Discord|Slack|Teams|Zoom|Skype|Telegram|WhatsApp|Signal|Messenger|Webex|Google Meet|Jitsi|Mattermost|Element|Thunderbird)' }
    @{ Cat = 'Jeux et lanceurs'; Motif = '(Steam|Epic Games|GOG|Ubisoft|Uplay|Origin|EA (App|Desktop)|Battle\.net|Blizzard|Rockstar|Riot|Xbox|Game Bar|Denuvo|Anti-Cheat|Minecraft|Cyberpunk|Resident Evil|Fortnite|League of Legends|Valorant|Roblox|itch|Sims|Skyrim|Genshin|Destiny|GTAV|eFootball|Life is Strange|desmume|dolphin-|Solitaire)' }
    @{ Cat = 'Securite'; Motif = '(Antivirus|Defender|Kaspersky|Bitdefender|Avast|AVG|Norton|McAfee|Malwarebytes|ESET|Sophos|Bitwarden|KeePass|1Password|LastPass|Dashlane|Nord(VPN|Pass|Updater)|Proton|VeraCrypt|Cryptomator|Yubi|Authy|GlassWire|Asterisk Key)' }
    @{ Cat = 'Metier et gestion'; Motif = '(MKAmb|Gestamb|Teletrans|Ambulance|MKTeletrans|WDMAP|Sage|EBP|Ciel|Odoo|SAP|Cegid|Chorus|Fortuneo|Banque|Compta)' }
    @{ Cat = 'Utilitaires'; Motif = '(7-Zip|WinRAR|WinZip|PeaZip|NanaZip|CCleaner|Revo|IObit|Everything|Total Commander|TreeSize|WizTree|Rufus|Ventoy|Etcher|CrystalDisk|HWiNFO|CPU-Z|GPU-Z|Speccy|AIDA|Autoruns|Process Explorer|Sysinternals|NirSoft|LastActivityView|ShareMouse|PowerToys|AutoHotkey|f\.lux|Flow Launcher|Ditto|Clipboard|Calculatrice|Sticky|Zip|Apple (Mobile|Software)|iCloud|Bonjour)' }
)

# Composants livres AVEC Windows : ils reviendront tout seuls a la reinstallation.
# Les isoler evite de noyer les 30 logiciels a reinstaller sous 120 lignes de bruit.
$MOTIF_WINDOWS = '^(Microsoft|MicrosoftWindows|MicrosoftCorporation\w*|Windows|windows)[\.\s]|' +
'^(Actualit|App Installer|Application Start|Am.liorations de la compatibilit|Assistance rapide|' +
'AV1 Video|Bloc-notes|Cam.ra Windows|Clipchamp|Dev Home|Extension|Game Speech|Horloge Windows|' +
'H.te d|H.te de|Hub de commentaires|Ink\.|Lecteur multim.dia|Magn.tophone|Mobile connect|' +
'Module d.exp.rience locale|MSN M.t.o|Obtenir de l|Outlook for Windows|Paint|Pense-b.tes|' +
'Photos Microsoft|PinningConfirmation|Power Automate|Raw Image|S.curit. Windows|Terminal Windows|' +
'Calculatrice|Outil Capture|CapturePicker|' +
'UDK Package|Web Media|Xbox|Your Phone)|' +
'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-'          # paquets Store sans nom lisible (GUID)

function Get-Categorie {
    param([string]$Nom, [string]$Editeur, [string]$Source)
    # La provenance prime sur le nom : un dossier de jeu s'appelle « ygg » ou
    # « sims », aucun mot-clef ne le devinera.
    if ($Source -match '^Jeu ') { return 'Jeux et lanceurs' }
    # WSL porte un nom Microsoft mais ne s'installe pas tout seul : c'est un outil.
    if ($Nom -match '(SubsystemForLinux|Sous-syst.me Windows pour Linux)') { return 'Developpement' }
    if ($Nom -match $MOTIF_WINDOWS) { return 'Systeme Windows' }
    $texte = "$Nom $Editeur"
    foreach ($r in $REGLES) {
        if ($texte -match $r.Motif) { return $r.Cat }
    }
    return 'A classer'
}

$resultats = New-Object System.Collections.Generic.List[object]

function Ajouter {
    param(
        [string]$Nom, [string]$Version, [string]$Editeur,
        [string]$Source, [string]$Emplacement, [string]$Date, [double]$TailleMo = 0
    )
    if ([string]::IsNullOrWhiteSpace($Nom)) { return }
    $resultats.Add([pscustomobject]@{
            Nom         = $Nom.Trim()
            Version     = $Version
            Editeur     = $Editeur
            Source      = $Source
            Emplacement = $Emplacement
            Date        = $Date
            TailleMo    = $TailleMo
            Categorie   = (Get-Categorie -Nom $Nom -Editeur $Editeur -Source $Source)
        })
}

# ------------------------------------------------------- 1. registre Windows
Write-Host '[1/6] Registre (installations classiques)...' -ForegroundColor Cyan
$clefs = @(
    @{ Chemin = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'; Src = 'Installe a la main (64 bits)' }
    @{ Chemin = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'; Src = 'Installe a la main (32 bits)' }
    @{ Chemin = 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'; Src = 'Installe a la main (utilisateur)' }
)
foreach ($c in $clefs) {
    $entrees = @()
    try { $entrees = Get-ItemProperty $c.Chemin -ErrorAction SilentlyContinue } catch {}
    foreach ($e in $entrees) {
        if (-not $e.DisplayName) { continue }
        if ($e.SystemComponent -eq 1) { continue }
        if ($e.ParentKeyName) { continue }          # mises a jour rattachees a un parent
        if ($e.ReleaseType -match 'Update|Hotfix|Security Update') { continue }
        $d = ''
        if ($e.InstallDate -match '^\d{8}$') {
            $d = '{0}/{1}/{2}' -f $e.InstallDate.Substring(6, 2), $e.InstallDate.Substring(4, 2), $e.InstallDate.Substring(0, 4)
        }
        $mo = 0
        if ($e.EstimatedSize) { $mo = [math]::Round($e.EstimatedSize / 1024, 1) }
        Ajouter -Nom $e.DisplayName -Version $e.DisplayVersion -Editeur $e.Publisher `
            -Source $c.Src -Emplacement $e.InstallLocation -Date $d -TailleMo $mo
    }
}

# --------------------------------------------------------- 2. Microsoft Store
Write-Host '[2/6] Microsoft Store (paquets Appx)...' -ForegroundColor Cyan
try {
    foreach ($p in (Get-AppxPackage -ErrorAction SilentlyContinue)) {
        if ($p.IsFramework) { continue }
        $nom = $p.Name
        try {
            $manifeste = Get-AppxPackageManifest $p -ErrorAction SilentlyContinue
            $joli = $manifeste.Package.Properties.DisplayName
            if ($joli -and $joli -notmatch '^ms-resource') { $nom = $joli }
        } catch {}
        Ajouter -Nom $nom -Version $p.Version -Editeur $p.Publisher `
            -Source 'Microsoft Store' -Emplacement $p.InstallLocation
    }
} catch { Write-Warning "Appx illisible : $_" }

# ---------------------------------------------------------------- 3. winget
Write-Host '[3/6] winget...' -ForegroundColor Cyan
if (Get-Command winget -ErrorAction SilentlyContinue) {
    try {
        $brut = winget list --disable-interactivity 2>$null | Out-String
        $lignes = $brut -split "`r?`n" | Where-Object { $_ -match '\S' }
        $entete = $lignes | Where-Object { $_ -match '^(Nom|Name)\s+(ID|Id)\s' } | Select-Object -First 1
        if ($entete) {
            $iId = $entete.IndexOf(($entete -split '\s+' | Where-Object { $_ -match '^(ID|Id)$' } | Select-Object -First 1))
            foreach ($l in $lignes) {
                if ($l -match '^-{5,}' -or $l -eq $entete) { continue }
                if ($l.Length -le $iId) { continue }
                $nom = $l.Substring(0, $iId).Trim()
                $reste = ($l.Substring($iId) -split '\s{2,}') | Where-Object { $_ -match '\S' }
                if (-not $nom) { continue }
                Ajouter -Nom $nom -Version ($reste[1]) -Editeur '' -Source 'winget' -Emplacement ($reste[0])
            }
        }
    } catch { Write-Warning "winget illisible : $_" }
}

# ------------------------------------------------- 4. gestionnaires portables
Write-Host '[4/6] scoop / chocolatey...' -ForegroundColor Cyan
$scoop = Join-Path $env:USERPROFILE 'scoop\apps'
if (Test-Path $scoop) {
    foreach ($a in Get-ChildItem $scoop -Directory -ErrorAction SilentlyContinue) {
        if ($a.Name -eq 'scoop') { continue }
        $v = (Get-ChildItem $a.FullName -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -ne 'current' } | Select-Object -Last 1).Name
        Ajouter -Nom $a.Name -Version $v -Source 'scoop (portable)' -Emplacement $a.FullName
    }
}
$choco = Join-Path $env:ProgramData 'chocolatey\lib'
if (Test-Path $choco) {
    foreach ($a in Get-ChildItem $choco -Directory -ErrorAction SilentlyContinue) {
        Ajouter -Nom $a.Name -Source 'chocolatey' -Emplacement $a.FullName
    }
}

# ------------------------------------------------------------------ 5. jeux
Write-Host '[5/6] Jeux (Steam, Epic, GOG, Xbox)...' -ForegroundColor Cyan
$pf86 = ${env:ProgramFiles(x86)}
$bibliosSteam = New-Object System.Collections.Generic.List[string]
$pistes = @("$pf86\Steam", "$env:ProgramFiles\Steam", 'D:\SteamLibrary', 'D:\Steam', 'E:\SteamLibrary', 'E:\Steam')
foreach ($racine in $pistes) {
    if ($racine -and (Test-Path "$racine\steamapps")) { $bibliosSteam.Add($racine) }
}
# La liste officielle des bibliotheques vit dans libraryfolders.vdf
foreach ($vdf in @("$pf86\Steam\steamapps\libraryfolders.vdf", 'D:\SteamLibrary\steamapps\libraryfolders.vdf')) {
    if ($vdf -and (Test-Path $vdf)) {
        foreach ($m in ([regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"'))) {
            $p = $m.Groups[1].Value -replace '\\\\', '\'
            if ((Test-Path "$p\steamapps") -and -not $bibliosSteam.Contains($p)) { $bibliosSteam.Add($p) }
        }
    }
}
foreach ($b in $bibliosSteam) {
    foreach ($acf in Get-ChildItem "$b\steamapps" -Filter 'appmanifest_*.acf' -ErrorAction SilentlyContinue) {
        $t = Get-Content $acf.FullName -Raw -Encoding UTF8   # les .acf sont en UTF-8
        $nom = ([regex]::Match($t, '"name"\s+"([^"]+)"')).Groups[1].Value
        $taille = ([regex]::Match($t, '"SizeOnDisk"\s+"(\d+)"')).Groups[1].Value
        $mo = 0; if ($taille) { $mo = [math]::Round([double]$taille / 1MB, 1) }
        if ($nom -and $nom -notmatch '^Steamworks') {
            Ajouter -Nom $nom -Source 'Jeu Steam' -Emplacement "$b\steamapps\common" -TailleMo $mo
        }
    }
}
$epic = Join-Path $env:ProgramData 'Epic\EpicGamesLauncher\Data\Manifests'
if (Test-Path $epic) {
    foreach ($f in Get-ChildItem $epic -Filter '*.item' -ErrorAction SilentlyContinue) {
        try {
            $j = Get-Content $f.FullName -Raw | ConvertFrom-Json
            Ajouter -Nom $j.DisplayName -Version $j.AppVersionString -Source 'Jeu Epic Games' -Emplacement $j.InstallLocation
        } catch {}
    }
}
foreach ($dossierJeux in @('D:\Games', 'D:\JEUX', 'C:\Games', 'D:\GOG Games')) {
    if (Test-Path $dossierJeux) {
        foreach ($g in Get-ChildItem $dossierJeux -Directory -ErrorAction SilentlyContinue) {
            Ajouter -Nom $g.Name -Source "Jeu pose sur le disque ($dossierJeux)" -Emplacement $g.FullName
        }
    }
}

# ------------------------------------- 6. dossiers de programmes hors systeme
Write-Host '[6/6] Dossiers de programmes (autres disques)...' -ForegroundColor Cyan
$aScanner = @()
foreach ($d in (Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -notin @('C') -and $_.Free })) {
    foreach ($n in @('Logiciels', 'Programmes', 'Program Files', 'Apps', 'Portable', 'Installation', 'Installations', 'Setup')) {
        $p = Join-Path $d.Root $n
        if (Test-Path $p) { $aScanner += $p }
    }
}
$aScanner += $DossiersSupplementaires | Where-Object { $_ -and (Test-Path $_) }
foreach ($p in ($aScanner | Select-Object -Unique)) {
    foreach ($sd in Get-ChildItem $p -Directory -ErrorAction SilentlyContinue) {
        $nom = $sd.Name
        # Un dossier qui s'appelle « 2024 » ou « 2022.3.48f1 » ne dit rien : c'est
        # un numero de version. Le vrai nom est celui de ce qu'il contient.
        if ($nom -match '^[\d][\d\.]*[a-zA-Z]?\d*$') {
            $enfant = Get-ChildItem $sd.FullName -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -notmatch '^(modules\.json|\.|_)' } | Select-Object -First 1
            if ($enfant) { $nom = "$($enfant.BaseName) ($($sd.Name))" }
        }
        Ajouter -Nom $nom -Source "Installe sur un autre disque ($p)" -Emplacement $sd.FullName `
            -Date $sd.LastWriteTime.ToString('dd/MM/yyyy')
    }
    foreach ($f in (Get-ChildItem $p -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Extension -in '.exe', '.msi' })) {
        Ajouter -Nom $f.BaseName -Source "Installeur conserve ($p)" -Emplacement $f.FullName `
            -Date $f.LastWriteTime.ToString('dd/MM/yyyy') -TailleMo ([math]::Round($f.Length / 1MB, 1))
    }
}

# ---------------------------------------------------------- dedoublonnage
# Une meme application apparait souvent deux fois (registre + winget, ou
# registre 32 et 64 bits). On garde la premiere vue et on note les autres
# sources a cote : perdre l'origine, c'est perdre le moyen de la reinstaller.
$parNom = @{}
foreach ($r in $resultats) {
    $clef = ($r.Nom -replace '[^\p{L}\p{Nd}]', '').ToLowerInvariant()
    if (-not $clef) { continue }
    if ($parNom.ContainsKey($clef)) {
        $ex = $parNom[$clef]
        if ($ex.Source -notlike "*$($r.Source)*") { $ex.Source = "$($ex.Source) + $($r.Source)" }
        if (-not $ex.Version -and $r.Version) { $ex.Version = $r.Version }
        if (-not $ex.Emplacement -and $r.Emplacement) { $ex.Emplacement = $r.Emplacement }
        if ($r.TailleMo -gt $ex.TailleMo) { $ex.TailleMo = $r.TailleMo }
    } else {
        $parNom[$clef] = $r
    }
}
# Apres fusion, la provenance la plus parlante l'emporte : un titre vu a la fois
# dans le registre et dans une bibliotheque de jeux est un jeu.
foreach ($r in $parNom.Values) {
    if ($r.Source -match 'Jeu (Steam|Epic|pose)') { $r.Categorie = 'Jeux et lanceurs' }
    elseif ($r.Emplacement -like 'C:\Windows\SystemApps*') { $r.Categorie = 'Systeme Windows' }
}
$final = $parNom.Values | Sort-Object Categorie, Nom

# ------------------------------------------------------------------ rapport
$ordre = @('Metier et gestion', 'Developpement', 'Bureautique et documents', 'Navigateurs',
    'Communication', 'Multimedia et creation', 'Reseau et serveur', 'Securite',
    'Utilitaires', 'Jeux et lanceurs', 'Pilotes et constructeur', 'Systeme Windows', 'A classer')

$md = New-Object System.Text.StringBuilder
$null = $md.AppendLine("# Inventaire des logiciels - $env:COMPUTERNAME")
$null = $md.AppendLine()
$null = $md.AppendLine("Releve du $(Get-Date -Format 'dd/MM/yyyy a HH:mm') - $($final.Count) entrees uniques.")
$null = $md.AppendLine("Fait pour preparer une reinstallation propre : ce document dit quoi reinstaller, ou c'etait, et d'ou ca venait.")
$null = $md.AppendLine()
foreach ($cat in $ordre) {
    $lot = @($final | Where-Object { $_.Categorie -eq $cat })
    if (-not $lot.Count) { continue }
    $null = $md.AppendLine("## $cat ($($lot.Count))")
    $null = $md.AppendLine()
    foreach ($i in $lot) {
        $bits = @()
        if ($i.Version) { $bits += "v$($i.Version)" }
        if ($i.Source) { $bits += $i.Source }
        if ($i.TailleMo -ge 1) { $bits += "$($i.TailleMo) Mo" }
        if ($i.Emplacement) { $bits += $i.Emplacement }
        $null = $md.AppendLine("- **$($i.Nom)** - " + ($bits -join ' | '))
    }
    $null = $md.AppendLine()
}
$texte = $md.ToString()

$dossierSortie = Split-Path $Sortie -Parent
if ($dossierSortie -and -not (Test-Path $dossierSortie)) { New-Item -ItemType Directory -Path $dossierSortie -Force | Out-Null }
[IO.File]::WriteAllText($Sortie, $texte, (New-Object Text.UTF8Encoding $false))
Write-Host "Rapport ecrit : $Sortie" -ForegroundColor Green

if ($Json) {
    $cheminJson = [IO.Path]::ChangeExtension($Sortie, '.json')
    [IO.File]::WriteAllText($cheminJson, ($final | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding $false))
    Write-Host "JSON ecrit : $cheminJson" -ForegroundColor Green
}

# ------------------------------------------------------- depot dans la tour
if ($TourUrl -and $TourLogin -and $TourMdp) {
    Write-Host 'Depot dans la tour...' -ForegroundColor Cyan
    $client = Join-Path $PSScriptRoot 'tour-client.ps1'
    if (-not (Test-Path $client)) { throw "tour-client.ps1 introuvable a cote du script." }
    . $client
    $session = Connexion-Tour -Url $TourUrl -Base $TourBase -Login $TourLogin -Mdp $TourMdp
    $titre = if ($TourTitre) { $TourTitre } else { "Logiciels installes sur $env:COMPUTERNAME au $(Get-Date -Format 'dd/MM/yyyy')" }
    $html = ConvertTo-HtmlSimple -Texte $texte
    if ($TourCible -eq 'depot') {
        $id = Creer-Enregistrement -Session $session -Modele 'depot.note' -Valeurs @{
            name = $titre; contenu = $texte; source = "Inventaire du poste $env:COMPUTERNAME"
        }
    } else {
        $id = Creer-Enregistrement -Session $session -Modele 'project.task' -Valeurs @{
            name = $titre; description = $html
        }
    }
    Write-Host "Depose dans la tour ($TourCible) - id $id" -ForegroundColor Green
}

$final | Group-Object Categorie | Sort-Object Count -Descending |
    Select-Object @{n = 'Categorie'; e = { $_.Name } }, Count | Format-Table -AutoSize
