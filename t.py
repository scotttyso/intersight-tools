#!/usr/bin/env python3
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import os, sys
script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.insert(0, f'{script_path}{os.sep}classes')
try:
    from classes import pcolor
    from dotmap import DotMap
    from pathlib import Path
    import json, logging, os, pexpect, platform, re
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

#=============================================================================
# Function - Basic Setup for the Majority of the modules
#=============================================================================
def base_script_settings(kwargs):
    #=========================================================================
    # Configure logger and Build kwargs
    #=========================================================================
    script_name = (sys.argv[0].split(os.sep)[-1]).split('.')[0]
    dest_dir    = f'{Path.home()}{os.sep}Logs'
    dest_file   = script_name + '.log'
    if not os.path.exists(dest_dir): os.mkdir(dest_dir)
    if not os.path.exists(os.path.join(dest_dir, dest_file)): 
        create_file = f'type nul >> {os.path.join(dest_dir, dest_file)}'; os.system(create_file)
    FORMAT = '%(asctime)-15s [%(levelname)s] [%(filename)s:%(lineno)s] %(message)s'
    logging.basicConfig(filename=f'{dest_dir}{os.sep}{script_name}.log', filemode='a', format=FORMAT, level=logging.DEBUG )
    logger = logging.getLogger('openapi')
    #=========================================================================
    # Determine the Script Path
    #=========================================================================
    args_dict = vars(kwargs.args)
    for k,v in args_dict.items():
        if type(v) == str and v != None: os.environ[k] = v
    kwargs.script_name = (sys.argv[0].split(os.sep)[-1]).split('.')[0]
    kwargs.script_path = os.path.dirname(os.path.realpath(sys.argv[0]))
    kwargs.home        = Path.home()
    kwargs.logger      = logger
    kwargs.op_system   = platform.system()
    kwargs.type_dotmap = type(DotMap())
    kwargs.type_none   = type(None)
    #=========================================================================
    # Import Stored Parameters and Add to kwargs
    #=========================================================================
    kwargs.ezdata = DotMap(json.load(open(os.path.join(kwargs.script_path, 'variables', 'hosts.json'), 'r', encoding='utf8')))
    return kwargs

#=============================================================================
# pexpect - Login Function
#=============================================================================
def child_login(kwargs):
    log_dir = os.path.join(str(Path.home()), 'Logs')
    if not os.path.isdir(log_dir): os.mkdir(log_dir)
    #=========================================================================
    # Determine Host Login Information
    #=========================================================================
    if sys.argv[1] == '-l':
        plength = 0; slength = 0
        for e in list(kwargs.ezdata.console_servers.keys()):
            for k, v in kwargs.ezdata.console_servers[e].items():
                if len(k) > plength: plength = len(k)
                if len(v.short_name) >  slength: slength = len(v.short_name)
        pcolor.Cyan(f'\n{"-"*130}\n\nTERMINAL SERVERS\n')
        for e in list(kwargs.ezdata.console_servers.keys()):
            pcolor.Green(f'Hostname: {e}\n')
            for k, v in kwargs.ezdata.console_servers[e].items():
                pcolor.Cyan("  Port: %-*s ShortName: %-*s Description: %s" % (plength,k,slength,v.short_name,v.description))
            pcolor.Green('')
        pcolor.Green('Short Names\n')
        hlength = 0; slength = 0; tlength = 0
        for k,v in kwargs.ezdata.short_names.items():
            if len(k) > slength: slength = len(k)
            if len(v.hostname) > hlength: hlength = len(v.hostname)
            if len(v.type)     > tlength: tlength = len(v.type)
        for k,v in kwargs.ezdata.short_names.items():
            pcolor.Cyan("  SN: %-*s Type: %-*s Host: %-*s Desc: %s" % (slength,k,tlength,v.type,hlength,v.hostname,v.description))
        pcolor.Cyan(f'\n{"-"*130}\n')
        sys.exit(0)
    x = sys.argv[1].split(',')
    if len(x) == 3:
        kwargs = kwargs | DotMap(hostname = x[0], port = x[1], protocol = x[2])
    else:
        kwargs = kwargs | DotMap(hostname = x[0], port = 22, protocol = 'ssh')
    if re.search('^[\\da-z]{2,3}c$', x[0]):
        match = False
        for e in list(kwargs.ezdata.console_servers.keys()):
            for k, v in kwargs.ezdata.console_servers[e].items():
                if v.short_name == x[0]:
                    kwargs = kwargs | DotMap(hostname = e, port = k, protocol = 'telnet', type = 'terminal')
                    match = True; break
            if match == True: break
        if match == False:
            print('error')
            sys.exit(1)
    if x[0] in list(kwargs.ezdata.short_names.keys()):
        kwargs = kwargs | kwargs.ezdata.short_names[x[0]]
    #=========================================================================
    # Determine Username/Password
    #=========================================================================
    if   'hx'  in kwargs.type: password = os.environ['hxpassword'];  kwargs.username = 'admin'
    elif 'imm' in kwargs.type: password = os.environ['immpassword']; kwargs.username = 'admin'
    elif 'lab' in kwargs.type: password = os.environ['labpassword']; kwargs.username = 'admin'
    elif 'kit' in kwargs.type: password = os.environ['kitpassword']; kwargs.username = 'imm-toolkit'
    elif re.search('^r14[2-3][a-z]-pdu', kwargs.hostname):
        kwargs.port = 23; kwargs.protocol = 'telnet'
        if re.search('3[a-e]', kwargs.hostname): password = os.environ['pdupassword']; kwargs.username = 'localadmin'; 
        else:  password = os.environ['pdupassword']; kwargs.username = 'admin'; kwargs.protocol = 'ssh'
    else: password = os.environ['password']; kwargs.username = os.environ['username']
    if   'aci' == kwargs.type: kwargs.username = f'apic#RICH\\\\{kwargs.username}'
    elif 'ucs' == kwargs.type: kwargs.username = f'ucs-RICH\\\\{kwargs.username}'
    elif kwargs.hostname == 'lnx2.rich.ciscolabs.com': kwargs.username = f'{kwargs.username}@rich.ciscolabs.com'
    #=========================================================================
    # Launch Local Shell
    #=========================================================================
    if kwargs.op_system == 'Windows':
        from pexpect import popen_spawn
        child = popen_spawn.PopenSpawn('cmd', encoding='utf-8', timeout=1)
    else:
        system_shell = os.environ['SHELL']
        child = pexpect.spawnu(system_shell, encoding='utf-8')
    child.logfile_read = sys.stdout
    #=========================================================================
    # Test Connectivity with Ping
    #=========================================================================
    if kwargs.op_system == 'Windows':
        child.sendline(f'ping -n 2 {kwargs.hostname}')
        child.expect(f'ping -n 2 {kwargs.hostname}')
        child.expect_exact('> ')
    else:
        child.sendline(f'ping -c 2 {kwargs.hostname}')
        child.expect(f'ping -c 2 {kwargs.hostname}')
        child.expect_exact('$ ')
    #=========================================================================
    # Function - Clear Terminal Line
    #=========================================================================
    def clear_terminal_line(kwargs):
        child.sendline(f'telnet {kwargs.hostname}')
        child.expect(f'telnet {kwargs.hostname}')
        term_check = False
        while term_check == False:
            i = child.expect([
                'closed', '[p|P]assword:', '[u|U]sername:', '(\\$ $|\>|%|[a-zA-Z0-9]#[ ]?$)', pexpect.EOF, pexpect.TIMEOUT])
            if   i == 1: child.sendline(os.environ['password'])
            elif i == 2: child.sendline(kwargs.username)
            elif i == 3: term_check = True
            elif i == 0 or i == 4 or i == 5:
                pcolor.Red(f'\n{"-"*108}\n')
                if i == 4 or i == 5: pcolor.Red(f'!!! FAILED !!!\n Could not open {kwargs.protocol.upper()} Connection to {kwargs.hostname}')
                elif i == 0:
                    pcolor.Red(f'!!! FAILED !!! to connect.  '\
                        f'Please Validate hostname: `{kwargs.hostname}` and username: `{kwargs.username}` is correct.')
                pcolor.Red(f'\n{"-"*108}\n')
                child.close()
                sys.exit(1)
        child.sendline(f'clear line tty {int(kwargs.port) - 2000}')
        child.expect(f'clear line tty')
        term_check = False
        while term_check == False:
            i = child.expect([
                'confirm', '(\\$ $|\>|%|[a-zA-Z0-9]#[ ]?$)'])
            if   i == 0: child.send('\r')
            elif i == 1: term_check = True
            elif i == 0 or i == 4 or i == 5:
                pcolor.Red(f'\n{"-"*108}\n')
                if i == 4 or i == 5: pcolor.Red(f'!!! FAILED !!!\n Could not open {kwargs.protocol.upper()} Connection to {kwargs.hostname}')
                elif i == 0:
                    pcolor.Red(f'!!! FAILED !!! to connect.  '\
                        f'Please Validate hostname: `{kwargs.hostname}` and username: `{kwargs.username}` is correct.')
                pcolor.Red(f'\n{"-"*108}\n')
                child.close()
                sys.exit(1)
        child.sendline(f'exit')
        child.expect(f'exit')
        child.expect(f'Connection closed by foreign host')
        child.sendline(f'telnet {kwargs.hostname} {kwargs.port}')
        child.expect(f'telnet {kwargs.hostname} {kwargs.port}')
    #=========================================================================
    # Initiate Remote Connection
    #=========================================================================
    if kwargs.protocol == 'telnet': 
        child.sendline(f'telnet {kwargs.hostname} {kwargs.port}')
        child.expect(f'telnet {kwargs.hostname} {kwargs.port}')
    else: 
        child.sendline(f'ssh -p {kwargs.port} {kwargs.username}@{kwargs.hostname} ')
        child.expect(f'ssh -p {kwargs.port}')
        child.expect(kwargs.hostname)
    logged_in = False
    while logged_in == False:
        i = child.expect([
            'Are you sure you want to continue', 'closed', '[p|P]assword:', '[u|U]sername:',
            '(\\$ $|\>|%|[a-zA-Z0-9]#[ ]?$)', 'Now Connected to:', pexpect.EOF, pexpect.TIMEOUT,
            'Host key verification failed.',
            'telnet: Unable to connect to remote host: Connection refused'])
        if   i == 0: child.sendline('yes')
        elif i == 2: child.sendline(password)
        elif i == 3: child.sendline(kwargs.username)
        elif i == 4: logged_in = True
        elif i == 5: logged_in = True
        elif i == 9: clear_terminal_line(kwargs)
        elif i == 1 or i == 6 or i == 7 or i == 8:
            pcolor.Red(f'\n{"-"*108}\n')
            if i == 6 or i == 7: pcolor.Red(f'!!! FAILED !!!\n Could not open {kwargs.protocol.upper()} Connection to {kwargs.hostname}')
            elif i == 1:
                pcolor.Red(f'!!! FAILED !!! to connect.  '\
                    f'Please Validate hostname: `{kwargs.hostname}` and username: `{kwargs.username}` is correct.')
            elif i == 8: pcolor.Red(f'!!! FAILED !!! to connect.  SSH Host Key has Changed.')
            pcolor.Red(f'\n{"-"*108}\n')
            child.close()
            sys.exit(1)

  
    child.logfile_read = None
    def output_filter(s):
        global filter_buffer, filter_size
        # print(s)
        filter_buffer += s.decode('utf-8')
        filter_buffer = filter_buffer[-filter_size:]

        if "sdf" in filter_buffer:
            child.logfile_read = sys.stdout
            child.sendcontrol('u')
            if kwargs.type == 'terminal':
                child.sendcontrol(']')
                child.expect('telnet>')
                child.sendline('quit')
                child.expect('quit')
            else:
                child.sendline('exit')
                child.expect('exit')
            logged_out = False
            while logged_out == False:
                i = child.expect(['Connection closed', '\\)#[ ]?$', '(\\$ $|\\$ \x07$|\>|%|[a-zA-Z0-9]#[ ]?$)', pexpect.EOF, pexpect.TIMEOUT])
                print(i)
                if   i == 3: logged_out = True
                elif i == 0: child.sendline('\r')
                elif i == 1: child.sendline('end'); child.expect('end')
                elif i == 2: child.sendline('exit'); child.expect('exit')
                elif i == 4:
                    print(child.before)
                    print(child.after)
                    print(child.buffer)
                    sys.exit(1)
            child.logfile_read = None
        return s
    child.interact(output_filter=output_filter)
    child.close()
    # Return values
    return kwargs

#=============================================================================
# Function: Main Script
#=============================================================================
def main():
    #=========================================================================
    # Configure Base Module Setup
    #=========================================================================
    kwargs = DotMap()
    kwargs = base_script_settings(kwargs)
    kwargs = child_login(kwargs)
    #=========================================================================
    # Prompt User for Main Menu
    #=========================================================================
    pcolor.Cyan(f'\n{"-"*108}\n\n  !!! Procedures Complete !!!\n  Closing Environment and Exiting Script...\n\n{"-"*108}\n')
    sys.exit(0)

filter_buffer = ''
filter_size   = 256
if __name__ == '__main__':
    main()
