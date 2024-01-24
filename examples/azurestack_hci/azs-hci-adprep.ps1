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
    [string]$y=$(throw "-y <yaml_file.yaml> is required.")
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
$log_dir = $homePath + $pathSep + "Logs"
if (!( Test-Path -PathType Container $log_dir)) {
    New-Item -ItemType Directory $log_dir | Out-Null
}
$credential_path = $homePath + $pathSep + "powershell.Cred"
If (Test-Path -PathType Leaf $credential_path) {
    $credential = Import-CliXml -Path $credential_path
} Else {
    $credential = Get-Credential
    $credential | Export-CliXml -Path $credential_path
}
if (!(Get-WindowsFeature -Name RSAT-AD-PowerShell)) {
    Install-WindowsFeature -Name RSAT-AD-PowerShell -IncludeAllSubFeature
}
if (!(Get-WindowsFeature -Name GPMC)) {
    Install-WindowsFeature -Name GPMC -IncludeAllSubFeature
}
Add-KdsRootKey -EffectiveTime ((get-date).addhours(-10))

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
# Test AzureStackHCI Active Directory Readiness
#=============================================================================
$ydata   = Get-Content -Path $y | ConvertFrom-Yaml
$ad =  $ydata.active_directory

$file = "AsHciADArtifactsPreCreationTool.ps1"
if ($ydata.proxy) {
    if ($ydata.proxy.username) {
        $proxy_user  = $ydata.proxy.username
        $proxy_pass  = ConvertTo-SecureString $env:proxy_password -AsPlainText -Force;
        $proxy_creds = New-Object System.Management.Automation.PSCredential ($proxy_user,$proxy_pass);
    }
}
if (!([System.IO.File]::Exists("./$file"))) {
    if (!($ydata.proxy)) { Invoke-WebRequest -URI "https://raw.githubusercontent.com/scotttyso/intersight-tools/master/examples/azurestack_hci/$file" -OutFile ".\$file"
    } else {
        if ($proxy_creds) {
            Invoke-WebRequest -URI "https://raw.githubusercontent.com/scotttyso/intersight-tools/master/examples/azurestack_hci/$file" -OutFile ".\$file" -Proxy $ydata.proxy.host -ProxyCredential $proxy_creds
        } else { Invoke-WebRequest -URI "https://raw.githubusercontent.com/scotttyso/intersight-tools/master/examples/azurestack_hci/$file" -OutFile ".\$file" -Proxy $ydata.proxy.host }
    }
}
if (!([System.IO.File]::Exists("./$file"))) {
    Invoke-WebRequest -URI "https://raw.githubusercontent.com/scotttyso/intersight-tools/master/examples/azurestack_hci/$file" -OutFile ".\$file"
}
foreach ($cluster in $ydata.clusters) {
    $node_list = @()
    foreach ($member in $cluster.members) {
        $node_list += $member.split(".")[0]
    }
    $node_list = $node_list -join "', '"
    $node_list = "'" + $node_list + "'"
    $dsplit = $ad.domain.split(".")
    $djoin = $dsplit -join ",DC="
    $domain_ou = "DC=" + $djoin
    $az_admin = $ad.azurestack_admin.split("@")[0]
    Write-Host ""
    Write-Host "Run the Following Commands in Order:" -ForegroundColor Yellow
    Write-Host "`$ad_user = '<your-domain>\$az_admin'" -ForegroundColor Green
    Write-Host "`$ad_pass = ConvertTo-SecureString '<new_hci_user_password>' -AsPlainText -Force;" -ForegroundColor Green
    Write-Host "`$adcreds = New-Object System.Management.Automation.PSCredential (`$ad_user,`$ad_pass)" -ForegroundColor Green
    Write-Host "`$node_list = @($node_list)" -ForegroundColor Green
    Write-HOst ".\AsHciADArtifactsPreCreationTool.ps1 -AsHciClusterName '$($cluster.cluster_name)' -AsHciDeploymentPrefix '$($ad.azurestack_prefix)' -AsHciDeploymentUserCredential `$adcreds -AsHciOUName 'ou=$($ad.azurestack_ou),$domain_ou' -AsHciPhysicalNodeList `$node_list -DomainFQDN '$($ad.domain)'" -ForegroundColor Green
    #Start-Process Powershell -Argumentlist "-ExecutionPolicy Bypass -NoProfile -File '.\$($file)' -AsHciClusterName '$($cluster.cluster_name)' -AsHciDeploymentPrefix '$($ad.azurestack_prefix)' -AsHciDeploymentUserCredential '$adcreds' -AsHciOUName '$($ad.azurestack_ou)' -AsHciPhysicalNodeList $($cluster.members) -DomainFQDN '$($ad.domain)'"
    #$ad_check.WaitForExit()
}
Exit 0
