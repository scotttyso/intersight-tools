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
    azs-hci-arcprep.ps1 -y azure.yaml
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
$environment_variables = @("azure_stack_subscription", "azure_stack_tenant", "windows_administrator_password")
foreach ($req_env in $environment_variables) {
    if (!([Environment]::GetEnvironmentVariable($req_env))) {
        Write-Host ""
        Write-Host "You Must Set the Following Environment Variables before Running This Script" -ForegroundColor Yellow
        Write-Host "  * `$env:azure_stack_subscription - Subscription for Azure" -ForegroundColor Green
        Write-Host "  * `$env:proxy_password - Only Required if Using a Proxy Server with Authentication" -ForegroundColor Green
        Write-Host "  * `$env:windows_administrator_password - Local Administrator Password for Azure Stack Hosts" -ForegroundColor Green
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
$ydata      = Get-Content -Path $y | ConvertFrom-Yaml
$password   = ConvertTo-SecureString $env:windows_administrator_password -AsPlainText -Force;
$credential = New-Object System.Management.Automation.PSCredential ("Administrator",$password);
$client_list = [object[]] @()
$global_node_list = [object[]] @()
foreach ($cluster in $ydata.clusters) {
    foreach ($node in $cluster.members) { $global_node_list += $node }
}
$gwsman = Get-WSManCredSSP
Add-KdsRootKey -EffectiveTime ((get-date).addhours(-10))
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
    Param([pscredential]$credential, [string]$cssp, [array]$node_list)
    if ($credssp -eq $True) {
        try {
            foreach ($node in $node_list) {
                Write-Host "Logging into Host $($node)" -ForegroundColor Yellow
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
# Enable WSManCredSSP Client on Local Machine
#=============================================================================
foreach ($node in $global_node_list) {
    $reg = [regex] "The machine is configured to $($node)"
    if ($gwsman -match $reg) { $client_list += $node }
}
if (!($global_node_list.Length -eq $client_list.Length)) {
    Write-Host "Enabling WSManCredSSP for Client List: $($global_node_list)" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role "Client" -DelegateComputer $global_node_list -Force | Out-Null
} else {
    Write-Host "WSManCredSSP Already Enabled for Client List: $($global_node_list)" -ForegroundColor Yellow
}
##=============================================================================
## AzureStackHCI - Install AzStackHCI.EnvironmentChecker on Node1
##=============================================================================
#LoginNodeList -credential $credential -cssp $False -node_list @($global_node_list[0])
#$sessions = Get-PSSession
#$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
#$session_results = Invoke-Command $sessions -ScriptBlock {
#    $computer_name = ([System.Net.DNS]::GetHostByName('').HostName).Split(".")[0]
#    $ydata         = $Using:ydata
#    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
#    #=============================================================================
#    # Validate NuGet is Running Minimum Version 2.8.5.201
#    #=============================================================================
#    Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Confirm:$False -Force
#    #=========================================================================
#    # Install PowerShell Modules
#    #=========================================================================
#    $required_modules = @("PowerShellGet", "AzStackHci.EnvironmentChecker")
#    foreach ($rm in $required_modules) {
#        if (!(Get-Module -ListAvailable -Name $rm)) {
#            Write-Host " * $computer_name`: Installing '$rm'." -ForegroundColor Green
#            Install-Module $rm -AllowClobber -Confirm:$False -Force
#        } else { Write-Host " * $computer_name`: '$rm' Already Installed." -ForegroundColor Cyan }
#    }
#    Return New-Object PsObject -property @{completed=$True}
#}
##=============================================================================
## Setup Environment for Next Loop; Sleep 10 Minutes if reboot_count gt 0
##=============================================================================
#Get-PSSession | Remove-PSSession | Out-Null
#$nrc = NodeAndRebootCheck -session_results $session_results -node_list @($global_node_list[0])
##=============================================================================
## AzureStackHCI - Connectivity Readiness Check
##=============================================================================
#LoginNodeList -credential $credential -cssp $False -node_list @($global_node_list[0])
#$sessions = Get-PSSession
#$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
#if (!($ydata.proxy)) { $session_results = Invoke-AzStackHciConnectivityValidation -PassThru -PsSession $sessions
#} else {
#    if ($proxy_creds) {
#        $session_results = Invoke-AzStackHciConnectivityValidation -PassThru -PsSession $sessions -Proxy $ydata.proxy.host -ProxyCredential $proxy_creds
#    } else { $session_results = Invoke-AzStackHciConnectivityValidation -PassThru -PsSession $sessions -Proxy $ydata.proxy.host }
#}
#$test_success = $True
#foreach ($result in $session_results) {
#    foreach($data in $result.AdditionalData) {
#        if ($data.PSComputerName) { $cluster_host = $data.PSComputerName
#        } else {$cluster_host = $data.Source }
#        if ($result.Status -eq "Succeeded") {
#            Write-Host "$cluster_host Result: $($result.Status) Test: $($result.Name)" -ForegroundColor Green
#        } else {
#            Write-Host "$cluster_host Result: $($result.Status) Test: $($result.Name)" -ForegroundColor Red
#            Write-Host "Test Description: $($result.Description)" -ForegroundColor Cyan
#            Write-Host "Test Additional Data: $($result.AdditionalData)" -ForegroundColor Cyan
#            Write-Host "Recommended Steps to Remediate: $($result.Remediation)" -ForegroundColor Cyan
#            Write-Host "For Further Assistance from Microsoft Refer to the following URL:" -ForegroundColor Yellow
#            Write-Host "https://learn.microsoft.com/en-us/azure-stack/hci/manage/use-environment-checker?tabs=connectivity" -ForegroundColor Yellow
#            $test_success = $False
#        }
#    }
#}
#if ($test_success -eq $False) {
#    Write-Host "Closing Environment...Exiting Script." -ForegroundColor Yellow
#    Stop-Transcript
#    Exit 1
#}
##=============================================================================
## AzureStackHCI - Hardware Readiness Check
##=============================================================================
#if (!($ydata.proxy)) { $session_results = Invoke-AzStackHciHardwareValidation -PassThru -PsSession $sessions
#} else {
#    if ($proxy_creds) {
#        $session_results = Invoke-AzStackHciHardwareValidation -PassThru -PsSession $sessions -Proxy $ydata.proxy.host -ProxyCredential $proxy_creds
#    } else { $session_results = Invoke-AzStackHciHardwareValidation -PassThru -PsSession $sessions -Proxy $ydata.proxy.host }
#}
#$test_success = $True
#foreach ($result in $session_results) {
#    $cluster_host = $result.TargetResourceID
#    if ($result.Status -eq "Succeeded") {
#        Write-Host "$cluster_host Result: $($result.Status) Test: $($result.Name)" -ForegroundColor Green
#    } elseif ($result.Severity -eq "Warning") {
#        Write-Host "$cluster_host Result: $($result.Status) Test: $($result.Name)" -ForegroundColor Yellow
#        Write-Host "Test Description: $($result.Description)" -ForegroundColor Cyan
#        Write-Host "Test Additional Data: $($result.AdditionalData)" -ForegroundColor Cyan
#        Write-Host "Recommended Steps to Remediate: $($result.Remediation)" -ForegroundColor Cyan
#    } else {
#        Write-Host "$cluster_host Result: $($result.Status) Test: $($result.Name)" -ForegroundColor Red
#        Write-Host "Test Description: $($result.Description)" -ForegroundColor Cyan
#        Write-Host "Test Additional Data: $($result.AdditionalData)" -ForegroundColor Cyan
#        Write-Host "Recommended Steps to Remediate: $($result.Remediation)" -ForegroundColor Cyan
#        Write-Host "For Further Assistance from Microsoft Refer to the following URL:" -ForegroundColor Yellow
#        Write-Host "https://learn.microsoft.com/en-us/azure-stack/hci/manage/use-environment-checker?tabs=hardware"-ForegroundColor Yellow
#        Write-Host ($result | Format-Table | Out-String)
#        $test_success = $False
#    }
#}
##=============================================================================
## Setup Environment for Next Loop; Sleep 10 Minutes if reboot_count gt 0
##=============================================================================
#if ($test_success -eq $False) {
#    Write-Host "Closing Environment...Exiting Script." -ForegroundColor Yellow
#    Stop-Transcript
#    Exit 1
#}
Get-PSSession | Remove-PSSession | Out-Null
#=============================================================================
# Install Modules and Register with Azure Arc
#=============================================================================
LoginNodeList -credential $credential -cssp $False -node_list $global_node_list
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
    $required_modules = @("PowerShellGet")
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
    # Install-WindowsFeature Active Directory RSAT PowerShell Module
    if (!(Get-WindowsFeature -Name RSAT-AD-PowerShell)) {
        Write-Host " * $computer_name`: Installing 'RSAT-AD-PowerShell'." -ForegroundColor Green
        Install-WindowsFeature -Name RSAT-AD-PowerShell -IncludeAllSubFeature
    } else { Write-Host " * $computer_name`: 'RSAT-AD-PowerShell' Already Installed." -ForegroundColor Cyan }
    # Install-WindowsFeature GPMC
    if (!(Get-WindowsFeature -Name GPMC)) {
        Write-Host " * $computer_name`: Installing 'GPMC'." -ForegroundColor Green
        Install-WindowsFeature -Name GPMC -IncludeAllSubFeature
    } else { Write-Host " * $computer_name`: 'GPMC' Already Installed." -ForegroundColor Cyan }
    $required_modules = @("AzsHCI.ARCinstaller")
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
    # Register Host with Azure Arc
    #=========================================================================
    $region = $ydata.azure_stack.region
    $RG     = $ydata.azure_stack.resource_group
    $SUB    = $Using:azure_subscription
    $TNT    = $Using:azure_tenant
    Connect-AzAccount -SubscriptionID $SUB -TenantId $TNT -DeviceCode
    $ARMtoken  = (Get-AzAccessToken).Token
    $id        = (Get-AzContext).Account.Id
    if (!($ydata.proxy)) {
        Invoke-AzStackHciArcInitialization -SubscriptionID $SUB -ResourceGroup $RG -TenantID $TNT -Region $region `
            -Cloud "AzureCloud" -ArmAccessToken $ARMtoken -AccountID $id
    } else {
        if ($Using:proxy_creds) {
            Invoke-AzStackHciArcInitialization -SubscriptionID $SUB -ResourceGroup $RG -TenantID $TNT -Region $region `
                -Cloud "AzureCloud" -ArmAccessToken $ARMtoken -AccountID $id -Proxy $ydata.proxy.host -ProxyCredential $Using:proxy_creds
        } else {
            Invoke-AzStackHciArcInitialization -SubscriptionID $SUB -ResourceGroup $RG -TenantID $TNT -Region $region `
                -Cloud "AzureCloud" -ArmAccessToken $ARMtoken -AccountID $id -Proxy $ydata.proxy.host }
    }
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
# Disable CredSSP on Hosts
#=============================================================================
LoginNodeList -credential $credential -cssp $False -node_list $global_node_list
$sessions = Get-PSSession
$session_results = Invoke-Command $sessions -scriptblock {
    $computer_name = ([System.Net.DNS]::GetHostByName('').HostName).Split(".")[0]
    Write-Host "$computer_name`: Beginning Disable Check of CredSSP." -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server | Out-Null
    $gwsman = Get-WSManCredSSP
    if (!($gwsman -match "This computer is not configured to receive credentials from a remote client computer")) {
        Write-Host "$computer_name`: Failed to Disable WSMan Credentials." -ForegroundColor Red
        Return New-Object PsObject -property @{completed=$False;reboot=$False}
    }
    Write-Host "$computer_name`: Completed Disable Check of CredSSP." -ForegroundColor Yellow
    Return New-Object PsObject -property @{completed=$True;reboot=$False}
}
#=============================================================================
# Clean Up the Environment - Close Sessions and Exit
#=============================================================================
Get-PSSession | Remove-PSSession | Out-Null
$nrc = NodeAndRebootCheck -session_results $session_results -node_list $global_node_list
#=============================================================================
# Clean Up the Environment - Remove AzStackHci.EnvironmentChecker
#=============================================================================
Write-Host ""
Write-Host "The Script is finished and you will no longer need 'AzStackHci.EnvironmentChecker'.  Do you want to remove the Module?" -ForegroundColor Yellow
Write-Host ""
$answer = Read-Host "Please enter 'Y' or 'N'"
if ($answer -eq 'Y') {
    LoginNodeList -credential $credential -cssp $False -node_list @($global_node_list[0])
    $sessions = Get-PSSession
    $sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
    $session_results = Invoke-Command $sessions -ScriptBlock {
        $computer_name = ([System.Net.DNS]::GetHostByName('').HostName).Split(".")[0]
        Write-Host ""
        Write-Host "$computer_name`: Removing 'AzStackHci.EnvironmentChecker' Module." -ForegroundColor Green
        Write-Host ""
        Remove-Module AzStackHci.EnvironmentChecker -Force
        Get-Module AzStackHci.EnvironmentChecker -ListAvailable | Where-Object {$_.Path -like "*$($_.Version)*"} | Uninstall-Module -force
        Return New-Object PsObject -property @{completed=$True;reboot=$False}
    }
    #=============================================================================
    # Clean Up the Environment - Close Sessions and Exit
    #=============================================================================
    Get-PSSession | Remove-PSSession | Out-Null
    $nrc = NodeAndRebootCheck -session_results $session_results -node_list $global_node_list

} else {
    Write-Host ""
    Write-Host "Skipping 'AzStackHci.EnvironmentChecker' Module Removal." -ForegroundColor Green
    Write-Host ""
}
#=============================================================================
# Clean Up the Environment - Close Sessions and Exit
#=============================================================================
Get-PSSession | Remove-PSSession | Out-Null
$nrc = NodeAndRebootCheck -session_results $session_results -node_list $global_node_list
Stop-Transcript
Disable-WSManCredSSP -Role "Client" | Out-Null
Exit 0
