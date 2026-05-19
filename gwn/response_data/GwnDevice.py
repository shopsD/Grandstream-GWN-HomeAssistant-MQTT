import datetime as dt
from dataclasses import dataclass

@dataclass(slots=True)
class GwnDevice:
    status: bool
    apType: str
    mac: str
    name: str
    ip: str
    last_boot: dt.datetime
    usage_bytes: int
    upload_bytes: int
    download_bytes: int
    clients: int
    versionFirmware: str 
    networkId: str
    ipv6: str

    # firmware info
    newFirmware: str 

    # detailed info port
    wireless: bool
    vlanCount: int
    ssidNumber: int # supported SSID count
    online: bool
    model: str
    deviceType: str

    # detailed info client
    channel_5: int
    channel_2_4: int
    channel_6: int
    partNumber: str
    bootVersion: str
    network: str
    temperature_c: int
    usedMemory_bytes: int
    channelload_2g4_percent: int
    channelload_6g_percent: int
    cpuUsage_percent: float
    channelload_5g_percent: int

    # channel info
    ap_2g4_channel: int
    ap_5g_channel: int
    ap_6g_channel: int

    # parsed channel info
    channel_lists_2g4: dict[int, str]
    channel_lists_5g: dict[int, str]
    channel_lists_6g: dict[int, str]
