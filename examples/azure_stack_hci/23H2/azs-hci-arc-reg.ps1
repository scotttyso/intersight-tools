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
vim Intersight/wizard/setup.yaml
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
$environment_variables = @("azure_stack_subscription", "azure_stack_tenant", "windows_administrator_password")
foreach ($req_env in $environment_variables) {
    if (!([Environment]::GetEnvironmentVariable($req_env))) {
        Write-Host ""
        Write-Host "You Must Set the Following Environment Variables before Running This Script" -ForegroundColor Yellow
        Write-Host "  * `$env:azure_stack_subscription=`"<your_subscription>`" - Subscription for Azure" -ForegroundColor Green
        Write-Host "  * `$env:azure_stack_tenant=`"<your_subscription>`" - Tenant for Azure" -ForegroundColor Green
        Write-Host "  * `$env:proxy_password=`"<proxy_password>`" - Only Required if Using a Proxy Server with Authentication" -ForegroundColor Green
        Write-Host "  * `$env:windows_administrator_password=`"<local_administrator_password>`" - Azure Stack Local Administrator Password" -ForegroundColor Green
        Write-Host "...Exiting"
        Write-Host ""
        Exit 1
    }
}
#=============================================================================
# Setup Environment
#=============================================================================
$azure_subscription = $env:azure_stack_subscription
$azure_tenant       = $env:azure_stack_tenant
$computer_name      = ([System.Net.DNS]::GetHostByName('').HostName).Split(".")[0]
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
# Import YAML Data
#=============================================================================
$global_node_list = [object[]] @()
$ydata            = Get-Content -Path $y | ConvertFrom-Yaml
foreach ($cluster in $ydata.clusters) { foreach ($node in $cluster.members) { $global_node_list += $node } }
#=============================================================================
# Install PowerShell Modules
#=============================================================================
Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
$required_modules = @("PowerShellGet", "powershell-yaml")
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
#=============================================================================
# Function: Node Length Check and Reboot Check
#=============================================================================
Function NodeAndRebootCheck {
    Param([psobject]$session_results, [array]$node_list)
    #$session_results | Format-Table | Out-String|ForEach-Object {Write-Host $_}
    $nodes = [object[]] @()
    $reboot_count = 0
    foreach ($result in $session_results) {
        if ($result.completed -eq $True) { $nodes += $result.PSComputerName}
        if ($result.reboot -eq $True) { $reboot_count++ | Out-Null }
    }
    Get-PSSession | Remove-PSSession | Out-Null
    if (!($nodes.Length -eq $node_list.Length)) {
        Write-Host "One or More Nodes Failed on Previous Task." -ForegroundColor Red
        Write-Host " * Original Node List: $node_list" -ForegroundColor Red
        Write-Host " * Completed Node List: $nodes" -ForegroundColor Red
        Write-Host "Please Review the Log Data.  Exiting..." -ForegroundColor Red
        Disable-WSManCredSSP -Role "Client" | Out-Null
        Stop-Transcript
        Exit 1
    }
    Return New-Object PsObject -property @{computer_names=$nodes;reboot_count=$reboot_count}
}
#=============================================================================
# Function: Login to AzureStack HCI Node List
#=============================================================================
Function LoginNodeList {
    Param([string]$cssp, [array]$node_list)
    #Param([pscredential]$credential, [string]$cssp, [array]$node_list)
    if ($credssp -eq $True) {
        try {
            foreach ($node in $node_list) {
                Write-Host "Logging into Host $($node)" -ForegroundColor Yellow
                $hostname   = $node.split("@")[0]
                $password   = ConvertTo-SecureString $env:windows_administrator_password -AsPlainText -Force;
                $credential = New-Object System.Management.Automation.PSCredential ("$hostname\Administrator",$password);
                New-PSSession -ComputerName $node -Credential $credential -Authentication Credssp | Out-Null
            }
        } catch {
            Write-Host "Failed to Login to one of the Hosts" -ForegroundColor Red
            Write-Host $_.Exception.Message
            Exit 1
        }
    } else {
        try {
            foreach ($node in $node_list) {
                Write-Host "Logging into Host $($node)" -ForegroundColor Yellow
                $hostname   = $node.split("@")[0]
                $password   = ConvertTo-SecureString $env:windows_administrator_password -AsPlainText -Force;
                $credential = New-Object System.Management.Automation.PSCredential ("$hostname\Administrator",$password);
                New-PSSession -ComputerName $node -Credential $credential | Out-Null
            }
        } catch {
            Write-Host "Failed to Login to one of the Hosts" -ForegroundColor Red
            Write-Host $_.Exception.Message
            Exit 1
        }
    }
}
Get-PSSession | Remove-PSSession | Out-Null
#=============================================================================
# Install Modules and Register with Azure Arc
#=============================================================================
LoginNodeList -cssp $False -node_list $global_node_list
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
$session_results = Invoke-Command $sessions -ScriptBlock {
    $computer_name = ([System.Net.DNS]::GetHostByName('').HostName).Split(".")[0]
    $ydata = $Using:ydata
    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
    #=============================================================================
    # Validate NuGet is Running Minimum Version 2.8.5.201
    #=============================================================================
    Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Confirm:$False -Force
    #=========================================================================
    # Install PowerShell Modules
    #=========================================================================
    $required_modules = @("PowerShellGet", "Az.Accounts", "Az.Resources", "Az.ConnectedMachine", "AzsHCI.ARCinstaller")
    foreach ($rm in $required_modules) {
        if (!(Get-Module -ListAvailable -Name $rm)) {
            Write-Host " * $computer_name`: Installing '$rm'." -ForegroundColor Green
            Install-Module $rm -AllowClobber -Confirm:$False -Force
            Import-Module $rm
        } else {
            Write-Host " * $computer_name`: '$rm' Already Installed." -ForegroundColor Cyan
            Import-Module $rm
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
    $reboot = $False
    $hyperv = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V
    if ($hyperv.State -eq "Disabled") {
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
        $reboot = $True
    } else { Write-Host " * $computer_name`: Microsoft-Hyper-V Already Installed." -ForegroundColor Cyan }
    Return New-Object PsObject -property @{completed=$True;reboot=$reboot}
}
#=============================================================================
# Setup Environment for Next Loop; Sleep 10 Minutes if reboot_count gt 0
#=============================================================================
Get-PSSession | Remove-PSSession | Out-Null
$nrc = NodeAndRebootCheck -session_results $session_results -node_list $global_node_list
if ($nrc.reboot_count -gt 0) {
    Write-Host "Sleeping for 10 Minutes to Wait for Server Reboots." -ForegroundColor Yellow
    Start-Sleep -Seconds 600
}
#=============================================================================
# Install Modules and Register with Azure Arc
#=============================================================================
LoginNodeList -cssp $False -node_list $global_node_list
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
$session_results = Invoke-Command $sessions -ScriptBlock {
    $computer_name = ([System.Net.DNS]::GetHostByName('').HostName).Split(".")[0]
    $ydata = $Using:ydata
    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
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
    $SUB    = $Using:azure_subscription
    $TNT    = $Using:azure_tenant
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
    Return New-Object PsObject -property @{completed=$True;reboot=$reboot}
}
#=============================================================================
# Cleanup the Script
#=============================================================================
Write-Host " * $computer_name`: Script Complete.  Closing Environment." -ForegroundColor Green
Stop-Transcript
Exit 0
