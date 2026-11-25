"""Системное извлечение диска через Windows PnP."""
from __future__ import annotations

import ctypes
import time
import uuid
from ctypes import wintypes
from pathlib import Path

_DISK_INTERFACE = uuid.UUID("53f56307-b6bf-11d0-94f2-00a0c91efb8b")
_IOCTL_STORAGE_GET_DEVICE_NUMBER = 0x002D1080
_ERROR_NO_MORE_ITEMS = 259
_INVALID_HANDLE = ctypes.c_void_p(-1).value


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


class _InterfaceData(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", _Guid),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class _DeviceInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", _Guid),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class _StorageDeviceNumber(ctypes.Structure):
    _fields_ = [
        ("DeviceType", wintypes.DWORD),
        ("DeviceNumber", wintypes.DWORD),
        ("PartitionNumber", wintypes.DWORD),
    ]


def _load_apis():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
    cfgmgr32 = ctypes.WinDLL("cfgmgr32", use_last_error=True)

    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel32.DeviceIoControl.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
    setupapi.SetupDiGetClassDevsW.argtypes = [
        ctypes.POINTER(_Guid), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD,
    ]
    setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_Guid), wintypes.DWORD,
        ctypes.POINTER(_InterfaceData),
    ]
    setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(_InterfaceData), wintypes.LPVOID,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(_DeviceInfo),
    ]
    setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
    setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

    cfgmgr32.CM_Request_Device_EjectW.argtypes = [
        wintypes.DWORD, ctypes.POINTER(ctypes.c_int), wintypes.LPWSTR,
        wintypes.ULONG, wintypes.ULONG,
    ]
    cfgmgr32.CM_Request_Device_EjectW.restype = wintypes.DWORD
    cfgmgr32.CM_Get_Parent.argtypes = [
        ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, wintypes.ULONG,
    ]
    cfgmgr32.CM_Get_Parent.restype = wintypes.DWORD
    cfgmgr32.CM_Get_Device_IDW.argtypes = [
        wintypes.DWORD, wintypes.LPWSTR, wintypes.ULONG, wintypes.ULONG,
    ]
    cfgmgr32.CM_Get_Device_IDW.restype = wintypes.DWORD

    return kernel32, setupapi, cfgmgr32


def _storage_number(kernel32, path: str) -> int | None:
    handle = kernel32.CreateFileW(path, 0, 0x7, None, 3, 0, None)
    if handle == _INVALID_HANDLE:
        return None

    try:
        device = _StorageDeviceNumber()
        returned = wintypes.DWORD()
        ok = kernel32.DeviceIoControl(
            handle,
            _IOCTL_STORAGE_GET_DEVICE_NUMBER,
            None,
            0,
            ctypes.byref(device),
            ctypes.sizeof(device),
            ctypes.byref(returned),
            None,
        )
        return device.DeviceNumber if ok else None
    finally:
        kernel32.CloseHandle(handle)


def _request_eject(cfgmgr32, devinst: int) -> str | None:
    veto_type = ctypes.c_int()
    veto_name = ctypes.create_unicode_buffer(256)
    result = cfgmgr32.CM_Request_Device_EjectW(
        devinst, ctypes.byref(veto_type), veto_name, len(veto_name), 0
    )
    if not result:
        return None

    failure = (
        f"код {result}, тип отказа {veto_type.value}"
        + (f", устройство {veto_name.value}" if veto_name.value else "")
    )

    parent = wintypes.DWORD()
    if cfgmgr32.CM_Get_Parent(ctypes.byref(parent), devinst, 0) == 0:
        parent_id = ctypes.create_unicode_buffer(512)
        got_id = cfgmgr32.CM_Get_Device_IDW(
            parent.value, parent_id, len(parent_id), 0
        ) == 0
        if got_id and parent_id.value.upper().startswith("USB\\VID_"):
            parent_veto_type = ctypes.c_int()
            parent_veto_name = ctypes.create_unicode_buffer(256)
            parent_result = cfgmgr32.CM_Request_Device_EjectW(
                parent.value,
                ctypes.byref(parent_veto_type),
                parent_veto_name,
                len(parent_veto_name),
                0,
            )
            if not parent_result:
                return None
            failure += (
                f"; отказ USB-устройства: код {parent_result}, "
                f"тип {parent_veto_type.value}"
                + (f", {parent_veto_name.value}" if parent_veto_name.value else "")
            )

    return f"Windows отказала в системном извлечении: {failure}."


def _eject_disk(setupapi, cfgmgr32, kernel32, disk_number: int, drive: str) -> str | None:
    disk_guid = _Guid.from_buffer_copy(_DISK_INTERFACE.bytes_le)
    info_set = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(disk_guid), None, None, 0x2 | 0x10
    )
    if info_set == _INVALID_HANDLE:
        error = ctypes.get_last_error()
        return f"Windows не смогла перечислить дисковые устройства (ошибка {error})."

    try:
        index = 0
        while True:
            interface = _InterfaceData()
            interface.cbSize = ctypes.sizeof(interface)
            found = setupapi.SetupDiEnumDeviceInterfaces(
                info_set, None, ctypes.byref(disk_guid), index, ctypes.byref(interface)
            )
            if not found:
                error = ctypes.get_last_error()
                if error == _ERROR_NO_MORE_ITEMS:
                    return f"Не удалось найти физический диск для тома {drive}."
                return f"Ошибка поиска дискового устройства Windows ({error})."
            index += 1

            required = wintypes.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                info_set, ctypes.byref(interface), None, 0, ctypes.byref(required), None
            )
            if not required.value:
                continue

            detail = ctypes.create_string_buffer(required.value)
            detail_size = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            ctypes.cast(detail, ctypes.POINTER(wintypes.DWORD))[0] = detail_size
            device_info = _DeviceInfo()
            device_info.cbSize = ctypes.sizeof(device_info)
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                info_set,
                ctypes.byref(interface),
                detail,
                required.value,
                ctypes.byref(required),
                ctypes.byref(device_info),
            ):
                continue

            device_path = ctypes.wstring_at(ctypes.addressof(detail) + 4)
            if _storage_number(kernel32, device_path) != disk_number:
                continue

            error = _request_eject(cfgmgr32, device_info.DevInst)
            if error:
                return error
            return _wait_for_volume(drive)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(info_set)


def _wait_for_volume(drive: str) -> str | None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not Path(drive + "\\").exists():
            return None
        time.sleep(0.25)
    return f"Windows приняла запрос, но том {drive} не исчез за 15 секунд."


def eject_volume(root: str | Path) -> str | None:
    """Return an error message if Windows cannot safely eject the volume."""
    drive = str(root)[:2]
    kernel32, setupapi, cfgmgr32 = _load_apis()
    disk_number = _storage_number(kernel32, "\\\\.\\" + drive)
    if disk_number is None:
        return f"Не удалось определить физический диск для {drive}."
    return _eject_disk(setupapi, cfgmgr32, kernel32, disk_number, drive)
