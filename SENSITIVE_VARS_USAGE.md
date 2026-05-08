# Using Sensitive Variables in Jinja Templates

## Overview

Sensitive environment variables are now validated during `load_configurations()` and securely stored in `kwargs.sensitive_vars` as a `DotMap` dictionary.

## Usage Pattern

### In Jinja Templates

Pass `sensitive_vars` to your template context alongside other data:

```python
rendered = template_env.get_template(template_name).render(
    item              = render_item,
    isight            = kwargs.intersight_api,
    name_prefix       = np,
    name_suffix       = ns,
    object_map        = kwargs.intersight_object_map,
    organization      = kwargs.org,
    org_moids         = kwargs.org_moids,
    rsg_moids         = kwargs.rsg_moids,
    sensitive_vars    = kwargs.sensitive_vars,  # NEW: pass sensitive dict
)
```

### Template Examples

#### iSCSI Boot Password:
```jinja2
{
  "Chap": {
    "Password": "{{ sensitive_vars.iscsi_boot_password_1 }}",
    "UserId": "{{ item.username | default('') }}"
  }
}
```

#### LDAP Bind Password:
```jinja2
{
  "BindPassword": "{{ sensitive_vars.ldap_binding_password_1 }}",
  "BindDn": "{{ item.bind_dn }}"
}
```

#### Drive Security Passphrase:
```jinja2
{
  "Passphrase": "{{ sensitive_vars.drive_security_current_security_key_passphrase }}"
}
```

#### Cisco.com Password (CCO):
```jinja2
{
  "Password": "{{ sensitive_vars.cco_password }}"
}
```

## Security Considerations

- ✓ Sensitive values **only in memory** during template rendering
- ✓ **Never logged** or persisted in config files
- ✓ **Validated at load time** - missing variables fail immediately
- ✓ **Namespaced clearly** - all sensitive data accessed via `sensitive_vars`
- ✓ **Audit trail** - templates explicitly reference sensitive fields

## Environment Variable Naming Convention

Sensitive variables follow this pattern:

```
{PREFIX}_{NUMBER}  # For numbered variables (e.g., passwords 1-64)
{PREFIX}           # For singular variables (e.g., API keys)
```

### Common Prefixes:

| Prefix | Template Usage | Count |
|--------|---|---|
| `iscsi_boot_password` | `sensitive_vars.iscsi_boot_password_1` through `_64` | Multiple |
| `ldap_binding_password` | `sensitive_vars.ldap_binding_password_1` | Multiple |
| `drive_security_current_security_key_passphrase` | `sensitive_vars.drive_security_current_security_key_passphrase` | Single |
| `cco_password` | `sensitive_vars.cco_password` | Single |
| `intersight_api_key_id` | `sensitive_vars.intersight_api_key_id` | Single |
| `fabric_interconnect_password` | `sensitive_vars.fabric_interconnect_password_1` through `_32` | Multiple |
| `linux_password` | `sensitive_vars.linux_password_1` through `_32` | Multiple |

## Export Commands

Required environment variables are exported as:

```bash
export iscsi_boot_password_1='your_password'
export ldap_binding_password_1='your_password'
export cco_password='your_password'
```

## Validation Flow

```
load_configurations()
  ↓
validate_all_sensitive_variables(model, schema_path)
  ↓
Checks schema for required sensitive var references
  ↓
Reads all env vars (fails if missing)
  ↓
Returns (success, missing_vars, error_messages, sensitive_vars_dict)
  ↓
Store in kwargs.sensitive_vars if successful
  ↓
Pass to templates as sensitive_vars parameter
```

## Example: Adding to a New Template

```jinja2
# File: classes/templates/intersight/policies/my_policy.json.j2
{
  "Name": {{ (name_prefix ~ item.name ~ name_suffix) | tojson }},
  "SecretField": "{{ sensitive_vars.my_sensitive_variable }}",
  "PublicField": "{{ item.public_value }}"
}
```

Then in your Python code:

```python
rendered = template_env.get_template('my_policy.json.j2').render(
    item           = item,
    name_prefix    = np,
    name_suffix    = ns,
    sensitive_vars = kwargs.sensitive_vars  # Make it available
)
```
