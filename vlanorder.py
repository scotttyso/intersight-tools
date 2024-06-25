#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions
    import os, urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
vlans = "74-80,82,110,162-172,177,178,192,196,199,201-205,207,213,214,216,2162,2164-2172,220,2204,2208,2216,223,2233,233,2982-2985,2997,300-304,310,456,500,501,520,601-603,605,607,608,613,614,629,630,712,715,800,913-924,936,937,941,942,945,948,957,961,966,967,975-977,982-984,994,995,997-999"
vlan_list = ezfunctions.vlan_list_full(vlans)
vlan_list = ezfunctions.vlan_list_format(vlan_list)
print(vlan_list)
