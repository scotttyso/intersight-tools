#!/usr/bin/env python3
"""
Schema Comparison Tool for BIOS Attributes
Compares BIOS attributes across:
1. intersight-tools/classes/templates/intersight/C800/bios.json.j2 (template)
2. intersight-tools/QA/885/885.json (Redfish data)
3. intersight-tools/schema/cisco-ai-pods.json (schema definition)
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Tuple


class BIOSSchemaComparator:
    def __init__(self, template_path: str, redfish_path: str, schema_path: str):
        self.template_path = Path(template_path)
        self.redfish_path = Path(redfish_path)
        self.schema_path = Path(schema_path)
        
        self.template_attrs = {}
        self.redfish_attrs = {}
        self.redfish_registry = {}
        self.schema_attrs = {}
        
    def load_template(self) -> Dict[str, str]:
        """Load attributes from Jinja2 template."""
        with open(self.template_path, 'r') as f:
            content = f.read()
        
        # Extract Attributes section from JSON template
        match = re.search(r'"Attributes"\s*:\s*\{(.+?)\n\s*\}', content, re.DOTALL)
        if not match:
            print(f"Warning: Could not find Attributes section in template")
            return {}
        
        attrs = {}
        # Find all "AttributeName": "{{ item.python_name | default(...) }}"
        pattern = r'"([^"]+)"\s*:\s*"{{.*?item\.([a-z0-9_]+)'
        for name, python_name in re.findall(pattern, match.group(1)):
            attrs[name] = python_name
        
        return attrs
    
    def load_redfish(self) -> Dict[str, any]:
        """Load BIOS attributes from Redfish JSON dump."""
        with open(self.redfish_path, 'r') as f:
            data = json.load(f)
        
        resources = data.get('resources', {})
        bios_key = "/redfish/v1/Systems/system/Bios"
        
        if bios_key in resources:
            bios = resources[bios_key]
            return bios.get('Attributes', {})
        
        return {}
    
    def load_redfish_registry(self) -> Dict[str, str]:
        """Load BIOS attribute registry (HelpText) from Redfish dump."""
        registry_dict = {}
        with open(self.redfish_path, 'r') as f:
            data = json.load(f)
        
        resources = data.get('resources', {})
        registry = resources.get("/redfish/v1/Registries/BiosAttributeRegistry", {})
        registry_entries = registry.get('RegistryEntries', {})
        attributes = registry_entries.get('Attributes', [])
        
        if isinstance(attributes, list):
            for attr in attributes:
                if isinstance(attr, dict) and 'AttributeName' in attr:
                    attr_name = attr['AttributeName']
                    help_text = attr.get('HelpText', 'N/A')
                    registry_dict[attr_name] = help_text
        
        return registry_dict
    
    def load_schema(self) -> Dict[str, Dict]:
        """Load BIOS policy schema from cisco-ai-pods.json."""
        with open(self.schema_path, 'r') as f:
            data = json.load(f)
        
        # Navigate to intersight.policies.bios definition
        definitions = data.get('definitions', {})
        bios_def = definitions.get('intersight.policies.bios', {})
        
        # Get properties from allOf structure
        all_of = bios_def.get('allOf', [])
        schema_props = {}
        
        for item in all_of:
            if 'properties' in item:
                schema_props.update(item['properties'])
        
        return schema_props
    
    def convert_to_snake_case(self, camel_case: str) -> str:
        """Convert CamelCase to snake_case."""
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_case)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    def load_all(self):
        """Load data from all sources."""
        print("Loading template attributes...")
        self.template_attrs = self.load_template()
        print(f"  Found {len(self.template_attrs)} attributes in template")
        
        print("Loading Redfish attributes...")
        self.redfish_attrs = self.load_redfish()
        print(f"  Found {len(self.redfish_attrs)} attributes in Redfish")
        
        print("Loading Redfish attribute registry...")
        self.redfish_registry = self.load_redfish_registry()
        print(f"  Found {len(self.redfish_registry)} descriptions in Redfish registry")
        
        print("Loading schema attributes...")
        self.schema_attrs = self.load_schema()
        print(f"  Found {len(self.schema_attrs)} attributes in schema")
    
    def find_mappings(self) -> Dict[str, Dict]:
        """Find correlations between template, Redfish, and schema attributes."""
        mappings = {}
        
        # For each template attribute
        for template_name, template_python in self.template_attrs.items():
            mapping = {
                'template': {
                    'name': template_name,
                    'python_name': template_python
                },
                'redfish': None,
                'schema': None,
                'match_type': 'no_match'
            }
            
            # Direct match in Redfish (exact same name)
            if template_name in self.redfish_attrs:
                mapping['redfish'] = {
                    'name': template_name,
                    'value': self.redfish_attrs[template_name],
                    'help_text': self.redfish_registry.get(template_name, 'N/A')
                }
                mapping['match_type'] = 'exact_redfish'
            
            # Try snake_case conversion for schema
            schema_key_snake = self.convert_to_snake_case(template_name)
            if schema_key_snake in self.schema_attrs:
                schema_info = self.schema_attrs[schema_key_snake]
                mapping['schema'] = {
                    'name': schema_key_snake,
                    'api_name': schema_info.get('intersight_api', 'N/A'),
                    'type': schema_info.get('type', 'N/A'),
                    'default': schema_info.get('default', 'N/A'),
                    'description': schema_info.get('description', 'N/A')
                }
                if mapping['match_type'] == 'exact_redfish':
                    mapping['match_type'] = 'exact_both'
                else:
                    mapping['match_type'] = 'exact_schema'
            
            # Try to find similar matches in schema if no exact match
            if mapping['schema'] is None:
                similar = self._find_similar(template_name, schema_key_snake)
                if similar:
                    mapping['schema'] = similar
                    mapping['match_type'] = 'possible_schema_match'
            
            mappings[template_name] = mapping
        
        return mappings
    
    def _find_similar(self, template_name: str, snake_case: str) -> Dict or None:
        """Find similar schema attributes."""
        # Try partial matches
        template_lower = template_name.lower()
        snake_lower = snake_case.lower()
        
        best_match = None
        best_score = 0
        
        for schema_key, schema_info in self.schema_attrs.items():
            schema_lower = schema_key.lower()
            
            # Calculate similarity score
            score = 0
            if template_lower in schema_lower or schema_lower in template_lower:
                score += 2
            
            # Check if api_name matches template_name
            api_name = schema_info.get('intersight_api', '').lower()
            if api_name == template_lower:
                score += 5
            
            if score > best_score:
                best_score = score
                best_match = {
                    'name': schema_key,
                    'api_name': schema_info.get('intersight_api', 'N/A'),
                    'description': schema_info.get('description', 'N/A'),
                    'similarity_score': score
                }
        
        return best_match if best_score >= 2 else None
    
    def generate_report(self, output_file: str = None):
        """Generate comparison report."""
        mappings = self.find_mappings()
        
        # Organize by match type
        by_type = defaultdict(list)
        for name, mapping in mappings.items():
            by_type[mapping['match_type']].append((name, mapping))
        
        # Create report content
        report = []
        report.append("# BIOS Schema Attribute Mapping Report")
        report.append(f"\nGenerated from comparison of:")
        report.append(f"1. Template: {self.template_path}")
        report.append(f"2. Redfish: {self.redfish_path}")
        report.append(f"3. Schema: {self.schema_path}")
        report.append("\n## Summary\n")
        report.append(f"| Match Type | Count |")
        report.append(f"|------------|-------|")
        
        for match_type in ['exact_both', 'exact_redfish', 'exact_schema', 'possible_schema_match', 'no_match']:
            count = len(by_type.get(match_type, []))
            report.append(f"| {match_type} | {count} |")
        
        # Detailed sections
        report.append("\n## Exact Matches (Both Redfish and Schema)")
        report.append("These attributes have exact matches in both the Redfish data and schema definition.\n")
        for name, mapping in sorted(by_type['exact_both']):
            report.append(f"### {name}")
            report.append(f"- **Python Name**: {mapping['template']['python_name']}")
            report.append(f"- **Redfish Value**: {mapping['redfish']['value']}")
            report.append(f"- **Schema API**: {mapping['schema']['api_name']}")
            
            # Extract first sentence of description for brevity
            description = mapping['schema'].get('description', 'N/A')
            if description and description != 'N/A':
                # Clean up description and get first sentence
                desc_clean = description.split('\n')[0].strip()
                if len(desc_clean) > 150:
                    desc_clean = desc_clean[:150] + "..."
                report.append(f"- **Description**: {desc_clean}")
            report.append("")
        
        report.append("\n## Exact Redfish Matches")
        report.append("These attributes exist in Redfish but have no schema definition.\n")
        for name, mapping in sorted(by_type['exact_redfish']):
            report.append(f"### {name}")
            report.append(f"- **Python Name**: {mapping['template']['python_name']}")
            report.append(f"- **Redfish Value**: {mapping['redfish']['value']}")
            
            # Add Redfish HelpText description
            help_text = mapping['redfish'].get('help_text', 'N/A')
            if help_text and help_text != 'N/A':
                # Truncate if too long
                if len(help_text) > 150:
                    help_text = help_text[:150] + "..."
                report.append(f"- **Redfish Description**: {help_text}")
            
            report.append(f"- **Note**: Consider adding to schema definition")
            report.append("")
        
        report.append("\n## Exact Schema Matches")
        report.append("These attributes have schema definitions but are not in Redfish dump.\n")
        for name, mapping in sorted(by_type['exact_schema']):
            report.append(f"### {name}")
            report.append(f"- **Template Name**: {mapping['template']['name']}")
            report.append(f"- **Python Name**: {mapping['template']['python_name']}")
            report.append(f"- **Schema API**: {mapping['schema']['api_name']}")
            
            # Extract first sentence of description for brevity
            description = mapping['schema'].get('description', 'N/A')
            if description and description != 'N/A':
                desc_clean = description.split('\n')[0].strip()
                if len(desc_clean) > 150:
                    desc_clean = desc_clean[:150] + "..."
                report.append(f"- **Description**: {desc_clean}")
            report.append("")
        
        report.append("\n## Possible Schema Matches")
        report.append("These may correspond to schema attributes (similarity score >= 2).\n")
        for name, mapping in sorted(by_type['possible_schema_match']):
            report.append(f"### {name}")
            report.append(f"- **Template Name**: {mapping['template']['name']}")
            report.append(f"- **Python Name**: {mapping['template']['python_name']}")
            report.append(f"- **Likely Schema Match**: {mapping['schema']['name']}")
            report.append(f"- **API Name**: {mapping['schema']['api_name']}")
            report.append(f"- **Similarity Score**: {mapping['schema']['similarity_score']}")
            
            # Extract first sentence of description for brevity
            description = mapping['schema'].get('description', 'N/A')
            if description and description != 'N/A':
                desc_clean = description.split('\n')[0].strip()
                if len(desc_clean) > 150:
                    desc_clean = desc_clean[:150] + "..."
                report.append(f"- **Description**: {desc_clean}")
            report.append("")
        
        report.append("\n## No Match Found")
        report.append("These template attributes have no match in either Redfish or schema.\n")
        no_match_count = len(by_type['no_match'])
        if no_match_count > 0 and no_match_count <= 50:
            for name, mapping in sorted(by_type['no_match']):
                report.append(f"- {name} (python: {mapping['template']['python_name']})")
        else:
            report.append(f"Total: {no_match_count} attributes")
        
        report_text = "\n".join(report)
        
        # Save to file
        if output_file is None:
            output_file = "bios_schema_mapping_notes.md"
        
        output_path = Path(output_file)
        output_path.write_text(report_text)
        
        print(f"\nReport saved to: {output_file}")
        return report_text


def main():
    # Define paths
    template_path = "/home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/classes/templates/intersight/C800/bios.json.j2"
    redfish_path = "/home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/QA/885/885.json"
    schema_path = "/home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/schema/cisco-ai-pods.json"
    output_file = "/home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/bios_schema_mapping_notes.md"
    
    # Run comparison
    print("=" * 60)
    print("BIOS Schema Comparison Tool")
    print("=" * 60)
    print()
    
    comparator = BIOSSchemaComparator(template_path, redfish_path, schema_path)
    comparator.load_all()
    print()
    
    report = comparator.generate_report(output_file)
    print("\nReport Preview (first 50 lines):")
    print("=" * 60)
    lines = report.split('\n')
    for line in lines[:50]:
        print(line)
    if len(lines) > 50:
        print(f"... ({len(lines) - 50} more lines)")


if __name__ == "__main__":
    main()
