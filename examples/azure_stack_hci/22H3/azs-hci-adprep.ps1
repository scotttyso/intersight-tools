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
    Script to Prepare Active Directory for the AzureStack HCI Cisco Validated Design

.DESCRIPTION
    Script to Prepare Active Directory for the AzureStack HCI Cisco Validated Design

.PARAMETER <y>
    YAML Input File containing Cluster Parameters.   

.EXAMPLE
    azs-hci-adprep.ps1 -y azure.yaml
#>

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
$computer_name = (Get-ComputerInfo).CsDNSHostName
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
#=============================================================================
# Install PowerShellGet and powershel-yaml
#=============================================================================
Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
$required_modules = @("PowerShellGet", "powershell-yaml")
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
#Get-WindowsFeature -Name RSAT-AD-PowerShell|Install-Windowsfeature 
# [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if (!(Get-WindowsFeature -Name RSAT-AD-PowerShell)) {
    Install-WindowsFeature -Name RSAT-AD-PowerShell -IncludeAllSubFeature
}
# Install-WindowsFeature GPMC
if (!(Get-WindowsFeature -Name GPMC)) {
    Install-WindowsFeature -Name GPMC -IncludeAllSubFeature
}
#Add-KdsRootKey -EffectiveTime ((get-date).addhours(-10))
#=============================================================================
# Install AsHciADArtifactsPreCreationTool
#=============================================================================
$required_modules = @("AsHciADArtifactsPreCreationTool:10.2402")
foreach ($rm in $required_modules) {
    $mod     = $rm.Split(":")[0]
    $version = $rm.Split(":")[1]
    $getmod  = Get-Module -ListAvailable -Name $mod
    if (!($getmod)) {
        Write-Host " * $($computer_name) Installing $mod Version $version." -ForegroundColor Green
        Install-Module $mod -AllowClobber -Confirm:$False -MinimumVersion $version -Force
        Import-Module $mod
    } elseif (!([Decimal]("$($getmod.Version.Major).$($getmod.Version.Minor)") -ge $version )) {
        Write-Host " * $($computer_name) Installing $mod Version $version." -ForegroundColor Green
        Install-Module $mod -AllowClobber -Confirm:$False -MinimumVersion $version -Force
        Import-Module $mod
    } else {
        Write-Host " * $($computer_name) $mod Already Installed." -ForegroundColor Cyan
        Import-Module $mod
    }
}
#=============================================================================
# Azure Stack HCI - Active Directory Shared Parameters
#=============================================================================
$ydata     = Get-Content -Path $y | ConvertFrom-Yaml
$domain_ou = "DC=" + ($ydata.active_directory.domain.split(".") -join ",DC=")
#$ad_pass   = ConvertTo-SecureString $env:windows_domain_password -AsPlainText -Force
#$ad_user   = $ydata.active_directory.administrator.split("@")[0]
#$ad_creds  = New-Object System.Management.Automation.PSCredential ($ad_user, $ad_pass)
#=============================================================================
# Azure Stack HCI - Active Directory Preparation - Per Cluster
#=============================================================================
$count = 1
foreach($cluster in $ydata.clusters) {
    $env_pass  = [Environment]::GetEnvironmentVariable("azure_stack_lcm_password")
    $org_unit  = "ou=$($ydata.active_directory.azure_stack_ou),$domain_ou"
    $azs_pass  = ConvertTo-SecureString $env_pass -AsPlainText -Force
    $azs_user  = $cluster.life_cycle_management_user.split("@")[0]
    $azs_creds = New-Object System.Management.Automation.PSCredential ($azs_user, $azs_pass)
    $node_list = @()
    foreach ($member in $cluster.members) { $node_list += $member.split(".")[0] }
    New-HciAdObjectsPreCreation -AzureStackLCMUserCredential $azs_creds -AsHciOUName $org_unit
    #$params = @{
    #    ActiveDirectoryCredentials = $azs_creds
    #    ActiveDirectoryServer      = "ad1.rich.ciscolabs.com"
    #    ADOUPath                   = $org_unit
    #    ClusterName                = $cluster.cluster_name
    #    DomainFQDN                 = $ydata.active_directory.domain
    #    NamingPrefix               = $cluster.naming_prefix
    #    PhysicalMachineNames       = $node_list
    #}
    #$ad_check = Invoke-AzStackHciExternalActiveDirectoryValidation  @params -PassThru
    #$params = @{
    #    AsHciClusterName              = $cluster.cluster_name
    #    AsHciDeploymentUserCredential = $azs_creds
    #    AsHciOUName                   = $org_unit
    #    DomainFQDN                    = $ydata.active_directory.domain
    #    AsHciDeploymentPrefix         = $cluster.naming_prefix
    #    AsHciPhysicalNodeList         = $node_list
    #}
    #Write-HOst ".\AsHciADArtifactsPreCreationTool.ps1 -AsHciClusterName `"$($cluster.cluster_name)`" -AsHciDeploymentPrefix $($cluster.naming_prefix) -AsHciDeploymentUserCredential `$azs_creds -AsHciOUName `"$org_unit`" -AsHciPhysicalNodeList `$node_list -DomainFQDN `"$($ydata.active_directory.domain)`"" -ForegroundColor Green
    #if ($ad_check -eq $True) { Write-Host "True" }
    $count += 1
}
Exit 0
