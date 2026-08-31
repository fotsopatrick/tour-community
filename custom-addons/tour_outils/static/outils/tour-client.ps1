<#
    Tour de controle - petit client JSON-RPC pour PowerShell
    --------------------------------------------------------
    Sert aux outils qui tournent sur le POSTE (le Bureau Windows, l'inventaire
    des logiciels) et qui doivent deposer leur resultat dans la tour, qui elle
    vit sur un serveur et ne voit pas la machine.

    N'utilise que des modeles standard (project.task) ou des modeles de la tour
    (depot.note) via call_kw : aucune route maison, donc rien a installer
    cote serveur.

    A sourcer :  . .\tour-client.ps1
#>

function ConvertTo-HtmlSimple {
    <# Markdown pauvre -> HTML lisible dans un champ description Odoo. #>
    param([Parameter(Mandatory)][string]$Texte)
    $lignes = $Texte -split "`r?`n"
    $sb = New-Object System.Text.StringBuilder
    $dansListe = $false
    foreach ($l in $lignes) {
        $e = [System.Web.HttpUtility]::HtmlEncode($l)
        if ($null -eq $e) { $e = '' }
        # gras markdown -> <b>
        $e = [regex]::Replace($e, '\*\*(.+?)\*\*', '<b>$1</b>')
        if ($l -match '^\s*-\s+') {
            if (-not $dansListe) { $null = $sb.Append('<ul>'); $dansListe = $true }
            $null = $sb.Append('<li>' + ($e -replace '^\s*-\s+', '') + '</li>')
            continue
        }
        if ($dansListe) { $null = $sb.Append('</ul>'); $dansListe = $false }
        switch -Regex ($l) {
            '^#### ' { $null = $sb.Append('<h5>' + ($e -replace '^#### ', '') + '</h5>'); break }
            '^### ' { $null = $sb.Append('<h4>' + ($e -replace '^### ', '') + '</h4>'); break }
            '^## ' { $null = $sb.Append('<h3>' + ($e -replace '^## ', '') + '</h3>'); break }
            '^# ' { $null = $sb.Append('<h2>' + ($e -replace '^# ', '') + '</h2>'); break }
            '^\s*$' { break }
            default { $null = $sb.Append('<p>' + $e + '</p>') }
        }
    }
    if ($dansListe) { $null = $sb.Append('</ul>') }
    return $sb.ToString()
}

function Invoke-TourRpc {
    param(
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][string]$Route,
        [hashtable]$Params = @{},
        $WebSession
    )
    $corps = @{ jsonrpc = '2.0'; method = 'call'; params = $Params } | ConvertTo-Json -Depth 12 -Compress
    $octets = [Text.Encoding]::UTF8.GetBytes($corps)
    $req = @{
        Uri         = ($Url.TrimEnd('/') + $Route)
        Method      = 'Post'
        Body        = $octets
        ContentType = 'application/json; charset=utf-8'
    }
    if ($WebSession) { $req.WebSession = $WebSession } else { $req.SessionVariable = 'nouvelle' }
    $reponse = Invoke-RestMethod @req
    if ($reponse.error) {
        $msg = $reponse.error.data.message
        if (-not $msg) { $msg = $reponse.error.message }
        throw "Tour : $msg"
    }
    if (-not $WebSession) {
        return [pscustomobject]@{ Resultat = $reponse.result; Session = $nouvelle }
    }
    return $reponse.result
}

function Connexion-Tour {
    <# Rend un objet session a passer aux autres fonctions. #>
    param(
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][string]$Base,
        [Parameter(Mandatory)][string]$Login,
        [Parameter(Mandatory)][string]$Mdp
    )
    Add-Type -AssemblyName System.Web -ErrorAction SilentlyContinue
    $r = Invoke-TourRpc -Url $Url -Route '/web/session/authenticate' -Params @{
        db = $Base; login = $Login; password = $Mdp
    }
    if (-not $r.Resultat.uid) { throw "Connexion refusee (base '$Base', login '$Login')." }
    return [pscustomobject]@{
        Url = $Url.TrimEnd('/'); Base = $Base; Uid = $r.Resultat.uid; Web = $r.Session
    }
}

function Appel-Modele {
    param(
        [Parameter(Mandatory)]$Session,
        [Parameter(Mandatory)][string]$Modele,
        [Parameter(Mandatory)][string]$Methode,
        [object[]]$Arguments = @(),
        [hashtable]$Kwargs = @{}
    )
    return Invoke-TourRpc -Url $Session.Url -Route '/web/dataset/call_kw' -WebSession $Session.Web -Params @{
        model = $Modele; method = $Methode; args = $Arguments; kwargs = $Kwargs
    }
}

function Creer-Enregistrement {
    param(
        [Parameter(Mandatory)]$Session,
        [Parameter(Mandatory)][string]$Modele,
        [Parameter(Mandatory)][hashtable]$Valeurs
    )
    return Appel-Modele -Session $Session -Modele $Modele -Methode 'create' -Arguments @(, $Valeurs)
}
