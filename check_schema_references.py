#!/usr/bin/env python3
import json
from classes import pcolor
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource
from jsonschema.validators import validator_for
from pathlib import Path

def find_broken_refs(schema_path):
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    # Initialize a registry and resource
    resource = Resource.from_contents(schema)
    registry = Registry().with_resource(uri="", resource=resource)
    
    # Get the correct validator for the schema version
    validator_cls = validator_for(schema)
    validator = validator_cls(schema, registry=registry)

    broken_refs = []

    # Recursively find all $ref keywords in the dictionary
    def check_node(node, path=""):
        if isinstance(node, dict):
            if "$ref" in node:
                ref_value = node["$ref"]
                try:
                    # Attempt to resolve the reference
                    registry.resolver().lookup(ref_value)
                except (NoSuchResource, Exception) as e:
                    broken_refs.append({
                        "path": path,
                        "ref": ref_value,
                        "error": str(e)
                    })
            
            for key, value in node.items():
                check_node(value, f"{path}/{key}" if path else key)
        
        elif isinstance(node, list):
            for i, item in enumerate(node):
                check_node(item, f"{path}[{i}]")

    check_node(schema)
    return broken_refs

# Usage
directory = Path("./schemas")
json_files = directory.glob("*.json")
for json_file in json_files:
    print(f"Checking {json_file}...")
    results = find_broken_refs(json_file)
    if not results:
        pcolor.Green(f"✅ All references are valid in {json_file}.")
    else:
        pcolor.Red(f"❌ Found broken references in {json_file}:")
    for error in results:
        pcolor.Yellow(f"Path: {error['path']} -> Ref: {error['ref']}")
        # print(f"Path: {error['path']} -> Ref: {error['ref']} (Error: {error['error']})")
        print("-" * 80)
