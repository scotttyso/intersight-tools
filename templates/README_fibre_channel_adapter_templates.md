# Fibre Channel Adapter Policy Templates Reference

Each template lists the FC adapter settings it configures.
Settings not listed are left at policy defaults.

---

## FCNVMeInitiator

_Recommended adapter settings for FC NVMe Initiator._

| Setting | Value | Description |
|---|---|---|
| `IoThrottleCount` | `256` | Maximum pending I/O operations on the virtual interface at one time. |
| `error_recovery.port_down_io_retry` | `30` | Number of I/O retries before marking a port unavailable. |
| `error_recovery.port_down_timeout` | `30000` | Milliseconds a remote FC port must be offline before marking unavailable. |

---

## FCNVMeTarget

_Recommended adapter settings for FC NVMe Target._

| Setting | Value | Description |
|---|---|---|
| `IoThrottleCount` | `256` | Maximum pending I/O operations on the virtual interface at one time. |
| `error_recovery.port_down_io_retry` | `30` | Number of I/O retries before marking a port unavailable. |
| `error_recovery.port_down_timeout` | `30000` | Milliseconds a remote FC port must be offline before marking unavailable. |

---

## Initiator

_Recommended adapter settings for SCSI Initiator._

| Setting | Value | Description |
|---|---|---|
| `IoThrottleCount` | `256` | Maximum pending I/O operations on the virtual interface at one time. |
| `error_recovery.port_down_io_retry` | `30` | Number of I/O retries before marking a port unavailable. |
| `error_recovery.port_down_timeout` | `10000` | Milliseconds a remote FC port must be offline before marking unavailable. |

---

## Linux

_Recommended adapter settings for Linux._

| Setting | Value | Description |
|---|---|---|
| `IoThrottleCount` | `256` | Maximum pending I/O operations on the virtual interface at one time. |
| `error_recovery.port_down_io_retry` | `30` | Number of I/O retries before marking a port unavailable. |
| `error_recovery.port_down_timeout` | `30000` | Milliseconds a remote FC port must be offline before marking unavailable. |

---

## Solaris

_Recommended adapter settings for Solaris._

| Setting | Value | Description |
|---|---|---|
| `IoThrottleCount` | `256` | Maximum pending I/O operations on the virtual interface at one time. |
| `error_recovery.port_down_io_retry` | `30` | Number of I/O retries before marking a port unavailable. |
| `error_recovery.port_down_timeout` | `30000` | Milliseconds a remote FC port must be offline before marking unavailable. |
| `flogi.retries` | `8` | Number of fabric login retry attempts after first failure. |
| `flogi.timeout` | `20000` | Milliseconds to wait before retrying fabric login. |

---

## Target

_Recommended adapter settings for Target._

| Setting | Value | Description |
|---|---|---|
| `IoThrottleCount` | `256` | Maximum pending I/O operations on the virtual interface at one time. |
| `error_recovery.port_down_io_retry` | `30` | Number of I/O retries before marking a port unavailable. |
| `error_recovery.port_down_timeout` | `30000` | Milliseconds a remote FC port must be offline before marking unavailable. |

---

## VMware

_Recommended adapter settings for VMware._

| Setting | Value | Description |
|---|---|---|
| `IoThrottleCount` | `256` | Maximum pending I/O operations on the virtual interface at one time. |
| `error_recovery.port_down_io_retry` | `30` | Number of I/O retries before marking a port unavailable. |
| `error_recovery.port_down_timeout` | `10000` | Milliseconds a remote FC port must be offline before marking unavailable. |

---

## Windows

_Recommended adapter settings for Windows._

| Setting | Value | Description |
|---|---|---|
| `IoThrottleCount` | `256` | Maximum pending I/O operations on the virtual interface at one time. |
| `error_recovery.port_down_io_retry` | `30` | Number of I/O retries before marking a port unavailable. |
| `error_recovery.port_down_timeout` | `30000` | Milliseconds a remote FC port must be offline before marking unavailable. |

---

## WindowsBoot

_Recommended adapter settings for Windows Boot._

| Setting | Value | Description |
|---|---|---|
| `IoThrottleCount` | `256` | Maximum pending I/O operations on the virtual interface at one time. |
| `error_recovery.port_down_io_retry` | `30` | Number of I/O retries before marking a port unavailable. |
| `error_recovery.port_down_timeout` | `5000` | Milliseconds a remote FC port must be offline before marking unavailable. |
| `plogi.retries` | `8` | Number of port login retry attempts after first failure. |
| `plogi.timeout` | `4000` | Milliseconds to wait before retrying port login. |

