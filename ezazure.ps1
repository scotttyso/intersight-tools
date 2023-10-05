# sudo apt-get -y install gss-ntlmssp
# pwsh -Command 'Install-Module -Name PSWSMan'
# JUMP HOST REQUIREMENTS
# Add-WindowsFeature -Name rsat-hyper-v-tools, rsat-adds-tools, failover-clustering, rsat-feature-tools-bitlocker-bdeaducext, gpmc -IncludeManagementTools
# 
#"""
# Script will complete host configuration after OS Installation.
# Includes All OS Customization of the AzureStack HCI Cisco Validated Design
#  * Bogna Trimouillat - btrimoui@cisco.com
#  * Tyson Scott 10/1/2023 - tyscott@cisco.com
#"""

#=============================================================================
# JSON File is a Required Parameter
# Pull in JSON Content
#=============================================================================
param (
    [switch]$force,
    [string]$j=$(throw "-j <json_file> is required.")
)
#=====================================================
# Start Log and Configure PowerCLI
#=====================================================
Start-Transcript -Path ".\Logs\$(get-date -f "yyyy-MM-dd_HH-mm-ss")_$($env:USER).log" -Append -Confirm:$false
Get-PSSession | Remove-PSSession | Out-Null

#=====================================================
# Setup Variables for Environment
#=====================================================
$feature_list = ("Hyper-V", "Failover-Clustering", "Data-Center-Bridging", "Bitlocker" , "FS-FileServer",
    "FS-SMBBW", "Hyper-V-PowerShell", "RSAT-AD-Powershell", "RSAT-Clustering-PowerShell", "NetworkATC",
    "NetworkHUD", "FS-DATA-Deduplication")
$jdata      = Get-Content -Path $j | ConvertFrom-Json
$cluster    = $jdata.cluster
$link_speed = $jdata.link_speed
$username   = $jdata.username
$password   = ConvertTo-SecureString $env:windows_administrator_password -AsPlainText -Force;
$credential = New-Object System.Management.Automation.PSCredential ($username,$password);
Enable-WSManCredSSP -Role "Client" -DelegateComputer $jdata.node_list -Force | Out-Null

#=============================================================================
# Configure Time Zone, Firewall Rules, and Installed Features
#=============================================================================
foreach ($node in $jdata.node_list) {
    Write-Host "Logging into Host $($node)" -ForegroundColor Yellow
    New-PSSession -ComputerName $node -Credential $credential | Out-Null
}
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
$session_results = Invoke-Command $sessions -ScriptBlock {
    $jdata = $Using:jdata
    ##########
    Write-Host "$($env:COMPUTERNAME) Beginning time zone '$($jdata.timezone)' Configuration." -ForegroundColor Yellow
    $tz = Get-TimeZone
    if (!($tz.Id -eq $jdata.timezone)) {Set-Timezone $jdata.timezone}
    $tz = Get-TimeZone
    if ($tz.Id -eq $jdata.timezone) {
        Write-Host " * $($env:COMPUTERNAME) Successfully Set Timezone to '$($jdata.timezone)'." -ForegroundColor Green
    } else {
        Write-Host " * $($env:COMPUTERNAME) Failed to Set Timezone to '$($jdata.timezone)'.  Exiting..." -ForegroundColor Red
        Return New-Object PsObject -property @{completed=$False}
    }
    Write-Host "$($env:COMPUTERNAME) Compeleted time zone '$($jdata.timezone)' Configuration." -ForegroundColor Yellow
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
    $gva = Get-PSSessionConfiguration -Name 'VirtualAccount'
    if (!($gva)) {
        Write-Host "$($env:COMPUTERNAME) Failed on VirtualAccount Check.  Please Run the Following PowerShell Command On Each Host." -ForegroundColor Red
        Write-Host " * Run: New-PSSessionConfigurationFile -RunAsVirtualAccount -Path .\VirtualAccount.pssc" -ForegroundColor Red
        Write-Host " * Run: Register-PSSessionConfiguration -Name 'VirtualAccount' -Path .\VirtualAccount.pssc -Force" -ForegroundColor Red
        Write-Host " * Validate with: Get-PSSessionConfiguration -Name 'VirtualAccount'" -ForegroundColor Red
        Return New-Object PsObject -property @{completed=$False}
    }
    Return New-Object PsObject -property @{completed=$True;reboot=$reboot}
}
#==============================================
# Setup Environment for Next Loop
#==============================================
#$session_results | Format-Table | Out-String|ForEach-Object {Write-Host $_}
$nodes = [object[]] @()
$reboot_count = 0
foreach ($result in $session_results) {
    if ($result.completed -eq $True) { $nodes += $result.PSComputerName}
    if ($result.reboot -eq $True) { $reboot_count++ | Out-Null }
}
Get-PSSession | Remove-PSSession | Out-Null
#==============================================
# Confirm All Nodes Completed
#==============================================
if (!$nodes.Length -eq $jdata.node_list.Length) {
    Write-Host "One or More Nodes Failed on Previous Task." -ForegroundColor Red
    Write-Host " * Original Node List: $($jdata.node_list)" -ForegroundColor Red
    Write-Host " * Completed Node List: $nodes" -ForegroundColor Red
    Write-Host "Please Review the Log Data.  Exiting..." -ForegroundColor Red
    Stop-Transcript
    Exit 1
}
#==============================================
# Sleep 10 Minutes if reboot_count gt 0
#==============================================
if ($reboot_count -gt 0) {
    Write-Host "Sleeping for 10 Minutes to Wait for Server Reboots." -ForegroundColor Yellow
    Start-Sleep -Seconds 600
}
foreach ($node in $jdata.node_list) {
    Write-Host "Logging into Host $($node)" -ForegroundColor Yellow
    New-PSSession -ComputerName $node -ConfigurationName "VirtualAccount" -Credential $credential
}
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
$session_results = Invoke-Command $sessions -Script {
    Write-Host "$($env:COMPUTERNAME) Beginning Check for NuGet and PSWindowsUpdate." -ForegroundColor Yellow
    $fng = Find-Package -Name NuGet
    if (!($fng | Where-Object {$_.Version -gt 2.8.5.200})) {
        Write-Host " * $($env:COMPUTERNAME) Installing NuGet Version 2.8.5.201." -ForegroundColor Green
        Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force
    } else {
        Write-Host " * $($env:COMPUTERNAME) NuGet Version 2.8.5.201+ Already Installed." -ForegroundColor Cyan
    }
    Write-Host "$($env:COMPUTERNAME) Completed Check for NuGet and PSWindowsUpdate." -ForegroundColor Yellow
    if (!(Get-Module -ListAvailable -Name PSWindowsUpdate)) {
        Write-Host " * $($env:COMPUTERNAME) Installing PSWindowsUpdate." -ForegroundColor Green
        Install-Module PSWindowsUpdate -Confirm:$False -Force
    } else {
        Write-Host " * $($env:COMPUTERNAME) PSWindowsUpdate Already Installed." -ForegroundColor Cyan
    }
    Import-Module PSWindowsUpdate
    $reboot = $False
    Write-Host "$($env:COMPUTERNAME) Beginning Check for Windows Updates." -ForegroundColor Yellow
    $gwu = Get-WUList -MicrosoftUpdate
    $gwu | Format-Table | Out-String|ForEach-Object {Write-Host $_}
    if ($gwu) {
        Write-Host " * $($env:COMPUTERNAME) Installing Windows Updates and Rebooting Host if Required." -ForegroundColor Green
        Install-WindowsUpdate -MicrosoftUpdate -AcceptAll -AutoReboot
        $reboot = $True
    } else {
        Write-Host " * $($env:COMPUTERNAME) Windows already up to date." -ForegroundColor Cyan
    }
    Write-Host "$($env:COMPUTERNAME) Completed Check for Windows Updates." -ForegroundColor Yellow
    Return New-Object PsObject -property @{completed=$True;reboot=$reboot}
}
#==============================================
# Setup Environment for Next Loop
#==============================================
$nodes = [System.Collections.ArrayList]@()
$reboot_count = 0
foreach ($result in $session_results) {
    if ($result.completed -eq $True) { $nodes.Add($result.PSComputerName)}
    if ($result.reboot -eq $True) { $reboot_count++ | Out-Null }
}
Get-PSSession | Remove-PSSession | Out-Null
#==============================================
# Confirm All Nodes Completed
#==============================================
if (!$nodes.Length -eq $jdata.node_list.Length) {
    Write-Host "One or More Nodes Failed on Previous Task." -ForegroundColor Red
    Write-Host " * Original Node List: $($jdata.node_list)" -ForegroundColor Red
    Write-Host " * Completed Node List: $nodes" -ForegroundColor Red
    Write-Host "Please Review the Log Data.  Exiting..." -ForegroundColor Red
    Stop-Transcript
    Exit 1
}
#==============================================
# Sleep 10 Minutes if reboot_count gt 0
#==============================================
if ($reboot_count -gt 0) {
    Write-Host "Sleeping for 10 Minutes to Wait for Server Reboots." -ForegroundColor Yellow
    Start-Sleep -Seconds 600
}

foreach ($node in $jdata.node_list) {
    Write-Host "Logging into Host $($node)" -ForegroundColor Yellow
    New-PSSession -ComputerName $node -Credential $credential
}
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
$session_results = Invoke-Command $sessions -ScriptBlock {
    Function RegistryKey {
        Param([string]$registry_path, [object]$key)
        $tp = Test-Path -path $registry_path
        if (!($tp)) {
            New-Item $registry_path
        }
        $reg = Get-ItemProperty -Path $registry_path
        if ($null -eq $reg.($key.name)) {
            New-Itemproperty -Path $registry_path -Name $key.name -Value $key.value -PropertyType $key.type | Out-Null
        } elseif (!($reg.($key.name) -eq $key.value)) {
            Write-Host "Update"
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
    $jdata = $Using:jdata
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
    Write-Host "$($env:COMPUTERNAME) Beginning Secure Boot State Check." -ForegroundColor Yellow
    $sb = Confirm-SecureBootUEFI
    if (!($sb -eq $true)) {
        Write-Host "$($env:COMPUTERNAME) Secure Boot State is not Enabled.  Exiting..." -ForegroundColor Red
        Return New-Object PsObject -property @{completed=$False}
    }
    Write-Host "$($env:COMPUTERNAME) Completed Secure Boot State Check." -ForegroundColor Yellow
    ##########
    Write-Host "$($env:COMPUTERNAME) Beginning Remote Desktop Access Configuration." -ForegroundColor Yellow
    $registry_path = "HKLM:\System\CurrentControlSet\Control\Terminal Server"
    $key = New-Object PsObject -property @{name="fDenyTSConnections"; value=0; type="Dword" }
    $regkey = RegistryKey $registry_path $key
    if (!($regkey.Completed -eq $True)) { Return New-Object PsObject -property @{completed=$False} }
    Write-Host "$($env:COMPUTERNAME) Completed Remote Desktop Access Configuration." -ForegroundColor Yellow
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
    Write-Host "$($env:COMPUTERNAME) Beginning Windows Secure Core Configuration." -ForegroundColor Yellow
    $registry_path = "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity"
    $key = New-Object PsObject -property @{name="Enabled"; value=1; type="Dword" }
    $regkey = RegistryKey $registry_path $key
    if (!($regkey.Completed -eq $True)) { Return New-Object PsObject -property @{completed=$False} }
    $key = New-Object PsObject -property @{name="WasEnabledBy"; value=0; type="Dword" }
    $regkey = RegistryKey $registry_path $key
    if (!($regkey.Completed -eq $True)) { Return New-Object PsObject -property @{completed=$False} }
    $registry_path = "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\SystemGuard"
    $key = New-Object PsObject -property @{name="Enabled"; value=1; type="Dword" }
    $regkey = RegistryKey $registry_path $key
    if (!($regkey.Completed -eq $True)) { Return New-Object PsObject -property @{completed=$False} }
    Write-Host "$($env:COMPUTERNAME) Completed Windows Secure Core Configuration." -ForegroundColor Yellow
    ###
    # MSINFo32.EXE on page 78
    Write-Host "$($env:COMPUTERNAME) Beginning Retrieval of physical NIC port names." -ForegroundColor Yellow
    $adapter_list = [System.Collections.ArrayList]@("SlotID 2 Port 1", "SlotID 2 Port 2")
    $gna = Get-NetAdapter
    foreach ($adapter in $adapter_list) {
        if ($gna | Where-Object {$_.Name -eq $adapter -and $_.Status -eq "Up" -and $_.LinkSpeed -eq $Using:link_speed}) {
            Write-Host " * $($env:COMPUTERNAME) Matched NetAdapter $adapter." -ForegroundColor Green
        } else {
            Write-Host " * $($env:COMPUTERNAME) Failed to Match NetAdapter '$adapter' with Status: 'Up', LinkSpeed: '$($Using:link_speed)'.  Exiting..." -ForegroundColor Red
            $gna | Format-Table Name, InterfaceDescription, Status, MacAddress, LinkSpeed | Out-String|ForEach-Object {Write-Host $_}
            Return New-Object PsObject -property @{completed=$False}
        }
    }
    Write-Host "$($env:COMPUTERNAME) Completed Retrieval of physical NIC port names." -ForegroundColor Yellow
    Write-Host "$($env:COMPUTERNAME) Beginning Create and Deploy Standalone Network ATC Intent." -ForegroundColor Yellow
    $gnis = Get-NetIntentStatus
    if (!($gnis | Where-Object {$_.IntentName -eq "mgmt_compute_storage" -and $_.ConfigurationStatus -eq "Success" -and $_.ProvisioningStatus -eq "Completed" -and $_.IsComputeIntentSet -eq $True -and $_.IsManagementIntentSet -eq $True -and $_.IsStorageIntentset -eq $True -and $_.IsStretchIntentSet -eq $True})) {
        if ($gnis | Where-Object {$_.IntentName -eq "mgmt_compute_storage"}) {
            Write-Host " * $($env:COMPUTERNAME) Failed to match NetIntent 'mgmt_compute_storage' with:" -ForegroundColor Red
            Write-Host "   ConfigurationStatus: 'Success'`   ProvisioningStatus: 'Completed'`   IsComputeIntentSet: 'True'" -ForegroundColor Red
            Write-Host "   IsManagementIntentSet: 'True'`   IsStorageIntentset: 'True'`   IsStretchIntentSet: 'True'.  `Exiting..." -ForegroundColor Red
            $gnis | Format-Table Host,IntentName,ConfigurationStatus,Error,ProvisioningStatus,IsComputeIntentSet,IsManagementIntentSet,IsStorageIntentset,IsStretchIntentSet | Out-String|ForEach-Object {Write-Host $_}
            Return New-Object PsObject -property @{completed=$False}
        } else {
            $AdapterOverride = New-NetIntentAdapterPropertyOverrides
            $AdapterOverride.NetworkDirectTechnology = 4
            $AdapterOverride
            $QoSOverride = New-NetIntentQoSPolicyOverRides
            $QoSOverride.PriorityValue8021Action_SMB = 4
            $QoSOverride.PriorityValue8021Action_Cluster = 5
            $QoSOverride
            $StorageOverride = new-NetIntentStorageOverrides
            $StorageOverride.EnableAutomaticIPGeneration = $false
            $StorageOverride
            $null = Add-NetIntent -AdapterName $adapter_list -Management -Compute -Storage -StorageVlans $jdata.storage_vlans[0].vlan_id, $jdata.storage_vlans[1].vlan_id -QoSPolicyOverrides $QoSOverride -AdapterPropertyOverrides $AdapterOverride -StorageOverrides $Storageoverride -Name mgmt_compute_storage
        }
    }
    $gnis = Get-NetIntentStatus
    if ($gnis | Where-Object {$_.IntentName -eq "mgmt_compute_storage" -and $_.ConfigurationStatus -eq "Success" -and $_.ProvisioningStatus -eq "Completed" -and $_.IsComputeIntentSet -eq $True -and $_.IsManagementIntentSet -eq $True -and $_.IsStorageIntentset -eq $True -and $_.IsStretchIntentSet -eq $True}) {
        Write-Host " * $($env:COMPUTERNAME) Matched NetIntent Network 'mgmt_compute_storage' Settings." -ForegroundColor Green
    } else {
        Write-Host " * $($env:COMPUTERNAME) Failed to match NetIntent 'mgmt_compute_storage' with:" -ForegroundColor Red
        Write-Host "   ConfigurationStatus: 'Success'`   ProvisioningStatus: 'Completed'`   IsComputeIntentSet: 'True'" -ForegroundColor Red
        Write-Host "   IsManagementIntentSet: 'True'`   IsStorageIntentset: 'True'`   IsStretchIntentSet: 'True'.  `Exiting..." -ForegroundColor Red
        $gnis | Format-Table Host,IntentName,ConfigurationStatus,Error,ProvisioningStatus,IsComputeIntentSet,IsManagementIntentSet,IsStorageIntentset,IsStretchIntentSet | Out-String|ForEach-Object {Write-Host $_}
        Return New-Object PsObject -property @{completed=$False}
    }
    Write-Host "$($env:COMPUTERNAME) Verifying Management vNIC in parent partition." -ForegroundColor Yellow
    $gna = Get-NetAdapter
    $gna_count = 0
    $vnames = @("vManagement(mgmt_compute_storage)", "vSMB(mgmt_compute_storage#SlotID 2 Port 1)", "vSMB(mgmt_compute_storage#SlotID 2 Port 2)")
    foreach ($vname in $vnames) {
        if ($gna | Where-Object {$_.Name -eq $vname -and $_.Status -eq "Up" -and $_.LinkSpeed -eq $Using:link_speed}) { $gna_count++ | Out-Null }
    }
    if ($gna_count -eq 3) {
        Write-Host " * $($env:COMPUTERNAME) Verified Virtual NIC Creation." -ForegroundColor Green
    } else {
        Write-Host " * $($env:COMPUTERNAME) Failed to Match Virtual NIC Creation.  Expected:" -ForegroundColor Red
        foreach ($vname in $vnames) {
            Write-Host "   Name: $vname, with Status: 'Up', LinkSpeed: '$($Using:link_speed)'" -ForegroundColor Red
        }
        $gna | Format-Table Name, InterfaceDescription, Status, MacAddress, LinkSpeed | Out-String|ForEach-Object {Write-Host $_}
        Return New-Object PsObject -property @{completed=$False}
    }
    Write-Host "  * $($env:COMPUTERNAME) Verifying Virtual Switch." -ForegroundColor Cyan
    $gvsw = Get-VMSwitch
    if ($gvsw | Where-Object {$_.Name -eq "ConvergedSwitch(mgmt_compute_storage)" -and $_.SwitchType -eq "External" -and $_.NetAdapterInterfaceDescription -eq "Teamed-Interface"}) {
        Write-Host " * $($env:COMPUTERNAME) Matched Virtual Switch Settings." -ForegroundColor Green
    } else {
        Write-Host " * $($env:COMPUTERNAME) Failed to Match Virtual Switch Settings.  Expected:" -ForegroundColor Red
        Write-Host "   Name: 'ConvergedSwitch(mgmt_compute_storage)', `SwitchType: 'External', `NetAdapterInterfaceDescription: 'Teamed-Interface'.  `Exiting..." -ForegroundColor Red
        $gvsw | Format-Table Name, SwitchType, NetAdapterInterfaceDescription, NetAdapterInterfaceDescriptions | Out-String|ForEach-Object {Write-Host $_}
        Return New-Object PsObject -property @{completed=$False}
    }
    Write-Host "  * $($env:COMPUTERNAME) Verifying SET Switch Load Balancing Algorithm." -ForegroundColor Cyan
    $gvsw = Get-VMSwitch | Get-VMSwitchTeam
    if ($gvsw | Where-Object {$_.Name -eq "ConvergedSwitch(mgmt_compute_storage)" -and $_.LoadBalancingAlgorithm -eq "HyperVPort"}) {
        Write-Host " * $($env:COMPUTERNAME) Matched SET Switch Load Balancing Algorithm." -ForegroundColor Green
    } else {
        Write-Host " * $($env:COMPUTERNAME) Failed to Match SET Switch Load Balancing Algorithm.  Expected: `Name: 'ConvergedSwitch(mgmt_compute_storage)', `LoadBalancingAlgorithm: 'HyperVPort'.  `Exiting..." -ForegroundColor Red
        $gvsw | Format-List | Out-String|ForEach-Object {Write-Host $_}
        Return New-Object PsObject -property @{completed=$False}
    }
    Write-Host "$($env:COMPUTERNAME) Completed Network ATC Intent Status Configuration." -ForegroundColor Yellow
    # CONFIRM ITEMS
    # Variables for Storage VLANs
    # $jdata.storage_vlans[0].gateway
    # $jdata.storage_vlans[1].gateway
    # Two Default Routes or One
    Write-Host "$($env:COMPUTERNAME) Beginning Configuring default route for Management NIC " -ForegroundColor Yellow
    $gateway_a = $jdata.storage_vlans[0].gateway
    $gateway_b = $jdata.storage_vlans[1].gateway
    $g_mgmt_route = Get-NetRoute | Where-Object {$_.DestinationPrefix -eq "0.0.0.0/0"}
    if ($g_mgmt_route | Where-Object {$_.DestinationPrefix -eq "0.0.0.0/0" -and $_.Gateway -eq $gateway_a -and $_.Metric -eq 10}) {
        New-NetRoute -DestinationPrefix 0.0.0.0/0 -InterfaceAlias "vManagement(mgmt_compute_storage)” -NextHop $gateway_a -RouteMetric 10
    }
    if ($g_mgmt_route | Where-Object {$_.DestinationPrefix -eq "0.0.0.0/0" -and $_.Gateway -eq $gateway_b -and $_.Metric -eq 10}) {
        New-NetRoute -DestinationPrefix 0.0.0.0/0 -InterfaceAlias "vManagement(mgmt_compute_storage)” -NextHop $gateway_b -RouteMetric 10
    }
    $mgmt_route_count = 0
    $g_mgmt_route = Get-NetRoute | Where-Object {$_.DestinationPrefix -eq "0.0.0.0/0"}
    if ($g_mgmt_route | Where-Object {$_.DestinationPrefix -eq "0.0.0.0/0" -and $_.Gateway -eq $gateway_a -and $_.Metric -eq 10}) {
        $mgmt_route_count++ | Out-Null
    }
    if ($g_mgmt_route | Where-Object {$_.DestinationPrefix -eq "0.0.0.0/0" -and $_.Gateway -eq $gateway_b -and $_.Metric -eq 10}) {
        $mgmt_route_count++ | Out-Null
    }
    if ($mgmt_route_count -eq 2) {
        Write-Host " * $($env:COMPUTERNAME) Verified Default Route for Management NIC." -ForegroundColor Green
    } else {
        Write-Host " * $($env:COMPUTERNAME) Failed to Match Default Route for Management NIC.  Expected:" -ForegroundColor Red
        Write-Host "   -DestinationPrefix: 0.0.0.0/0, with Gateway: $gateway_a, Metric: '10'" -ForegroundColor Red
        Write-Host "   -DestinationPrefix: 0.0.0.0/0, with Gateway: $gateway_b, Metric: '10'" -ForegroundColor Red
        $g_mgmt_route | Where-Object {$_.DestinationPrefix -eq "0.0.0.0/0"} | Out-String|ForEach-Object {Write-Host $_}
        Return New-Object PsObject -property @{completed=$False}
    }
    Write-Host "$($env:COMPUTERNAME) Completed Configuring default route for Management NIC " -ForegroundColor Yellow
    Return New-Object PsObject -property @{completed=$True}
}
#==============================================
# Setup Environment for Next Loop
#==============================================
$nodes = [System.Collections.ArrayList]@()
foreach ($result in $session_results) {
    if ($result.completed -eq $True) { $nodes.Add($result.PSComputerName)}
}
Get-PSSession | Remove-PSSession | Out-Null
Remove-Variable session_results
#==============================================
# Confirm All Nodes Completed
#==============================================
if (!$nodes.Length -eq $jdata.node_list.Length) {
    Write-Host "One or More Nodes Failed on Previous Task." -ForegroundColor Red
    Write-Host " * Original Node List: $($jdata.node_list)" -ForegroundColor Red
    Write-Host " * Completed Node List: $nodes" -ForegroundColor Red
    Write-Host "Please Review the Log Data.  Exiting..." -ForegroundColor Red
    Stop-Transcript
    Exit 1
}
$x = $jdata.storage_vlans[0].ip_address -split "."
$prefix_a  = ($jdata.storage_vlans[0].gateway -split ".")[1]
$network_a = "$($x[0]).$($x[1]).$($x[2])."
$host_ip_a = $x[3]
$x = $jdata.storage_vlans[1].ip_address -split "/"
$prefix_b  = ($jdata.storage_vlans[1].gateway -split ".")[1]
$network_b = "$($x[0]).$($x[1]).$($x[2])."
$host_ip_b = $x[3]
$nodes = @()
foreach ($node in $jdata.node_list) {
    $ip_address_a = $network_a+$host_ip_a.ToString()
    $ip_address_b = $network_b+$host_ip_b.ToString()
    $session = New-CimSession -ComputerName $node -Credential $credential
    $gnic = Get-NetIPConfiguration -CimSession $session -InterfaceAlias vSMB*
    if (!($gnic | Where-Object {$_.InterfaceAlias -eq "vSMB(mgmt_compute_storage#SlotID 2 Port 1)" -and $_.IPAddress -eq $ip_address_a -and $_.PrefixLength -eq $prefix_a})) {
        New-NetIPAddress -CimSession $session -InterfaceAlias "vSMB(mgmt_compute_storage#SlotID 2 Port 1)" -IPAddress $ip_address_a -PrefixLength $prefix_a
    }
    if (!($gnic | Where-Object {$_.InterfaceAlias -eq "vSMB(mgmt_compute_storage#SlotID 2 Port 2)" -and $_.IPAddress -eq $ip_address_b -and $_.PrefixLength -eq $prefix_b})) {
        New-NetIPAddress -CimSession $session -InterfaceAlias "vSMB(mgmt_compute_storage#SlotID 2 Port 2)" -IPAddress $ip_address_b -PrefixLength $prefix_b
    }
    $gnic = Get-NetIPConfiguration -CimSession $session -InterfaceAlias vSMB*
    if ($gnic | Where-Object {$_.InterfaceAlias -eq "vSMB(mgmt_compute_storage#SlotID 2 Port 1)" -and $_.IPAddress -eq $ip_address_a -and $_.PrefixLength -eq $prefix_a}) {
        Write-Host " * $($env:COMPUTERNAME) Matched vSMB(mgmt_compute_storage#SlotID 2 Port 1)." -ForegroundColor Green
    } else {
        Write-Host " * $($env:COMPUTERNAME) Failed to Match vSMB(mgmt_compute_storage#SlotID 2 Port 1).  Expected: " -ForegroundColor Red
        Write-Host "   Name: 'vSMB(mgmt_compute_storage#SlotID 2 Port 1)' `   IP Address: $ip_address_a`   Prefix: $prefix_a   `Exiting..." -ForegroundColor Red
        $gnic | Format-Table | Out-String|ForEach-Object {Write-Host $_}
        Exit 1
    }
    if ($gnic | Where-Object {$_.InterfaceAlias -eq "vSMB(mgmt_compute_storage#SlotID 2 Port 2)" -and $_.IPAddress -eq $ip_address_b -and $_.PrefixLength -eq $prefix_b}) {
        Write-Host " * $($env:COMPUTERNAME) Matched vSMB(mgmt_compute_storage#SlotID 2 Port 2)." -ForegroundColor Green
        $node.Add($node)
    } else {
        Write-Host " * $($env:COMPUTERNAME) Failed to Match vSMB(mgmt_compute_storage#SlotID 2 Port 2).  Expected: " -ForegroundColor Red
        Write-Host "   Name: 'vSMB(mgmt_compute_storage#SlotID 2 Port 2)' `   IP Address: $ip_address_b`   Prefix: $prefix_b   `Exiting..." -ForegroundColor Red
        $gnic | Format-Table | Out-String|ForEach-Object {Write-Host $_}
        Exit 1
    }
    $host_ip_a++
    $host_ip_b++
}
Get-CimSession | Remove-CimSession
Remove-Variable session
#==============================================
# Confirm All Nodes Completed
#==============================================
if (!$nodes.Length -eq $jdata.node_list.Length) {
    Write-Host "One or More Nodes Failed on Previous Task." -ForegroundColor Red
    Write-Host " * Original Node List: $($jdata.node_list)" -ForegroundColor Red
    Write-Host " * Completed Node List: $nodes" -ForegroundColor Red
    Write-Host "Please Review the Log Data.  Exiting..." -ForegroundColor Red
    Stop-Transcript
    Exit 1
}
#==============================================
# Log Into Nodes and Run Next Section
#==============================================
foreach ($node in $jdata.node_list) {
    Write-Host "Logging into Host $($node)" -ForegroundColor Yellow
    New-PSSession -ComputerName $node -Credential $credential
}
$sessions = Get-PSSession
$sessions | Format-Table | Out-String|ForEach-Object {Write-Host $_}
$session_results = Invoke-Command $sessions -ScriptBlock {
    Write-Host "$($env:COMPUTERNAME) Begin Removing DNS Registration from Storage vNICs." -ForegroundColor Yellow
    $int_aliases = @("vSMB(mgmt_compute_storage#SlotID 2 Port 1)", "vSMB(mgmt_compute_storage#SlotID 2 Port 2)")
    $gdnsclient = Get-DnsClient -InterfaceAlias vSMB*
    foreach ($int_alias in $int_aliases) {
        if (!($gdnsclient | Where-Object {$_.InterfaceAlias -eq $int_alias -and $_.RegisterThisConnectionsAddress -eq $False})) {
            Set-DnsClient -InterfaceAlias $int_alias -RegisterThisConnectionsAddress:$False
        }
    }
    $gdnsclient = Get-DnsClient -InterfaceAlias vSMB*
    foreach ($int_alias in $int_aliases) {
        if ($gdnsclient | Where-Object {$_.InterfaceAlias -eq $int_alias -and $_.RegisterThisConnectionsAddress -eq $False}) {
            Write-Host " * $($env:COMPUTERNAME) Completed DNS Registration Removal from Storage vNIC: $int_alias." -ForegroundColor Cyan
        } else {
            Write-Host " * $($env:COMPUTERNAME) Failed to remove DNS Registration from Storage vNIC: $int_alias." -ForegroundColor Red
            $gdnsclient | Where-Object {$_.InterfaceAlias -eq $int_alias} | Format-Table InterfaceAlias,RegisterThisConnectionsAddress | Out-String|ForEach-Object {Write-Host $_}
            Return New-Object PsObject -property @{completed=$False}
        }
    }
    Write-Host "$($env:COMPUTERNAME) Completed Removing DNS Registration from Storage vNICs." -ForegroundColor Yellow
    ##########
    Write-Host "$($env:COMPUTERNAME) Begin Configuring vSwitch to pass 802.1p priority marking." -ForegroundColor Yellow
    $gtest = Get-VMNetworkAdapter -ManagementOS
    if (!($gtest | Where-Object {$_.Name -eq “vManagement(mgmt_compute_storage)" -and $_.IeeePriorityTag -eq "On"})) {
        Set-VMNetworkAdapter -Name  “vManagement(mgmt_compute_storage)" -ManagementOS -IeeePriorityTag On
    }
    $gtest = Get-VMNetworkAdapter -ManagementOS
    if ($gtest | Where-Object {$_.Name -eq “vManagement(mgmt_compute_storage)" -and $_.IeeePriorityTag -eq "On"}) {
        Write-Host " * $($env:COMPUTERNAME) Completed Configuring vSwitch to pass 802.1p priority marking." -ForegroundColor Cyan
    } else {
        Write-Host " * $($env:COMPUTERNAME) Failed to Configure vSwitch to pass 802.1p priority marking." -ForegroundColor Red
        $gtest | Where-Object {$_.Name -eq “vManagement(mgmt_compute_storage)"} | Format-Table Name,IeeePriorityTag | Out-String|ForEach-Object {Write-Host $_}
        Return New-Object PsObject -property @{completed=$False}
    }
    Write-Host "$($env:COMPUTERNAME) Completed Configuring vSwitch to pass 802.1p priority marking." -ForegroundColor Yellow
    Write-Host "$($env:COMPUTERNAME) Begin Validating vNIC VLANs Configuration." -ForegroundColor Yellow
    $gtest = Get-VMNetworkAdapter -ManagementOS | Get-VMNetworkAdapterIsolation
    $icount = 0
    foreach ($int_alias in $int_aliases) {
        $int_short = ($int_alias.Replace("vSMB(", "")).Replace(")", "")
        $vlan_id = $Using.jdata.stroage_vlans[$icount].vlan_id
        if ($gtest | Where-Object {$_.ParentAdapter -match $int_short -and $_.DefaultIsolationID -eq $vlan_id}) {
            Write-Host " * $($env:COMPUTERNAME) Validated $int_alias VLAN ID: $vlan_id." -ForegroundColor Cyan
        } else {
            Write-Host " * $($env:COMPUTERNAME) Failed to Match $int_alias VLAN ID: $vlan_id." -ForegroundColor Red
            $gtest | Where-Object {$_.ParentAdapter -match $int_short} | Format-Table IsolationMode, DefaultIsolationID, ParentAdapter -AutoSize | Out-String|ForEach-Object {Write-Host $_}
            Return New-Object PsObject -property @{completed=$False}
        }
        icount++ | Out-Null
    }
    Write-Host "$($env:COMPUTERNAME) Completed Validating vNIC VLANs Configuration." -ForegroundColor Yellow

    Write-Host "Verifying NIC status " -ForegroundColor Yellow
    Get-NetAdapter | Sort-Object Name | Format-Table Name,InterfaceDescription,Status,MTUSize,LinkSpeed
    Write-Host "Verifying RDMA and RoCEv2 status on physical NICS " -ForegroundColor Yellow
    Get-NetAdapterAdvancedProperty -InterfaceDescription "Mellanox ConnectX*" -DisplayName "NetworkDirect*" | Format-Table Name, InterfaceDescription,DisplayName,DisplayValue
    Write-Host "Verifying that RDMA is enabled on the Storage vNICs" -ForegroundColor Yellow
    Get-NetAdapterRdma | Format-Table
    Write-Host "Verify Mapping of each storage vNIC to the respective fabric " -ForegroundColor Yellow
    Get-VMNetworkAdapterTeamMapping -ManagementOS | Format-Table ComputerName,NetAdapterName,ParentAdapter
    Write-Host "Verify Storage vNIC RDMA operational status " -ForegroundColor Yellow
    Get-SmbClientNetworkInterface | Format-Table FriendlyName, RDMACapable
    Write-Host " Verifing Traffic Class Configuration " -ForegroundColor Yellow
    Get-NetQosTrafficClass | Format-Table -AutoSize
    Write-Host "Verifying that DCBX is set to Not Willing mode" -ForegroundColor Yellow
    Get-netadapter | Get-NetQosDcbxSetting | Format-Table InterfaceAlias, PolicySet, Willing
    ### Storage Spaces Direct
    Write-Host "Preparing disk for Storage Spaces Direct" -ForegroundColor Yellow
    Write-Host "Cleaning Storage Drives...."
    #Remove Exisiting virtual disks and storage pools
    Update-StorageProviderCache
    Get-StoragePool | Where-Object IsPrimordial -eq $False | Set-StoragePool -IsReadOnly:$False -ErrorAction SilentlyContinue
    Get-StoragePool | Where-Object IsPrimordial -eq $False | Get-VirtualDisk | Remove-VirtualDisk -Confirm:$False -ErrorAction SilentlyContinue
    Get-StoragePool | Where-Object IsPrimordial -eq $False | Remove-StoragePool -Confirm:$False -ErrorAction SilentlyContinue
    Get-PhysicalDisk | Reset-PhysicalDisk -ErrorAction SilentlyContinue
    Get-Disk | Where-Object Number -ne $null | Where-Object IsBoot -ne $True | Where-Object IsSystem -ne $True | Where-Object PartitionStyle -ne RAW | ForEach-Object {
        $_ | Set-Disk -isoffline:$False
        $_ | Set-Disk -isreadonly:$False
        $_ | Clear-Disk -RemoveData -RemoveOEM -Confirm:$False
        $_ | Set-Disk -isreadonly:$True
        $_ | Set-Disk -isoffline:$True
    }
    #Inventory Storage Disks
    Get-Disk | Where-Object {Number -Ne $Null -and IsBoot -Ne $True -and IsSystem -Ne $True -and PartitionStyle -Eq RAW} | Group-Object -NoElement -Property FriendlyName | Format-Table
    #Get-Disk | Where-Object Number -Ne $Null | Where-Object IsBoot -Ne $True | Where-Object IsSystem -Ne $True | Where-Object PartitionStyle -Eq RAW | Group-Object -NoElement -Property FriendlyName | Format-Table
}

$CandidateClusterNode = $jdata.node_list[0]
Invoke-Command $CandidateClusterNode -Credential $credential -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    $null = Enable-WSManCredSSP -Role Server -Force
}
Invoke-Command $CandidateClusterNode -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    $nodes = $Using:jdata.node_list
    Write-Host " Validating Cluster Nodes..." -ForegroundColor Yellow
    Test-Cluster -Node $nodes -Include "System Configuration",Networking,Inventory, “Storage Spaces Direct”
    Write-Host " Creating the cluster..." -ForegroundColor Yellow

    New-Cluster -Name $cluster -Node $nodes -StaticAddress 192.168.126.25 -NoStorage
    Get-Cluster | Format-Table Name, SharedVolumesRoot
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Checking cluster nodes..." -ForegroundColor Yellow
    Get-ClusterNode -Cluster $Using:cluster | Format-Table Name, State, Type
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
$nodes = (Get-ClusterNode -Cluster $cluster).Name
foreach ($node in $nodes) {
    Invoke-Command $node -scriptblock {
        Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
        Write-Host " Identifying and Removing Standalone Network ATC Intent." -ForegroundColor Yellow
        $intent = Get-NetIntent | Where-Object {$_.Scope -Like 'Host' -and $_.IntentName -EQ 'mgmt_compute_storage'}
        Write-Host "Removing Standalone Network ATC Intent $intent" -ForegroundColor Yellow
        Remove-NetIntent -Name $intent.IntentName
    }
}
Invoke-Command  $cluster -Credential $credential -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role Server -Force | Out-Null
}
Invoke-Command $cluster -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Create and Deploy Clustered Network ATC Intent " -ForegroundColor Yellow
    #$clusterName = Get-cluster
    $QoSOverride = New-NetIntentQoSPolicyOverRides
    $AdapterOverride = New-NetIntentAdapterPropertyOverrides
    $storageOverride = new-NetIntentStorageOverrides
    $QoSOverride.PriorityValue8021Action_SMB = 4
    $QoSOverride.PriorityValue8021Action_Cluster = 5
    $AdapterOverride.NetworkDirectTechnology = 4
    $storageOverride.EnableAutomaticIPGeneration = $false
    $QoSOverride
    $AdapterOverride
    $storageOverride
    Add-NetIntent -AdapterName "SlotID 2 Port 1", "SlotID 2 Port 2" -Management -Compute -Storage -StorageVlans 107, 207 -QoSPolicyOverrides $QoSOverride -AdapterPropertyOverrides $AdapterOverride -StorageOverrides $storageoverride -Name mgmt_compute_storage

    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host "Verify Clustered Network ATC Intent Status" -ForegroundColor Yellow
    $clusterName = (Get-cluster).Name
    Get-NetIntent -ClusterName $clusterName| Select-Object IntentName,scope
    Get-NetIntentStatus -ClusterName $clusterName | Select-Object Host, IntentName, ConfigurationStatus, ProvisioningStatus
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
$nodes = (Get-ClusterNode -Cluster $cluster).Name
foreach ($node in $nodes) {
    Invoke-Command $node -Credential $credential -scriptblock {
        Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
        Write-Host " Enabling CredSSP" -ForegroundColor Yellow
        Enable-WSManCredSSP -Role Server -Force | Out-Null
        Write-Host "Verifying NIC Port Status " -ForegroundColor Yellow
        Get-netadapter | Format-Table Name, InterfaceDescription, Status, MTUSize, MacAddress, LinkSpeed
        Write-Host " Disabling CredSSP" -ForegroundColor Yellow
        Disable-WSManCredSSP -Role Server
        Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
        Get-WSManCredSSP
    }
}
Invoke-Command $cluster -Credential $credential -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role Server -Force | Out-Null
}
Invoke-Command $cluster -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Checking cluster networks " -ForegroundColor Yellow
    $clusterName = (Get-cluster).Name
    Get-ClusterNetwork -Cluster $clusterName | Format-Table name,address,state,role -autosize
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
Invoke-Command $cluster -Credential $credential -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role Server -Force | Out-Null
}
Invoke-Command $cluster -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Verifying cluster network interfaces " -ForegroundColor Yellow
    $clusterName = (Get-cluster).Name
    Get-ClusterNetworkInterface -Cluster $clusterName | Sort-Object Name | Format-Table Network, Name
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
Invoke-Command  $cluster -Credential $credential -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role Server -Force | Out-Null
}
Invoke-Command $cluster -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Checking Management cluster network settings " -ForegroundColor Yellow
    $clusterName = (Get-cluster).Name
    Get-ClusterNetwork -Cluster $clusterName -Name “mgmt_compute_storage(Management)” | Format-Table *
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
Invoke-Command $cluster -Credential $credential -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role Server -Force | Out-Null
}

Invoke-Command $cluster -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Verifying Management network exclusion from Live Migration Network list " -ForegroundColor Yellow
    $clusterName = (Get-cluster).Name
    Get-ClusterResourceType -Cluster $clusterName -Name "Virtual Machine" | Get-ClusterParameter -Name MigrationExcludeNetworks | Format-Table *
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
$nodes = (Get-ClusterNode -Cluster $cluster).Name
foreach ($node in $nodes) {
    Invoke-Command $node -scriptblock {
        Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
        Write-Host "Configuring Live Migration to use SMB protocol" -ForegroundColor Yellow
        Set-VMHost -VirtualMachineMigrationPerformanceOption SMB
        Get-VMHost | Format-Table VirtualMachineMigrationPerformanceOption
    }
}
$nodes = (Get-ClusterNode -Cluster $cluster).Name
foreach ($node in $nodes) {
    Invoke-Command $node -scriptblock {
        Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
        Write-Host "Configuring Live Migration Bandwidth Limit: 3625MB" -ForegroundColor Yellow
        Set-SMBBandwidthLimit -Category LiveMigration -BytesPerSecond 3625MB
        Get-SMBBandwidthLimit -Category LiveMigration
    }
}
$nodes = (Get-ClusterNode -Cluster $cluster).Name
foreach ($node in $nodes) {
    Invoke-Command $node -scriptblock {
        $MgmtBandwidthLimit = "10000000"
        Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
        Write-Host "Configuring management vNIC maximum bandwidth Limit: $MgmtBandwidthLimit" -ForegroundColor Yellow
        Set-VMNetworkAdapter -ManagementOS -Name "vManagement(mgmt_compute_storage)" -MaximumBandwidth $MgmtBandwidthLimit
        Write-Host "Verifying management vNIC maximum bandwidth Limit" -ForegroundColor Yellow
        (Get-VMNetworkAdapter -ManagementOS -Name "vManagement(mgmt_compute_storage)").BandwidthSetting | Format-Table ParentAdapter, MaximumBandwidth
    }
}
$FSW = “fsw01.ucs-spaces.lab”
#$FSWDomain = “ucs-spaces.lab”
$ShareName = "FSW-AzS-HCI-M6-C1"
$SharePath = "C:\FileShareWitness\FSW-AzS-HCI-M6-C1"
Invoke-Command -ComputerName $FSW -ScriptBlock {
    #Create Directory on File Share Witness
    Write-Host "Creating directory on files share witness"
    mkdir $Using:SharePath
    #Create file share on the file share witness
    Write-Host "Creating file share on file share witness"
    new-smbshare -Name $Using:ShareName -Path $Using:SharePath -FullAccess “ucs-spaces.lab\Domain Admins", "ucs-spaces.lab\AzS-HCI-M6-C1$", "ucs-spaces.lab\AzS-HCI1-N1$”, "ucs-spaces.lab\AzS-HCI1-N2$”, "ucs-spaces.lab\AzS-HCI1-N3$”, "ucs-spaces.lab\AzS-HCI1-N4$”
    #Verify file share on file share witness
    Write-Host "Verifying file share on file share witness"
    Get-SmbShare -Name $Using:ShareName | Format-Table name,path -AutoSize
    #Verify file share permissions on the file share witness
    Write-Host "Verifing file share permissions on the file share witness"
    Get-SmbShareAccess -Name $Using:ShareName | Format-Table -AutoSize
    #Set file level permissions on the file share directory that match the file share permissions
    Write-Host "Setting file level permissions on the file share directory that match the file share permissions"
    Set-SmbPathAcl -ShareName $Using:ShareName
    #Verify file level permissions on the file share
    Write-Host "Verifying file level permissions on the file share"
    Get-Acl -Path $Using:SharePath | Format-List
}
Get-ClusterResource -Cluster $cluster -Name "File Share Witness" | Get-ClusterParameter -Name SharePath
Invoke-Command $cluster -Credential $credential -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role Server -Force | Out-Null
}
Invoke-Command $cluster -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Configuring Cluster-Aware Updating ... " -ForegroundColor Yellow
    $clusterName = (Get-cluster).Name
    Add-CauClusterRole -ClusterName $clusterName -DaysOfWeek Tuesday,Saturday -IntervalWeeks 3 -MaxFailedNodes 1 -MaxRetriesPerNode 2 -EnableFirewallRules -Force
    Write-Host " Verifying Cluster-Aware Updating configuraiton " -ForegroundColor Yellow
    Get-CauClusterRole -ClusterName $clusterName | Format-Table
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
Invoke-Command $cluster -Credential $credential -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role Server -Force | Out-Null
}

Invoke-Command $cluster -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    $clusterName = (Get-cluster).Name
    Write-Host " Configuring Kernel Soft Reboot  for Cluster Aware Updating ... " -ForegroundColor Yellow
    Get-Cluster -Name $clusterName | Set-ClusterParameter -Name CauEnableSoftReboot -Value 1 -Create
    Write-Host " Verifying Kernel Soft Reboot configuraiton " -ForegroundColor Yellow
    Get-Cluster -Name $clusterName | Get-ClusterParameter -Name CauEnableSoftReboot | Format-Table Name, Value
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
Invoke-Command $cluster -Credential $credential -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role Server -Force | Out-Null
}
Invoke-Command $cluster -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    #$clusterName = (Get-cluster).Name
    Write-Host " Enabling Storage Spaces Direct " -ForegroundColor Yellow
    Enable-ClusterStorageSpacesDirect -Confirm:$false
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
Invoke-Command $cluster -Credential $credential -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role Server -Force | Out-Null
}

Invoke-Command $cluster -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    #$clusterName = (Get-cluster).Name
    Write-Host " Verifying Storage Pools " -ForegroundColor Yellow
    Get-StoragePool | Format-Table friendlyname, OperationalStatus, HealthStatus, IsPrimordial, IsReadonly
    Write-Host " Verifying NVMe SSD Cache Tier " -ForegroundColor Yellow
    Get-PhysicalDisk | Where-Object Usage -eq "Journal" | Format-Table FriendlyName, CanPool, HealthStatus, Usage, Size
    Write-Host " Verifying Storage Tier configuration " -ForegroundColor Yellow
    Get-storagetier | Format-Table FriendlyName, ResiliencySettingName, MediaType, NumberOfDataCopies, PhysicalDiskRedundancy
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
Invoke-Command $cluster -Credential $credential -scriptblock {
    Write-Host "Cluster Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Enabling CredSSP" -ForegroundColor Yellow
    Enable-WSManCredSSP -Role Server -Force | Out-Null
}
Invoke-Command $cluster -Credential $credential -authentication Credssp -scriptblock {
    Write-Host "Host Name:" $env:COMPUTERNAME -ForegroundColor Green
    Write-Host " Creating Virtual Disk " -ForegroundColor Yellow
    New-Volume -StoragePoolFriendlyName “S2D*” -FriendlyName VDisk01 -FileSystem CSVFS_ReFS -ResiliencySettingName Mirror -Size 4TB
    Write-Host " Disabling CredSSP" -ForegroundColor Yellow
    Disable-WSManCredSSP -Role Server
    Write-Host " Verifying that CredSSP are disabled on target server..." -ForegroundColor Yellow
    Get-WSManCredSSP
}
Invoke-Command $cluster -scriptblock {Get-VirtualDisk}
Invoke-Command $cluster -scriptblock {Get-ClusterSharedVolume | Format-Table Name,SharedVolumeInfo,OwnerNode}
Invoke-Command $cluster -Credential $credential -scriptblock {
    Write-Host "$($Using:Cluster) Beginning Configuration of Storage Polices." -ForegroundColor Yellow
    $storage_qos = [System.Collections.ArrayList]@(
        @{name="Copper"  ;min=50; max=100};
        @{name="Bronze"  ;min=100;max=250};
        @{name="Gold"    ;min=50; max=100};
        @{name="Platinum";min=100;max=250};
        @{name="Silver"  ;min=50; max=100}
    )
    $gsqp = Get-StorageQoSPolicy
    foreach ($qos in $storage_qos) {
        if ($gsqp | Where-Object {$_.Name -eq $qos.name -and $_.MinimumIops -eq $qos.min -and $_.MaximumIops -eq $qos.max -and $_.PolicyType -eq "Dedicated"}) {
            Write-Host " * $($Using:cluster) Storage Policy $($qos.name) already configured." -ForegroundColor Cyan
        } elseif ($gsqp | Where-Object {$_.Name -eq $qos.name}) {
            Write-Host " * $($Using:cluster) Storage Policy $($qos.name) created, but settings incorrect...Updating." -ForegroundColor Cyan
            Get-StorageQosPolicy -Name $qos.name | Set-StorageQoSPolicy -MinimumIops $qos.min -MaximumIops $qos.max -PolicyType Dedicated
        } else {
            Write-Host " * $($Using:cluster) Creating Storage Policy $($qos.name)." -ForegroundColor Cyan
            New-StorageQoSPolicy -Name $qos.name -MinimumIops $qos.min -MaximumIops $qos.max -PolicyType Dedicated
        }
    }
    $gsqp = Get-StorageQoSPolicy
    foreach ($qos in $storage_qos.PSObject.Properties) {
        if ($gsqp | Where-Object {$_.Name -eq $qos.name -and $_.MinimumIops -eq $qos.min -and $_.MaximumIops -eq $qos.max -and $_.PolicyType -eq "Dedicated"}) {
            Write-Host " * $($Using:cluster) Storage Policy $($qos.name) Configured." -ForegroundColor Cyan
        } else {
            Write-Host " * $($Using:cluster) Failed Configuring Storage Policy $($qos.name).  Expected:" -ForegroundColor Red
            Write-Host "   MinimumIops: $($qos.min)" -ForegroundColor Red
            Write-Host "   MaximumIops: $($qos.max)" -ForegroundColor Red
            Write-Host "   PolicyType: Dedicated" -ForegroundColor Red
            Get-StorageQoSPolicy -Name $qos.name | Format-Table Name,Status, MinimumIops,MaximumIops,MaximumIOBandwidth,PolicyID
            Return New-Object PsObject -property @{completed=$False}
        }
    }
    Write-Host "$($Using:Cluster) Completed Configuration of Storage Polices." -ForegroundColor Yellow
    Return New-Object PsObject -property @{completed=$True}
}
Exit 0