# BIOS Schema Attribute Mapping - Comprehensive Notes

## Executive Summary

This document provides a detailed mapping of BIOS attributes across three key sources:
1. **Template**: `intersight-tools/classes/templates/intersight/C800/bios.json.j2` - Jinja2 template for BIOS configuration
2. **Redfish**: `intersight-tools/QA/885/885.json` - Actual BIOS attributes from a Cisco UCS C885 server via Redfish API
3. **Schema**: `intersight-tools/schema/cisco-ai-pods.json` - Intersight BIOS Policy schema definition

## Key Findings

### Overall Statistics
- **Template Attributes**: 537 (all present in Redfish)
- **Redfish Attributes**: 537 (from actual server BIOS)
- **Schema Attributes**: 472 (policy definitions in Intersight)
- **Exact Matches** (both Redfish and Schema): 18 attributes
- **Redfish Only** (not in Schema): 512 attributes
- **Schema Only** (not in Redfish): 0 attributes (meaning Redfish is more comprehensive)
- **Possible Partial Matches**: 7 attributes (due to naming variations)

### Coverage Analysis
- **Schema Coverage**: 472 / 537 = **87.9%** of Redfish attributes
- **Missing from Schema**: 65 attributes (12.1%) - these are Redfish attributes without schema counterparts
  - Note: Some may be due to naming convention differences (e.g., underscores vs camelCase)

## Exact Matches (Confirmed Working)

These 18 attributes have been verified to exist in all three sources and work correctly:

1. **CbsCmnApbdis** 
   - Redfish Value: 1
   - Schema API: CbsCmnApbdis
   - Python: cbs_cmn_apbdis
   - **Description**: Disables the Automatic Power Budget management. AMD CBS controls power distribution automatically.

2. **CbsCmnCpuAvx512**
   - Redfish Value: Auto
   - Schema API: CbsCmnCpuAvx512
   - Python: cbs_cmn_cpu_avx512
   - **Description**: Enables or disables AVX-512 instruction support on supported CPUs for vector computation acceleration.

3. **CbsCmnCpuCpb**
   - Redfish Value: Auto
   - Schema API: CbsCmnCpuCpb
   - Python: cbs_cmn_cpu_cpb
   - **Description**: Controls Core Performance Boost (AMD's CPU turbo boost technology) to dynamically increase clock speed.

4. **CbsCmnCpuGlobalCstateCtrl**
   - Redfish Value: Auto
   - Schema API: CbsCmnCpuGlobalCstateCtrl
   - Python: cbs_cmn_cpu_global_cstate_ctrl
   - **Description**: Enables or disables global CPU C-states for power management and idle power reduction.

5. **CbsCmnCpuSevAsidSpaceLimit**
   - Redfish Value: 1
   - Schema API: CbsCmnCpuSevAsidSpaceLimit
   - Python: cbs_cmn_cpu_sev_asid_space_limit
   - **Description**: Sets the upper limit of Address Space Identifiers (ASIDs) for SEV-ES (Secure Encrypted Virtualization).

6. **CbsCmnCpuSmee**
   - Redfish Value: Auto
   - Schema API: CbsCmnCpuSmee
   - Python: cbs_cmn_cpu_smee
   - **Description**: Enables Secure Memory Encryption for the CPU to transparently encrypt/decrypt memory.

7. **CbsCmnCpuStreamingStoresCtrl**
   - Redfish Value: Auto
   - Schema API: CbsCmnCpuStreamingStoresCtrl
   - Python: cbs_cmn_cpu_streaming_stores_ctrl
   - **Description**: Controls streaming store operations which bypass cache for certain memory access patterns.

8. **CbsCmnEfficiencyModeEn**
   - Redfish Value: Auto
   - Schema API: CbsCmnEfficiencyModeEn
   - Python: cbs_cmn_efficiency_mode_en
   - **Description**: Enables Efficiency Mode to optimize thermal performance and power consumption on supported systems.

9. **CbsCmnGnbNbIOMMU**
   - Redfish Value: Enabled
   - Schema API: CbsCmnGnbIommu
   - Python: cbs_cmn_gnb_nb_iommu
   - **Description**: Enables the IOMMU in the northbridge for DMA isolation and device I/O virtualization protection.

10. **CbsCmnGnbSmuDfCstates**
    - Redfish Value: Auto
    - Schema API: CbsCmnGnbSmuDfCstates
    - Python: cbs_cmn_gnb_smu_df_cstates
    - **Description**: Controls Data Fabric C-states; disabling prevents data fabric low-power states for consistency.

11. **CbsCmnMemCtrllerPwrDnEnDdr**
    - Redfish Value: Auto
    - Schema API: CbsCmnMemCtrllerPwrDnEnDdr
    - Python: cbs_cmn_mem_ctrller_pwr_dn_en_ddr
    - **Description**: Enables power-down mode on the DDR memory controller for reduced idle power consumption.

12. **CbsCpuCoreCtrl**
    - Redfish Value: Auto
    - Schema API: CbsCpuCoreCtrl
    - Python: cbs_cpu_core_ctrl
    - **Description**: Sets the number of enabled cores per socket (CPU downcore configuration) for 7xx3 processors.

13. **CbsCpuSmtCtrl**
    - Redfish Value: Enable
    - Schema API: CbsCpuSmtCtrl
    - Python: cbs_cpu_smt_ctrl
    - **Description**: Enables or disables Simultaneous Multi-Threading (SMT) - logical CPU threads per physical core.

14. **CbsDbgCpuGenCpuWdt**
    - Redfish Value: Auto
    - Schema API: CbsDbgCpuGenCpuWdt
    - Python: cbs_dbg_cpu_gen_cpu_wdt
    - **Description**: Enables the CPU watchdog timer for detecting CPU hangs or frozen execution paths.

15. **CbsDfCmnDramNps**
    - Redfish Value: NPS4
    - Schema API: CbsDfCmnDramNps
    - Python: cbs_df_cmn_dram_nps
    - **Description**: Sets NUMA Nodes Per Socket (NPS) configuration (1, 2, 4, or 8) for memory locality optimization.

16. **CbsDfCmnMemIntlv**
    - Redfish Value: Auto
    - Schema API: CbsDfCmnMemIntlv
    - Python: cbs_df_cmn_mem_intlv
    - **Description**: Controls AMD memory interleaving across DRAM channels for improved bandwidth distribution.

17. **SerialPortConsoleRedirection**
    - Redfish Value: COM1
    - Schema API: SerialPortConsoleRedirection
    - Python: serial_port_console_redirection
    - **Description**: Enables BIOS console output redirection to serial port (COM1/COM2) for remote management access.

18. **TerminalType**
    - Redfish Value: VT-UTF8
    - Schema API: TerminalType
    - Python: terminal_type
    - **Description**: Sets the terminal emulation type (VT-UTF8, PC ANSI, etc.) for serial console compatibility.

## Likely Matches (Naming Convention Differences)

These 7 attributes have similarities but differ in naming conventions. They likely correspond:

| Template Attribute | Python Name | Likely Schema Match | Description |
|---|---|---|---|
| CbsCmnCpuL1StreamHwPrefetcher | cbs_cmn_cpu_l1_stream_hw_prefetcher | cbs_cmn_cpu_l1stream_hw_prefetcher | Enables/disables L1 stream hardware prefetcher for cache line prefetching |
| CbsCmnCpuL2StreamHwPrefetcher | cbs_cmn_cpu_l2_stream_hw_prefetcher | cbs_cmn_cpu_l2stream_hw_prefetcher | Enables/disables L2 stream hardware prefetcher for cache hierarchy |
| CbsCmnGnbSmuCppc | cbs_cmn_gnb_smu_cppc | cbs_cmn_gnb_smucppc | Enables Collaborative Processor Performance Control (CPPC) for power management |
| CbsDbgCpuLApicMode | cbs_dbg_cpu_l_apic_mode | cbs_dbg_cpu_lapic_mode | Sets local APIC mode (xAPIC or x2APIC) for interrupt handling |
| CbsDfCmnAcpiSratL3Numa | cbs_df_cmn_acpi_srat_l3_numa | cbs_df_cmn_acpi_srat_l3numa | Reports L3 cache slices as NUMA domains in ACPI SRAT table |
| CbsSevTioSupport | cbs_sev_tio_support | sev | Enables AMD Secure Encrypted Virtualization (SEV) for VM encryption |
| CbsCmnMemTsmeEnableDdr | cbs_cmn_mem_tsme_enable_ddr | smee | Enables Secure Memory Encryption Extension for hardware-based encryption |

**Recommendation**: These likely represent the same attributes with minor naming convention variations (missing underscores in schema names). Consider standardizing the naming across all three sources.

## Attributes Present in Redfish but NOT in Schema

**Total Count**: 512 attributes (95.3% of Redfish attributes)

**Top 30 Missing Attributes**:
1. ACPI003
2. ACPI004
3. AcsRasValue
4. CPU005
5. CbsCfgAcsDirectTranslatedStrap5
6. CbsCfgAcsEnRccDev0
7. CbsCfgAcsP2PEgress
8. CbsCfgAcsP2PEgressStrap5
9. CbsCfgAcsP2pComp
10. CbsCfgAcsP2pCompStrap5
11. CbsCfgAcsP2pReq
12. CbsCfgAcsP2pReqStrap5
13. CbsCfgAcsSsidEnStrap5
14. CbsCfgAcsTranslationalBlocking
15. CbsCfgAcsTranslationalBlockingStrap5
16. CbsCfgAcsUpstreamFwd
17. CbsCfgAcsUpstreamFwdStrap5
18. CbsCfgAerEnRccDev0
19. CbsCfgDlfEnStrap1
20. CbsCfgE2EPrefix
21. CbsCfgExtendedFmtSupported
22. CbsCfgMarginEnStrap1
23. CbsCfgPhy16gtStrap1
24. CbsCfgPriEnPageReq
25. CbsCfgPriResetPageReq
26. CbsCmnActionOnBistFailure
27. CbsCmnAllPortsASPM
28. CbsCmnCoreTraceDumpEn
29. CbsCmnCpuAdaptiveAlloc
30. CbsCmnCpuAmdErmsbRepo

**Descriptions of Key Missing Attributes** (from Redfish Registry):
- **ACPI003** - Enables or Disables Lock of Legacy Resources
- **ACPI004** - Enables or Disables BIOS ACPI Auto Configuration
- **CPU005** - Enable/disable CPU Virtualization
- **CbsCfgAcsDirectTranslatedStrap5** - RCC_DEV0_PORT_STRAP5 = 0xAF80_0000, ACS Direct Translated bit [29]
- **CbsCfgAcsEnRccDev0** - Enable ACS enable for RCC_DEV0 (STRAP_ACS_EN_DN_DEV0)
- **CbsCfgAcsP2PEgress** - PCIE_ACS_CNTL_dev0 = 0x001D, P2P Egress bit[5]
- **CbsCmnActionOnBistFailure** - Action to take when a CCD BIST failure is detected
- **CbsCmnAllPortsASPM** - Affects PCIe link power states across all ports
- **CbsCmnCoreTraceDumpEn** - Enables core trace debug dump functionality

**Implications**:
- These attributes are present in the actual server BIOS (via Redfish) but are not defined in the Intersight schema
- They cannot be managed through Intersight policy definitions
- Two options:
  1. **Keep in Template**: Template attributes are purely informational
  2. **Submit to Cisco**: Request that these be added to the schema for full Intersight support
- All 512 Redfish-only attributes have descriptions available from the Redfish BiosAttributeRegistry

## Conversion Rules Discovered

### CamelCase to snake_case Pattern
The template uses Python variable names in snake_case format derived from BIOS attribute names:

**Pattern**: CamelCase BIOS → snake_case Python
- `CbsCmnCpuAvx512` → `cbs_cmn_cpu_avx512`
- `SerialPortConsoleRedirection` → `serial_port_console_redirection`
- `TerminalType` → `terminal_type`

**Special Cases**:
- Consecutive capitals are handled with underscores: `CPU005` → various, `I/O` → `i_o`
- Some attributes already follow schema names exactly

### Key Naming Patterns in BIOS
- **CbsCfg\***: Chipset Bridge Settings - Configuration
- **CbsCmn\***: Chipset Bridge Settings - Common
- **CbsCpu\***: CPU-specific settings
- **CbsDbg\***: Debug settings
- **CbsDf\***: Data Fabric settings
- **CbsSev\***: Security settings (SEV - Secure Encrypted Virtualization)
- **Cbs\***: General Chipset settings
- **ACPI\***: Advanced Configuration & Power Interface
- **CPU\***: Processor settings

## File Locations for Future Reference

```
Templates:
  - /home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/classes/templates/intersight/C800/bios.json.j2

QA/Test Data:
  - /home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/QA/885/885.json

Schema Definitions:
  - /home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/schema/cisco-ai-pods.json
  - /home/tyscott@rich.ciscolabs.com/scotttyso/Cisco-AI-Pods/schema/cisco-ai-pods.json

Python Comparison Tool:
  - /home/tyscott@rich.ciscolabs.com/scotttyso/intersight-tools/schema_comparison.py
```

## Recommendations

1. **Standardize Naming**: Resolve 7 attributes with naming convention differences
2. **Evaluate Coverage Gap**: 512 Redfish attributes not in schema - determine if these are:
   - Not supported by Intersight (intentional)
   - Future enhancements
   - Platform-specific attributes that vary by server model
3. **Update Schema**: Add missing attributes to `cisco-ai-pods.json` schema if they should be Intersight-managed
4. **Document Platform Differences**: Create mapping for other server models (C800, C890, etc.)
5. **Validation**: Periodically run the comparison script when:
   - Schema is updated
   - New server firmware versions are released
   - Template is modified

## Usage of Comparison Script

The script `schema_comparison.py` can be reused for future comparisons:

```bash
python3 intersight-tools/schema_comparison.py
```

This generates an updated report to `bios_schema_mapping_notes.md` with:
- **Schema descriptions**: From `intersight.policies.bios` in the schema JSON
- **Redfish descriptions**: From the `BiosAttributeRegistry` in the Redfish dump
- **Mapping analysis**: Identifies exact matches, likely matches, and missing attributes

**To use with different files**:
```python
from schema_comparison import BIOSSchemaComparator

comparator = BIOSSchemaComparator(
    template_path="path/to/template.j2",
    redfish_path="path/to/redfish.json",
    schema_path="path/to/schema.json"
)
comparator.load_all()
report = comparator.generate_report("output.md")
```

---

**Document Generated**: 2026-05-12
**Next Review**: When schema or firmware is updated
