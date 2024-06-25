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
#=============================================================================
# Install PowerShell Modules
#=============================================================================
Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
$required_modules = @("Az.Accounts:2.13.2", "Az.Resources:6.12.0", "Az.ConnectedMachine:0.5.2")
foreach ($rm in $required_modules) {
    $mod     = $rm.Split(":")[0]
    $version = $rm.Split(":")[1]
    $getmod  = Get-Module -ListAvailable -Name $mod
    $modver   = [Decimal]("$($getmod.Version.Major).$($getmod.Version.Minor)$($getmod.Version.Build)")
    $vcompare = ($version).split(".")
    $vcompare = [Decimal]("$($vcompare[0]).$($vcompare[1])$($vcompare[2])")
    Write-Host $modver
    Write-Host $vcompare
    if (!($getmod)) {
        Write-Host " * $($computer_name) Installing $mod Version $version." -ForegroundColor Green
        Install-Module $mod -AllowClobber -Confirm:$False -RequiredVersion $version -Force
        Import-Module $mod
    } elseif (!($modver -eq $vcompare )) {
        Write-Host " * $($computer_name) Installing $mod Version $version." -ForegroundColor Green
        Install-Module $mod -AllowClobber -Confirm:$False -RequiredVersion $version -Force
        Import-Module $mod
    } else {
        Write-Host " * $($computer_name) $mod Already Installed." -ForegroundColor Cyan
        Import-Module $mod
    }
}
$required_modules = @("AzsHCI.ARCinstaller")
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
# Test AzureStackHCI Active Directory Readiness
#=============================================================================
$ydata   = Get-Content -Path $y | ConvertFrom-Yaml
$ad =  $ydata.active_directory

foreach ($cluster in $ydata.clusters) {
    $node_list = @()
    foreach ($member in $cluster.members) { $node_list += $member.split(".")[0] }
    $node_list = $node_list -join "', '"
    $node_list = "'" + $node_list + "'"
    $dsplit = $ad.domain.split(".")
    $djoin = $dsplit -join ",DC="
    $domain_ou = "DC=" + $djoin
    $az_admin = $ad.azure_stack_admin.split("@")[0]
    Write-Host ""
    Write-Host "Run the Following Commands in Order:" -ForegroundColor Yellow
    Write-Host "`$ad_user   = '<your-domain>\$az_admin'" -ForegroundColor Green
    Write-Host "`$ad_pass   = ConvertTo-SecureString '<new_hci_user_password>' -AsPlainText -Force;" -ForegroundColor Green
    Write-Host "`$adcreds   = New-Object System.Management.Automation.PSCredential (`$ad_user,`$ad_pass)" -ForegroundColor Green
    Write-Host "`$node_list = @($node_list)" -ForegroundColor Green
    Write-Host "`$params = @{"
    Write-Host "    AsHciClusterName              = '$($cluster.cluster_name)'"
    Write-Host "    AsHciDeploymentPrefix         = '$($ad.azure_stack_prefix)'"
    Write-Host "    AsHciDeploymentUserCredential = `$adcreds"
    Write-Host "    AsHciOUName                   = 'ou=$($ad.azure_stack_ou),$domain_ou'"
    Write-Host "    AsHciPhysicalNodeList         = $node_list"
    Write-Host "    DomainFQDN                    = '$($ad.domain)'"
    Write-Host "}"
    Write-Host ".\AsHciADArtifactsPreCreationTool.ps1 @params" -ForegroundColor Green
    Write-Host ""
    Write-Host ""
    Write-Host "After you have Validated the AD Prep has completed successfully.  Run the Arc integration registration and validation" -ForegroundColor Yellow
    Write-Host "See: https://learn.microsoft.com/en-us/azure-stack/hci/deploy/deployment-arc-register-server-permissions?tabs=powershell" -ForegroundColor Yellow
    Write-Host "Note: Arc_resourcegroup_name represents the resource group that you plan to use to onboard your Azure Stack HCI cluster." -ForegroundColor Yellow
    Write-Host "# The Azure Tenant where you want to onboard your Azure Stack HCI cluster" -ForegroundColor Yellow
    Write-Host "`$tenant = '<Your_tenant_ID>'" -ForegroundColor Green
    Write-Host "# The Azure Subscription you want to use to onboard your Azure Stack HCI cluster" -ForegroundColor Yellow
    Write-Host "`$subscription = '<Your_subscription_ID>'" -ForegroundColor Green
    Write-Host "# The Azure Region you want to use to onboard your Azure Stack HCI cluster" -ForegroundColor Yellow
    Write-Host "`$region = '<azure_region i.e. eastus>'" -ForegroundColor Green
    Write-Host "# Arc_resourcegroup_name represents the resource group that you plan to use to onboard your Azure Stack HCI cluster" -ForegroundColor Yellow
    Write-Host "`$resource_group = '<ARC_resourcegroup_name>'" -ForegroundColor Green
    Write-Host "# Proxy Server is only required if you need a Proxy Server to communicate outbound." -ForegroundColor Yellow
    Write-Host "`$proxy = 'http://proxyaddress:port'" -ForegroundColor Green
    Write-Host "`$nodes = [string[]]($node_list)" -ForegroundColor Green
    Write-Host "Connect-AzAccount -Tenant `$tenant -Subscription `$subscription -DeviceCode" -ForegroundColor Green
    Write-Host "`$ARMtoken = (Get-AzAccessToken).Token" -ForegroundColor Green
    Write-Host "`$Id = (Get-AzContext).Account.Id " -ForegroundColor Green
    Write-Host "Invoke-AzStackHciArcIntegrationValidation -SubscriptionID `$subscription -ArcResourceGroupName `$resource_group -NodeNames `$nodes" -ForegroundColor Green
    Write-Host "Invoke-AzStackHciArcIntegrationValidation -SubscriptionID `$subscription -ArcResourceGroupName `$resource_group -NodeNames `$nodes" -ForegroundColor Green
    Write-Host ""
    Write-Host ""
    Write-Host "For More Details see `Run the Arc integration validator` at:" -ForegroundColor Yellow
    Write-Host "https://github.com/MicrosoftDocs/azure-stack-docs/blob/main/azure-stack/hci/manage/use-environment-checker.md" -ForegroundColor Yellow
}
Exit 0
