#!/usr/bin/env python3
""" Infrastructure Deployment - 
This Script is built to Deploy VIBs to ESXi.
The Script uses argparse to take in the following CLI arguments:
    y or yaml-file:             The input YAML File.
"""
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path= os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import ezfunctions, pcolor
    from dotmap import DotMap
    from pathlib import Path
    import argparse, json, logging, os, pexpect, re, socket, time, yaml
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
#=================================================================
# Function: Parse Arguments
#=================================================================
def cli_arguments():
    Parser = argparse.ArgumentParser(description='ESXi VIB Deployment Module')
    Parser.add_argument( '-y', '--yaml-file',                       help = 'The input YAML File.' )
    kwargs = DotMap()
    kwargs.args = Parser.parse_args()
    return kwargs

#=================================================================
# The Main Module
#=================================================================
def main():
    #==============================================
    # Configure logger and Build kwargs
    #==============================================
    script_name = (sys.argv[0].split(os.sep)[-1]).split('.')[0]
    dest_dir = f"{Path.home()}{os.sep}Logs"
    dest_file = script_name + '.log'
    if not os.path.exists(dest_dir): os.mkdir(dest_dir)
    if not os.path.exists(os.path.join(dest_dir, dest_file)): 
        create_file = f'type nul >> {os.path.join(dest_dir, dest_file)}'; os.system(create_file)
    FORMAT = '%(asctime)-15s [%(levelname)s] [%(filename)s:%(lineno)s] %(message)s'
    logging.basicConfig( filename=f"{dest_dir}{os.sep}{script_name}.log", filemode='a', format=FORMAT, level=logging.DEBUG )
    logger = logging.getLogger('openapi')
    kwargs = cli_arguments()
    #==============================================
    # Process the YAML input File
    #==============================================
    if (kwargs.args.yaml_file):
        yfile = open(os.path.join(kwargs.args.yaml_file), 'r')
        ydata = DotMap(yaml.safe_load(yfile))
    else:
        pcolor.Red('yaml_file is a required argument.  Please run again with -y <yaml_file>')
    for e in ydata.esxi_servers:
        kwargs.servers[e] = DotMap(rebooted = False)
        esx_host = e
        pcolor.Green(f"\n{'-'*91}\n")
        pcolor.Green(f"   Beginning Host Customization for {esx_host}.")
        pcolor.Green(f"\n{'-'*91}\n")
        time.sleep(2)
        kwargs.hostname   = esx_host
        kwargs.password   = 'vmware_esxi_password'
        kwargs.username   = 'root'
        kwargs.host_prompt= f'root\\@{k}\\:'
        child, kwargs     = ezfunctions.child_login(kwargs)
        #==============================================
        # Install the VIB
        #==============================================
        vib = ydata.vib_file
        repo_url = f'https://{ydata.repo_server}/repo/{vib}'
        child.sendline(f'rm -f /tmp/{vib}')
        child.expect(f'rm -f')
        child.expect(kwargs.host_prompt)
        if 'https' in repo_url:
            child.sendline(f'wget --no-checkcertificate {repo_url}')
        else: child.sendline(f'wget {repo_url}')
        attempt_count = 0
        download_success = False
        while download_success == False:
            i = child.expect(['error getting response', 'saved', kwargs.host_prompt, pexpect.TIMEOUT])
            if i == 3 or attempt_count == 3:
                pcolor.Red(f"\n{'-'*91}\n")
                pcolor.Red(f'!!! FAILED !!!\n Failed to Download {vib} via {kwargs.repo_server}')
                pcolor.Red(f"\n{'-'*91}\n")
                sys.exit(1)
            elif i == 0:
                child.sendline(f'wget {repo_url}')
                attempt_count += 1
                time.sleep(5)
            elif i == 1: download_success = True
            elif i == 2:
                child.sendline(f'wget {repo_url}')
                attempt_count += 1
                time.sleep(5)
        child.sendline(f'esxcli software component apply -d /tmp/{vib}')
        child.expect(f'esxcli software component apply')
        cmd_check = False
        while cmd_check == False:
            regex1 = re.compile(f"(Components Installed: [a-zA-Z\\-\\_\\.]+)\r")
            regex2 = re.compile('(Message: [a-zA-Z\\d ,]+\\.)\r')
            regex3 = re.compile('Reboot Required: true')
            regex4 = re.compile('Reboot Required: false')
            i = child.expect([regex1, regex2, regex3, regex4])
            if   i == 0: pcolor.Green(f'\n\n    {(child.match).group(1)}\n\n')
            elif i == 1: pcolor.Green(f'\n\n    VIB {vib} install message is {(child.match).group(1)}\n\n')
            elif i == 2: reboot_required = True; cmd_check = True
            elif i == 3: reboot_required = False; cmd_check = True
        if reboot_required == True:
            pcolor.Green(f'\n\nNeed to reboot {esx_host}\n\n')
            child.sendline('reboot')
            child.expect('closed')
            reboot_count += 1
            kwargs.servers[e].rebooted = True
        else:
            pcolor.Green(f'\n\nno reboot required for {esx_host}\n\n')
            kwargs.servers[e].rebooted = False
            child.sendline('exit')
            child.expect('closed')
        pcolor.Green(f"\n{'-'*91}\n")
        pcolor.Green(f"   Completed Base Configuration for {esx_host}")
        pcolor.Green(f"\n{'-'*91}\n")
        time.sleep(2)
    child.close()

    def isReachable(ipOrName, port, timeout=2):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((ipOrName, int(port)))
            s.shutdown(socket.SHUT_RDWR)
            return True
        except: return False
        finally: s.close()
    
    failed_hosts = 0
    if reboot_count > 0:
        time.sleep(240)
        for k,v in kwargs.servers.items():
            if v.rebooted == True:
                esx_host = e
                pcolor.Green(f"   Checking Host {esx_host} Reachability after reboot.")
                reach_count = 0
                reachable = False
                while reachable == False:
                    connected = isReachable(esx_host, '443')
                    if connected == True:
                        pcolor.Green(f"   Connection to {esx_host} Succeeded..")
                        reachable = True
                    else:
                        if reach_count == 5:
                            pcolor.Cyan(f"   Connection to {esx_host} Failed.  Skipping Host.")
                            kwargs.servers[k].failed_host = True
                            failed_hosts += 1
                            reachable = True
                        else:
                            reach_count += 1
                            pcolor.Cyan(f"   Connection to {esx_host} Failed.  Sleeping for 2 minutes.")
                            time.sleep(120)
        if failed_hosts > 0:
            for k,v in kwargs.servers.items():
                esx_host = k
                if v.get('failed_host'): pcolor.Cyan(f"   Connection to {esx_host} Failed.  Host Failed.")
            sys.exit(1)
