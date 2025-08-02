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
vlans = "1124,1431,1434,1165,3139,3140,3142,3145,3146,3190,3193,3195,3145,3196,3147,2234,2431,3340,3342,3346,3393,3396,3347,2002,1000,1908,1089,1096,3235,3236,3237,3241,3242,3284,3285,3287,2601,2602,2606,2611,2612,2615,2682,2686,2691,2695,3431,3464,3436,3466,3437,3470,3441,3481,3484,3485,2002,2501,2502,2504,2506,2508,2511,2512,2513,2515,2581,2582,2586,2591,2529,2595,3231,2580,91, 2511, 2591,92,2780"
vlan_list = ezfunctions.vlan_list_full(vlans)
vlan_list = ezfunctions.vlan_list_format(vlan_list)
print(vlan_list)
