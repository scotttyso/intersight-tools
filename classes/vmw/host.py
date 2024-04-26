"""
* *******************************************************
* Copyright (c) VMware, Inc. 2016-2018. All Rights Reserved.
* SPDX-License-Identifier: MIT
* *******************************************************
*
* DISCLAIMER. THIS PROGRAM IS PROVIDED TO YOU "AS IS" WITHOUT
* WARRANTIES OR CONDITIONS OF ANY KIND, WHETHER ORAL OR WRITTEN,
* EXPRESS OR IMPLIED. THE AUTHOR SPECIFICALLY DISCLAIMS ANY IMPLIED
* WARRANTIES OR CONDITIONS OF MERCHANTABILITY, SATISFACTORY QUALITY,
* NON-INFRINGEMENT AND FITNESS FOR A PARTICULAR PURPOSE.
"""

__author__ = 'VMware, Inc.'


import pyVim.task
from com.vmware.vcenter_client import (Folder, Host)
from pyVmomi import vim # pyright: ignore

"""
#---------------QueryConnectionInfoViaSpec---------------
$spec = New-Object VMware.Vim.HostConnectSpec
$spec.HostName = 'r143e-2-1-4.rich.ciscolabs.com'
$spec.Password = 'Sensitive data is not recorded'
$spec.VimAccountPassword = 'Sensitive data is not recorded'
$spec.Port = -1
$spec.Force = $false
$spec.UserName = 'root'
$_this = Get-View -Id 'Datacenter-datacenter-1001'
$_this.QueryConnectionInfoViaSpec($spec)

#---------------QueryConnectionInfoViaSpec---------------
$spec = New-Object VMware.Vim.HostConnectSpec
$spec.HostName = 'r143e-2-1-4.rich.ciscolabs.com'
$spec.Password = 'Sensitive data is not recorded'
$spec.VimAccountPassword = 'Sensitive data is not recorded'
$spec.Port = -1
$spec.Force = $false
$spec.UserName = 'root'
$_this = Get-View -Id 'Datacenter-datacenter-1001'
$_this.QueryConnectionInfoViaSpec($spec)

#---------------QueryConnectionInfoViaSpec---------------
$spec = New-Object VMware.Vim.HostConnectSpec
$spec.HostName = 'r143e-2-1-4.rich.ciscolabs.com'
$spec.Password = 'Sensitive data is not recorded'
$spec.VimAccountPassword = 'Sensitive data is not recorded'
$spec.Port = -1
$spec.Force = $false
$spec.UserName = 'root'
$_this = Get-View -Id 'Datacenter-datacenter-1001'
$_this.QueryConnectionInfoViaSpec($spec)

#---------------AddStandaloneHost_Task---------------
$spec = New-Object VMware.Vim.HostConnectSpec
$spec.HostName = 'r143e-2-1-4.rich.ciscolabs.com'
$spec.Password = 'Sensitive data is not recorded'
$spec.VimAccountPassword = 'Sensitive data is not recorded'
$spec.VmFolder = New-Object VMware.Vim.ManagedObjectReference
$spec.VmFolder.Type = 'Folder'
$spec.VmFolder.Value = 'group-v1002'
$spec.LockdownMode = 'lockdownDisabled'
$spec.Force = $true
$spec.UserName = 'root'
$addConnected = $true
$license = 'TN214-4E0D0-M8VN9-0P0KP-1J8PM'
$_this = Get-View -Id 'Folder-group-h11063'
$_this.AddStandaloneHost_Task($spec, $null, $addConnected, $license)

"""
#=====================================================
# Function - Create Host
#=====================================================
def create_host_vapi(context, esx_host, kwargs):
    """
    Adds a single Host to the vCenter inventory under the named Datacenter
    using vAPI.
    """
    create_spec = Host.CreateSpec(
        hostname                = esx_host,
        user_name               = kwargs.esx.username,
        password                = kwargs.esx.password,
        folder                  = kwargs.vcenter.host.folder,
        thumbprint_verification = Host.CreateSpec.ThumbprintVerification.NONE)
    host = context.client.vcenter.Host.create(create_spec)
    kwargs.esxhosts[esx_host].moid = host
    print(f"\nCreated Host: `{host}` Name: `{esx_host}`")
    return kwargs


#=====================================================
# Function - Detect Existing Hosts
#=====================================================
def detect_host(context, names, kwargs):
    """Find host based on host name"""

    host_summaries = context.client.vcenter.Host.list(
        Host.FilterSpec(names=names))
    if len(host_summaries) > 0:
        for e in host_summaries:
            host      = e.host
            host_name = e.name
        print(f"Detected Host: `{host}` Name: `{host_name}`.")
        context.testbed.entities['HOST_IDS'][host_name] = host
        return True
    else:
        print("Host '{}' missing".format(host_name))
        return False


#=====================================================
# Function - Detect Existing Hosts
#=====================================================
def detect_hosts(context, esx_hosts, kwargs):
    """Find hosts based on hostnames"""
    kwargs.host_summaries = context.client.vcenter.Host.list(
        Host.FilterSpec(names=set(esx_hosts)))
    if len(kwargs.host_summaries) > 0:
        print(f'\n{"-"*91}\n')
        for i in kwargs.host_summaries:
            print(f"Detected Host '{i.name}' as {i.host}")
        print(f'\n{"-"*91}\n')
        return kwargs
    else: return kwargs


#=====================================================
# Function - Get Moid for Host Folder in Cluster
#=====================================================
def host_folders(context, kwargs):
    """Define Cluster Host Folder"""
    folder_summaries = context.client.vcenter.Folder.list(
        Folder.FilterSpec(type=Folder.Type.HOST, datacenters=set([kwargs.vcenter.datacenter.moid])))
    print(folder_summaries)
    kwargs.vcenter.host.folder = folder_summaries[0].folder
    for i in folder_summaries:
        print(f"\nDetected Host Folder '{i.name}' as {i.folder}")
    return kwargs


#=====================================================
# Function - Move Host into Cluster
#=====================================================
def move_host_into_cluster_vim(context, cluster_name, esx_host, kwargs):
    """Use vim api to move host to another cluster"""
    TIMEOUT = 30  # sec

    host         = kwargs.esxhosts[esx_host].moid
    host_mo      = vim.HostSystem(host, context.soap_stub)

    # Move the host into the cluster
    if not host_mo.runtime.inMaintenanceMode:
        task = host_mo.EnterMaintenanceMode(TIMEOUT)
        pyVim.task.WaitForTask(task)
    print(f"\nHost '{host}' ({esx_host}) in maintenance mode")

    cluster = kwargs.vcenter.cluster[cluster_name].moid
    cluster_mo = vim.ClusterComputeResource(cluster, context.soap_stub)
    print(cluster_mo)
    task = cluster_mo.MoveInto([host_mo])
    pyVim.task.WaitForTask(task)
    print(f"\nHost '{host}' ({esx_host}) moved into Cluster {cluster} ({cluster_name})")

    task = host_mo.ExitMaintenanceMode(TIMEOUT)
    pyVim.task.WaitForTask(task)
    print(f"\nHost '{host}' ({esx_host}) out of maintenance mode")


#=====================================================
# Function - Remove Hosts
#=====================================================
def remove_hosts(context):
    """Delete hosts after sample run"""
    host1_name = context.testbed.config['ESX_HOST1']
    host2_name = context.testbed.config['ESX_HOST2']
    names = set([host1_name, host2_name])

    host_summaries = context.client.vcenter.Host.list(
        Host.FilterSpec(names=names))
    print('Found {} Hosts matching names {}'.
          format(len(host_summaries), ', '.
                 join(["'{}'".format(n) for n in names])))

    for host_summary in host_summaries:
        host = host_summary.host
        print("Deleting Host '{}' ({})".format(host_summary.name, host))
        context.client.vcenter.Host.delete(host)

