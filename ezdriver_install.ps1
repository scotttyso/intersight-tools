param (
    [string]$model=$(throw "-model 'model' is required (BxxxM5|BxxxM6|CxxxM5|CxxxM6|CxxxM7|X210M6|X210M7|X410M7)."),
    [string]$os_version=$(throw "-os_version 'os_version' is required (W2K16|W2K19|W2K22)."),
    [switch]$force
)
# Validate model properly set
$models = @("BxxxM5", "BxxxM6", "CxxxM5", "CxxxM6", "CxxxM7", "X210M6", "X210M7", "X410M7")
if (!($models.contains($model))) {
    Write-Host "`nIncorrect value for '-model'.  Supported models are:" -ForegroundColor Red
    foreach($m in $models) { Write-Host " * $($m)" -ForegroundColor Green }
    Exit(1)
}
# Validate os_version properly set
$versions = @("W2K16", "W2K19", "W2K22")
if (!($versions.contains($os_version))) {
    Write-Host "`nIncorrect value for '-os_version'.  Supported versions are:" -ForegroundColor Red
    foreach($v in $versions) { Write-Host " * $($v)" -ForegroundColor Green }
    Exit(1)
}
# Determine the Volume Drive Letter for the Drivers CD
$volumes = @("C", "D", "E", "F", "G", "H", "I", "J", "K", "L")
$found = $false
while ($found -eq $false) {
    foreach ($vol in $volumes) {
        if ((Test-Path -PathType Leaf "$($vol):\tag.txt") -and (Test-Path -PathType Leaf "$($vol):\release.txt")) {
            $volume = $vol
            $found = $true
            Write-Host "Volume is '$($volume):\'"
        }
    }
}
# Obtain Driver Files and Folders for Install
$chip_readme = Get-Content "$($volume):\ChipSet\Intel\$($model)\$($os_version)\README.html"
$chip_file = $chip_readme | Select-String -Pattern '(?<=href\=\"\.\.\/\.\.\/).+exe(?=\"\>)'
$chip_exe = "$($volume):\ChipSet\Intel\$(($chip_file.Matches[0].Value).Replace("/", "\"))"
$mlnx_file = (Get-ChildItem -Path "$($volume):\Network\Mellanox\ConnectX4-5-6\$($os_version)\" -Filter *.exe | Select-Object -First 1).Name
$mlnx_exe = "$($volume):\Network\Mellanox\ConnectX4-5-6\$($os_version)\$($mlnx_file)"
$strg_folder = "$($volume):\Storage\Intel\C600"

# Install Chipset Driver
& $chip_exe -silent
Start-Sleep -Seconds 5

# Install Mellanox Driver
$log_file = "c:\temp\$(get-date -f "yyyy-MM-dd_HH-mm-ss")mlnx-log.txt"
& $mlnx_exe /S /v/qn /v"/l*vx $log_file"
Start-Sleep -Seconds 5

# Install Storage Drivers
Start-Process PNPUtil -ArgumentList "/add-driver","$($strg_folder)\*.inf","/install"
Exit(0)
