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
    Function to Update Drivers on Azure Stack Nodes

.DESCRIPTION
    Install Drivers on AzureStack HCI Nodes After Operating System Installation

.PARAMETER <y>
    YAML Input File containing Cluster Parameters.   

.EXAMPLE
    ezdriver_install.ps1 -y ezdriver_install.yaml
#>
#=============================================================================
# JSON File is a Required Parameter
# Pull in JSON Content
#=============================================================================
param (
    [switch]$force,
    [string]$y=$(throw "-y <yaml_file> is required.")
)
#=============================================================================
# Start Log and Configure PowerCLI
#=============================================================================
${env_vars} = Get-Childitem -Path Env:* | Sort-Object Name
if ((${env_vars} | Where-Object {$_.Name -eq "OS"}).Value -eq "Windows_NT") {
    $computer_name = $env:COMPUTERNAME; $pathSep  = "\"
    $homePath = (${env_vars} | Where-Object {$_.Name -eq "HOMEPATH"}).Value
} else {
    $computer_name = $env:NAME; $pathSep  = "/"
    $homePath = (${env_vars} | Where-Object {$_.Name -eq "HOME"}).Value
}
$log_directory = $homePath + $pathSep + "Logs"
if (!(Test-Path -PathType Container $log_directory)) { New-Item -ItemType Directory $log_directory }
#=============================================================================
# Setup Variables for Environment
#=============================================================================
$required_modules = @("powershell-yaml")
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
#=============================================================================
# Setup Environment
#=============================================================================
$credential_path = $homePath + $pathSep + "powershell.Cred"
If (Test-Path -PathType Leaf $credential_path) {
    $credential = Import-CliXml -Path $credential_path
} Else {
    $credential = Get-Credential
    $credential | Export-CliXml -Path $credential_path
}
Start-Transcript -Path ".\Logs\$(get-date -f "yyyy-MM-dd_HH-mm-ss")_$($env:USER).log" -Append -Confirm:$false
Get-PSSession | Remove-PSSession | Out-Null

#=============================================================================
# Validate YAML Input Arguments - operating_system/server_model
#=============================================================================
$ydata = Get-Content -Path $y -Raw | ConvertFrom-Yaml
$models = @("BxxxM5", "BxxxM6", "CxxxM5", "CxxxM6", "CxxxM7", "X210M6", "X210M7", "X410M7")
$os_versions = @("W2K16", "W2K19", "W2K22")
if (!($os_versions.contains($ydata.operating_system))) {
    Write-Host "`n$($ydata.operating_system) is an incorrect value for 'operating_system'.  Supported versions are:" -ForegroundColor Red
    foreach($v in $os_versions) { Write-Host " * $($v)" -ForegroundColor Green }
    Stop-Transcript
    Exit(1)
}
if (!($models.contains($ydata.server_model))) {
    Write-Host "`n$($ydata.server_model) is an incorrect value for 'server_model'.  Supported models are:" -ForegroundColor Red
    foreach($m in $models) { Write-Host " * $($m)" -ForegroundColor Green }
    Stop-Transcript
    Exit(1)
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
# Connect to Azure Stack Nodes and Install Updated Drivers
#=============================================================================
$share_password = $env:share_password
LoginNodeList -credential $credential -cssp $False -node_list $ydata.node_list
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
$session_results = Invoke-Command $sessions -ScriptBlock {
    #=========================================================================
    # Setup Variables on Nodes
    #=========================================================================
    $ydata = $Using:ydata
    $model = $ydata.server_model
    $os_version = $ydata.operating_system
    $share_path = $ydata.network_share
    $credential = $Using:credential
    #=========================================================================
    # Connect to Network Share
    #=========================================================================
    New-Item -Path "C:\" -Name "temp" -ItemType Directory -Force | Out-Null
    $file_share  = New-PSDrive -Name "ShareNAME" -PSProvider "FileSystem" -Root $share_path -Credential $credential
    if (!($file_share.Root)) {
        Write-Host " * $($env:COMPUTERNAME) Failed to connect to Network Share '$($share_path)'.  Exiting..." -ForegroundColor Red
        Return New-Object PsObject -property @{completed=$False}
    }
    #=========================================================================
    # Obtain Driver Files and Folders for Install
    #=========================================================================
    $chip_readme = Get-Content "$($file_share.Root)\ChipSet\Intel\$($model)\$($os_version)\README.html"
    $chip_regex  = $chip_readme | Select-String -Pattern '(?<=href\=\"\.\.\/\.\.\/).+exe(?=\"\>)'
    $chip_path    = "$(($chip_regex.Matches[0].Value).Replace("/", "\"))"
    Copy-Item "$($file_share.Root)\ChipSet\Intel\$($chip_path)" "C:\temp" -Force | Out-Null
    $chip_exe = $chip_path.Split("\")[2]
    $mlnx_exe = (Get-ChildItem -Path "$($file_share.Root)\Network\Mellanox\ConnectX4-5-6\$($os_version)\" -Filter *.exe | Select-Object -First 1).Name
    Copy-Item "$($file_share.Root)\Network\Mellanox\ConnectX4-5-6\$($os_version)\$($mlnx_exe)" "C:\temp" -Force | Out-Null
    Copy-Item -Path "$($file_share.Root)\Storage\Intel\C600\$($os_version)" -Destination "C:\temp\$($os_version)" -Recurse -Force | Out-Null
    Remove-PsDrive -Name $file_share.Name
    if (!($chip_exe)) {
        Write-Host " * $($env:COMPUTERNAME) Failed to Locate Intel Chipset Drivers in '$($file_share.Root)\ChipSet\Intel\$($model)\$($os_version)\README.html'.  Exiting..." -ForegroundColor Red
        Return New-Object PsObject -property @{completed=$False}
    }
    if (!($mlnx_exe)) {
        Write-Host " * $($env:COMPUTERNAME) Failed to Locate Mellanox Drivers in '$($file_share.Root)\Network\Mellanox\ConnectX4-5-6\$($os_version)\'.  Exiting..." -ForegroundColor Red
        Return New-Object PsObject -property @{completed=$False}
    }
    Return New-Object PsObject -property @{completed=$True; chip_exe=$chip_exe; mlnx_exe=$mlnx_exe; $reboot=$False}
}
#=============================================================================
# Setup Environment for Next Loop
#=============================================================================
Get-PSSession | Remove-PSSession | Out-Null
NodeAndRebootCheck -session_results $session_results -node_list $jdata.node_list
foreach ($result in $session_results) {
    $chip_exe = $result.chip_exe
    $mlnx_exe = $result.mlnx_exe
}
#=============================================================================
# Install Storage Drivers
#=============================================================================
LoginNodeList -credential $credential -cssp $False -node_list $ydata.node_list
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
Write-Host "Installing Storage Drivers" -ForegroundColor Cyan
$session_results = Invoke-Command $sessions -ScriptBlock {
    $ydata = $Using:ydata
    $os_version = $ydata.operating_system
    Start-Process PNPUtil -ArgumentList "/add-driver","C:\temp\$($os_version)\*.inf","/install" -Wait -Verb RunAs
    Return New-Object PsObject -property @{completed=$True}
} -asJob
#=============================================================================
# Setup Environment for Next Loop
#=============================================================================
Get-PSSession | Remove-PSSession | Out-Null
NodeAndRebootCheck -session_results $session_results -node_list $jdata.node_list
#=============================================================================
# Install Mellanox Driver
#=============================================================================
LoginNodeList -credential $credential -cssp $False -node_list $ydata.node_list
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
Write-Host "Installing Network Drivers" -ForegroundColor Cyan
$session_results = Invoke-Command $sessions -ScriptBlock {
    $ydata = $Using:ydata
    $mlnx_exe = $Using:mlnx_exe
    $log_file = "c:\temp\$(get-date -f "yyyy-MM-dd_HH-mm-ss")mlnx-log.txt"
    Start-Process "C:\temp\$($mlnx_exe)" -ArgumentList "/S", "/v/qn", "/v`"/l*vx $($log_file)`"" -Wait -Verb RunAs
    Return New-Object PsObject -property @{completed=$True}
} -asJob
#=============================================================================
# Setup Environment for Next Loop
#=============================================================================
Get-PSSession | Remove-PSSession | Out-Null
NodeAndRebootCheck -session_results $session_results -node_list $jdata.node_list
#=============================================================================
# Install ChipSet Drivers
#=============================================================================
LoginNodeList -credential $credential -cssp $False -node_list $ydata.node_list
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
$session_results = Invoke-Command $sessions -ScriptBlock {
    $ydata = $Using:ydata
    $chip_exe = $Using:chip_exe
    Start-Process "C:\temp\$($chip_exe)" -ArgumentList "-silent" -Wait -Verb RunAs
    Return New-Object PsObject -property @{completed=$True}
} -asJob
NodeAndRebootCheck -session_results $session_results -node_list $jdata.node_list
Stop-Transcript
Exit(0)
