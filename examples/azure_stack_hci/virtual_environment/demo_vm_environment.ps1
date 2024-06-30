$internal_adapter = New-VMSwitch -SwitchName "vEthernet (Internal - Virtual Switch)" -SwitchType Internal
New-NetIPAddress -IPAddress 192.168.0.1 -PrefixLength 24 -InterfaceIndex $internal_adapter.ifIndex
New-NetNat -Name Internal -InternalIPInterfaceAddressPrefix 192.168.0.0/24

$https_port = 5443
$ip = 91
$rdp_port = 13389
$virtual_machines = @("azs-cls01-n01", "azs-cls01-n02")
foreach ($vm in $virtual_machines) {
    If ([bool]!($rdp_port%2)) { $base_path = "L:\"
    } else { $base_path = "K:\"}
    $vm_path = $base_path + "Hyper-V\"
    New-Vm -Name $vm -MemoryStartupBytes 32GB -Generation 2 -Path $vm_path
    Add-VMDvdDrive -VMName $vm -Path "C:\Users\tyscott\Downloads\AzureStackHCI_20349.1607_en-us.iso"
    Add-VmNetworkAdapter -VmName $vm
    Get-VmNetworkAdapter -VmName $vm|Connect-VmNetworkAdapter -SwitchName $internal_adapter.Name
    Get-VmNetworkAdapter -VmName $vm|Set-VmNetworkAdapter -MacAddressSpoofing On
    Set-VmProcessor -VmName $vm -Count 8
    new-VHD -Path "$($vm_path)\$($vm)\VirtualDisk\system.vhdx" -SizeBytes 127GB
    new-VHD -Path "$($vm_path)\$($vm)\VirtualDisk\data.vhdx" -SizeBytes 127GB
    Add-VMHardDiskDrive -VmName $vm -Path "$($vm_path)\$($vm)\VirtualDisk\system.vhdx"
    Add-VMHardDiskDrive -VmName $vm -Path "$($vm_path)\$($vm)\VirtualDisk\data.vhdx"
    foreach ($x in 1..6) {
        new-VHD -Path "$($vm_path)\$($vm)\VirtualDisk\s2d$($x).vhdx" -SizeBytes 1024GB
        Add-VMHardDiskDrive -VmName $vm -Path "$($vm_path)\$($vm)\VirtualDisk\s2d$($x).vhdx"
    }
    Set-VMKeyProtector -VMName $vm -NewLocalKeyProtector
    Enable-VmTpm -VmName $vm
    Get-VMIntegrationService -VmName $vm |Where-Object {$_.name -like "T*"}|Disable-VMIntegrationService
    Set-VmProcessor -VmName $vm -ExposeVirtualizationExtensions $true
    Add-NetNatStaticMapping -NatName Internal -ExternalIPAddress 0.0.0.0 -InternalIPAddress "192.168.0.$($ip)" -Protocol TCP -ExternalPort $https_port -InternalPort 443
    Add-NetNatStaticMapping -NatName Internal -ExternalIPAddress 0.0.0.0 -InternalIPAddress "192.168.0.$($ip)" -Protocol TCP -ExternalPort $rdp_port -InternalPort 3389
    $https_port ++
    $ip ++
    $rdp_port ++
}
