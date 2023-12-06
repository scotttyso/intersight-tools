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
    Script to Prepare Active Directory for the AzureStack HCI Cisco Validated Design

.DESCRIPTION
    Script to Prepare Active Directory for the AzureStack HCI Cisco Validated Design

.PARAMETER <y>
    YAML Input File containing Cluster Parameters.   

.EXAMPLE
    azs-hci-adprep.ps1 -y azure.yaml
#>

# JUMP HOST REQUIREMENTS
# Add-WindowsFeature -Name rsat-hyper-v-tools, rsat-adds-tools, failover-clustering, rsat-feature-tools-bitlocker-bdeaducext, gpmc -IncludeManagementTools

#=============================================================================
# YAML File is a Required Parameter
# Pull in YAML Content
#=============================================================================
param (
    [string]$j=$(throw "-y <yaml_file.yaml> is required.")
)
#=============================================================================
# Validate Running with Administrator Privileges
#=============================================================================
if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')) {
    Write-Host "Script must run with elevated Administrator permissions...Exiting" -Foreground Red
    Exit 1
}
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
if (!( Test-Path -PathType Container $homePath + $pathSep + "Logs")) {
    New-Item -ItemType Directory $homePath + $pathSep + "Logs" | Out-Null
}
$credential_path = $homePath + $pathSep + "powershell.Cred"
If (Test-Path -PathType Leaf $credential_path) {
    $credential = Import-CliXml -Path $credential_path
} Else {
    $credential = Get-Credential
    $credential | Export-CliXml -Path $credential_path
}
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
Start-Transcript -Path ".\Logs\$(get-date -f "yyyy-MM-dd_HH-mm-ss")_$($env:USER).log" -Append -Confirm:$false
#=============================================================================
# Test AzureStackHCI Active Directory Readiness
#=============================================================================
$ydata   = Get-Content -Path $y | ConvertFrom-Yaml
$ad_user = $ydata.active_directory.admin
$ad_pass = ConvertTo-SecureString $env:windows_administrator_password -AsPlainText -Force;
$adcreds = New-Object System.Management.Automation.PSCredential ($ad_user,$ad_pass)
$ad =  $ydata.active_directory 
$file = "AsHciADArtifactsPreCreationTool.ps1"
if (!([System.IO.File]::Exists("./$file"))) {
    Invoke-WebRequest -URI "https://raw.githubusercontent.com/scotttyso/intersight-tools/master/examples/azurestack_hci/$file" -OutFile ".\$file"
}
$ad_check = Start-Process Powershell -Argumentlist "-ExecutionPolicy Bypass -NoProfile -File '.\$($file)' -AsHciClusterName '$($ydata.cluster)' -AsHciDeploymentPrefix '$($ad.naming_prefix)' -AsHciDeploymentUserCredential '$adcreds' -AsHciOUName '$($ad.ou)' -AsHciPhysicalNodeList $($ydata.node_list) -DomainFQDN '$($ad.fqdn)'"
$ad_check.WaitForExit()
Stop-Transcript
Exit 0
