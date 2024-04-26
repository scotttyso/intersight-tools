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

from com.vmware.vcenter_client import (Datacenter, Folder)


def folder_list_datacenter_folder(context):
    return context.client.vcenter.Folder.list(Folder.FilterSpec(type=Folder.Type.DATACENTER))


def detect_datacenter(context, kwargs):
    """Find the datacenter with the given name"""
    datacenter_name = kwargs.vcenter.datacenter.name
    names = set([datacenter_name])
    datacenter_summaries = context.client.vcenter.Datacenter.list(
        Datacenter.FilterSpec(names=names))
    if len(datacenter_summaries) > 0:
        datacenter = datacenter_summaries[0].datacenter
        kwargs.vcenter.datacenter.moid = datacenter
        print("Detected Datacenter '{}' as {}".
              format(datacenter_name, datacenter))
        return True, kwargs
    else:
        print("Datacenter '{}' doesn't exist.".format(datacenter_name))
        return False, kwargs


def create_datacenter(context, kwargs):
    """Create datacenters for running vcenter samples"""
    # Find a Folder in which to put the Datacenters
    folder_summaries = folder_list_datacenter_folder(context)
    folder = folder_summaries[0].folder
    print("Creating datacenters in Folder '{}' ({})".
          format(folder, folder_summaries[0].name))

    # Create datacenter
    datacenter_name = kwargs.vcenter.datacenter
    kwargs.datacenter = context.client.vcenter.Datacenter.create(
        Datacenter.CreateSpec(name=datacenter_name, folder=folder)
    )
    print("Created Datacenter '{}' ({})".format(kwargs.datacenter, datacenter_name))
    return kwargs


def remove_datacenters(context, kwargs):
    """Remove datacenters"""

    # Look for the two datacenters
    datacenter_name = kwargs.vcenter.datacenter
    names = set([datacenter_name])

    datacenter_summaries = context.client.vcenter.Datacenter.list(
        Datacenter.FilterSpec(names=names))
    print("Found {} Datacenters matching names {}".
          format(len(datacenter_summaries), ", ".
                 join(["'{}'".format(n) for n in names])))

    for datacenter_summary in datacenter_summaries:
        datacenter = datacenter_summary.datacenter
        print("Deleting Datacenter '{}' ({})".
              format(datacenter, datacenter_summary.name))
        context.client.vcenter.Datacenter.delete(datacenter, force=True)

