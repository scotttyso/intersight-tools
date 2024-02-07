<#
Copyright (c) 2018 Cisco and/or its affiliates.
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
#>

# This script sets API configuration parameters for use in other scripts.
# All params are optional.  If not set, environment variables are used.
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
    Script to Login to the Intersight API

.DESCRIPTION
    Script to Login to the Intersight API

.PARAMETER <a>
    Intersight API Key ID.   

.PARAMETER <f>
    Intersight Fully Qualified Domain Name.   

.PARAMETER <k>
    Intersight Secret Key File Path.   

.EXAMPLE
    azs-hci-adprep.ps1 -y azure.yaml
#>
[cmdletbinding()]
param(
    # The Intersight root URL for the API endpoint. The default is https://intersight.com
    [string]$f = "intersight.com",
    [string]$a = $env:intersight_api_key_id,
    [string]$k = $env:intersight_secret_key
)
$required_modules = @("Intersight.PowerShell")
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
$var_list = @('intersight_api_key_id', 'intersight_fqdn', 'intersight_secret_key')
foreach ($var in $var_list) {
    $arg_check = $True
    if ($var -eq "intersight_api_key_id") {
        if (!$a) { $arg_check = $False; $var_key = 'a'}
    } elseif ($var -eq "intersight_fqdn") {
        if (!$k) { $arg_check = $False; $var_key = 'f'}
    } elseif ($var -eq "intersight_secret_key") {
        if (!$k) { $arg_check = $False; $var_key = 'k'}
    }
    if (!$arg_check) {
        Write-Host ""
        Write-Host "-------------------------------------------------------------------------------------------" -ForegroundColor Cyan
        Write-Host "  "
        Write-Host "  The Script did not find '$var' as an argument or environment variable." -ForegroundColor Cyan
        Write-Host "  To not be prompted for the value of '$var' each time do one of the following:" -ForegroundColor Cyan
        Write-Host "  "
        Write-Host "  Supply as argument:  -$var_key '$($var)_value'" -ForegroundColor Cyan
        Write-Host "  "
        Write-Host "  Add to environment  - `$env:$var='$($var)_value'" -ForegroundColor Cyan
        Write-Host "  "
        Write-Host "-------------------------------------------------------------------------------------------" -ForegroundColor Cyan
        Write-Host ""
        if ($var -eq "intersight_api_key_id") {
            $a = read-host -Prompt "Please supply a value for the Intersight API Key ID parameter"
        } elseif ($var -eq "intersight_secret_key") {
            $k = read-host -Prompt "Please supply a value for the Intersight API Secret Key Path parameter"
        }
    }
}
if ($k.Contains("~")) {
    $temp = $k.Replace("~", "")
    $k_full = "$($HOME)$($temp)"
} else {
    $k_full = $k
}
# Configure Intersight API signing
Write-Host $a
Write-Host $k_full
#exit
$ApiParams = @{                       
    BasePath          = "https://$($f)"
    ApiKeyId          = $a
    ApiKeyFilePath    = $k_full
    HttpSigningHeader = @("(request-target)", "Host", "Date", "Digest")
}
Write-Host @ApiParams
Set-IntersightConfiguration @ApiParams