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
vlans = "3705,3715,3716,3728,3729,3730,3731,3805,3828,3829,3830,3831,3832"
vlan_list = ezfunctions.vlan_list_full(vlans)
vlan_list = ezfunctions.vlan_list_format(vlan_list)
print(vlan_list)
