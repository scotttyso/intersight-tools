#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, pcolor, validating
    from copy import deepcopy
    from dotmap import DotMap
    import json, numpy, os, pexpect, platform, re, requests, socket, subprocess, time, urllib3
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Class must be instantiated with Variables
class api(object):
    def __init__(self, type):
        self.type = type

    #=====================================================
    # ESX Host Initialization
    #=====================================================
    def esx(self, kwargs):
        #=====================================================
        # Send Begin Notification
        #=====================================================
        validating.begin_section('vCenter', self.type.capitalize())
        time.sleep(2)
        if kwargs.args.deployment_type == 'flexpod':
            #=====================================================
            # Test Repo URL for NetAppNasPlugin
            #=====================================================
            kwargs.sensitive_var = 'imm_transition_password'
            kwargs  = ezfunctions.sensitive_var_value(kwargs)
            imm_transition_password=kwargs.var_value
            s = requests.Session()
            data = json.dumps({'username':'admin','password':{imm_transition_password}})
            url = f'https://{kwargs.repo_server}/api/v1/'
            try: r = s.post(data = data, headers= {'Content-Type': 'application/json'}, url = f'{url}login', verify = False)
            except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}\n'); sys.exit(1)
            if not r.status_code == 200: pcolor.Red(r.text); sys.exit(1)
            jdata = json.loads(r.text)
            token = jdata['token']
            for uri in ['repo/files', 'logout']:
                try: r = s.get(url = f'{url}{uri}', headers={'x-access-token': token}, verify=False)
                except requests.exceptions.ConnectionError as e: pcolor.Red(f'!!! ERROR !!!\n{e}'); sys.exit(1)
                if 'repo' in uri: jdata = json.loads(r.text)
                if not r.status_code == 200: pcolor.Red(r.text); sys.exit(1)
            netapp_plugin = ''
            for e in jdata['repofiles']:
                if 'NetAppNasPlugin' in e['file_path']: netapp_plugin = e['file_path'].split('/')[2]
            if netapp_plugin == '':
                pcolor.Red('!!! ERROR !!!\nCould not determine the file location for the NetAppNasPlugin.')
                pcolor.Red('Validate that you have uploaded NetAppNasPlugin2.0.1.zip or newer to the IMM Transition Tool Software Repository.')
                pcolor.Red('Exiting...')

        #=====================================================
        # Load Variables and Login to ESXi Hosts
        #=====================================================
        reboot_count = 0
        server_profiles = deepcopy(kwargs.server_profiles)
        for k, v in server_profiles.items():
            esx_host = k + '.' + kwargs.dns_domains[0]
            pcolor.Green(f"\n{'-'*108}\n")
            pcolor.Green(f"   Beginning Host Customization for {esx_host}.")
            pcolor.Green(f"\n{'-'*108}\n")
            time.sleep(2)
            kwargs.hostname   = esx_host
            kwargs.password   = 'vmware_esxi_password'
            kwargs.username   = 'root'
            kwargs.host_prompt= f'root\\@{k}\\:'
            child, kwargs     = ezfunctions.child_login(kwargs)

            #=====================================================
            # Enable DNS, NTP, SSH Shell, and WGET
            #=====================================================
            ntp_cfg = 'esxcli system ntp set '
            for ntp in kwargs.ntp_servers: ntp_cfg = ntp_cfg + f'--server {ntp} '
            ntp_cfg = ntp_cfg + '--enabled true'
            cmds = [
                'vim-cmd hostsvc/enable_ssh > /dev/null 2>&1',
                'chkconfig SSH on > /dev/null 2>&1',
                'esxcli network firewall ruleset set -e true -r httpClient',
                f'esxcli system hostname set --fqdn={esx_host}',
                'vim-cmd hostsvc/enable_ssh',
                'vim-cmd hostsvc/enable_esx_shell',
                'vim-cmd hostsvc/advopt/update UserVars.SuppressShellWarning long 1',
                ntp_cfg,
                'cd /tmp',
                f'ping {kwargs.repo_server.split("/")[2]}'
            ]
            for cmd in cmds:
                cmds = cmd.split(' ')
                child.sendline(cmd)
                child.expect(cmds[0])
                child.expect(kwargs.host_prompt)

            reboot_required = False
            if kwargs.args.deployment_type == 'flexpod':
                vib = netapp_plugin
                repo_url = f'https://{kwargs.repo_server}/repo/{vib}'
                child.sendline(f'rm -f {vib}')
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
                        pcolor.Red(f"\n{'-'*108}\n")
                        pcolor.Red(f'!!! FAILED !!!\n Failed to Download {vib} via {kwargs.repo_server}')
                        pcolor.Red(f"\n{'-'*108}\n")
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
                child.sendline(f'esxcli software vib install -d /tmp/{vib}')
                child.expect(f'esxcli software vib install')
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
            child.sendline('esxcfg-advcfg -s 0 /Misc/HppManageDegradedPaths')
            child.expect(kwargs.host_prompt)
            if reboot_required == True:
                pcolor.Green(f'\n\nNeed to reboot {esx_host}\n\n')
                child.sendline('reboot')
                child.expect('closed')
                reboot_count += 1
                kwargs.server_profiles[k].rebooted = True
            else:
                pcolor.Green(f'\n\nno reboot required for {esx_host}\n\n')
                kwargs.server_profiles[k].rebooted = False
                child.sendline('exit')
                child.expect('closed')
            pcolor.Green(f"\n{'-'*108}\n")
            pcolor.Green(f"   Completed Base Configuration for {esx_host}")
            pcolor.Green(f"\n{'-'*108}\n")
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
            for k, v in server_profiles.items():
                if v.rebooted == True:
                    esx_host = k + '.' + kwargs.dns_domains[0]
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
                                kwargs.server_profiles[k].failed_host = True
                                failed_hosts += 1
                                reachable = True
                            else:
                                reach_count += 1
                                pcolor.Cyan(f"   Connection to {esx_host} Failed.  Sleeping for 2 minutes.")
                                time.sleep(120)
            if failed_hosts > 0:
                for k, v in kwargs.server_profiles.items():
                    esx_host = k + '.' + kwargs.dns_domains[0]
                    if v.get('failed_host'): pcolor.Cyan(f"   Connection to {esx_host} Failed.  Host Failed.")
                sys.exit(1)

        #=====================================================
        # Send End Notification and return kwargs
        #=====================================================
        validating.end_section('vCenter', self.type.capitalize())
        return kwargs

    #=====================================================
    # Host Configuration with PowerCLI
    #=====================================================
    def powercli(self, kwargs):
        #=====================================================
        # VMware Attributes
        #=====================================================
        for item in kwargs.virtualization:
            #=====================================================
            # Add Global Attributes - datacenter|cluster|dns|ntp etc
            #=====================================================
            models = []
            for k, v in kwargs.server_profiles.items():
                gen = re.search('(M[0-9])', v.model).group(1)
                models.append(f"{(v.cpu).capitalize()}-{gen}")
            models = numpy.unique(numpy.array(models))
            for model in models: kwargs.vmware.clusters[model].name = model
            kwargs.vmware.datacenter = item.datacenter
            kwargs.vmware.datastores = []
            for i in kwargs.imm_dict.orgs[kwargs.org].storage.appliances:
                kwargs.vmware.datastores.extend(i.datastores)
            kwargs.vmware.dns_domains= kwargs.dns_domains
            kwargs.vmware.dns_servers= kwargs.dns_servers
            kwargs.vmware.name       = item.name
            kwargs.vmware.ntp_servers= kwargs.ntp_servers
            kwargs.vmware.servers    = []
            kwargs.vmware.username   = item.username
            kwargs.vmware.ucs_domain = v.domain

            #=====================================================
            # Add Servers
            #=====================================================
            for k, v in kwargs.server_profiles.items():
                idict = DotMap(
                    iscsi        = [],
                    license_type = item.license_type,
                    name         = v.name + '.' + kwargs.dns_domains[0],
                    nvme_adapters= [],
                    serial       = v.serial,
                    server_dn    = '',
                    syslog_server= item.syslog_server,
                    vswitches    = [])
                if len(v.domain) == 0: idict.server_dn = v.server_id
                else:
                    if v.object_type == 'compute.RackUnit':
                        idict.server_dn  = f"{v.domain}-{v.server_id}"
                    else: idict.server_dn= f"{v.domain}-{v.chassis_id}-{v.slot}"

                if len(v.iscsi) > 0:
                    edict = DotMap(port_groups=[], targets=[])
                    for e in v.iscsi: edict.port_groups.append(e.vlan_name)
                    for e in kwargs.imm_dict.orgs[kwargs.org].storage.appliances:
                        for s in e.iscsi.interfaces: edict.targets.append(s.ip_address)
                    idict.iscsi.append(edict)
                if len(v.nvme) > 0:
                    for e in kwargs.imm_dict.orgs[kwargs.org].storage.appliances:
                        controllers = []
                        nqn_id = e.nvme.nqn
                        for s in e.nvme.interfaces: controllers.append(s.ip_address)
                        clength = len(controllers) // 2
                        for vv in item.virtual_switches:
                            if 'storage' in vv.data_types:
                                indx = [e for e, d in enumerate(item.virtual_switches) if vv.name in d.values()][0]
                                indx = indx*2
                                for x in range(indx,indx+2):
                                    ndict = DotMap(controllers=[],mac_address='',subsystem_nqn='')
                                    if x % 2 == 0: ndict.controllers = controllers[:clength]
                                    else: ndict.controllers = controllers[clength:]
                                    ndict.mac_address = v.macs[x].mac
                                    ndict.subsystem_nqn = nqn_id
                                    idict.nvme_adapters.append(ndict)
                vmk = 0
                for vv in item.virtual_switches:
                    indx = [e for e, d in enumerate(item.virtual_switches) if vv.name in d.values()][0]
                    indx = indx*2
                    if re.search('vswitch0', vv.name, re.IGNORECASE): vv.name = 'vSwitch0'
                    vdict = DotMap(name=vv.name,
                        maca=v.macs[indx].mac,
                        macb=v.macs[indx+1].mac,
                        mtu=9000, type=vv.type, vmks=[])
                    def create_vmk_dictionary(vmk, values, kwargs):
                        kdict = DotMap(
                            ip        = values.ip,
                            management= kwargs.management,
                            name      = f"vmk{vmk}",
                            netmask   = values.netmask,
                            nvme      = kwargs.nvme,
                            port_group= values.vlan_name,
                            vmotion   = kwargs.vmotion)
                        if vmk == 'vmk0': kdict.port_group = 'Management Network'
                        return kdict
                    kwargs.management= False
                    kwargs.nvme      = False
                    kwargs.vmotion   = False
                    if 'management' in vv.data_types:
                        kwargs.management= True
                        values= v.inband
                        kdict = create_vmk_dictionary(vmk, values, kwargs)
                        vdict.vmks.append(deepcopy(kdict))
                        kwargs.management= False
                        vmk+=1
                    if 'migration' in vv.data_types:
                        kwargs.vmotion= True
                        values= v.migration
                        kdict = create_vmk_dictionary(vmk, values, kwargs)
                        vdict.vmks.append(deepcopy(kdict))
                        kwargs.vmotion= False
                        vmk+=1
                    if 'storage' in vv.data_types:
                        if len(v.nfs) > 0:
                            values= v.nfs
                            kdict = create_vmk_dictionary(vmk, values, kwargs)
                            vdict.vmks.append(deepcopy(kdict))
                            vmk+=1
                        if len(v.iscsi) == 2:
                            for x in v.iscsi:
                                values= x
                                kdict = create_vmk_dictionary(vmk, values, kwargs)
                                vdict.vmks.append(deepcopy(kdict))
                                vmk+=1
                        if len(v.nvme) == 2:
                            for x in v.nvme:
                                values= x
                                kwargs.nvme= True
                                kdict = create_vmk_dictionary(vmk, values, kwargs)
                                vdict.vmks.append(deepcopy(kdict))
                                kwargs.nvme= False
                                vmk+=1
                    # Append Virtual Switches to Dictionary
                    idict.vswitches.append(vdict)
                kwargs.vmware.servers.append(idict)
            #=====================================================
            # Add Virtual Switches
            #=====================================================
            for i in item.virtual_switches:
                if re.search('vswitch0', i.name, re.IGNORECASE): i.name = 'vSwitch0'
                kwargs.vmware.vswitches[i.name] = DotMap(
                    data_types = i.data_types,
                    mtu        = 9000,
                    name       = i.name,
                    port_groups= [],
                    type       = i.type
                )
                if 'management' in i.data_types:
                    pg = DotMap(
                        name     ="Management Network",
                        primary  =False,
                        secondary=False,
                        vlan     =None)
                    kwargs.vmware.vswitches[i.name].port_groups.append(pg)
                if 'migration' in i.data_types:
                    pg = DotMap(
                        name     =kwargs.migration.name,
                        primary  =False,
                        secondary=False,
                        vlan     =None)
                    native = True
                    if 'management' in i.data_types: native = False
                    elif 'storage' in i.data_types: native = False
                    if native == False: pg.vlan = kwargs.migration.vlan_id
                    kwargs.vmware.vswitches[i.name].port_groups.append(pg)
                elif 'storage' in i.data_types:
                    vcount = 0
                    for e in kwargs.vlans:
                        if re.search('(iscsi|nfs|nvme)', e.vlan_type):
                            pg = DotMap(
                                name     =e.name,
                                primary  =False,
                                secondary=False,
                                vlan     =None)
                            if not 'iscsi' in e.vlan_type: pg.vlan = e.vlan_id
                            if re.search('(iscsi|nvme)', e.vlan_type):
                                if vcount % 2 == 0: pg.primary = True
                                else: pg.secondary = True
                                vcount += 1
                            kwargs.vmware.vswitches[i.name].port_groups.append(pg)

        #=====================================================
        # Write Attributes to settings.json
        #=====================================================
        json_file = os.path.join(kwargs.args.dir, 'vcenter_json_data.json')
        with open(json_file, 'w') as fp:
            json_formated = json.dumps({'vcenters':[kwargs.vmware]}, indent=4)
            print(json_formated, file=fp)
        if platform.system() == 'Windows': pwsh = 'powershell.exe'
        else: pwsh = 'pwsh'

        #=====================================================
        # Add Sensitive Passwords to env
        #=====================================================
        kwargs.sensitive_var = 'vmware_esxi_password'
        kwargs = ezfunctions.sensitive_var_value(kwargs)
        kwargs.sensitive_var = 'vmware_vcenter_password'
        kwargs = ezfunctions.sensitive_var_value(kwargs)

        #=====================================================
        # Run the PowerShell Script
        #=====================================================
        commandline_options = [pwsh, '-ExecutionPolicy', 'Unrestricted', '-File', '/usr/bin/ezvcenter.ps1', '-j', json_file]
        results = subprocess.run(
            commandline_options, stdout = subprocess.PIPE, stderr = subprocess.PIPE, universal_newlines = True)
        pcolor.LightPurple(results.returncode)  # 0 = SUCCESS, NON-ZERO = FAIL  
        pcolor.LightPurple(results.stdout)      # Print Output
        pcolor.LightPurple(results.stderr)      # Print any Error Output

        if results.returncode == 0:  # COMPARING RESULT
            pcolor.Green(f"\n{'-'*108}\n")
            pcolor.Green(f"  Completed Configuring the Virtualization Environment Successfully.")
            pcolor.Green(f"\n{'-'*108}\n")
        else:
            pcolor.Green(f"\n{'-'*108}\n")
            pcolor.Green(f"  !!! ERROR !!!\n Something went wrong with the Configuration of the Virtualization Environment")
            pcolor.Green(f"\n{'-'*108}\n")
        return kwargs
