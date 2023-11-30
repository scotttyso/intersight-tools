Install-Module PowerShellGet -AllowClobber -Force
Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
Install-Module -Name AzStackHci.EnvironmentChecker
$session = New-PSSession -ComputerName azs-cl01-host1.ucs-spaces.lab -Credential $credential
Invoke-AzStackHciConnectivityValidation -PsSession $session
Invoke-AzStackHciConnectivityValidation -PsSession $session -PassThru