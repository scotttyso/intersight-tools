# BIOS Allowed Values Report

| Key | Schema Property | Display Name | Default Value | Redfish Allowed Values | Schema Allowed Values |
|---|---|---|---|---|---|
| CPU005 | svm_mode | SVM Mode | Enabled | Disabled, Enabled | platform-default, enabled, disabled |
| CbsCmnApbdis | cbs_cmn_apbdis | APBDIS | Auto | 0, 1, Auto | platform-default, 0, 1, Auto |
| CbsCmnCpuAvx512 | cbs_cmn_cpu_avx512 | AVX512 | Auto | Disabled, Enabled, Auto | platform-default, Auto, disabled, enabled |
| CbsCmnCpuCpb | cbs_cmn_cpu_cpb | Core Performance Boost | Auto | Disabled, Auto | platform-default, Auto, disabled |
| CbsCmnCpuGlobalCstateCtrl | cbs_cmn_cpu_global_cstate_ctrl | Global C-state Control | Disabled | Disabled, Enabled, Auto | platform-default, Auto, disabled, enabled |
| CbsCmnCpuL1BurstPrefetchMode | cbs_cmn_cpu_l1_burst_prefetch_mode | L1 Burst Prefetch Mode | Auto | Disable, Enable, Auto | platform-default, Auto, disable, enable |
| CbsCmnCpuL1StreamHwPrefetcher | cbs_cmn_cpu_l1stream_hw_prefetcher | L1 Stream HW Prefetcher | Auto | Disable, Enable, Auto | platform-default, Auto, disabled, enabled |
| CbsCmnCpuL2StreamHwPrefetcher | cbs_cmn_cpu_l2stream_hw_prefetcher | L2 Stream HW Prefetcher | Auto | Disable, Enable, Auto | platform-default, Auto, disabled, enabled |
| CbsCmnCpuSmee | cbs_cmn_cpu_smee | SMEE | Auto | Disable, Enable, Auto | platform-default, Auto, disabled, enabled |
| CbsCmnCpuStreamingStoresCtrl | cbs_cmn_cpu_streaming_stores_ctrl | Streaming Stores Control | Auto | Disabled, Enabled, Auto | platform-default, Auto, disabled, enabled |
| CbsCmnGnbNbIOMMU | cbs_cmn_gnb_nb_iommu | IOMMU | Auto | Disabled, Enabled, Auto | platform-default, Auto, disabled, enabled |
| CbsCmnMemBootTimePostPackageRepair | post_package_repair | DRAM Boot Time Post Package Repair | Disable | Enable, Disable | platform-default, Disabled, Hard PPR |
| CbsCmnMemCsInterleaveDdr | cbs_cmn_mem_cs_interleave_ddr | Chipselect Interleaving | Auto | Disabled, Auto | platform-default, Auto, Disabled |
| CbsCmnMemCtrllerBankSwapModeDdr | cbs_cmn_mem_ctrller_bank_swap_mode_ddr | BankSwapMode | Auto | Auto, Disabled, Swap CPU | platform-default, Auto, Disabled, Swap CPU |
| CbsCmnMemCtrllerPwrDnEnDdr | cbs_cmn_mem_ctrller_pwr_dn_en_ddr | Power Down Enable | Auto | Disabled, Enabled, Auto | platform-default, Auto, disabled, enabled |
| CbsCmnMemDramRefreshRate | cbs_cmn_mem_dram_refresh_rate | DRAM Refresh Rate | 3.9 usec | 3.9 usec, 1.95 usec | platform-default, 1.95 usec, 3.9 usec |
| CbsCmnMemDramScrubTime | cbs_df_cmn_dram_scrub_time | DRAM Scrub Time | 24 hours | Disabled, 1 hour, 4 hours, 6 hours, 8 hours, 12 hours, 16 hours, 24 hours, 48 hours | platform-default, 1 hour, 4 hours, 6 hours, 8 hours, 12 hours, 16 hours, 24 hours, 48 hours, Auto, Disabled |
| CbsCmnMemHealingBistEnableBitMaskDdr | cbs_cmn_mem_healing_bist_enable_bit_mask_ddr | DDR Healing BIST | Disabled | Disabled, PMU Mem BIST, Self-Healing Mem BIST, PMU and Self-Healing Mem BIST | platform-default, PMU Mem BIST, PMU and Self-Healing Mem BIST, Self-Healing Mem BIST |
| CbsCmnMemRuntimePostPackageRepair | runtime_post_package_repair | DRAM Runtime Post Package Repair | Disable | Enable, Disable | platform-default, enabled, disabled |
| CbsCmnMemTsmeEnableDdr | tsme | TSME | Auto | Auto, Enabled, Disabled | platform-default, Auto, disabled, enabled |
| CbsCmnPcieCAPLinkSpeed | cbs_cmn_pcie_cap_link_speed | PCIE Link Speed Capability | Auto | Maximum speed, Gen1, Gen2, GEN3, GEN4, GEN5, Auto | platform-default, Gen1, Gen2, GEN3, GEN4, GEN5, Maximum Speed |
| CbsCpuCcdCtrl | cbs_cpu_ccd_ctrl_ssp | CCD Control | Auto | Auto, 2 CCDs, 4 CCDs, 6 CCDs, 8 CCDs, 10 CCDs, 12 CCDs, 14 CCDs | platform-default, 2 CCDs, 3 CCDs, 4 CCDs, 6 CCDs, 8 CCDs, 10 CCDs, 12 CCDs, 14 CCDs, Auto |
| CbsCpuSmtCtrl | cbs_cpu_smt_ctrl | SMT Control | Auto | Disable, Enable, Auto | platform-default, Auto, disabled, enabled |
| CbsDbgCpuLApicMode | cbs_dbg_cpu_lapic_mode | Local APIC Mode | Auto | xAPIC, x2APIC, Auto | platform-default, Auto, Compatibility, X2APIC, XAPIC |
| CbsDfCmn3LinkMaxXgmiSpeed | cbs_df_cmn4link_max_xgmi_speed | 3-link xGMI max speed | Auto | 20Gbps, 25Gbps, 32Gbps, Auto | platform-default, 20Gbps, 25Gbps, 32Gbps, Auto |
| CbsDfCmnAcpiSratL3Numa | cbs_df_cmn_acpi_srat_l3numa | ACPI SRAT L3 Cache As NUMA Domain | Auto | Disabled, Enabled, Auto | platform-default, Auto, disabled, enabled |
| CbsDfCmnDramNps | cbs_df_cmn_dram_nps | NUMA nodes per socket | Auto | NPS0, NPS1, NPS2, NPS4, Auto | platform-default, Auto, NPS0, NPS1, NPS2, NPS4 |
| CbsDfCmnMemIntlv | cbs_df_cmn_mem_intlv_control | Memory interleaving | Auto | Disabled, Enabled, Auto | platform-default, Auto, disabled, enabled |
| CbsSevSnpSupport | cbs_sev_snp_support | SEV-SNP Support | Auto | Disable, Enable, Auto | platform-default, Auto, disabled, enabled |
| IPMI103 | os_boot_watchdog_timer | OS Watchdog Timer | Disabled | Enabled, Disabled | platform-default, enabled, disabled |
| IPMI104 | os_boot_watchdog_timer_timeout | OS Wtd Timer Timeout | 10 | range[1,30] | platform-default, 5-minutes, 10-minutes, 15-minutes, 20-minutes |
| IPMI105 | os_boot_watchdog_timer_policy | OS Wtd Timer Policy | Reset | Do Nothing, Reset, Power Down, Power Cycle | platform-default, do-nothing, power-off, reset |
| NVLCK002 | pop_support | Password protection of Runtime Variables | Enabled | Enabled, Disabled | platform-default, enabled, disabled |
| NWSK001 | ipv4pxe | IPv4 PXE Support | Enabled | Disabled, Enabled | platform-default, enabled, disabled |
| NWSK002 | ipv6pxe | IPv6 PXE Support | Disabled | Disabled, Enabled | platform-default, enabled, disabled |
| NWSK006 | ipv4http | IPv4 HTTP Support | Enabled | Disabled, Enabled | platform-default, enabled, disabled |
| NWSK007 | ipv6http | IPv6 HTTP Support | Disabled | Disabled, Enabled | platform-default, enabled, disabled |
| PCID002 | sr_iov | SR-IOV Support | Enabled | Disabled, Enabled | platform-default, enabled, disabled |
| PCID003 | bme_dma_mitigation | BME DMA Mitigation | Disabled | Disabled, Enabled | platform-default, enabled, disabled |
| TCG006 | tpm_pending_operation | Pending operation | None | None, TPM Clear | platform-default, None, TpmClear |
| TER002 | console_redirection | Console Redirection | Enabled | Disabled, Enabled | platform-default, com-0, com-1, disabled, enabled, serial-port-a |
| TER0022 | baud_rate | Bits per second | 115200 | 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600 | platform-default, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600 |
| TER013 | terminal_type | Terminal Type | ANSI | VT100, VT100Plus, VT-UTF8, ANSI | platform-default, pc-ansi, vt100, vt100-plus, vt-utf8 |
| TER05E |  | Flow Control | None | None, Hardware RTS/CTS |  |
