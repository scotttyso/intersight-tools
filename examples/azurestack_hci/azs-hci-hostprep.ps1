<#
Copyright (c) 2023 Cisco and/or its affiliates.
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
    Includes All OS Customization of the AzureStack HCI Cisco Validated Design

.DESCRIPTION
    Configure AzureStack HCI After Operating System Installation

.PARAMETER <y>
    YAML Input File containing Cluster Parameters.   

.EXAMPLE
    azs-hci-hostprep.ps1 -y azure.yaml
#>

# JUMP HOST REQUIREMENTS
# Add-WindowsFeature -Name rsat-hyper-v-tools, rsat-adds-tools, failover-clustering, rsat-feature-tools-bitlocker-bdeaducext, gpmc -IncludeManagementTools

#=============================================================================
# YAML File is a Required Parameter
# Pull in YAML Content
#=============================================================================
param (
    [string]$y=$(throw "-y <yaml_file.yaml> is required.")
)
#=============================================================================
# Validate Running with Administrator Privileges
#=============================================================================
if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')) {
    Write-Host "Script must run with elevated Administrator permissions...Exiting" -Foreground Red
    Exit 1
}
Add-KdsRootKey -EffectiveTime ((get-date).addhours(-10))
#=============================================================================
# Start Log and Configure PowerCLI
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
Start-Transcript -Path ".\Logs\$(get-date -f "yyyy-MM-dd_HH-mm-ss")_$($env:USER).log" -Append -Confirm:$false
Get-PSSession | Remove-PSSession | Out-Null
#=============================================================================
# Install YAML PowerShell Module
#=============================================================================
Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
$required_modules = @("PowerShellGet", "AzStackHci.EnvironmentChecker", "powershell-yaml")
foreach ($rm in $required_modules) {
    if (!(Get-Module -ListAvailable -Name $rm)) {
        Write-Host " * $($computer_name) Installing $rm." -ForegroundColor Green
        Install-Module $rm -AllowClobber -Confirm:$False -Force
        Import-Module $rm
    } else {
        Write-Host " * $($computer_name) $rm Already Installed." -ForegroundColor Cyan
        Import-Module $rm
    }
}
#=============================================================================
# Setup Variables for Environment
#=============================================================================
$feature_list = (
    "Hyper-V", "Failover-Clustering", "Data-Center-Bridging", "Bitlocker" , "FS-FileServer", "FS-SMBBW", "Hyper-V-PowerShell",
    "RSAT-AD-Powershell", "RSAT-Clustering-PowerShell", "NetworkATC", "NetworkHUD", "FS-DATA-Deduplication"
)
$ydata      = Get-Content -Path $y | ConvertFrom-Yaml
$username   = $ydata.active_directory.azurestack_admin
$password   = ConvertTo-SecureString $env:windows_administrator_password -AsPlainText -Force;
$credential = New-Object System.Management.Automation.PSCredential ($username,$password);
$client_list = [object[]] @()
$global_node_list = [object[]] @()
foreach ($cluster in $ydata.clusters) {
    foreach ($node in $cluster.members) { $global_node_list += $node }
}
$gwsman = Get-WSManCredSSP
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
# Connect to Azure Stack Nodes and Install Updated Drivers
#=============================================================================
#LoginNodeList -credential $credential -cssp $False -node_list $global_node_list
#$sessions = Get-PSSession
#$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
#$session_results = Invoke-Command $sessions -ScriptBlock {
#    #=========================================================================
#    # Setup Variables on Nodes
#    #=========================================================================
#    $ydata = $Using:ydata
#    $model = $ydata.server_model
#    $os_version = $ydata.operating_system
#    $share_path = $ydata.network_share
#    $credential = $Using:credential
#    #=========================================================================
#    # Connect to Network Share
#    #=========================================================================
#    New-Item -Path "C:\" -Name "temp" -ItemType Directory -Force | Out-Null
#    $file_share  = New-PSDrive -Name "ShareNAME" -PSProvider "FileSystem" -Root $share_path -Credential $credential
#    if (!($file_share.Root)) {
#        Write-Host " * $($env:COMPUTERNAME) Failed to connect to Network Share '$($share_path)'.  Exiting..." -ForegroundColor Red
#        Return New-Object PsObject -property @{completed=$False}
#    }
#    #=========================================================================
#    # Obtain Driver Files and Folders for Install
#    #=========================================================================
#    $chip_readme = Get-Content "$($file_share.Root)\ChipSet\Intel\$($model)\$($os_version)\README.html"
#    $chip_regex  = $chip_readme | Select-String -Pattern '(?<=href\=\"\.\.\/\.\.\/).+exe(?=\"\>)'
#    $chip_path    = "$(($chip_regex.Matches[0].Value).Replace("/", "\"))"
#    Copy-Item "$($file_share.Root)\ChipSet\Intel\$($chip_path)" "C:\temp" -Force | Out-Null
#    $chip_exe = $chip_path.Split("\")[2]
#    $mlnx_exe = (Get-ChildItem -Path "$($file_share.Root)\Network\Mellanox\ConnectX4-5-6\$($os_version)\" -Filter *.exe | Select-Object -First 1).Name
#    Copy-Item "$($file_share.Root)\Network\Mellanox\ConnectX4-5-6\$($os_version)\$($mlnx_exe)" "C:\temp" -Force | Out-Null
#    Copy-Item -Path "$($file_share.Root)\Storage\Intel\C600\$($os_version)" -Destination "C:\temp\$($os_version)" -Recurse -Force | Out-Null
#    Remove-PsDrive -Name $file_share.Name
#    if (!($chip_exe)) {
#        Write-Host " * $($env:COMPUTERNAME) Failed to Locate Intel Chipset Drivers in '$($file_share.Root)\ChipSet\Intel\$($model)\$($os_version)\README.html'.  Exiting..." -ForegroundColor Red
#        Return New-Object PsObject -property @{completed=$False}
#    }
#    if (!($mlnx_exe)) {
#        Write-Host " * $($env:COMPUTERNAME) Failed to Locate Mellanox Drivers in '$($file_share.Root)\Network\Mellanox\ConnectX4-5-6\$($os_version)\'.  Exiting..." -ForegroundColor Red
#        Return New-Object PsObject -property @{completed=$False}
#    }
#    Return New-Object PsObject -property @{completed=$True; chip_exe=$chip_exe; mlnx_exe=$mlnx_exe; $reboot=$False}
#}
##=============================================================================
## Setup Environment for Next Loop
##=============================================================================
#Get-PSSession | Remove-PSSession | Out-Null
#NodeAndRebootCheck -session_results $session_results -node_list $jdata.node_list
#foreach ($result in $session_results) {
#    $chip_exe = $result.chip_exe
#    $mlnx_exe = $result.mlnx_exe
#}

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
#=============================================================================
# Configure Time Zone, Firewall Rules, and Installed Features
#=============================================================================
LoginNodeList -credential $credential -cssp $False -node_list $global_node_list
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
$session_results = Invoke-Command $sessions -ScriptBlock {
    $ydata = $Using:ydata
    ##########
    Write-Host "$($env:COMPUTERNAME) Beginning Time Zone: '$($ydata.timezone)' Configuration." -ForegroundColor Yellow
    $tz = Get-TimeZone
    if (!($tz.Id -eq $ydata.timezone)) {
        Set-Timezone $ydata.timezone
        $tz = Get-TimeZone
        if ($tz.Id -eq $ydata.timezone) {
            Write-Host " * $($env:COMPUTERNAME) Successfully Set Time Zone to: '$($ydata.timezone)'." -ForegroundColor Green
        } else {
            Write-Host " * $($env:COMPUTERNAME) Failed to Set Time Zone to: '$($ydata.timezone)'.  Exiting..." -ForegroundColor Red
            Return New-Object PsObject -property @{completed=$False}
        }
    } else {
        Write-Host " * $($env:COMPUTERNAME) Timezone already set to: '$($ydata.timezone)'." -ForegroundColor Cyan
    }
    Write-Host "$($env:COMPUTERNAME) Compeleted Time Zone: '$($ydata.timezone)' Configuration." -ForegroundColor Yellow
    ##########
    Write-Host "$($env:COMPUTERNAME) Beginning Remote Desktop Network Firewall Rule(s) Configuration." -ForegroundColor Yellow
    $network_firewall = Get-NetFirewallRule -DisplayGroup "Remote Desktop"
    foreach ($item in $network_firewall) {
        if (!($item.Enabled -eq $true)) { Enable-NetFirewallRule -Name $item.Name }
    }
    $network_firewall = Get-NetFirewallRule -DisplayGroup "Remote Desktop"
    foreach ($item in $network_firewall) {
        if ($item.Enabled -eq $true) {
            Write-Host " * $($env:COMPUTERNAME) Successfully Configured Remote Desktop Network Firewall Rule $($item.Name)." -ForegroundColor Green
        } else {
            Write-Host " * $($env:COMPUTERNAME) Failed on Enabling Remote Desktop Network Firewall Rule $($item.Name).  Exiting..." -ForegroundColor Red
            Return New-Object PsObject -property @{completed=$False}
        }
    }
    Write-Host "$($env:COMPUTERNAME) Completed Remote Desktop Network Firewall Rule(s) Configuration." -ForegroundColor Yellow
    ##########
    Write-Host "$($env:COMPUTERNAME) Beginning Check for Required Windows Features and Restarting Host." -ForegroundColor Yellow
    $new_list = [System.Collections.ArrayList]@()
    $reboot = $False
    $wf = Get-WindowsFeature | Select-Object *
    foreach ($item in $Using:feature_list) {
        if ($wf | Where-Object {$_.Name -eq $item}) {
            if (!(($wf | Where-Object {$_.Name -eq $item}).Installed -eq $true)) { $new_list.Add($item) }
        } else { Write-Host "$($env:COMPUTERNAME) Unknown Feature '$($item)'" -ForegroundColor Red
        }
    }
    if ($new_list.Length -gt 0) {
        Add-WindowsFeature -Name $new_list -IncludeAllSubFeature -IncludeManagementTools -Restart
        $reboot = $True
    }
    Write-Host "$($env:COMPUTERNAME) Completed Check for Required Windows Features and Restarted Host." -ForegroundColor Yellow
    #$gva = Get-PSSessionConfiguration -Name 'VirtualAccount'
    #if (!($gva)) {
    #    Write-Host "$($env:COMPUTERNAME) Failed on VirtualAccount Check.  Please Run the Following PowerShell Command On Each Host." -ForegroundColor Red
    #    Write-Host " * Run: New-PSSessionConfigurationFile -RunAsVirtualAccount -Path .\VirtualAccount.pssc" -ForegroundColor Red
    #    Write-Host " * Run: Register-PSSessionConfiguration -Name 'VirtualAccount' -Path .\VirtualAccount.pssc -Force" -ForegroundColor Red
    #    Write-Host " * Validate with: Get-PSSessionConfiguration -Name 'VirtualAccount'" -ForegroundColor Red
    #    Return New-Object PsObject -property @{completed=$False}
    #}
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
# Customize the AzureStack HCI OS Environment
#=============================================================================
LoginNodeList -credential $credential -cssp $False -node_list $global_node_list
$sessions = Get-PSSession
$session_results = Invoke-Command $sessions -ScriptBlock {
    Function RegistryKey {
        Param([string]$registry_path, [object]$key)
        $tp = Test-Path -path $registry_path
        if (!($tp)) { New-Item $registry_path }
        $reg = Get-ItemProperty -Path $registry_path
        if ($null -eq $reg.($key.name)) {
            New-Itemproperty -Path $registry_path -Name $key.name -Value $key.value -PropertyType $key.type | Out-Null
        } elseif (!($reg.($key.name) -eq $key.value)) {
            Write-Host " * $($env:COMPUTERNAME) Updating Key: '$($key.name)' Value: '$($key.value)'" -ForegroundColor Green
            $reg | Set-ItemProperty -Name $key.name -Value $key.value | Out-Null
        }
        $reg = Get-ItemProperty -Path $registry_path
        if ($reg.($key.name) -eq $key.value) {
            Write-Host " * $($env:COMPUTERNAME) Successfully Set '$registry_path\$($key.name)' to '$($key.value)'." -ForegroundColor Green
            Return New-Object PsObject -property @{completed=$True}
        } else {
            Write-Host " * $($env:COMPUTERNAME) Failed to Set '$registry_path\$($key.name)' to '$($key.value)'." -ForegroundColor Red
            $reg | Format-Table | Out-String|ForEach-Object {Write-Host $_}
            Return New-Object PsObject -property @{completed=$False}
        }
    }
    $ydata = $Using:ydata
    ##########
    Write-Host "$($env:COMPUTERNAME) Beginning Check for Windows Features..." -ForegroundColor Yellow
    $wf = Get-WindowsFeature | Select-Object *
    foreach ($item in $Using:feature_list) {
        if (!(($wf | Where-Object {$_.Name -eq $item}).Installed -eq $true)) {
            Write-Host "Failed on Enabling Windows Feature $item.  Exiting..." -ForegroundColor Red
            Return New-Object PsObject -property @{completed=$False}
        }
    }
    Write-Host "$($env:COMPUTERNAME) Completed Check for Windows Features..." -ForegroundColor Yellow
    ##########
    Write-Host "$($env:COMPUTERNAME) Beginning Memory Crashdump Registry settings Configuring." -ForegroundColor Yellow
    $keys = ("CrashDumpEnabled", "FilterPages")
    $registry_path = "HKLM:\System\CurrentControlSet\Control\CrashControl"
    foreach ($item in $keys) {
        $key = New-Object PsObject -property @{name=$item; value=1; type="Dword" }
        $regkey = RegistryKey $registry_path $key
        if (!($regkey.Completed -eq $True)) { Return New-Object PsObject -property @{completed=$False} }
    }
    Write-Host "$($env:COMPUTERNAME) Completed Memory Crashdump Registry settings Configuring." -ForegroundColor Yellow
    ##########
    Write-Host "$($env:COMPUTERNAME) Begin Validating Secure-Core Configuration." -ForegroundColor Yellow
    $sb = Confirm-SecureBootUEFI
    if (!($sb -eq $true)) {
        Write-Host "$($env:COMPUTERNAME) Secure Boot State is not Enabled.  Exiting..." -ForegroundColor Red
        Return New-Object PsObject -property @{completed=$False}
    }
    #$file = "./KernelDmaProtection.ps1"
    #if (!([System.IO.File]::Exists("$file"))) {
    #    Invoke-WebRequest -URI "https://raw.githubusercontent.com/scotttyso/intersight-tools/master/examples/azurestack_hci/$file" -OutFile "$file" -UseBasicParsing
    #}
    #Start-Process -FilePath ".\$file" -PassThru -Wait -RedirectStandardOutput stdout.txt -RedirectStandardError stderr.txt
    #Write-Host
    #$dma_protection = "$file"
    #if (!($dma_protection -eq $True)) {
    #    Write-Host " * $($env:COMPUTERNAME) Failed.  Kernel DMA Protection is not Enabled."  -ForegroundColor Red
    #    Write-Host "   Manually Check Output of 'msinfo32.exe' for 'Kernel DMA Protection' State: 'On'." -ForegroundColor Red
    #    Return New-Object PsObject -property @{completed=$False}
    #}
    #Remove-Item "$file" | Out-Null
    Write-Host "$($env:COMPUTERNAME) Completed Validating Secure-Core Configuration." -ForegroundColor Yellow
    Return New-Object PsObject -property @{completed=$True}
}
#=============================================================================
# Setup Environment for Next Loop; Sleep 10 Minutes if reboot_count gt 0
#=============================================================================
Get-PSSession | Remove-PSSession | Out-Null
$nrc = NodeAndRebootCheck -session_results $session_results -node_list $global_node_list
#=============================================================================
# Test AzureStackHCI Connectivity Readiness
#=============================================================================
LoginNodeList -credential $credential -cssp $False -node_list $global_node_list
$sessions = Get-PSSession | Where-Object {$_.Transport -eq "WSMan"}
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
if (!($ydata.proxy)) { $session_results = Invoke-AzStackHciConnectivityValidation -PassThru -PsSession $sessions
} else {
    if ($proxy_creds) {
        $session_results = Invoke-AzStackHciConnectivityValidation -PassThru -PsSession $sessions -Proxy $ydata.proxy.host -ProxyCredential $proxy_creds
    } else { $session_results = Invoke-AzStackHciConnectivityValidation -PassThru -PsSession $sessions -Proxy $ydata.proxy.host }
}
$test_success = $True
foreach ($result in $session_results) {
    foreach($data in $result.AdditionalData) {
        if ($data.PSComputerName) { $cluster_host = $data.PSComputerName
        } else {$cluster_host = $data.Source }
        if ($result.Status -eq "Succeeded") {
            Write-Host "$cluster_host Result: $($result.Status) Test: $($result.Name)" -ForegroundColor Green
        } else {
            Write-Host "$cluster_host Result: $($result.Status) Test: $($result.Name)" -ForegroundColor Red
            Write-Host "Test Description: $($result.Description)" -ForegroundColor Cyan
            Write-Host "Test Additional Data: $($result.AdditionalData)" -ForegroundColor Cyan
            Write-Host "Recommended Steps to Remediate: $($result.Remediation)" -ForegroundColor Cyan
            Write-Host "For Further Assistance from Microsoft Refer to the following URL:" -ForegroundColor Yellow
            Write-Host "https://learn.microsoft.com/en-us/azure-stack/hci/manage/troubleshoot-environment-validation-issues" -ForegroundColor Yellow
            $test_success = $False
        }
    }
}
if ($test_success -eq $False) {
    Write-Host "Closing Environment...Exiting Script." -ForegroundColor Yellow
    Stop-Transcript
    Exit 1
}
#=============================================================================
# Test AzureStackHCI Hardware Readiness
#=============================================================================
if (!($ydata.proxy)) { $session_results = Invoke-AzStackHciConnectivityValidation -PassThru -PsSession $sessions
} else {
    if ($proxy_creds) {
        $session_results = Invoke-AzStackHciConnectivityValidation -PassThru -PsSession $sessions -Proxy $ydata.proxy.host -ProxyCredential $proxy_creds
    } else { $session_results = Invoke-AzStackHciConnectivityValidation -PassThru -PsSession $sessions -Proxy $ydata.proxy.host }
}
$test_success = $True
foreach ($result in $session_results) {
    $cluster_host = $result.TargetResourceID
    if ($result.Status -eq "Succeeded") {
        Write-Host "$cluster_host Result: $($result.Status) Test: $($result.Name)" -ForegroundColor Green
    } else {
        Write-Host "$cluster_host Result: $($result.Status) Test: $($result.Name)" -ForegroundColor Red
        Write-Host "Test Description: $($result.Description)" -ForegroundColor Cyan
        Write-Host "Test Additional Data: $($result.AdditionalData)" -ForegroundColor Cyan
        Write-Host "Recommended Steps to Remediate: $($result.Remediation)" -ForegroundColor Cyan
        Write-Host "For Further Assistance from Microsoft Refer to the following URL:" -ForegroundColor Yellow
        Write-Host "https://learn.microsoft.com/en-us/azure-stack/hci/manage/troubleshoot-environment-validation-issues"-ForegroundColor Yellow
        $test_success = $False
    }
}
if ($test_success -eq $False) {
    Write-Host "Closing Environment...Exiting Script." -ForegroundColor Yellow
    Stop-Transcript
    Exit 1
}
#=============================================================================
# Test AzureStackHCI Active Directory Readiness
#=============================================================================
#$ad = $ydata.active_directory
#foreach ($cluster in $ydata.clusters) {
#    $ad_user = $ad.administrator
#    $ad_pass = ConvertTo-SecureString $env:windows_administrator_password -AsPlainText -Force;
#    $adcreds = New-Object System.Management.Automation.PSCredential ($ad_user,$ad_pass)
#    $node_list = @()
#    foreach ($member in $cluster.members) {
#        $node_list += $member.split(".")[0]
#    }
#    $dsplit = $ad.domain.split(".")
#    $djoin = $dsplit -join ",DC="
#    $domain_ou = "DC=" + $djoin
#    $ad_check = Invoke-AzStackHciExternalActiveDirectoryValidation  -ActiveDirectoryCredentials $adcreds -ADOUPath "ou=$($ad.azurestack_ou),$domain_ou" -ClusterName $cluster.cluster_name -DomainFQDN $ad.domain -NamingPrefix $ad.azurestack_prefix -PhysicalMachineNames $node_list
#    if ($ad_check -eq $True) { Write-Host "True" }
#}

Get-PSSession | Remove-PSSession | Out-Null
$nrc = NodeAndRebootCheck -session_results $session_results -node_list $global_node_list
Stop-Transcript
#=============================================================================
# Disable CredSSP on Hosts
#=============================================================================
LoginNodeList -credential $credential -cssp $False -node_list $node_list
$sessions = Get-PSSession
$session_results = Invoke-Command $sessions -scriptblock {
    Write-Host "$($env:COMPUTERNAME) Beginning Disable Check of CredSSP." -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server | Out-Null
    $gwsman = Get-WSManCredSSP
    if (!($gwsman -match "This computer is not configured to receive credentials from a remote client computer")) {
        Write-Host "$($env:COMPUTERNAME) Failed to Disable WSMan Credentials." -ForegroundColor Red
        Return New-Object PsObject -property @{completed=$False}
    }
    Write-Host "$($env:COMPUTERNAME) Completed Disable Check of CredSSP." -ForegroundColor Yellow
    Return New-Object PsObject -property @{completed=$True}
}
#=============================================================================
# Setup Environment for Next Loop
#=============================================================================
Get-PSSession | Remove-PSSession | Out-Null
$nrc = NodeAndRebootCheck -session_results $session_results -node_list $node_list
Stop-Transcript
Disable-WSManCredSSP -Role "Client" | Out-Null
Exit 0
