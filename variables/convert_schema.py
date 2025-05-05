#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    import json, os, re
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
#=================================================================
# Function: Main Script
#=================================================================
def main():
    ezdata = json.load(open(os.path.join(script_path, 'easy-imm.json')))
    for e in ['scripts', 'templates', 'wizard']:
        ezdata['components'].pop(e)
    ezdata['$schema'] = 'http://json-schema.org/draft-07/schema#'
    plist = []
    for k,v in ezdata['components']['schemas'].items():
        pkeys = list(v.keys())
        plist = ['profiles.chassis.targets', 'profiles.server.targets']
        plist2 = ['profiles.chassis', 'profiles.server']
        if 'allOf' in pkeys:
            if k in plist:
                ezdata['components']['schemas'][k]['allOf'].pop(2)
            else:
                if len(ezdata['components']['schemas'][k]['allOf']) > 2:
                    print(json.dumps(ezdata['components']['schemas'][k], indent=4))
                    exit(0)
            if len(ezdata['components']['schemas'][k]['allOf']) > 1:
                ezdata['components']['schemas'][k]['allOf'].pop(0)
            if k == 'profiles.chassis.targets':
                ezdata['components']['schemas'][k]['allOf'][0]['required'].append('serial_number')
            if k in plist:
                ezdata['components']['schemas'][k]['allOf'][0]['properties'].update(
                    {'serial_number': {'$ref': f'#/components/schemas/abstract_serial/properties/serial_number'}})
            ezdata['components']['schemas'][k]['allOf'][0]['required'].sort()
            ezdata['components']['schemas'][k]['allOf'][0].update({'additionalProperties': False})
            if k in plist: prp = 'abstract_profile'
            elif ezdata['components']['schemas'][k]['intersight_type'] == 'policies': prp = 'abstract_policy'
            elif ezdata['components']['schemas'][k]['intersight_type'] == 'pools': prp = 'abstract_pool'
            elif re.search('profile|template', ezdata['components']['schemas'][k]['intersight_type']): prp = 'abstract_profile'
            if not k in plist2:
                ezdata['components']['schemas'][k]['allOf'][0]['required'].append('name')
                ezdata['components']['schemas'][k]['allOf'][0]['properties'].update(
                    {'description': {'$ref': f'#/components/schemas/{prp}/properties/description'}})
                ezdata['components']['schemas'][k]['allOf'][0]['properties'].update(
                    {'name': {'$ref': f'#/components/schemas/{prp}/properties/name'}})
                descr = 'An arbitrary key and value pair that can be used to tag REST resources and organize managed objects by\nassigning meta-data tags to any object.\n\nRequired Attributes:\n  * key\n  * value'
                ezdata['components']['schemas'][k]['allOf'][0]['properties'].update(
                    {'tags': {'description':descr,'items':{'$ref': f'#/components/schemas/{prp}/properties/tags'},'title':'tags - Tags','type':'array'}})
            if re.search('port|organizations', k):
                ezdata['components']['schemas'][k]['allOf'][0]['properties'].pop('name')
                ezdata['components']['schemas'][k]['allOf'][0]['required'].remove('name')
            if re.search('^(ip|iqn|mac|uuid|wwnn|wwpn)$', k):
                ezdata['components']['schemas'][k]['allOf'][0]['properties'].update(
                    {'assignment_order': {'$ref': f'#/components/schemas/{prp}/properties/assignment_order'}})
            ezdata['components']['schemas'][k]['allOf'][0] = dict(sorted(ezdata['components']['schemas'][k]['allOf'][0].items()))
            ezdata['components']['schemas'][k]['allOf'][0]['properties'] = dict(sorted(
                ezdata['components']['schemas'][k]['allOf'][0]['properties'].items()))
    with open(os.path.join(script_path, 'new.json'), 'w') as f:
        json.dump(ezdata, f, indent=4)

if __name__ == '__main__':
    main()
