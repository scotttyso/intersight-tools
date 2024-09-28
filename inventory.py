#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions, isight, pcolor
    from dotmap import DotMap
    from stringcase import snakecase
    import argparse, json, os, re, urllib3, yaml
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
#=================================================================
# Function: Parse Arguments
#=================================================================
def cli_arguments():
    parser = argparse.ArgumentParser(description ='Intersight BIOS Key Check Module')
    parser = ezfunctions.base_arguments(parser)
    return DotMap(args = parser.parse_args())
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
    #=============================================================
    # Chassis Inventory
    #=============================================================
    def chassis_inventory(d, mtype, chassis):
        dkeys = list(d.keys())
        mkeys = list(chassis[mtype].keys())
        if 'model' in dkeys:
            if not d.model in mkeys: chassis[mtype][d.model] = 1
            else: chassis[mtype][d.model] += 1
        return chassis
    #=============================================================
    # Domain Inventory
    #=============================================================
    def domain_inventory(d, mtype, domain):
        for a, b in d.items():
            for i in b:
                ikeys = list(i.keys())
                mkeys = list(domain[mtype].keys())
                if 'model' in ikeys:
                    if not i.model in mkeys: domain[mtype][i.model] = 1
                    else: domain[mtype][i.model] += 1
        return domain
    #=============================================================
    # Server Inventory
    #=============================================================
    def server_inventory(d, mtype, server):
        if re.search('memory|processors', mtype):
            mtype = mtype.split('_')[0]
            mkeys = list(server[mtype].keys())
            for a, b in d.items():
                if not b in mkeys and len(b) > 0: server[mtype][b] = 1
                elif len(b) > 0: server[mtype][b] += 1
        elif re.search('adapters', mtype):
            dkeys = list(server[mtype].keys())
            for a, b in d.items():
                if not b.model in dkeys: server[mtype][b.model] = 1
                else: server[mtype][b.model] += 1
        elif 'fan' in mtype: server[mtype] += 1
        elif re.search('power', mtype):
            mkeys = list(d.keys())
            dkeys = list(server[mtype].keys())
            if 'model' in mkeys:
                if not d.model in dkeys: server[mtype][d.model] = 1
                else: server[mtype][d.model] += 1
        elif re.search('storage', mtype):
            dkeys = list(server[mtype].keys())
            for a, b in d.items():
                if not b.model in dkeys: server[mtype][b.model] = 1
                else: server[mtype][b.model] += 1
                if type(b.disks) == type_dotmap and len(b.disks) > 0:
                    for x,y in b.disks.items():
                        ddkeys = list(server.disks.keys())
                        if not y.pid in ddkeys: server.disks[y.model] = 1
                        else:  server.disks[y.model] += 1
        return server
    #=============================================================
    # Get Counts for Inventory from inventory Script
    #=============================================================
    type_dotmap = type(DotMap())
    type_none = type(None)
    inventory = DotMap(json.load(open(os.path.join(kwargs.script_path, 'inventory.json'), 'r')))
    chassis   = DotMap(fan_modules    = DotMap(), io_modules  = DotMap(), models              = DotMap(), power_supplies = DotMap())
    domain    = DotMap(fan_modules    = DotMap(), models      = DotMap(), power_supplies      = DotMap())
    server    = DotMap(adapters       = DotMap(), disks       = DotMap(), fan_modules         = 0,        memory = DotMap(), models = DotMap(),
                       power_supplies = DotMap(), processors  = DotMap(), storage_controllers = DotMap())
    elist = ['expander_modules', 'fan_modules', 'io_modules', 'power_supplies']
    for k,v in inventory.chassis.items():
        mkeys = list(chassis.models.keys())
        if not v.model in mkeys: chassis.models[v.model] = 1
        else: chassis.models[v.model] += 1
        for e in elist:
            if type(v[e]) != type_none:
                for d in v[e]:
                    if re.search('expander_modules|io_modules', e): dtype = 'io_modules'
                    else: dtype = e
                    chassis = chassis_inventory(d, dtype, chassis)
    chassis.models = DotMap(sorted(chassis.models.items()))
    elist = ['fan_modules', 'io_modules', 'power_supplies']
    for e in elist: chassis[e] = DotMap(sorted(chassis[e].items()))
    print(json.dumps(chassis, indent=4))
    elist = ['fan_modules', 'power_supplies']
    for k,v in inventory.domains.items():
        mkeys = list(domain.models.keys())
        if not v.model in mkeys: domain.models[v.model] = 1
        else: domain.models[v.model] += 1
        for e in elist:
            if type(v[e]) != type_none:
                for d in v[e]: domain = domain_inventory(d, e, domain)
    domain.models = DotMap(sorted(domain.models.items()))
    for e in elist: domain[e] = DotMap(sorted(domain[e].items()))
    print(json.dumps(domain, indent=4))
    elist = ['adapters', 'fan_modules', 'memory_inventory', 'power_supplies', 'processors', 'storage_controllers']
    for k,v in inventory.servers.items():
        mkeys = list(server.models.keys())
        if not v.model in mkeys: server.models[v.model] = 1
        else: server.models[v.model] += 1
        for e in elist:
            if type(v[e]) == list:
                for d in v[e]: server = server_inventory(d, e, server)
            elif type(v[e]) == type_dotmap: server = server_inventory(v[e], e, server)
    server.models = DotMap(sorted(server.models.items()))
    elist = ['adapters', 'fan_modules', 'memory', 'power_supplies', 'processors', 'storage_controllers']
    for e in elist:
        if not type(server[e]) == int: server[e] = DotMap(sorted(server[e].items()))
    print(json.dumps(server, indent=4))

if __name__ == '__main__': main()
