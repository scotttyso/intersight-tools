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
    azs-hci-witness.ps1 -y azure.yaml
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
if (!( Test-Path -PathType Container $homePath + $pathSep + "Logs")) {
    New-Item -ItemType Directory $homePath + $pathSep + "Logs" | Out-Null
}
#=============================================================================
# Setup Variables for Environment
#=============================================================================
$ydata      = Get-Content -Path $y | ConvertFrom-Yaml
$username   = $ydata.active_directory.username
$password   = ConvertTo-SecureString $env:domain_administrator_password -AsPlainText -Force;
$credential = New-Object System.Management.Automation.PSCredential ($username,$password);
$global_node_list = [object[]] @()
foreach ($cluster in $ydata.clusters) {
    foreach ($node in $cluster.members) { $global_node_list += $node }
}
Start-Transcript -Path ".\Logs\$(get-date -f "yyyy-MM-dd_HH-mm-ss")_$($env:USER).log" -Append -Confirm:$false
Get-PSSession | Remove-PSSession | Out-Null
#=============================================================================
# Function: Node Length Check and Reboot Check
#=============================================================================
Function NodeAndRebootCheck {
    Param([psobject]$session_results, [array]$node_list)
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
#=============================================================================
# Configure File Share Witness if Domain Based
#=============================================================================
if ($ydata.file_share_witness.type -eq "domain") {
    $node_list = [object[]] @($ydata.file_share_witness.host)
    LoginNodeList -credential $credential -cssp $False -node_list $node_list
    $sessions = Get-PSSession
    $session_results = Invoke-Command $sessions -ScriptBlock {
        $ydata      = $Using:ydata
        $domain     = $ydata.file_share_witness.domain
        $witness    = $ydata.file_share_witness.host
        $share_path = "\\$($ydata.file_share_witness.host)\$($ydata.file_share_witness.share_name)"
        $share_name = $ydata.file_share_witness.share_name
        #Create Directory on File Share Witness
        Write-Host "$($witness): Begin Creating directory on File Share Witness." -ForegroundColor Yellow
        $test_dir = Test-Path -PathType Container $share_path
        if (!($test_dir)) { New-Item -ItemType Directory -Force $share_path | Out-Null }
        $test_dir = Test-Path -PathType Container $share_path
        if (!($test_dir)) {
            Write-Host "Failed Creating Directory $($share_path).  Exiting..." -ForegroundColor Red
            Return New-Object PsObject -property @{completed=$False}
        }
        Write-Host "$($witness): Completed Creating directory on File Share Witness." -ForegroundColor Yellow
        Write-Host "$($witness): Begin Configuring File Share on File Share Witness" -ForegroundColor Yellow
        $access_list  = @()
        foreach ($computer in $global_node_list) { $access_list.Add("$domain\$($computer.split('.')[0])$") }
        $access_list.Add(“$domain\Domain Admins")
        $gsmb = Get-SmbShare -Name $share_name
        $share_assigned = $True
        foreach ($access in $access_list) { if (!($gsmb | Where-Object {$_.AccountName -eq $access})) { $share_assigned = $False }}
        if ($share_assigned -eq $False) {
            Write-Host "$($witness): Adding File Share $share_name on File Share." -ForegroundColor Green
            $gsmb = New-SmbShare -Name $share_name -Path $share_path -FullAccess $access_list | Out-Null
        } else { $gsmb = Get-SmbShare -Name $share_name }
        $share_assigned = $True
        foreach ($access in $access_list) { if (!($gsmb | Where-Object {$_.AccountName -eq $access})) { $share_assigned = $False }}
        if ($share_assigned -eq $False) {
            Write-Host "$($witness): Failed to Configure File Share: $share_name." -ForegroundColor Red
            Return New-Object PsObject -property @{completed=$False}
        }
        Write-Host "$($witness): Completed Configuring File Share on File Share Witness" -ForegroundColor Yellow
        #NOT SURE ON THIS
        #Verify file share permissions on the file share witness
        #Write-Host "Verifing file share permissions on the file share witness"
        #Get-SmbShareAccess -Name $share_name | Format-Table -AutoSize
        #Set file level permissions on the file share directory that match the file share permissions
        Write-Host "$($witness): Begin Setting file level permissions on $share_name." -ForegroundColor Yellow
        $gsmb = Get-SmbShare -Name $share_name
        $share_access = $True
        foreach ($access in $access_list) { if (!($gsmb | Where-Object {$_.Access -match "$($access).+Allow.+FullControl"})) { $share_access = $False }}
        if ($share_access -eq $False) {
            Write-Host "$($witness): Adding File Share: '$share_name' Access Settings." -ForegroundColor Green
            $gsmb = Set-SmbPathAcl -ShareName $share_name | Out-Null
        } else { $gsmb = Set-SmbPathAcl -ShareName $share_name }
        $share_access = $True
        foreach ($access in $access_list) { if (!($gsmb | Where-Object {$_.Access -match "$($access).+Allow.+FullControl"})) { $share_access = $False }}
        if ($share_access -eq $False) {
            Write-Host "$($witness): Failed to Configure File Share: '$share_name' Access Settings." -ForegroundColor Red
            Return New-Object PsObject -property @{completed=$False}
        }
        Write-Host "$($witness): Completed Setting file level permissions on $share_name." -ForegroundColor Yellow
        Return New-Object PsObject -property @{completed=$True}
    }
    #=============================================================================
    # Setup Environment for Next Loop
    #=============================================================================
    Get-PSSession | Remove-PSSession | Out-Null
    NodeAndRebootCheck -session_results $session_results -node_list $global_node_list
    #=============================================================================
    # Configure Cluster Quorum Witness File Share
    #=============================================================================
    LoginNodeList -credential $credential -cssp $False -node_list [object[]] @($cluster)
    $sessions = Get-PSSession
    $session_results = Invoke-Command $sessions -scriptblock {
        $ydata      = $Using:ydata
        $witness    = $ydata.file_share_witness.host
        $share_name = $ydata.file_share_witness.share_name
        Write-Host "$($cluster): Begin Setting Cluster Witness File Share: '\\$witness\$share_name'." -ForegroundColor Yellow
        $gcq = Get-ClusterQuorum
        if (!($gcq | Where-Object {$_.FileShareWitness -eq "\\$witness\$share_name" })) {
            Write-Host "$($cluster): Adding Cluster Quorum Witness File Share: '\\$witness\$share_name'." -ForegroundColor Green
            Set-ClusterQuorum -Cluster $Cluster -FileShareWitness "\\$witness\$share_name"
        } else { Write-Host "$($cluster): Cluster Quorum Witness File Share: '\\$witness\$share_name' already configured." -ForegroundColor Cyan }
        $gcq = Get-ClusterQuorum
        if (!($gcq | Where-Object {$_.FileShareWitness -eq "\\$witness\$share_name" })) {
            Write-Host "$($cluster): Failed to Set Cluster Quorum Witness File Share: '\\$witness\$share_name'." -ForegroundColor Red
            Return New-Object PsObject -property @{completed=$False}
        }
        Write-Host "$($cluster): Completed Setting Cluster Witness File Share: '\\$witness\$share_name'." -ForegroundColor Yellow
        Return New-Object PsObject -property @{completed=$True}
    }
    #=============================================================================
    # Setup Environment for Next Loop
    #=============================================================================
    Get-PSSession | Remove-PSSession | Out-Null
    NodeAndRebootCheck -session_results $session_results -node_list $global_node_list
}
Stop-Transcript
Exit 0
