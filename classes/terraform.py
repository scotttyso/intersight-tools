#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from classes import isight, pcolor
    import os, re, subprocess, sys
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

#=============================================================================
# Build IMM Policies
#=============================================================================
class state(object):
    def __init__(self, type):
        self.type = type
    
    def run_commands(self, kwargs):
        #child.sendline('')
        if self.type == 'lan_connectivity': policy = 'intersight_vnic_eth_if'
        else: policy = 'intersight_vnic_fc_if'
        for v in kwargs.names:
            moid    = kwargs.isight[kwargs.org].policy[f'{self.type}.{kwargs.vnic}'][v]
            #command = f'terraform import module.policies[\\"map\\"].{policy}.map[\\"{kwargs.org}/{kwargs.policy}/{v}\\"] {moid}'
            result = subprocess.run(
                ['terraform', 'import', f'module.policies[\\"map\\"].{policy}.map[\\"{kwargs.org}/{kwargs.policy}/{v}\\"]', moid],
                capture_output=True,
                text=True)
            pcolor.Yellow(result.stdout)
            #child.sendline(command)
            #child.expect(moid)
            #child.expect('Import successful')
        pcolor.Cyan('')
        return kwargs

    def state_import(self, kwargs):
        #system_shell = os.environ['SHELL']
        #child = pexpect.spawn(system_shell, encoding='utf-8', timeout=60, codec_errors='ignore')
        #child.logfile_read = sys.stdout
        kwargs = isight.api('organization').all_organizations(kwargs)
        orgs   = list(kwargs.imm_dict.orgs.keys())
        for org in orgs:
            kwargs.org = org
            pkeys = list(kwargs.imm_dict.orgs[org].policies.keys())
            for p in ['lan_connectivity', 'san_connectivity']:
                self.type = p
                if self.type in pkeys:
                    names  = [e.name for e in kwargs.imm_dict.orgs[org].policies[self.type]]
                    kwargs = isight.api_get(False, names, self.type, kwargs)
                    for e in kwargs.imm_dict.orgs[org].policies[self.type]:
                        names = []
                        if 'lan' in p: kwargs.vnic = 'vnics'
                        else: kwargs.vnic = 'vhbas'
                        for d in e[kwargs.vnic]: names.extend(d.names)
                        kwargs.pmoid  = kwargs.isight[org].policy[self.type][e.name]
                        kwargs.policy = e.name
                        kwargs        = isight.api_get(False, names, f'{self.type}.{kwargs.vnic}', kwargs)
                        kwargs.names  = names
                        kwargs = state(self.type).run_commands(kwargs)
        #child.close()
        return kwargs
