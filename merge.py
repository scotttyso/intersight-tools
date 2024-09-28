#!/usr/bin/env python3
from copy import deepcopy
from dotmap import DotMap
import json, numpy, os, re
data = DotMap(json.load(open(os.path.join('terraform.bkp'), 'r')))
moid_map = DotMap()
org_names = DotMap()
parent_types = ['intersight_fabric_port_policy',
                'intersight_fabric_eth_network_policy',
                'intersight_fabric_fc_network_policy',
                'intersight_storage_storage_policy',
                'intersight_vnic_lan_connectivity_policy',
                'intersight_vnic_san_connectivity_policy']
for e in data.resources:
    if e.type == 'intersight_organization_organization':
        for i in e.instances:
            org_names[i.attributes.moid] = i.attributes.name
for e in data.resources:
    if e.type in parent_types:
        for i in e.instances:
            org = org_names[i.attributes.organization[0].moid]
            moid_map[e.type][i.attributes.moid] = DotMap(org = org, name = i.attributes.name)
resource_types = list(numpy.unique(numpy.array([e.type for e in data.resources])))
resources = []
for e in resource_types:
    if re.search('policy|role|pin|port|vlan|vsan|drive|vnic', e): edata = DotMap(module = 'module.policies[\"map\"]', mode = 'managed', type = e, name = 'map', provider = 'provider[\"registry.terraform.io/ciscodevnet/intersight\"]', instances = [])
    elif 'pool'    in e: edata = DotMap(module = 'module.pools[\"map\"]', mode = 'managed', type = e, name = 'map', provider = 'provider[\"registry.terraform.io/ciscodevnet/intersight\"]', instances = [])
    elif 'profile' in e: edata = DotMap(module = 'module.profiles[\"map\"]', mode = 'managed', type = e, name = 'map', provider = 'provider[\"registry.terraform.io/ciscodevnet/intersight\"]', instances = [])
    elif 'organization' in e: edata = DotMap(module = 'module.organizations[\"map\"]', mode = 'managed', type = e, name = 'map', provider = 'provider[\"registry.terraform.io/ciscodevnet/intersight\"]', instances = [])
    for r in data.resources:
        if r.type == e: edata.instances.extend(r.instances)
    resources.append(edata)
for x in range(0,len(resources)):
    for i in range(0,len(resources[x].instances)):
        # idata = resources[x].instances[i]
        idata = DotMap(**dict(index_key = 'blah'), **dict(resources[x].instances[i]))
        adata = idata.attributes
        akeys = list(adata.keys())
        r     = resources[x]
        def parent_function(rtype, pmoid, istring):
            parent_name = moid_map[rtype][pmoid].name
            parent_org  = moid_map[rtype][pmoid].org
            return f'{parent_org}/{parent_name}/{istring}'
        if 'organization' in akeys: org_name = org_names[adata.organization[0].moid]
        if 'intersight_fabric_lan_pin_group'  == r.type: idata.index_key = parent_function('intersight_fabric_port_policy', adata.parent[0].moid, adata.name)
        elif 'intersight_storage_drive_group' == r.type: idata.index_key = parent_function('intersight_storage_storage_policy', adata.parent[0].moid, adata.name)
        elif 'intersight_vnic_eth_if' == r.type: idata.index_key = parent_function('intersight_vnic_lan_connectivity_policy', adata.parent[0].moid, adata.name)
        elif 'intersight_vnic_fc_if'  == r.type: idata.index_key = parent_function('intersight_vnic_san_connectivity_policy', adata.parent[0].moid, adata.name)
        elif 'port_id_start'           in akeys: idata.index_key = parent_function('intersight_fabric_port_policy', adata.parent[0].moid, f'1-{adata.port_id_start}')
        elif 'pc_id'                   in akeys: idata.index_key = parent_function('intersight_fabric_port_policy', adata.parent[0].moid, adata.pc_id)
        elif 'port_id'                 in akeys: idata.index_key = parent_function('intersight_fabric_port_policy', adata.parent[0].moid, f'1-0-{adata.port_id}')
        elif 'vlan_id'                 in akeys: idata.index_key = parent_function('intersight_fabric_eth_network_policy', adata.parent[0].moid, adata.vlan_id)
        elif 'vsan_id'                 in akeys: idata.index_key = parent_function('intersight_fabric_fc_network_policy', adata.parent[0].moid, adata.vsan_id)
        elif 'name'                    in akeys: idata.index_key = f'{org_name}/{adata.name}'
        print(idata.index_key)
        resources[x].instances[i] = deepcopy(idata)
data.resources = resources
wr_file = open('terraform.tfstate', 'w')
wr_file.write(json.dumps(data, indent=4))
