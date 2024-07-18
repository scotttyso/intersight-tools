## EZCLAIM Synopsis

The purpose of `ezclaim.py` is to register Standalone C-Series to Intersight.

See example YAML File `examples/ezclaim/ezclaim.yaml`.

Examples:

### Load Sensitive Variables into Environment

#### Linux

```bash
## Bash Intersight Variables
export intersight_api_key_id="<your_intersight_api_key>"
export intersight_secret_key="~/Downloads/SecretKey.txt"
export local_user_password_1="<cimc-password>"
export proxy_password="<proxy-password-if-required>"
```

#### Windows

```powershell
## Powershell Intersight Variables
$env:intersight_api_key_id="<your_intersight_api_key>"
$env:intersight_secret_key="$HOME\Downloads\SecretKey.txt"
$env:local_user_password_1="<cimc-password>"
$env:proxy_password="<proxy-password-if-required>"
```

### Run the Script

#### Linux

```bash
./ezclaim.py -y {device_list.yaml}
```

#### Windows

```powershell
.\ezclaim.py -y {device_list.yaml}
```

### Example YAML File


### [Back to Top](#ezclaim-synopsis)

