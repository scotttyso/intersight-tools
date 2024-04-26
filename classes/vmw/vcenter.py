#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import ezfunctions, pcolor, validating
    from classes.vmw import cluster, datacenter, datastore, host, network, ssl_helper, util
    from dotmap import DotMap
    from pyVmomi import vim # pyright: ignore
    from vmware.vapi.vsphere.client import create_vsphere_client
    import json, numpy, os, pyVim.connect, re, requests, ssl, time, urllib3
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Global options for debugging
print_payload = False
print_response_always = True
print_response_on_fail = True

# Log levels 0 = None, 1 = Class only, 2 = Line
log_level = 2

# Exception Classes
class InsufficientArgs(Exception): pass
class ErrException(Exception): pass
class InvalidArg(Exception): pass
class LoginFailed(Exception): pass


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
        validating.begin_section('vCenter', self.type)
        time.sleep(2)
        #=====================================================
        # Load Variables and Login to Storage Array
        #=====================================================
        kwargs['Variable'] = 'esx_password'
        kwargs = ezfunctions.sensitive_var_value(**kwargs)
        kwargs.esx.password = kwargs['var_value']
        for k, v in kwargs.server_profiles.items():
            esx_host = k + '.' + kwargs.dns_domains[0]
            print(f"\n{'-'*91}\n")
            print(f"   Beginning Base Configuration for {esx_host}. Including dns, ntp, ssh, and vibs.")
            print(f"\n{'-'*91}\n")
            time.sleep(2)
            kwargs.hostname     = esx_host
            kwargs.hostPassword = 'esx_password'
            kwargs.username     = 'root'
            kwargs.hostPrompt   = f'root\\@{k}\\:'
            child, kwargs      = ezfunctions.child_login(kwargs, **kwargs)
            #=====================================================
            # Get TPM Key if Installed
            #=====================================================
            child.sendline('esxcli system settings encryption get')
            tpm_installed = False
            cmd_check = False
            while cmd_check == False:
                regex1 = re.compile('Mode: TPM')
                i = child.expect([regex1, kwargs.hostPrompt])
                if i == 0: tpm_installed = True
                elif i == 1: cmd_check == True
            if tpm_installed == True:
                child.sendline('esxcli system settings encryption recovery list')
                cmd_check = False
                while cmd_check == False:
                    regex1 = re.compile('(\\{[A-Z\\d\\-]+\\})[ ]+([A-Z\\d\\-]+)\r')
                    i = child.expect([regex1, kwargs.hostPrompt])
                    if i == 0:
                        v['recovery_id'] = (child.match).group(1)
                        v['recovery_key'] = (child.match).group(2)
                    elif i == 1: cmd_check == True
                    child.sendline('')
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
                f'esxcli system hostname set --fqdn={esx_host}'
                f'esxcli network ip dns search add -d {kwargs.dns_domains[0]}',
                'vim-cmd hostsvc/enable_ssh',
                'vim-cmd hostsvc/enable_esx_shell',
                'vim-cmd hostsvc/advopt/update UserVars.SuppressShellWarning long 1',
                ntp_cfg, 'cd /tmp'
            ]
            for cmd in cmds:
                child.sendline(cmd)
                child.expect(kwargs.hostPrompt)
            for dns in kwargs.dns_servers:
                child.sendline(f'esxcli network ip dns server add -s {dns}')
                child.expect(kwargs.hostPrompt)
            for domain_name in kwargs.dns_domains:
                child.sendline(f'esxcli network ip dns search add -d {domain_name}')
                child.expect(kwargs.hostPrompt)
            #=====================================================
            # Install VIBs
            #=====================================================
            kwargs.repository_server = 'rdp1.rich.ciscolabs.com'
            kwargs.repository_path = '/'
            kwargs.vib_files = [
                'Broadcom-lsi-mr3_7.719.02.00-1OEM.700.1.0.15843807_18724954.zip',
                'Cisco-nenic_1.0.45.0-1OEM.700.1.0.15843807_20904742.zip',
                'Cisco-nfnic_5.0.0.37-1OEM.700.1.0.15843807_20873938.zip',
                'NetAppNasPlugin2.0.1.zip'
            ]
            reboot_required = False
            for vib in kwargs.vib_files:
                repo_url = ezfunctions.repo_url_test(vib, kwargs)
                child.sendline(f'rm -f {vib}')
                child.expect(kwargs.hostPrompt)
                child.sendline(f'wget --no-check-certificate {repo_url}')
                child.expect('saved')
                child.expect(kwargs.hostPrompt)
                if re.search('(Broadcom|Cisco)', vib): child.sendline(f'esxcli software component apply -d /tmp/{vib}')
                else: child.sendline(f'esxcli software vib install -d /tmp/{vib}')
                cmd_check = False
                while cmd_check == False:
                    regex1 = re.compile(f"(Components Installed: [a-zA-Z\\-\\_\\.]+)\r")
                    regex2 = re.compile('(Message: [a-zA-Z\\d ,]+\\.)\r')
                    regex3 = re.compile('Reboot Required: true')
                    i = child.expect([regex1, regex2, regex3, kwargs.hostPrompt])
                    if   i == 0: print(f'\n\n    {(child.match).group(1)}\n\n')
                    elif i == 1: print(f'\n\n    VIB {vib} install message is {(child.match).group(1)}\n\n')
                    elif i == 2: reboot_required = True
                    elif i == 3: cmd_check = True
            child.sendline('esxcfg-advcfg -s 0 /Misc/HppManageDegradedPaths')
            child.expect(kwargs.hostPrompt)
            if reboot_required == True:
                child.sendline('reboot')
                child.expect('closed')
            else:
                child.sendline('exit')
                child.expect('closed')
            print(f"\n{'-'*91}\n")
            print(f"   Completed Base Configuration for {esx_host}")
            print(f"\n{'-'*91}\n")
            time.sleep(2)
        child.close()
        print(kwargs.server_profiles)
        #=====================================================
        # Send End Notification and return kwargs
        #=====================================================
        validating.end_section('vCenter', self.type)
        return kwargs, kwargs

    #=====================================================
    # vCenter Configuration
    #=====================================================
    def vcenter(self, kwargs):
        #=====================================================
        # Send Begin Notification
        #=====================================================
        validating.begin_section(self.type, 'Host')
        time.sleep(2)
        #=====================================================
        # Load Variables and Login to vCenter API's
        #=====================================================
        kwargs.esx.username            = 'root'
        kwargs.vcenter.datacenter.name = 'NETAPP'
        kwargs.vcenter.server          = 'vcenter.rich.ciscolabs.com'
        kwargs.vcenter.username        = 'administrator@rich.local'
        kwargs['Variable'] = 'esx_password'
        kwargs = ezfunctions.sensitive_var_value(**kwargs)
        kwargs.esx.password = kwargs['var_value']
        kwargs['Variable'] = 'vcenter_password'
        kwargs = ezfunctions.sensitive_var_value(**kwargs)
        kwargs.vcenter.password = kwargs['var_value']

        # Connect to VIM API Endpoint on vCenter system
        context = ssl_helper.get_unverified_context()
        service_instance = pyVim.connect.SmartConnect(host       = kwargs.vcenter.server,
                                                      user       = kwargs.vcenter.username,
                                                      pwd        = kwargs.vcenter.password,
                                                      sslContext = context)
        # Connect to vAPI Endpoint on vCenter system
        session = ssl_helper.get_unverified_session()
        client = create_vsphere_client(server   = kwargs.vcenter.server,
                                       username = kwargs.vcenter.username,
                                       password = kwargs.vcenter.password,
                                       session  = session)
        context = util.Context(service_instance, client)
        #==============================================
        # Configure Data Center
        #==============================================
        dcFound, kwargs = datacenter.detect_datacenter(context, kwargs)
        if dcFound == False:
            kwargs = datacenter.create_datacenter(context, kwargs)
        #==============================================
        # Configure Cluster
        #==============================================
        models = []
        for k, v in kwargs.server_profiles.items(): models.append(v.model)
        models = numpy.unique(numpy.array(models))
        for cluster_name in models:
            clusterFound, kwargs = cluster.detect_cluster(context, cluster_name, kwargs)
            if clusterFound == False:
                kwargs = cluster.create_cluster_vapi2(context, cluster_name, kwargs)
        #==============================================
        # Find Cluster Host Folder and Existing Hosts
        #==============================================
        kwargs = host.host_folders(context, kwargs)
        #print(kwargs.vcenter.host.folder)

        esx_hosts = []
        for i in kwargs.server_profiles.keys():
            esx_hosts.append(i + '.' + kwargs.dns_domains[0])
        kwargs = host.detect_hosts(context, esx_hosts, kwargs)
        #==============================================
        # Add ESXi Hosts to DC And Move to Cluster
        #==============================================
        for k, v in kwargs.server_profiles.items():
            esx_host = k + '.' + kwargs.dns_domains[0]
            index = [i for i, d in enumerate(kwargs.host_summaries) if esx_host in d.name]
            if len(index) == 0:
                kwargs = host.create_host_vapi(context, esx_host, kwargs)
                host.move_host_into_cluster_vim(context, v['model'], esx_host, kwargs)
            else:
                kwargs.esxhosts[esx_host].moid = kwargs.host_summaries[index[0]].host
        #print(kwargs.esxhosts)

        datastore.create_vmfs_datastore(context, kwargs)
        #=====================================================
        # Send End Notification and return kwargs
        #=====================================================
        validating.end_section(self.type, 'Host')
        return kwargs, kwargs
