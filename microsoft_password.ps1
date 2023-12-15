param (
    [string]$p=$(throw "-p 'password' is required")
)
$ad_pass = ConvertTo-SecureString $env:windows_administrator_password -AsPlainText -Force;
$adcreds = New-Object System.Management.Automation.PSCredential ($ad_user,$ad_pass)
${adcreds} | Export-CliXml -Path ".\vcenterpowercli.Cred"