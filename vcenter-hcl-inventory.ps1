param
(
    [string]$j,
    [switch]$force
    # $(throw "-j is required. It is the Source of Data for the Script.")
    #[string]$placeholder = "" #not a required switch allows targeting VM's based upon cluster
)

# Get script directory and set working directory
$jsonData = Get-Content -Path $j | ConvertFrom-Json
$todaysDate = (Get-Date).tostring("yyyy-MM-dd_HH-mm-ss")

$vcenters = @()
foreach ($k in $jsonData.vcenters.PSObject.Properties) {
    $vcenters += $k.value.name
}

$computer_name = [Environment]::MachineName
#=============================================================================
# Setup Environment
#=============================================================================
${env_vars} = Get-Childitem -Path Env:* | Sort-Object Name
if ((${env_vars} | Where-Object {$_.Name -eq "OS"}).Value -eq "Windows_NT") {
    $homePath = (${env_vars} | Where-Object {$_.Name -eq "HOMEPATH"}).Value
    $pathSep  = "\"
} else {
    $homePath = (${env_vars} | Where-Object {$_.Name -eq "HOME"}).Value
    $pathSep  = "/"
}
$log_dir = $homePath + $pathSep + "Logs"
if (!( Test-Path -PathType Container $log_dir)) {
    New-Item -ItemType Directory $log_dir | Out-Null
}
$credential_path = $homePath + $pathSep + "powercli.Cred"
If (Test-Path -PathType Leaf $credential_path) {
    $credential = Import-CliXml -Path $credential_path
} Else {
    $credential = Get-Credential
    $credential | Export-CliXml -Path $credential_path
}
# Import VMware PS modules
$required_modules = @("VMware.PowerCLI")
foreach ($rm in $required_modules) {
    if (!(Get-Module -ListAvailable -Name $rm)) {
        Write-Host " * $($computer_name) Installing $rm." -ForegroundColor Green
        Install-Module $rm -Confirm:$False -Force
        Import-Module $rm
    } else {
        Write-Host " * $($computer_name) $rm Already Installed." -ForegroundColor Cyan
        Import-Module $rm
    }
}
# User must install powerCLI: Install-Module VMware.PowerCLI -Scope CurrentUser
Set-PowerCLIConfiguration -Scope Session -WebOperationTimeoutSeconds 3600 -InvalidCertificateAction Ignore -Confirm:$false
Set-PowerCLIConfiguration -Scope User -ParticipateInCEIP $True -Confirm:$False

# Set Output PowerShell Object
$Output = @()

foreach($vcenter in $vcenters) {
    Write-Host "Connect to vcenter $vcenter"
    if ($vcenter) {
        try {
            $null = Connect-viserver $vcenter -Credential $credential
        }
        catch {
            Write-Host "There was an issue with connecting to $vcenter"
            Exit(1)
        }
    }
    else {
        Write-Host "Unable to Connect to the vCenter."
        Exit(1)
    }
    # Get collection of Clusters and hosts
    Get-Cluster | ForEach-Object {
        $cluster = $_
        write-host "Cluster is $cluster"
        $cluster | Get-VMHost | Where-Object {$_.ConnectionState -eq “Connected”} | ForEach-Object {
            $vmhost = $_
            write-host "ESX host is $vmhost"
            $esxHost = Get-EsxCli -VMHost $vmhost;
            $physServer = $esxHost.hardware.platform.get().SerialNumber | Select-Object @{N='Hostname';E={$vmhost}}, @{N='Serial';E={$_}};
            $hostVibs = $esxHost.software.vib.list() | Select-Object ID,InstallDate,Name,Vendor,Version | Where-Object {$_.Name -match "ucs-tool-esxi"};

            # Merge Output from phyServer and hostVibs
            $OutputItem = New-Object PSObject;
            $OutputItem | Add-Member NoteProperty "Hostname" $physServer.Hostname;
            $OutputItem | Add-Member NoteProperty "Serial" $physServer.Serial;
            $OutputItem | Add-Member NoteProperty "vCenter" $vcenter
            $OutputItem | Add-Member NoteProperty "Cluster" $cluster.Name
            $OutputItem | Add-Member NoteProperty "ID" $hostVibs.ID;
            $OutputItem | Add-Member NoteProperty "InstallDate" $hostVibs.InstallDate;
            $OutputItem | Add-Member NoteProperty "Name" $hostVibs.Name;
            $OutputItem | Add-Member NoteProperty "Vendor" $hostVibs.Vendor;
            $OutputItem | Add-Member NoteProperty "Version" $hostVibs.Version;

            # Add OutputItem to Output Object
            $Output += $OutputItem;
        }
    }
    write-host "Disconnecting from vCenter $vcenter"
    $null = Disconnect-VIServer $vcenter -Force -Confirm:$false
}
# Save the Output to a JSON File
$Output | ConvertTo-Json -depth 100 | Out-File "$todaysDate.json"

#Stop-Transcript
Exit