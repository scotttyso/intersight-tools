#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions, isight, pcolor
    from copy import deepcopy
    from dotmap import DotMap
    from jinja2 import Template
    from json_ref_dict import materialize, RefDict
    from stringcase import pascalcase, snakecase
    import argparse, json, jsonref, os, re, urllib3, yaml
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
#=================================================================
# Function: YAML Dumper
#=================================================================
class yaml_dumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(yaml_dumper, self).increase_indent(flow, False)
#=================================================================
# Function: Parse Arguments
#=================================================================
def cli_arguments():
    parser = argparse.ArgumentParser(description ='Intersight BIOS Key Check Module')
    parser = ezfunctions.base_arguments(parser)
    return DotMap(args = parser.parse_args())
#=================================================================
# Function: BOIS Keys
#=================================================================
def bios_keys(kwargs):
    #=============================================================
    # Sorting BIOS Tokens from easy-imm.json
    #=============================================================
    keys      = list(kwargs.ezdata.bios.allOf[1].properties.keys())
    bios_keys = []
    for e in keys: bios_keys.append(kwargs.ezdata.bios.allOf[1].properties[e].intersight_api)
    bios_keys.extend([
        'AccountMoid', 'Ancestors', 'ClassId', 'CreateTime', 'Description', 'DomainGroupMoid', 'ModTime', 'Moid', 'Name', 'ObjectType',
        'Organization', 'Owners', 'PermissionResources', 'Profiles', 'SharedScope', 'Tags'])
    kwargs.method   = 'get'
    kwargs.names    = list(kwargs.org_names.keys())
    kwargs.org      = 'default'
    kwargs.uri      = kwargs.ezdata.bios.intersight_uri
    kwargs          = isight.api('multi_org').calls(kwargs)
    api_docs        = json.load(open(os.path.join(kwargs.script_path, 'variables', 'intersight-openapi.json'), 'r', encoding='utf8'))
    intersight_bios = DotMap(api_docs['components']['schemas']['bios.Policy']['allOf'][1]['properties'])
    bios            = DotMap()
    defaults        = DotMap()
    for k in list(kwargs.results[0].keys()):
        if not k in bios_keys:
            bios[snakecase(k)] = DotMap(
                default = intersight_bios[k].default, description = f'The default value is `platform-default`.  {intersight_bios[k].description}',
                enum = intersight_bios[k].enum, intersight_api = k, title = snakecase(k), type = 'string')
            defaults[snakecase(k)] = intersight_bios[k].default
    pcolor.LightGray(f'{"-"*54}')
    pcolor.Yellow('New Keys:\n')
    if len(bios) > 0:
        pcolor.Yellow(json.dumps(bios, indent=4))
        pcolor.Yellow(yaml.dump(defaults.toDict(), Dumper=ezfunctions.yaml_dumper, default_flow_style=False))
    else: pcolor.Yellow('None')
    bkeys = list(kwargs.results[0].keys())
    pcolor.LightGray(f'\n{"-"*54}')
    pcolor.Yellow('Removed Keys:\n')
    rcount = 0
    for k in bios_keys:
        if not k in bkeys and k != 'bios_template': pcolor.Yellow(k); rcount += 1
    if rcount == 0: pcolor.Yellow('None')
    pcolor.LightGray(f'\n{"-"*54}')
    pcolor.Yellow('Description Keys:\n')
    descr = kwargs.ezdata['policies'].properties.bios.description
    dsplit = descr.split('\n')
    dkeys = []
    for e in dsplit:
        if re.search(r'\* \`([a-zA-Z0-9\_]+)`$', e): dkeys.append(re.search(r'\* \`([a-zA-Z0-9\_]+)`$', e).group(1))
    keys.remove('bios_template')
    for e in keys:
        if not e in dkeys: pcolor.Yellow(e)
    for k,v in kwargs.ezdata.bios.allOf[1].properties.items():
        vkeys = list(v.keys())
        if 'enum' in vkeys and k != 'bios_template':
            for e in intersight_bios[v.intersight_api].enum:
                if not e in v.enum:
                    pcolor.LightGray(f'{"-"*54}')
                    pcolor.Yellow(''); pcolor.Yellow(k); pcolor.Yellow('')
                    pcolor.Yellow(f'intersight enum is:')
                    pcolor.Yellow(json.dumps(intersight_bios[v.intersight_api].enum, indent=4))
                    pcolor.Yellow(f'easy-imm enum is:')
                    pcolor.Yellow(json.dumps(v.enum, indent=4))
            if not intersight_bios[v.intersight_api].default == v.default:
                pcolor.LightGray(f'{"-"*54}')
                pcolor.Yellow(''); pcolor.Yellow(k); pcolor.Yellow('')
                pcolor.Yellow(f'intersight default is:')
                pcolor.Yellow(intersight_bios[v.intersight_api].default)
                pcolor.Yellow(f'easy-imm default is:')
                pcolor.Yellow(v.default)
#=================================================================
# Function: BIOS Templates
#=================================================================
def bios_templates(kwargs):
    #=============================================================
    # Configure Base Module Setup
    #=============================================================
    kwargs = cli_arguments()
    kwargs = ezfunctions.base_script_settings(kwargs)
    kwargs = isight.api('organization').all_organizations(kwargs)
    #=============================================================
    # Sorting BIOS Tokens from easy-imm.json
    #=============================================================
    keys      = list(kwargs.ezdata.bios.allOf[1].properties.keys())
    bios_keys = DotMap()
    bios_json = DotMap()
    bios_yaml = DotMap()
    for e in keys: bios_keys[kwargs.ezdata.bios.allOf[1].properties[e].intersight_api] = e
    bkeys         = list(bios_keys.keys())
    kwargs.method = 'get'
    kwargs.names  = list(kwargs.org_names.keys()) + ['5ddfd9ff6972652d31ee6582']
    kwargs.org    = 'default'
    kwargs.uri    = kwargs.ezdata.bios.intersight_uri
    kwargs        = isight.api('multi_org').calls(kwargs)
    templates     = list(kwargs.ezdata['intersight.bios.templates'].properties.keys())
    for e in list(kwargs.results):
        if e.Organization.Moid == '5ddfd9ff6972652d31ee6582':
            jdict = DotMap(); ydict = DotMap()
            for k,v in e.items():
               if k in bkeys and v != 'platform-default':
                   jdict[k] = v
                   ydict[bios_keys[k]] = v
            if not e.Name in templates:
                bios_json[e.Name] = jdict
                bios_yaml[e.Name] = ydict
            elif e.Name in templates:
                tkeys = list(kwargs.ezdata['intersight.bios.templates'].properties[e.Name])
                tdict = deepcopy(jdict)
                match_false = False
                for a,b in jdict.items():
                    if not a in tkeys: match_false = True
                    else: tdict.pop(a)
                if match_false == True or len(tdict) > 0:
                    bios_json[e.Name] = jdict
                    bios_yaml[e.Name] = ydict
    bios_json = DotMap(sorted(bios_json.items()))
    bios_yaml = DotMap(sorted(bios_yaml.items()))
    pcolor.LightGray(f'{"-"*54}')
    pcolor.Yellow('New BIOS Templates:\n')
    if len(bios_json) > 0:
        pcolor.Yellow(json.dumps(bios_json, indent=4))
        pcolor.Yellow(yaml.dump(bios_yaml.toDict(), Dumper = yaml_dumper, default_flow_style=False))
    else: pcolor.Yellow('None\n')

def setup(kwargs):
    depricated = DotMap({
        'vnic.EthNetworkPolicy': ['TargetPlatform'],
        'fabric.EthNetworkControlPolicy': ['NetworkPolicy'],
    })
    ignore_keys = ['AccountMoid', 'Ancestors', 'ClassId', 'CreateTime', 'Description', 'DomainGroupMoid', 'ModTime', 'Moid', 'Name', 'ObjectType',
        'Organization', 'Owners', 'PermissionResources', 'Profiles', 'SharedScope', 'Tags']
    idata = json.loads(open(os.path.join(kwargs.script_path, 'variables', 'intersight-openapi-v3-1.0.11-20260220062446536.json'), encoding='utf8').read())
    idata = DotMap(idata)
    for k,v in kwargs.ezdata.items():
        klist = []
        vlist = list(v.keys())
        if 'intersight_type' in vlist:
            if 'allOf' in vlist: properties = v.allOf[1].properties
            else: properties = v.properties
            ezkeys = []
            for e in properties.keys():
                if type(properties[e].intersight_api) == str and re.search(r'ref:', properties[e].intersight_api):
                    ezkeys.append(properties[e].intersight_api.split(':')[1])
                else: ezkeys.append(properties[e].intersight_api)
            ilist = []
            for ik, iv in idata.components.schemas[v.object_type].allOf[1].properties.items():
                if not ik in ezkeys and not ik in ignore_keys:
                    if ik in depricated[v.object_type]: continue
                    else: ilist.append(ik)
            klist = {v.object_type: ilist}
            if len(klist[v.object_type]) > 0: print(klist)
    exit()
    print(json.dumps(klist, indent=4))
    exit()
    idata = {'components': {'schemas': idata['definitions']}}
    idata = jsonref.loads(json.dumps(idata))
    # idata = json.loads(json.dumps(idata))
    print(idata['definitions']['ippool.Pool'])
    exit()
    print(json.dumps(idata['definitions']['ippool.Pool'], indent=4))
    exit()
    idata = json.load(open(os.path.join(kwargs.script_path, 'variables', 'intersight-openapi-v3-1.0.11-20260220062446536.json'), encoding='utf8'))
    idata = {'components': {'schemas': idata['definitions']}}
    for k,v in idata['definitions'].items():
        if 'allOf' in v.keys() and len(v['allOf']) > 1:
            print(v)
            idata['definitions'][k] = v['allOf'][1]
    
    idata = DotMap(idata)
    print(json.dumps(idata['definitions']['ippool.Pool'].toDict(), indent=4))
    exit()
    intersight_json = json.load(open(os.path.join(kwargs.script_path, 'variables', 'intersight-openapi-v3-1.0.11-20260220062446536.json'), encoding='utf8'))
    print(intersight_json['definitions']['ippool.Pool']['allOf'])
    exit()
    intersight_data = materialize(RefDict({'ippool.Pool': intersight_json['definitions']['ippool.Pool']}))
    exit()
    pools_list = ['ip', 'iqn', 'mac', 'uuid', 'wwnn', 'wwpn']
    policies_list = ['auditd', 'bios', 'device_connector', 'ethernet_network', 'ethernet_network_control', 'ethernet_network_group',
        'ethernet_qos', 'fibre_channel_network', 'fibre_channel_qos', 'firmware', 'flow_control', 'ipmi_over_lan', 'iscsi_adapter',
        'iscsi_static_target', 'memory', 'multicast', 'network_connectivity', 'ntp', 'port', 'power', 'scrub', 'serial_over_lan',
        'smtp', 'ssh', 'switch_control', 'syslog', 'thermal', 'virtual_kvm', 'vlan']
    profiles_list = ['chassis', 'domain', 'servers']
    templates_list = profiles_list
    idata = {}
    for i in pools_list:
        idata = idata | {kwargs.ezdata[i].object_type: {'allOf': intersight_json['definitions'][kwargs.ezdata[i].object_type]['allOf']}}
    for i in policies_list:
        idata = idata | {kwargs.ezdata[i].object_type: {'allOf': intersight_json['definitions'][kwargs.ezdata[i].object_type]['allOf']}}
    idata = DotMap(materialize(RefDict(idata)))
    print(json.dumps(idata, indent=4))
    exit()
    for i in pools_list:
        print(kwargs.ezdata[i].object_type)
        idata = materialize(RefDict(intersight_json['definitions'][kwargs.ezdata[i].object_type]['allOf']))
        print(json.dumps(idata, indent=4))
        exit()
        pk = list(kwargs.ezdata[i].keys())
        # if 'allOf' in pk:
        #     # pcolor.LightGray(f'{"="*20} {f'{i.upper()}'} {"="*20}')
        #     pcolor.Yellow(json.dumps(kwargs.ezdata[i].allOf[1].properties.toDict(), indent=4))
        # else: print(f'{"="*20} {f'{i.upper()} no allOf'} {"="*20}')

    exit()
    bios_json = DotMap(ijson['definitions']['bios.Policy']['allOf'][1]['properties'])
    bios_data = deepcopy(kwargs.ezdata.bios.allOf[1])
    for k, v in kwargs.ezdata.bios.allOf[1].properties.items():
        if not re.search('bios_template', k):
            bios_data.properties[k].description = f'The default value is `{bios_json[v.intersight_api].default}`.  {bios_json[v.intersight_api].description}'
            bios_data.properties[k].default = bios_json[v.intersight_api].default
            if 'enum' in bios_json[v.intersight_api].keys(): bios_data.properties[k].enum = bios_json[v.intersight_api].enum
    print(json.dumps(bios_data.toDict(), indent=4))
        #if re.search('string|integer', v['type']):
        #    pcolor.LightGray(f'{"="*20} {k.upper()} {"="*20}')
        #    pcolor.Yellow(f"{v.description}\n")
        #    pcolor.Yellow(f"Default Value: {v.default}")
        #    if 'enum' in v.keys(): pcolor.Yellow(f"Enum Values: {json.dumps(v.enum, indent=4)}")
    exit()
    #plist = [
    #    'auditd.json.j2',
    #    'bios.json.j2',
    #    'device_connector.json.j2',
    #    'ethernet_network.json.j2',
    #    'ethernet_network_control.json.j2',
    #    'ethernet_network_group.json.j2',
    #    'ethernet_qos.json.j2',
    #    'fibre_channel_network.json.j2',
    #    'fibre_channel_qos.json.j2',
    #    'firmware.json.j2',
    #    'flow_control.json.j2',
    #    'ipmi_over_lan.json.j2',
    #    'iscsi_adapter.json.j2',
    #    'iscsi_static_target.json.j2',
    #    'memory.json.j2',
    #    'multicast.json.j2',
    #    'network_connectivity.json.j2',
    #    'ntp.json.j2',
    #    'port.json.j2',
    #    'power.json.j2',
    #    'scrub.json.j2',
    #    'serial_over_lan.json.j2',
    #    'smtp.json.j2',
    #    'ssh.json.j2',
    #    'switch_control.json.j2',
    #    'syslog.json.j2',
    #    'thermal.json.j2',
    #    'virtual_kvm.json.j2',
    #    'vlan.json.j2'
    #]
    plist = [
        'ip.json.j2',
        'iqn.json.j2',
        'mac.json.j2',
        'uuid.json.j2',
        'wwnn.json.j2',
        'wwpn.json.j2'
        ]
    data = DotMap(
        local_logging = DotMap(minimum_severity = 'warning'),
        organization = "default",
        org_moids = kwargs.org_moids,
        # tags = [DotMap(key = 'example', value = 'example')]
    )
    for i in plist:
        pcolor.LightGray(f'\n{"="*20} {i.upper()} {"="*20}\n')
        # output = Template(open(os.path.join(kwargs.script_path, 'lib', 'templates', 'intersight', 'policies', i), 'r', encoding='utf8').read()).render(data.toDict())
        # pcolor.Yellow(output)
        output = json.loads(Template(open(os.path.join(kwargs.script_path, 'lib', 'templates', 'intersight', 'pools', i), 'r', encoding='utf8').read()).render(data.toDict()))
        pcolor.Yellow(json.dumps(output, indent=4))
    exit()
    data = DotMap(
        description = "Example IP Pool",
        ipv4_blocks = [
            DotMap({
                "from": "192.168.65.10",
                "gateway": "192.168.64.1",
                "netmask": "255.255.254.0",
                "primary_dns": "192.168.64.15",
                "secondary_dns": "192.168.64.100"
            })
        ],
        #ipv4_configuration = DotMap(
        #    gateway = "192.168.64.1",
        #    netmask = "255.255.254.0",
        #    primary_dns = "192.168.64.15",
        #    secondary_dns = "192.168.64.100"
        #),
        name = "example-ip-pool",
        organization = "default",
        org_moids = kwargs.org_moids
    )
    output = json.loads(Template(open(os.path.join(kwargs.script_path, 'lib', 'templates', 'intersight', 'pools', 'ip.json.j2'), 'r', encoding='utf8').read()).render(data.toDict()))
    pcolor.LightGray(f'\n{"="*20} POOLS {"="*20}\n')
    pcolor.Yellow(json.dumps(output, indent=4))
    pcolor.Yellow(output)
    exit()
    blist = ['AccountMoid', 'Ancestors', 'ClassId', 'CreateTime', 'DisplayNames', 'DomainGroupMoid', 'ModTime', 'Moid', 'ObjectType',
        'Owners', 'Parent', 'PermissionResources', 'Profiles', 'SharedScope', 'VersionContext']
    
    # for i in ['organizations', 'policies', 'pools', 'profiles']:
    for i in ['pools']:
        idata = DotMap(json.load(open(os.path.join(kwargs.script_path, 'lib', 'templates', 'intersight', i, f'bios.json'), 'r', encoding='utf8')))
        pcolor.LightGray(f'\n{"="*20} {i.upper()} {"="*20}\n')
        idata = DotMap(json.load(open(os.path.join(kwargs.script_path, 'lib', 'templates', 'intersight', i, f'bios.json'), 'r', encoding='utf8')))
        for k, v in kwargs.ezdata.bios.allOf[1].properties.items():
            if re.search('string|integer', v['type']) and v.intersight_api in idata.keys():
                idata[v.intersight_api] = f"{{{{ {k} | default({v.default}) }}}}"
        with open(os.path.join(kwargs.script_path, 'lib', 'templates', 'intersight', i, f'bios.json'), 'w', encoding='utf8') as f:
            json.dump(idata.toDict(), f, indent=4)

#=================================================================
# Function: Main Script
#=================================================================
def main():
    #=============================================================
    # Configure Base Module Setup
    #=============================================================
    kwargs = cli_arguments()
    kwargs = ezfunctions.base_script_settings(kwargs)
    kwargs = isight.api('organization').all_organizations(kwargs)
    # setup(kwargs)
    bios_keys(kwargs)
    bios_templates(kwargs)

if __name__ == '__main__':
    main()
