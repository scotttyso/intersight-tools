# configure api signing params
. "$PSScriptRoot\apiv1.ps1"

$fabricInterconnects = Get-IntersightNetworkElementSummary -Filter "Contains(Name,'cx-hx-fi2-ucsm') " -Top 1000

foreach($fi in $fabricInterconnects.Results)
{
    Write-Host $fi.Name

    $filter = "Ancestors.Moid eq '" + $fi.Moid + "'" 
    $totalPorts = Get-IntersightEtherPhysicalPort -Filter $filter -Top 1000 -InlineCount allpages
    Write-Host "Total Ports: " $totalPorts.Count

    $filter = "Ancestors.Moid eq '" + $fi.Moid + "' and Role eq 'unknown'" 
    $availablePorts = Get-IntersightEtherPhysicalPort -Filter $filter -Top 1000 -InlineCount allpages
    Write-Host "Available Ports: " $availablePorts.Count

    Write-Host "Used Ports: " ($totalPorts.Count - $availablePorts.Count) "`n"

}  