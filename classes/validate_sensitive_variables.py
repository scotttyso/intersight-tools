#!/usr/bin/env python3
"""
Sensitive Variables Validator

Validates all sensitive environment variables required by Ansible playbooks
against a merged data model. Collects ALL missing variables and reports them
together before failing.

This is a precursor validation that runs before any Ansible modules execute.

Usage:
  python3 validate_sensitive_variables.py --model merged_model.json
  python3 validate_sensitive_variables.py --model merged_model.json --schema schema.json

Exit Codes:
  0 — All required sensitive variables found and valid
  1 — One or more sensitive variables missing or invalid
"""

import json
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Schema path (relative to filter_plugins directory)
_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "cisco-ai-pods.json"

# Sensitive variable patterns indexed by prefix
# Maps env_prefix -> (schema_key, description)
# Note: Many env prefixes map to canonical schema keys to avoid duplication
_SENSITIVE_VAR_PATTERNS = {
    "cert_mgmt_certificate": ("certificate", "Pure Storage Certificate"),
    "cert_mgmt_intermediate_certificate": ("certificate", "Pure Storage Intermediate Certificate"),
    "cert_mgmt_passphrase": ("cert_mgmt_passphrase", "Pure Storage Certificate Passphrase"),
    "cert_mgmt_private_key": ("private_key", "Pure Storage Private Key"),
    "cco_password": ("cco_password", "Cisco.com Password"),
    "drive_security_current_security_key_passphrase": ("drive_security_passphrase", "Drive Security Passphrase"),
    "fabric_interconnect_password": ("fabric_interconnect_password", "Fabric Interconnect Password"),
    "intersight_api_key_id": ("intersight_api_key_id", "Intersight API Key"),
    "ipmi_key": ("ipmi_key", "IPMI Key"),
    "iscsi_boot_password": ("iscsi_boot_password", "iSCSI Boot Password"),
    "iso_web_server_password": ("iso_web_server_password", "ISO Web Server Password"),
    "ldap_bind_password": ("ldap_binding_password", "LDAP Bind Password"),
    "ldap_binding_password": ("ldap_binding_password", "LDAP Binding Password"),
    "linux_password": ("linux_password", "Linux Password"),
    "local_user_password": ("local_user_password", "Local User Password"),
    "persistent_passphrase": ("persistent_passphrase", "Persistent Memory Passphrase"),
    "pure_api_token": ("pure_api_token", "Pure Storage API Token"),
    "redfish_password": ("redfish_password", "Redfish/BMC Password"),
    "root_password": ("root_password", "Root Password"),
    "snmp_auth_passphrase": ("snmp_password", "SNMP Auth Passphrase"),
    "snmp_community": ("snmp_community_string", "SNMP Community String"),
    "snmp_community_string": ("snmp_community_string", "SNMP Community String"),
    "snmp_password": ("snmp_password", "SNMP Password"),
    "snmp_privacy_passphrase": ("snmp_password", "SNMP Privacy Passphrase"),
    "ssh_public_key": ("ssh_public_key", "SSH Public Key"),
    "vmedia_password": ("vmedia_password", "Virtual Media Password"),
    "vmware_esxi_password": ("vmware_esxi_password", "VMware ESXi Password"),
    "windows_admin_password": ("windows_admin_password", "Windows Admin Password"),
}

# Cache for schema properties
_SENSITIVE_SCHEMA_PROPS: Dict[str, Any] = {}


def load_schema(schema_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load schema and extract sensitive variable properties."""
    global _SENSITIVE_SCHEMA_PROPS
    
    if schema_path is None:
        schema_path = _SCHEMA_PATH
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found at {schema_path}")
    
    with open(schema_path) as f:
        schema = json.load(f)
    
    if "definitions" not in schema or "abstract.sensitive_variables" not in schema["definitions"]:
        raise ValueError("Schema missing 'definitions.abstract.sensitive_variables'")
    
    _SENSITIVE_SCHEMA_PROPS = schema["definitions"]["abstract.sensitive_variables"].get("properties", {})
    return schema


def _wrap_cli_text(text: str, indent: str = "  ", width: int = 100) -> str:
    """Wrap text to specified width with indentation for CLI output."""
    return textwrap.fill(text, width=width, subsequent_indent=indent, break_long_words=False, break_on_hyphens=False)


def _format_export_command(env_var_name: str, schema_key: Optional[str] = None) -> str:
    """Format export command suggestion for a missing variable."""
    lines = [
        "\n  To fix this, run:",
        f"    export {env_var_name}='<your_value_here>'",
    ]
    
    if schema_key and schema_key in _SENSITIVE_SCHEMA_PROPS:
        schema_rule = _SENSITIVE_SCHEMA_PROPS[schema_key]
        description = schema_rule.get("description", "").strip()
        if description:
            lines.append(f"\n  Description:\n    {_wrap_cli_text(description)}")
    
    return "\n".join(lines)


def collect_required_sensitive_variables(model: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    """
    Collect all required sensitive variable environment variable names from model.
    
    Returns:
        Dict mapping env_var_name -> (env_prefix, schema_key)
    """
    required_vars: Dict[str, Tuple[str, str]] = {}
    
    def traverse_model(obj: Any, path: str = "") -> None:
        """Recursively traverse model looking for sensitive variable identifiers."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                
                # Check if this key matches a sensitive variable prefix pattern
                for env_prefix, (schema_key, _) in _SENSITIVE_VAR_PATTERNS.items():
                    # Key could be the field name itself or part of it
                    if key == env_prefix or key.endswith(f"_{env_prefix}"):
                        # Value should be an integer ID (1-64)
                        if isinstance(value, int) and 0 < value <= 64:
                            env_var_name = f"{env_prefix}_{value}"
                            required_vars[env_var_name] = (env_prefix, schema_key)
                
                # Recurse into nested structures
                traverse_model(value, current_path)
        
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                traverse_model(item, f"{path}[{idx}]")
    
    traverse_model(model)
    return required_vars


def validate_all_sensitive_variables(
    model: Dict[str, Any],
    schema_path: Optional[Path] = None,
) -> Tuple[bool, List[str], List[str]]:
    """
    Validate all sensitive variables in model.
    
    Returns:
        Tuple of (success: bool, missing_vars: List[str], error_messages: List[str])
    """
    load_schema(schema_path)
    
    required_vars = collect_required_sensitive_variables(model)
    missing_vars = []
    error_messages = []
    
    for env_var_name, (env_prefix, schema_key) in sorted(required_vars.items()):
        env_value = os.environ.get(env_var_name)
        
        if env_value in (None, ""):
            missing_vars.append(env_var_name)
            error_msg = f"Missing required environment variable '{env_var_name}'"
            error_msg += _format_export_command(env_var_name, schema_key)
            error_messages.append(error_msg)
    
    success = len(missing_vars) == 0
    return success, missing_vars, error_messages


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate all sensitive environment variables required by data model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to merged model JSON file",
    )
    parser.add_argument(
        "--schema",
        type=str,
        help="Path to JSON schema (default: schema/cisco-ai-pods.json)",
    )
    
    args = parser.parse_args()
    
    try:
        model_path = Path(args.model)
        if not model_path.exists():
            print(f"ERROR: Model file not found: {model_path}", file=sys.stderr)
            sys.exit(1)
        
        with open(model_path) as f:
            model = json.load(f)
        
        schema_path = Path(args.schema) if args.schema else None
        success, missing_vars, error_messages = validate_all_sensitive_variables(model, schema_path)
        
        if success:
            print("✓ All required sensitive environment variables are present and valid.")
            sys.exit(0)
        else:
            print(f"\nERROR: {len(missing_vars)} missing sensitive environment variable(s):\n", file=sys.stderr)
            for msg in error_messages:
                print(msg, file=sys.stderr)
            print(file=sys.stderr)
            sys.exit(1)
    
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
