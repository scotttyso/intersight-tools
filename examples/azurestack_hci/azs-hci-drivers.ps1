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
    Includes driver installation tasks for the AzureStack HCI Cisco Validated Design

.DESCRIPTION
    Install Drivers in Azure Stack HCI Cluster Nodes

.PARAMETER <y>
    YAML Input File containing Cluster Parameters.   

.EXAMPLE
    azs-hci-drivers.ps1 -y answers.yaml
#>

#=========================================================================
# Get Parameters and validate Admin privileges
#=========================================================================
param (
    [string]$y=$(throw "-y <yaml_file.yaml> is required.")
)
# Make sure Running as Administrator
if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')) {
    Write-Host "Script must run with elevated Administrator permissions...Exiting" -Foreground Red
    Exit 1
}
#=========================================================================
# IMPORT powershell-yaml
#=========================================================================
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
#=========================================================================
# Import YAML Data and Setup Variables
#=========================================================================
$ydata        = Get-Content -Path $y -Raw | ConvertFrom-Yaml
$driver_mount = $ydata.driver_mount
$driver_path  = "$($ydata.driver_path)\drivers"
$fpath        = $ydata.driver_path
$image_path   = "$($ydata.driver_path)\images"
$model        = $ydata.server_model
$models       = @("BxxxM5", "BxxxM6", "CxxxM5", "CxxxM6", "CxxxM7", "CxxxM8", "X210M6", "X210M7", "X410M7")
$os_versions  = @("W2K16", "W2K19", "W2K22")
$os_version   = $ydata.operating_system
New-Item -Path $ydata.driver_path -Name "drivers" -ItemType Directory -Force | Out-Null
New-Item -Path $ydata.driver_path -Name "images" -ItemType Directory -Force | Out-Null
#=========================================================================
# Test Variables
#=========================================================================
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
$images = @("boot.wim", "install.wim")
foreach ($image in $images) {
    if (!(Test-Path -Path "$($fpath)\AzureStack\sources\$($image)")) {
        Write-Host "Failed to Locate the Azure Stack $image file at '$($fpath)\AzureStack\sources\$image'.  Validate File Path" -ForegroundColor Red
        Exit(1)
    }
}
#=========================================================================
# Files Missing from RemoteInstall
#=========================================================================
Copy-Item -Path "C:\Windows\System32\RemInst\boot\x64\wdsmgfw.efi" -Destination "$($fpath)RemoteInstall\Boot\x64" -Recurse -Force | Out-Null
if (!(Test-Path -Path "$($fpath)RemoteInstall\Boot\x64\wdsmgfw.efi")) {
    Write-Host "Failed to Locate the wdsmgfw.efi file in '$($fpath)RemoteInstall\Boot\x64'.  Validate File Path" -ForegroundColor Red
    Exit(1)
}
Copy-Item -Path "C:\Windows\Boot\Fonts\wgl4_boot.ttf" -Destination "$($fpath)RemoteInstall\Boot\Fonts" -Recurse -Force | Out-Null
if (!(Test-Path -Path "$($fpath)RemoteInstall\Boot\Fonts\wgl4_boot.ttf")) {
    Write-Host "Failed to Locate the wgl4_boot.ttf file in '$($fpath)RemoteInstall\Boot\Fonts'.  Validate File Path" -ForegroundColor Red
    Exit(1)
}
#=========================================================================
# Obtain Drivers and Extract Contents if necessary
#=========================================================================
$chip_readme = Get-Content "$($driver_mount)\ChipSet\Intel\$($model)\$($os_version)\README.html"
$chip_regex  = $chip_readme | Select-String -Pattern '(?<=href\=\"\.\.\/\.\.\/).+exe(?=\"\>)'
$chip_path   = "$(($chip_regex.Matches[0].Value).Replace("/", "\"))"
$chip_exe    = $chip_path.Split("\")[2]
if (!($chip_exe)) {
    Write-Host " * $($env:COMPUTERNAME) Failed to Locate Intel Chipset Drivers in '$($driver_mount)\ChipSet\Intel\$($model)\$($os_version)\README.html'.  Exiting..." -ForegroundColor Red
    Exit(1)
}
Start-Process "$($driver_mount)\ChipSet\Intel\$($chip_path)" -ArgumentList "-extract", "$($driver_path)\chipset" -Wait
# Intel Storage Drivers
Copy-Item -Path "$($driver_mount)\Storage\Intel\C600\$($os_version)" -Destination "$($driver_path)\storage" -Recurse -Force | Out-Null
# Mellanox Driver Executable
$mlnx_exe = (Get-ChildItem -Path "$($driver_mount)\Network\Mellanox\ConnectX4-5-6\$($os_version)\" -Filter *.exe | Select-Object -First 1).Name
if (!($mlnx_exe)) {
    Write-Host " * $($env:COMPUTERNAME) Failed to Locate Mellanox Drivers in '$($driver_mount)\Network\Mellanox\ConnectX4-5-6\$($os_version)\'.  Exiting..." -ForegroundColor Red
    Exit(1)
}
Copy-Item "$($driver_mount)\Network\Mellanox\ConnectX4-5-6\$($os_version)\$($mlnx_exe)" $driver_path -Force | Out-Null
Start-Process "$($driver_path)\$mlnx_exe" -ArgumentList "/a","/vMT_DRIVERS_ONLY=1"-Verb RunAs -Wait
if (!(Test-Path -Path "$($driver_path)\chipset\Readme.txt")) {
    Write-Host "Failed to Locate the Intel Chipset README.  Validate File Path" -ForegroundColor Red
    Exit(1)
}
if (!(Test-Path -Path "$($driver_path)\mlnx\mlx5muxp.inf")) {
    Write-Host "Failed to Locate the Mellanox driver files in '$($driver_path)\mlnx'.  Validate File Path" -ForegroundColor Red
    Exit(1)
}
if (!(Test-Path -Path "$($driver_path)\storage\MegaSR1.inf")) {
    Write-Host "Failed to Locate the Intel Storage Drivers in '$($driver_path)\storage'.  Validate File Path" -ForegroundColor Red
    Exit(1)
}
Write-Host "Successfully extracted the driver files for installation." -ForegroundColor Yellow
#=========================================================================
# Loop Thru the Driver Packages and add them to the boot.wim and install.wim
#=========================================================================
$images = @("boot.wim", "install.wim")
foreach ($image in $images) {
    # Mount Image
    Write-Host ""; Write-Host "Mounting '$($fpath)AzureStack\sources\$($image)'." -ForegroundColor Yellow
    #Mount-WindowsImage -ImagePath ":$($fpath)\AzureStack\sources\$($image)" -Index 1 -Path $image_path
    Start-Process Dism -ArgumentList "/Mount-Image", "/ImageFile:$($fpath)AzureStack\sources\$($image)", "/Index:1", "/MountDir:$($image_path)" -NoNewWindow
    Start-Sleep -Seconds 60
    # Add the Intel Chipset Drivers
    Write-Host ""; Write-Host "Adding Chipset Drivers to '$($fpath)AzureStack\sources\$($image)'." -ForegroundColor Yellow
    Start-Process Dism -ArgumentList "/Image:$($image_path)", "/Add-Driver", "/Driver:$($fpath)drivers\chipset", "/Recurse" -NoNewWindow -Wait
    # Add the Intel Storage Drivers
    Write-Host ""; Write-Host "Adding Storage Drivers to '$($fpath)AzureStack\sources\$($image)'." -ForegroundColor Yellow
    Start-Process Dism -ArgumentList "/Image:$($image_path)", "/Add-Driver", "/Driver:$($fpath)drivers\storage", "/Recurse" -NoNewWindow -Wait
    # Add the Mellanox Adapter Drivers
    Write-Host ""; Write-Host "Adding Adapter Drivers to '$($fpath)AzureStack\sources\$($image)'." -ForegroundColor Yellow
    Start-Process Dism -ArgumentList "/Image:$($image_path)", "/Add-Driver", "/Driver:$($fpath)drivers\mlnx", "/Recurse" -NoNewWindow -Wait
    Write-Host ""; Write-Host "Unmounting '$($fpath)AzureStack\sources\$($image)'." -ForegroundColor Yellow
    # Unmount the Image file
    Start-Process Dism -ArgumentList "/Unmount-Image", "/MountDir:$($image_path)", "/Commit" -NoNewWindow -Wait
}
Write-Host ""; Write-Host "Successfully Added the Drivers to the boot and image WIM Files." -ForegroundColor Yellow
Import-WdsBootImage -Path "$($fpath)AzureStack\sources\boot.wim" -NewImageName AzureStackHCI
$image_group = New-WdsInstallImageGroup -Name "AzureStackHCI"
Import-WdsInstallIMage -ImageGroup $image_group.Name -Path "$($fpath)AzureStack\sources\install.wim" -NewImageName AzureStackHCI
Write-Host ""; Write-Host "Successfully Added the Windows images to Windows Deployment Services." -ForegroundColor Yellow
Exit(0)
