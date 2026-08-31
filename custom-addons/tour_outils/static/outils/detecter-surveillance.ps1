<#
    Tour de controle - Detecteur de surveillance
    --------------------------------------------
    Repond a une question precise : est-ce qu'un outil de surveillance
    (surveillance employeur, controle parental, keylogger, agent MDM/RMM,
    prise en main a distance) est installe sur CE poste ?

    Six sources, parce qu'aucune ne suffit seule :
      1. les logiciels installes (registre 32/64 bits + utilisateur)
      2. les services Windows et leurs executables
      3. les processus en cours
      4. ce qui se lance au demarrage (cles Run + dossiers Demarrage)
      5. les taches planifiees qui ne viennent pas de Microsoft
      6. le statut d'entreprise de la machine (domaine / MDM via dsregcmd)

    Usage :
        .\detecter-surveillance.ps1                     # rapport + page web qui s'ouvre
        .\detecter-surveillance.ps1 -Sortie C:\tmp\rapport.md
        .\detecter-surveillance.ps1 -SansOuvrir         # ne pas ouvrir le navigateur

    Deux sorties : une page web (le resultat explique simplement, aux couleurs
    de la tour) et un rapport Markdown (le detail technique). Ne modifie RIEN
    sur la machine : lecture seule. Tout reste sur le poste, rien n'est envoye.
#>
[CmdletBinding()]
param(
    [string] $Sortie = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'rapport-surveillance.md'),
    [switch] $SansOuvrir
)

$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'

# ------------------------------------------------------------- les listes
# Premiere liste : les outils de surveillance CONNUS. En trouver un est un
# constat, pas un soupcon. Motifs en minuscules, compares avec -match.
$SURVEILLANCE = @(
    @{ Motif = 'teramind';                    Nom = 'Teramind';            Type = 'surveillance employeur' }
    @{ Motif = 'activtrak';                   Nom = 'ActivTrak';           Type = 'surveillance employeur' }
    @{ Motif = 'veriato|spector';             Nom = 'Veriato/Spector';     Type = 'surveillance employeur' }
    @{ Motif = 'hubstaff';                    Nom = 'Hubstaff';            Type = 'suivi du temps + captures' }
    @{ Motif = 'time ?doctor';                Nom = 'Time Doctor';         Type = 'suivi du temps + captures' }
    @{ Motif = 'kickidler';                   Nom = 'Kickidler';           Type = 'surveillance employeur' }
    @{ Motif = 'interguard';                  Nom = 'InterGuard';          Type = 'surveillance employeur' }
    @{ Motif = 'staffcop';                    Nom = 'StaffCop';            Type = 'surveillance employeur' }
    @{ Motif = 'desktime';                    Nom = 'DeskTime';            Type = 'suivi du temps' }
    @{ Motif = 'workpuls|insightful';         Nom = 'Workpuls/Insightful'; Type = 'surveillance employeur' }
    @{ Motif = 'mspy';                        Nom = 'mSpy';                Type = 'logiciel espion' }
    @{ Motif = 'flexispy';                    Nom = 'FlexiSpy';            Type = 'logiciel espion' }
    @{ Motif = 'eyezy';                       Nom = 'Eyezy';               Type = 'logiciel espion' }
    @{ Motif = 'spyrix';                      Nom = 'Spyrix';              Type = 'keylogger' }
    @{ Motif = 'refog';                       Nom = 'Refog';               Type = 'keylogger' }
    @{ Motif = 'kidlogger';                   Nom = 'KidLogger';           Type = 'keylogger' }
    @{ Motif = 'ardamax';                     Nom = 'Ardamax';             Type = 'keylogger' }
    @{ Motif = 'qustodio';                    Nom = 'Qustodio';            Type = 'controle parental' }
    @{ Motif = 'norton family';               Nom = 'Norton Family';       Type = 'controle parental' }
    @{ Motif = 'net nanny';                   Nom = 'Net Nanny';           Type = 'controle parental' }
    @{ Motif = 'mobicip';                     Nom = 'Mobicip';             Type = 'controle parental' }
    @{ Motif = 'keylog';                      Nom = 'Keylogger (generique)'; Type = 'keylogger' }
)

# Deuxieme liste : les agents d'administration a distance (RMM) et la prise
# en main a distance. Legitimes si c'est TOI qui les as installes ; un signe
# de laisse d'entreprise sinon. On les signale a part.
$ACCES_DISTANCE = @(
    @{ Motif = 'meshagent|mesh agent';               Nom = 'MeshAgent' }
    @{ Motif = 'screenconnect|connectwise';          Nom = 'ScreenConnect/ConnectWise' }
    @{ Motif = 'ateraagent|atera';                   Nom = 'Atera' }
    @{ Motif = 'ninjarmm|ninjaone';                  Nom = 'NinjaOne' }
    @{ Motif = 'centrastage|datto rmm';              Nom = 'Datto RMM' }
    @{ Motif = 'kaseya';                             Nom = 'Kaseya' }
    @{ Motif = 'tacticalrmm|tactical rmm';           Nom = 'Tactical RMM' }
    @{ Motif = 'splashtop streamer';                 Nom = 'Splashtop Streamer' }
    @{ Motif = 'teamviewer';                         Nom = 'TeamViewer' }
    @{ Motif = 'anydesk';                            Nom = 'AnyDesk' }
    @{ Motif = 'rustdesk';                           Nom = 'RustDesk' }
    @{ Motif = 'chrome remote desktop';              Nom = 'Chrome Remote Desktop' }
    @{ Motif = 'dwagent|dwservice';                  Nom = 'DWService' }
)

# ------------------------------------------------------- la collecte (6 sources)
Write-Host 'Collecte en cours (lecture seule)...'

# 1. Logiciels installes
$logiciels = foreach ($cle in @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*')) {
    Get-ItemProperty $cle | Where-Object { $_.DisplayName } | ForEach-Object {
        [pscustomobject]@{ Nom = $_.DisplayName; Detail = "$($_.Publisher)"; Source = 'logiciel installe' }
    }
}

# 2. Services et leurs executables
$services = Get-CimInstance Win32_Service | ForEach-Object {
    [pscustomobject]@{ Nom = "$($_.DisplayName) [$($_.Name)]"; Detail = "$($_.PathName) ($($_.State))"; Source = 'service' }
}

# 3. Processus en cours
$processus = Get-Process | ForEach-Object {
    [pscustomobject]@{ Nom = $_.ProcessName; Detail = "$($_.Path)"; Source = 'processus' }
} | Sort-Object Nom -Unique

# 4. Demarrage : cles Run + dossiers Demarrage (raccourcis resolus)
$demarrage = @()
foreach ($cle in @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run')) {
    $props = Get-ItemProperty $cle
    if ($props) {
        $props.PSObject.Properties | Where-Object { $_.Name -notmatch '^PS' } | ForEach-Object {
            $demarrage += [pscustomobject]@{ Nom = $_.Name; Detail = "$($_.Value)"; Source = 'demarrage (registre)' }
        }
    }
}
$shell = New-Object -ComObject WScript.Shell
foreach ($dossier in @(
        [Environment]::GetFolderPath('Startup'),
        [Environment]::GetFolderPath('CommonStartup'))) {
    Get-ChildItem $dossier -File | ForEach-Object {
        $cible = $_.FullName
        if ($_.Extension -eq '.lnk') { $cible = $shell.CreateShortcut($_.FullName).TargetPath }
        $demarrage += [pscustomobject]@{ Nom = $_.BaseName; Detail = $cible; Source = 'demarrage (dossier)' }
    }
}

# 5. Taches planifiees hors Microsoft
$taches = Get-ScheduledTask | Where-Object {
    $_.TaskPath -notlike '\Microsoft*' -and $_.Author -notlike 'Microsoft*'
} | ForEach-Object {
    $action = ($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join ' ; '
    [pscustomobject]@{ Nom = $_.TaskName; Detail = "$action (auteur : $($_.Author))"; Source = 'tache planifiee' }
}

# 6. Domaine / MDM
$dsreg = (dsregcmd /status) -join "`n"
$domaine = [pscustomobject]@{
    AzureAdJoined    = if ($dsreg -match 'AzureAdJoined\s*:\s*(\S+)') { $Matches[1] } else { '?' }
    DomainJoined     = if ($dsreg -match 'DomainJoined\s*:\s*(\S+)') { $Matches[1] } else { '?' }
    WorkplaceJoined  = if ($dsreg -match 'WorkplaceJoined\s*:\s*(\S+)') { $Matches[1] } else { '?' }
}
# Un vrai enrolement MDM porte un UPN ; les entrees systeme de Windows n'en ont pas.
$mdm = @(Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Enrollments' -ErrorAction SilentlyContinue |
    Where-Object { (Get-ItemProperty $_.PSPath).UPN })

# --------------------------------------------------------------- l'analyse
$inventaire = @($logiciels) + @($services) + @($processus) + @($demarrage) + @($taches)

function Chercher($listeMotifs) {
    foreach ($outil in $listeMotifs) {
        $vus = $inventaire | Where-Object { "$($_.Nom) $($_.Detail)" -match $outil.Motif }
        if ($vus) {
            [pscustomobject]@{
                Nom     = $outil.Nom
                Type    = $outil.Type
                Sources = ($vus | ForEach-Object { "$($_.Source) : $($_.Nom)" } | Sort-Object -Unique) -join ' | '
            }
        }
    }
}

$trouves_surveillance = @(Chercher $SURVEILLANCE)
$trouves_distance     = @(Chercher $ACCES_DISTANCE)
$machine_entreprise   = ($domaine.DomainJoined -eq 'YES') -or ($domaine.AzureAdJoined -eq 'YES') -or ($mdm.Count -gt 0)

# --------------------------------------------------------------- le verdict
if ($trouves_surveillance.Count -eq 0 -and -not $machine_entreprise) {
    $verdict = 'NON : aucun outil de surveillance connu, pas de domaine d''entreprise, pas de MDM.'
} elseif ($trouves_surveillance.Count -gt 0) {
    $verdict = "OUI : $($trouves_surveillance.Count) outil(s) de surveillance detecte(s) - voir le detail."
} else {
    $verdict = 'DOUTEUX : pas d''outil de surveillance connu, mais la machine est rattachee a une organisation (domaine ou MDM).'
}

# --------------------------------------------------------------- le rapport
$L = New-Object System.Collections.Generic.List[string]
$L.Add('# Rapport de surveillance du poste')
$L.Add('')
$L.Add("Machine : $env:COMPUTERNAME - le $(Get-Date -Format 'dd/MM/yyyy HH:mm')")
$L.Add('')
$L.Add("## Verdict : $verdict")
$L.Add('')
if ($trouves_surveillance.Count -gt 0) {
    $L.Add('## Outils de surveillance detectes')
    $L.Add('')
    $L.Add('| Outil | Type | Vu dans |')
    $L.Add('|---|---|---|')
    foreach ($t in $trouves_surveillance) { $L.Add("| $($t.Nom) | $($t.Type) | $($t.Sources) |") }
    $L.Add('')
}
$L.Add('## Rattachement a une organisation')
$L.Add('')
$L.Add("- Domaine Windows : $($domaine.DomainJoined) - Azure AD : $($domaine.AzureAdJoined) - Compte pro ajoute : $($domaine.WorkplaceJoined)")
$L.Add("- Enrolements MDM reels (avec UPN) : $($mdm.Count)")
$L.Add('')
if ($trouves_distance.Count -gt 0) {
    $L.Add('## Acces a distance presents (legitimes si installes par toi)')
    $L.Add('')
    foreach ($t in $trouves_distance) { $L.Add("- **$($t.Nom)** - $($t.Sources)") }
    $L.Add('')
    $L.Add('Si tu ne reconnais pas l''un d''eux, c''est lui le suspect numero un.')
    $L.Add('')
}
$L.Add('## Les limites de ce verdict (a lire)')
$L.Add('')
$L.Add('Ce verdict n''est PAS une garantie. L''outil compare la machine a une liste')
$L.Add('d''outils de surveillance CONNUS. Un verdict NON veut dire : aucun signe')
$L.Add('connu trouve - pas : impossible qu''on te surveille.')
$L.Add('')
$L.Add('Ce qui lui echappe par construction :')
$L.Add('- un espion fait sur mesure, renomme, ou cache plus profond (rootkit) ;')
$L.Add('- la surveillance cote RESEAU (box, VPN, reseau du travail) : elle ne se voit pas depuis ce poste.')
$L.Add('')
$L.Add('Si le doute est serieux : reinstallation propre de Windows, et mots de passe')
$L.Add('changes depuis un AUTRE appareil.')
$L.Add('')
$L.Add('## Ce qui a ete passe en revue')
$L.Add('')
$L.Add("- $(@($logiciels).Count) logiciels installes (registre 32/64 bits + utilisateur)")
$L.Add("- $(@($services).Count) services Windows")
$L.Add("- $(@($processus).Count) processus en cours")
$L.Add("- $(@($demarrage).Count) entrees de demarrage (registre + dossiers)")
$L.Add("- $(@($taches).Count) taches planifiees hors Microsoft")
$L.Add('- statut domaine/MDM via dsregcmd et la cle Enrollments')
$L.Add('')
$L.Add('Lecture seule : rien n''a ete modifie, rien n''a ete envoye.')

$L | Out-File -FilePath $Sortie -Encoding utf8

# --------------------------------------------------------------- la page web
# Le rapport Markdown est pour la machine et les archives ; la page web est
# pour l'humain : le verdict en grand, explique simplement, aux couleurs de
# la tour (fond #020817, cartes #0f172a, bleu #3b82f6). Les accents passent
# par des entites HTML pour que ce script reste en ASCII pur.
function Enc([string]$s) {
    if (-not $s) { return '' }
    ($s -replace '&', '&amp;') -replace '<', '&lt;' -replace '>', '&gt;'
}
function OuiNon([string]$v) {
    if ($v -eq 'YES') { return '<span class="puce mauvais">Oui</span>' }
    if ($v -eq 'NO')  { return '<span class="puce ok">Non</span>' }
    return "<span class=""puce"">$(Enc $v)</span>"
}

if ($trouves_surveillance.Count -eq 0 -and -not $machine_entreprise) {
    $couleur = '#22c55e'; $glyphe = '&#10003;'
    $titreVerdict = 'Personne ne te surveille'
    $sousTitre = 'Aucun outil de surveillance connu, pas de domaine d&rsquo;entreprise, pas de MDM.'
} elseif ($trouves_surveillance.Count -gt 0) {
    $couleur = '#ef4444'; $glyphe = '&#10005;'
    $titreVerdict = 'Un outil de surveillance est install&eacute;'
    $sousTitre = 'Le d&eacute;tail est juste en dessous. Avant de paniquer : certains outils sont install&eacute;s volontairement (contr&ocirc;le parental, suivi du temps choisi).'
} else {
    $couleur = '#f59e0b'; $glyphe = '!'
    $titreVerdict = 'Pas d&rsquo;espion connu, mais la machine est rattach&eacute;e &agrave; une organisation'
    $sousTitre = 'Un domaine ou un enr&ocirc;lement MDM a &eacute;t&eacute; d&eacute;tect&eacute; : cette organisation peut administrer le poste.'
}

$blocs = ''
if ($trouves_surveillance.Count -gt 0) {
    $lignes = ($trouves_surveillance | ForEach-Object {
        "<tr><td>$(Enc $_.Nom)</td><td>$(Enc $_.Type)</td><td>$(Enc $_.Sources)</td></tr>"
    }) -join "`n"
    $blocs += '<section class="carte"><h2>Ce qui a &eacute;t&eacute; trouv&eacute;</h2>' +
        '<table><tr><th>Outil</th><th>Type</th><th>Vu dans</th></tr>' + $lignes + '</table>' +
        '<p class="note">Si tu n&rsquo;as pas install&eacute; ces outils toi-m&ecirc;me, quelqu&rsquo;un d&rsquo;autre l&rsquo;a fait.</p></section>'
}
$blocs += '<section class="carte limites"><h2>Ce que ce verdict garantit &mdash; et ce qu&rsquo;il ne garantit pas</h2>' +
    '<p>L&rsquo;outil compare ta machine &agrave; une liste d&rsquo;outils de surveillance <b>connus</b>. Un verdict vert veut dire : <b>aucun signe connu trouv&eacute;</b> &mdash; pas &laquo; impossible qu&rsquo;on te surveille &raquo;.</p>' +
    '<ul><li>Un espion fait sur mesure, renomm&eacute;, ou cach&eacute; plus profond (rootkit) peut lui &eacute;chapper.</li>' +
    '<li>La surveillance c&ocirc;t&eacute; r&eacute;seau (box, VPN, r&eacute;seau du travail) ne se voit pas depuis ce poste.</li>' +
    '<li>Si le doute est s&eacute;rieux : r&eacute;installation propre de Windows, et mots de passe chang&eacute;s depuis un <b>autre</b> appareil.</li></ul></section>'
$blocs += '<section class="carte"><h2>Rattachement &agrave; une organisation</h2>' +
    '<div class="ligne"><span>Domaine d&rsquo;entreprise</span>' + (OuiNon $domaine.DomainJoined) + '</div>' +
    '<div class="ligne"><span>Compte professionnel (Azure AD)</span>' + (OuiNon $domaine.AzureAdJoined) + '</div>' +
    '<div class="ligne"><span>Enr&ocirc;lement MDM r&eacute;el</span>' +
    $(if ($mdm.Count -gt 0) { '<span class="puce mauvais">Oui (' + $mdm.Count + ')</span>' } else { '<span class="puce ok">Non</span>' }) +
    '</div></section>'
if ($trouves_distance.Count -gt 0) {
    $items = ($trouves_distance | ForEach-Object { "<li><b>$(Enc $_.Nom)</b> &mdash; $(Enc $_.Sources)</li>" }) -join "`n"
    $blocs += '<section class="carte"><h2>Acc&egrave;s &agrave; distance pr&eacute;sents</h2><ul>' + $items + '</ul>' +
        '<p class="note">L&eacute;gitimes si c&rsquo;est toi qui les as install&eacute;s. Un nom que tu ne reconnais pas ici, c&rsquo;est le suspect num&eacute;ro un.</p></section>'
}

$gabarit = @'
<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rapport de surveillance</title>
<style>
:root{--fond:#020817;--carte:#0f172a;--bord:#1e293b;--texte:#e2e8f0;--sourd:#94a3b8;--bleu:#3b82f6;--accent:%%COULEUR%%}
*{box-sizing:border-box;margin:0}
body{background:var(--fond);color:var(--texte);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:40px 16px}
main{max-width:760px;margin:0 auto;display:grid;gap:16px}
header{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
header .marque{font-weight:700;letter-spacing:.02em}
header .marque span{color:var(--bleu)}
header small{color:var(--sourd)}
.carte{background:var(--carte);border:1px solid var(--bord);border-radius:.5rem;padding:24px;transition:transform .15s ease,border-color .15s ease,box-shadow .15s ease}
.carte:hover{transform:translateY(-2px);border-color:#334155;box-shadow:0 8px 24px rgba(0,0,0,.35)}
.hero{display:flex;align-items:center;gap:20px;border-left:4px solid var(--accent)}
.pastille{flex:none;width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:30px;font-weight:700;color:#fff;background:var(--accent)}
.hero h1{font-size:1.5rem;line-height:1.3}
.hero p{color:var(--sourd);margin-top:4px}
h2{font-size:1.05rem;margin-bottom:12px;color:var(--bleu)}
table{width:100%;border-collapse:collapse;font-size:.95rem}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--bord)}
th{color:var(--sourd);font-weight:600}
tr:hover td{background:rgba(30,41,59,.5)}
ul{padding-left:20px}
.note{color:var(--sourd);font-size:.9rem;margin-top:12px}
.grille{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px}
.tuile{background:#1e293b;border-radius:.5rem;padding:14px;text-align:center;transition:transform .15s ease}
.tuile:hover{transform:translateY(-2px)}
.tuile b{display:block;font-size:1.6rem;color:#fff}
.tuile span{color:var(--sourd);font-size:.85rem}
.ligne{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--bord)}
.ligne:last-child{border-bottom:none}
.puce{font-weight:700;padding:2px 12px;border-radius:999px;font-size:.85rem;background:#1e293b;color:var(--texte)}
.puce.ok{background:rgba(34,197,94,.13);color:#4ade80}
.puce.mauvais{background:rgba(239,68,68,.13);color:#f87171}
footer{color:var(--sourd);font-size:.85rem;text-align:center;padding:8px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head>
<body><main>
<header><div class="marque">Tour de <span>contr&ocirc;le</span> &mdash; d&eacute;tecteur de surveillance</div><small>%%MACHINE%% &mdash; %%DATE%%</small></header>
<section class="carte hero"><div class="pastille">%%GLYPHE%%</div><div><h1>%%TITREVERDICT%%</h1><p>%%SOUSTITRE%%</p></div></section>
%%BLOCS%%
<section class="carte"><h2>Ce qui a &eacute;t&eacute; pass&eacute; en revue</h2><div class="grille">
<div class="tuile"><b>%%NBLOG%%</b><span>logiciels install&eacute;s</span></div>
<div class="tuile"><b>%%NBSVC%%</b><span>services Windows</span></div>
<div class="tuile"><b>%%NBPROC%%</b><span>processus en cours</span></div>
<div class="tuile"><b>%%NBDEM%%</b><span>lancements au d&eacute;marrage</span></div>
<div class="tuile"><b>%%NBTACHES%%</b><span>t&acirc;ches planifi&eacute;es</span></div>
</div></section>
<footer>Lecture seule : rien n&rsquo;a &eacute;t&eacute; modifi&eacute;, rien n&rsquo;a &eacute;t&eacute; envoy&eacute;.</footer>
</main></body></html>
'@

$SortieHtml = [System.IO.Path]::ChangeExtension($Sortie, 'html')
$page = $gabarit.
    Replace('%%COULEUR%%', $couleur).
    Replace('%%GLYPHE%%', $glyphe).
    Replace('%%TITREVERDICT%%', $titreVerdict).
    Replace('%%SOUSTITRE%%', $sousTitre).
    Replace('%%BLOCS%%', $blocs).
    Replace('%%MACHINE%%', (Enc $env:COMPUTERNAME)).
    Replace('%%DATE%%', (Get-Date -Format 'dd/MM/yyyy HH:mm')).
    Replace('%%NBLOG%%', @($logiciels).Count).
    Replace('%%NBSVC%%', @($services).Count).
    Replace('%%NBPROC%%', @($processus).Count).
    Replace('%%NBDEM%%', @($demarrage).Count).
    Replace('%%NBTACHES%%', @($taches).Count)
$page | Out-File -FilePath $SortieHtml -Encoding utf8

Write-Host ''
Write-Host "VERDICT : $verdict"
Write-Host ''
Write-Host 'Ce verdict n''est PAS une garantie : l''outil compare a une liste d''outils'
Write-Host 'CONNUS. Un espion sur mesure, renomme ou cache plus profond (rootkit) peut'
Write-Host 'lui echapper, et la surveillance cote reseau ne se voit pas depuis ce poste.'
Write-Host ''
Write-Host "Rapport : $Sortie"
Write-Host "Page    : $SortieHtml"
if (-not $SansOuvrir) { Start-Process $SortieHtml }
