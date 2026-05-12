# BIOS Schema Attribute Mapping Report

Generated from comparison of:
1. Template: /home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/classes/templates/intersight/C800/bios.json.j2
2. Redfish: /home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/QA/885/885.json
3. Schema: /home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/schema/cisco-ai-pods.json

## Summary

| Match Type | Count |
|------------|-------|
| exact_both | 12 |
| exact_redfish | 28 |
| exact_schema | 0 |
| possible_schema_match | 5 |
| no_match | 0 |

## Exact Matches (Both Redfish and Schema)
These attributes have exact matches in both the Redfish data and schema definition.

### CbsCmnApbdis
- **Python Name**: cbs_cmn_apbdis
- **Redfish Value**: 1
- **Schema API**: CbsCmnApbdis
- **Description**: The default value is `platform-default`.  BIOS Token for setting APBDIS configuration.  AMD CBS: Disables the Automatic Power Budget management to giv...

### CbsCmnCpuAvx512
- **Python Name**: cbs_cmn_cpu_avx512
- **Redfish Value**: Auto
- **Schema API**: CbsCmnCpuAvx512
- **Description**: The default value is `platform-default`.  BIOS Token for setting AVX512 configuration.  AMD CBS: Enables or disables AVX-512 instruction support on su...

### CbsCmnCpuCpb
- **Python Name**: cbs_cmn_cpu_cpb
- **Redfish Value**: Auto
- **Schema API**: CbsCmnCpuCpb
- **Description**: The default value is `platform-default`.  BIOS Token for setting Core Performance Boost configuration.  AMD CBS: Controls Core Performance Boost (AMD'...

### CbsCmnCpuGlobalCstateCtrl
- **Python Name**: cbs_cmn_cpu_global_cstate_ctrl
- **Redfish Value**: Auto
- **Schema API**: CbsCmnCpuGlobalCstateCtrl
- **Description**: The default value is `platform-default`.  BIOS Token for setting Global C State Control configuration.  AMD CBS: Enables or disables global CPU C-stat...

### CbsCmnCpuSmee
- **Python Name**: cbs_cmn_cpu_smee
- **Redfish Value**: Auto
- **Schema API**: CbsCmnCpuSmee
- **Description**: The default value is `platform-default`.  BIOS Token for setting CPU SMEE configuration.  AMD CBS: Enables Secure Memory Encryption for the CPU to tra...

### CbsCmnCpuStreamingStoresCtrl
- **Python Name**: cbs_cmn_cpu_streaming_stores_ctrl
- **Redfish Value**: Auto
- **Schema API**: CbsCmnCpuStreamingStoresCtrl
- **Description**: The default value is `platform-default`.  BIOS Token for setting Streaming Stores Control configuration.  AMD CBS: Controls streaming store operations...

### CbsCmnGnbNbIOMMU
- **Python Name**: cbs_cmn_gnb_nb_iommu
- **Redfish Value**: Enabled
- **Schema API**: CbsCmnGnbNbIommu
- **Description**: The default value is `platform-default`.  BIOS Token for setting IOMMU configuration.  AMD CBS: Enables the IOMMU in the northbridge/GNB for DMA isola...

### CbsCmnMemCtrllerPwrDnEnDdr
- **Python Name**: cbs_cmn_mem_ctrller_pwr_dn_en_ddr
- **Redfish Value**: Auto
- **Schema API**: CbsCmnMemCtrllerPwrDnEnDdr
- **Description**: The default value is `platform-default`.  BIOS Token for setting Power Down Enable configuration.  AMD CBS: Enables power-down mode on the DDR memory ...

### CbsCpuSmtCtrl
- **Python Name**: cbs_cpu_smt_ctrl
- **Redfish Value**: Enable
- **Schema API**: CbsCpuSmtCtrl
- **Description**: The default value is `platform-default`.  BIOS Token for setting CPU SMT Mode configuration.  AMD CBS: Enables or disables Simultaneous Multi-Threadin...

### CbsDfCmnDramNps
- **Python Name**: cbs_df_cmn_dram_nps
- **Redfish Value**: NPS4
- **Schema API**: CbsDfCmnDramNps
- **Description**: The default value is `platform-default`.  BIOS Token for setting NUMA Nodes per Socket configuration.  AMD CBS: Sets NUMA Nodes Per Socket (NPS) to co...

### CbsDfCmnMemIntlv
- **Python Name**: cbs_df_cmn_mem_intlv
- **Redfish Value**: Auto
- **Schema API**: CbsDfCmnMemIntlv
- **Description**: The default value is `platform-default`.  BIOS Token for setting AMD Memory Interleaving configuration.  AMD CBS: Controls AMD memory interleaving acr...

### CbsSevSnpSupport
- **Python Name**: cbs_sev_snp_support
- **Redfish Value**: Auto
- **Schema API**: CbsSevSnpSupport
- **Description**: The default value is `platform-default`.  BIOS Token for setting SEV-SNP Support configuration.  AMD CBS: Enables AMD Secure Encrypted Virtualization ...


## Exact Redfish Matches
These attributes exist in Redfish but have no schema definition.

### CPU005
- **Python Name**: cpu005
- **Redfish Value**: Enabled
- **Redfish Description**: Enable/disable CPU Virtualization
- **Note**: Consider adding to schema definition

### CbsCmnCpuL1BurstPrefetchMode
- **Python Name**: cbs_cmn_cpu_l1_burst_prefetch_mode
- **Redfish Value**: Auto
- **Redfish Description**: Option to Enable | Disable L1 Burst Prefetch Mode
- **Note**: Consider adding to schema definition

### CbsCmnMemBootTimePostPackageRepair
- **Python Name**: cbs_cmn_mem_boot_time_post_package_repair
- **Redfish Value**: Disable
- **Redfish Description**: Enable or Disable DRAM Boot Time Post Package Repair.  
- **Note**: Consider adding to schema definition

### CbsCmnMemCsInterleaveDdr
- **Python Name**: cbs_cmn_mem_cs_interleave_ddr
- **Redfish Value**: Auto
- **Redfish Description**: Interleave memory blocks across the DRAM chip selects for node 0.
- **Note**: Consider adding to schema definition

### CbsCmnMemCtrllerBankSwapModeDdr
- **Python Name**: cbs_cmn_mem_ctrller_bank_swap_mode_ddr
- **Redfish Value**: Auto
- **Redfish Description**: BankSwapMode value: 0=Disabled, 1=SwapCPU
- **Note**: Consider adding to schema definition

### CbsCmnMemDramRefreshRate
- **Python Name**: cbs_cmn_mem_dram_refresh_rate
- **Redfish Value**: 3.9 usec
- **Redfish Description**: DRAM refresh rate: 1.95us or 3.9us (default)
- **Note**: Consider adding to schema definition

### CbsCmnMemDramScrubTime
- **Python Name**: cbs_cmn_mem_dram_scrub_time
- **Redfish Value**: 24 hours
- **Redfish Description**: Provide a value that is the number of hours to scrub memory.
- **Note**: Consider adding to schema definition

### CbsCmnMemHealingBistEnableBitMaskDdr
- **Python Name**: cbs_cmn_mem_healing_bist_enable_bit_mask_ddr
- **Redfish Value**: Disabled
- **Redfish Description**: This item enables a full memory test. Please note that this is a memory content test and is separate and distinct from the MBIST test of Interface and...
- **Note**: Consider adding to schema definition

### CbsCmnMemRuntimePostPackageRepair
- **Python Name**: cbs_cmn_mem_runtime_post_package_repair
- **Redfish Value**: Disable
- **Redfish Description**: Enable or Disable DRAM Run Time Post Package Repair.  
- **Note**: Consider adding to schema definition

### CbsCmnPcieCAPLinkSpeed
- **Python Name**: cbs_cmn_pcie_cap_link_speed
- **Redfish Value**: Auto
- **Redfish Description**: Set all PCIe port speed capability
- **Note**: Consider adding to schema definition

### CbsCpuCcdCtrl
- **Python Name**: cbs_cpu_ccd_ctrl
- **Redfish Value**: Auto
- **Redfish Description**: Sets the number of active CCDs.  Once this option has been used to remove any CCDs, a POWER CYCLE is required in order for future selections to take e...
- **Note**: Consider adding to schema definition

### CbsDfCmn3LinkMaxXgmiSpeed
- **Python Name**: cbs_df_cmn3_link_max_xgmi_speed
- **Redfish Value**: 32Gbps
- **Redfish Description**: Specifies the max frequency used for XGMI PState in a 3-link topology.
- **Note**: Consider adding to schema definition

### IPMI103
- **Python Name**: ipmi103
- **Redfish Value**: Disabled
- **Redfish Description**: If enabled, starts a BIOS timer which can only be shut off by Management Software after the OS loads.  Helps determine that the OS successfully loaded...
- **Note**: Consider adding to schema definition

### IPMI104
- **Python Name**: ipmi104
- **Redfish Value**: 10
- **Redfish Description**: Enter the value Between 1 to 30 min for OS Boot Watchdog Timer Expiration. Not available if OS Boot Watchdog Timer is disabled.
- **Note**: Consider adding to schema definition

### IPMI105
- **Python Name**: ipmi105
- **Redfish Value**: Reset
- **Redfish Description**: Configure how the system should respond if the OS Boot Watchdog Timer expires. Not available if OS Boot Watchdog Timer is disabled.
- **Note**: Consider adding to schema definition

### NVLCK002
- **Python Name**: nvlck002
- **Redfish Value**: Enabled
- **Redfish Description**: Control the NVRAM Runtime Variable protection through System Admin Password
- **Note**: Consider adding to schema definition

### NWSK001
- **Python Name**: nwsk001
- **Redfish Value**: Disabled
- **Redfish Description**: Enable/Disable IPv4 PXE boot support. If disabled, IPv4 PXE boot support will not be available.
- **Note**: Consider adding to schema definition

### NWSK002
- **Python Name**: nwsk002
- **Redfish Value**: Disabled
- **Redfish Description**: Enable/Disable IPv6 PXE boot support. If disabled, IPv6 PXE boot support will not be available.
- **Note**: Consider adding to schema definition

### NWSK006
- **Python Name**: nwsk006
- **Redfish Value**: Disabled
- **Redfish Description**: Enable/Disable IPv4 HTTP boot support. If disabled, IPv4 HTTP boot support will not be available.
- **Note**: Consider adding to schema definition

### NWSK007
- **Python Name**: nwsk007
- **Redfish Value**: Disabled
- **Redfish Description**: Enable/Disable IPv6 HTTP boot support. If disabled, IPv6 HTTP boot support will not be available.
- **Note**: Consider adding to schema definition

### PCID001
- **Python Name**: pcid001
- **Redfish Value**: Enabled
- **Redfish Description**: Globally Enables or Disables 64bit capable Devices to be Decoded in Above 4G Address Space (Only if System Supports 64 bit PCI Decoding).
- **Note**: Consider adding to schema definition

### PCID002
- **Python Name**: pcid002
- **Redfish Value**: Enabled
- **Redfish Description**: If system has SR-IOV capable PCIe Devices, this option Enables or Disables Single Root IO Virtualization Support.
- **Note**: Consider adding to schema definition

### PCID003
- **Python Name**: pcid003
- **Redfish Value**: Disabled
- **Redfish Description**: Re-enable Bus Master Attribute disabled during Pci enumeration for PCI Bridges after SMM Locked 
- **Note**: Consider adding to schema definition

### TCG006
- **Python Name**: tcg006
- **Redfish Value**: None
- **Redfish Description**: Schedule an Operation for the Security Device. NOTE: Your Computer will reboot during restart in order to change State of Security Device.
- **Note**: Consider adding to schema definition

### TER002
- **Python Name**: ter002
- **Redfish Value**: Enabled
- **Redfish Description**: Console Redirection Enable or Disable.
- **Note**: Consider adding to schema definition

### TER0022
- **Python Name**: ter0022
- **Redfish Value**: 115200
- **Redfish Description**: Selects serial port transmission speed. The speed must be matched on the other side. Long or noisy lines may require lower speeds.
- **Note**: Consider adding to schema definition

### TER013
- **Python Name**: ter013
- **Redfish Value**: ANSI
- **Redfish Description**: Emulation: ANSI: Extended ASCII char set. VT100: ASCII char set. VT100Plus: Extends VT100 to support color, function keys, etc. VT-UTF8: Uses UTF8 enc...
- **Note**: Consider adding to schema definition

### TER05E
- **Python Name**: ter05_e
- **Redfish Value**: None
- **Redfish Description**: Flow control can prevent data loss from buffer overflow. When sending data, if the receiving buffers are full, a 'stop' signal can be sent to stop the...
- **Note**: Consider adding to schema definition


## Exact Schema Matches
These attributes have schema definitions but are not in Redfish dump.


## Possible Schema Matches
These may correspond to schema attributes (similarity score >= 2).

### CbsCmnCpuL1StreamHwPrefetcher
- **Template Name**: CbsCmnCpuL1StreamHwPrefetcher
- **Python Name**: cbs_cmn_cpu_l1_stream_hw_prefetcher
- **Likely Schema Match**: cbs_cmn_cpu_l1stream_hw_prefetcher
- **API Name**: CbsCmnCpuL1streamHwPrefetcher
- **Similarity Score**: 5
- **Description**: The default value is `platform-default`.  BIOS Token for setting L1 Stream HW Prefetcher configuration.  AMD CBS: Enables or disables the L1 stream ha...

### CbsCmnCpuL2StreamHwPrefetcher
- **Template Name**: CbsCmnCpuL2StreamHwPrefetcher
- **Python Name**: cbs_cmn_cpu_l2_stream_hw_prefetcher
- **Likely Schema Match**: cbs_cmn_cpu_l2stream_hw_prefetcher
- **API Name**: CbsCmnCpuL2streamHwPrefetcher
- **Similarity Score**: 5
- **Description**: The default value is `platform-default`.  BIOS Token for setting L2 Stream HW Prefetcher configuration.  AMD CBS: Enables or disables the L2 stream ha...

### CbsCmnMemTsmeEnableDdr
- **Template Name**: CbsCmnMemTsmeEnableDdr
- **Python Name**: cbs_cmn_mem_tsme_enable_ddr
- **Likely Schema Match**: smee
- **API Name**: Smee
- **Similarity Score**: 2
- **Description**: The default value is `platform-default`.  BIOS Token for setting SMEE configuration.  Enables AMD Secure Memory Encryption Extension for hardware-base...

### CbsDbgCpuLApicMode
- **Template Name**: CbsDbgCpuLApicMode
- **Python Name**: cbs_dbg_cpu_l_apic_mode
- **Likely Schema Match**: cbs_dbg_cpu_lapic_mode
- **API Name**: CbsDbgCpuLapicMode
- **Similarity Score**: 5
- **Description**: The default value is `platform-default`.  BIOS Token for setting Local APIC Mode configuration.  AMD CBS: Sets the local APIC mode (xAPIC or x2APIC) f...

### CbsDfCmnAcpiSratL3Numa
- **Template Name**: CbsDfCmnAcpiSratL3Numa
- **Python Name**: cbs_df_cmn_acpi_srat_l3_numa
- **Likely Schema Match**: cbs_df_cmn_acpi_srat_l3numa
- **API Name**: CbsDfCmnAcpiSratL3numa
- **Similarity Score**: 5
- **Description**: The default value is `platform-default`.  BIOS Token for setting ACPI SRAT L3 Cache As NUMA Domain configuration.  AMD CBS: Reports AMD L3 cache slice...


## No Match Found
These template attributes have no match in either Redfish or schema.

Total: 0 attributes