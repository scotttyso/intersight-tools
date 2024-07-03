<#
Copyright (c) 2024 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.0 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
.SYNOPSIS
    Script to Register Cluster Nodes to Arc for the AzureStack HCI Cisco Validated Design

.DESCRIPTION
    Script to Register Cluster Nodes to Arc for the AzureStack HCI Cisco Validated Design

.PARAMETER <y>
    YAML Input File containing Cluster Parameters.   

.EXAMPLE
    azs-hci-arcprep.ps1 -y azs-answers.yaml
#>
#=============================================================================
# YAML File is a Required Parameter
# Pull in YAML Content
#=============================================================================
param ([string]$y=$(throw "-y <yaml_file.yaml> is required."))
#=============================================================================
# Validate Running with Administrator Privileges
#=============================================================================
if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')) {
    Write-Host ""
    Write-Host "Script must run with elevated Administrator permissions...Exiting" -Foreground Yellow
    Write-Host "...Exiting"
    Write-Host ""
    Exit 1
}
#=============================================================================
# Check Environment for Required Variables
#=============================================================================
$environment_variables = @("azure_stack_subscription", "azure_stack_tenant")
foreach ($req_env in $environment_variables) {
    if (!([Environment]::GetEnvironmentVariable($req_env))) {
        Write-Host ""
        Write-Host "You Must Set the Following Environment Variables before Running This Script" -ForegroundColor Yellow
        Write-Host "  * `$env:azure_stack_subscription - Subscription for Azure" -ForegroundColor Green
        Write-Host "  * `$env:azure_stack_tenant - Tenant for Azure" -ForegroundColor Green
        Write-Host "  * `$env:proxy_password - Only Required if Using a Proxy Server with Authentication" -ForegroundColor Green
        Write-Host "...Exiting"
        Write-Host ""
        Exit 1
    }
}
#=============================================================================
# Setup Environment
#=============================================================================
$computer_name = ([System.Net.DNS]::GetHostByName('').HostName).Split(".")[0]
${env_vars} = Get-Childitem -Path Env:* | Sort-Object Name
if ((${env_vars} | Where-Object {$_.Name -eq "OS"}).Value -eq "Windows_NT") {
    $homePath = (${env_vars} | Where-Object {$_.Name -eq "HOMEPATH"}).Value
    $pathSep  = "\"
} else {
    $homePath = (${env_vars} | Where-Object {$_.Name -eq "HOME"}).Value
    $pathSep  = "/"
}
#=============================================================================
# Log Setup
#=============================================================================
$log_dir = $homePath + $pathSep + "Logs"
if (!( Test-Path -PathType Container $log_dir)) { New-Item -ItemType Directory $log_dir | Out-Null }
Start-Transcript -Path ".\Logs\$(get-date -f "yyyy-MM-dd_HH-mm-ss")_$($env:USER).log" -Append -Confirm:$false
#=============================================================================
# Validate NuGet is Running Minimum Version 2.8.5.201
#=============================================================================
Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Confirm:$False -Force
#=============================================================================
# Install PowerShell Modules
#=============================================================================
Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
$required_modules = @("PowerShellGet", "powershell-yaml", "Az.Accounts", "Az.Resources", "Az.ConnectedMachine", "AzsHCI.ARCinstaller")
foreach ($rm in $required_modules) {
    if (!(Get-Module -ListAvailable -Name $rm)) {
        Write-Host " * $computer_name`: Installing $rm." -ForegroundColor Green
        Install-Module $rm -AllowClobber -Confirm:$False -Force
        Import-Module $rm
    } else {
        Write-Host " * $computer_name`: $rm Already Installed." -ForegroundColor Cyan
        Import-Module $rm
    }
}
#=============================================================================
# Import YAML Data
#=============================================================================
$global_node_list = [object[]] @()
$ydata            = Get-Content -Path $y | ConvertFrom-Yaml
foreach ($cluster in $ydata.clusters) { foreach ($node in $cluster.members) { $global_node_list += $node } }
#=============================================================================
# Setup Proxy Authentication if Needed
#=============================================================================
$proxy_creds = ''
if ($ydata.proxy) {
    if ($ydata.proxy.username) {
        $proxy_user  = $ydata.proxy.username
        $proxy_pass  = ConvertTo-SecureString $env:proxy_password -AsPlainText -Force;
        $proxy_creds = New-Object System.Management.Automation.PSCredential ($proxy_user,$proxy_pass);
    }
}
#=========================================================================
# Clean Inventory Storage Drives that will be used by Storage Spaces Direct
#=========================================================================
Update-StorageProviderCache
Get-StoragePool | Where-Object IsPrimordial -eq $false | Set-StoragePool -IsReadOnly:$false -ErrorAction SilentlyContinue
Get-StoragePool | Where-Object IsPrimordial -eq $false | Get-VirtualDisk | Remove-VirtualDisk -Confirm:$false -ErrorAction SilentlyContinue
Get-StoragePool | Where-Object IsPrimordial -eq $false | Remove-StoragePool -Confirm:$false -ErrorAction SilentlyContinue
Get-PhysicalDisk | Reset-PhysicalDisk -ErrorAction SilentlyContinue
Get-Disk | Where-Object Number -ne $null | Where-Object IsBoot -ne $true | Where-Object IsSystem -ne $true | Where-Object PartitionStyle -ne RAW |
    ForEach-Object {
        $_ | Set-Disk -isoffline:$false
        $_ | Set-Disk -isreadonly:$false
        $_ | Clear-Disk -RemoveData -RemoveOEM -Confirm:$false
        $_ | Set-Disk -isreadonly:$true
        $_ | Set-Disk -isoffline:$true
    } 
#Inventory Storage Disks
Get-Disk | Where-Object Number -Ne $Null | Where-Object IsBoot -Ne $True | Where-Object IsSystem -Ne $True | Where-Object PartitionStyle -Eq RAW | 
    Group-Object -NoElement -Property FriendlyName | Format-Table
#=========================================================================
# Install Microsoft-Hyper-V
#=========================================================================
$hyperv = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V
if ($hyperv.State -eq "Disabled") {
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
} else { Write-Host " * $computer_name`: Microsoft-Hyper-V Already Installed." -ForegroundColor Cyan }
#=========================================================================
# Import PowerShell Modules
#=========================================================================
$required_modules = @("Az.Accounts", "Az.Resources", "Az.ConnectedMachine", "AzsHCI.ARCinstaller")
foreach ($rm in $required_modules) { Import-Module $rm }
#=========================================================================
# Register Host with Azure Arc
#=========================================================================
$region = $ydata.azure_stack.region
$RG     = $ydata.azure_stack.resource_group
$SUB    = $env:azure_stack_subscription
$TNT    = $env:azure_stack_tenant
Update-AzConfig -EnableLoginByWam $False
Connect-AzAccount -SubscriptionID $SUB -TenantId $TNT -DeviceCode
$ARMtoken  = (Get-AzAccessToken).Token
$id        = (Get-AzContext).Account.Id
if (!($ydata.proxy)) {
    Write-Host " * $computer_name`: Registering with Azure ARC." -ForegroundColor Cyan
    Invoke-AzStackHciArcInitialization -SubscriptionID $SUB -ResourceGroup $RG -TenantID $TNT -Region $region `
        -Cloud "AzureCloud" -ArmAccessToken $ARMtoken -AccountID $id
    Write-Host " * $computer_name`: Completed Registration with Azure ARC.  Review Output to Confirm Successful Registration." -ForegroundColor Green
} else {
    if ($Using:proxy_creds) {
        Write-Host " * $computer_name`: Registering with Azure ARC." -ForegroundColor Cyan
        Invoke-AzStackHciArcInitialization -SubscriptionID $SUB -ResourceGroup $RG -TenantID $TNT -Region $region `
            -Cloud "AzureCloud" -ArmAccessToken $ARMtoken -AccountID $id -Proxy $ydata.proxy.host -ProxyCredential $Using:proxy_creds
        Write-Host " * $computer_name`: Completed Registration with Azure ARC.  Review Output to Confirm Successful Registration." -ForegroundColor Green
    } else {
        Write-Host " * $computer_name`: Registering with Azure ARC." -ForegroundColor Cyan
        Invoke-AzStackHciArcInitialization -SubscriptionID $SUB -ResourceGroup $RG -TenantID $TNT -Region $region `
            -Cloud "AzureCloud" -ArmAccessToken $ARMtoken -AccountID $id -Proxy $ydata.proxy.host }
        Write-Host " * $computer_name`: Completed Registration with Azure ARC.  Review Output to Confirm Successful Registration." -ForegroundColor Green
    }
Update-AzConfig -EnableLoginByWam $True
#=============================================================================
# ICMPv4 Firewall Policy
#=============================================================================
Write-Host "Do you want to Allow ICMP for Manageability?"
$answer = Read-Host "Enter 'Y' or 'N'"
if ($answer -eq "Y") {
    Write-Host "Creating Rule to allow ICMPv4 in the Advanced Firewall Policy." -ForegroundColor Green
    netsh advfirewall firewall add rule name="Allow ICMPv4" protocol=icmpv4:8,any dir=in action=allow
} else { Write-Host "Skipping in the Advanced Firewall Policy." -ForegroundColor Green }
#=============================================================================
# Cleanup Script and Exit
#=============================================================================
Write-Host " * $computer_name`: Script Complete.  Closing Environment." -ForegroundColor Green
Stop-Transcript
Exit 0
