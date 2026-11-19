"""Klip çıkarma kilidi: panelden başlatılan iş ile zamanlanmış günlük betik AYNI ANDA çalışmasın.

Kilit, çalışma dizininde `klip-cikar.kilit` dosyasıdır (JSON: pid, sahip, zaman). Dosya `O_EXCL` ile yaratılır.
Sahip süreç ölmüşse (PID yok) ya da dosya çok eskiyse (BAYAT_SN) kilit bayat sayılır ve alınır.
Windows'ta `os.kill(pid, 0)` süreci ÖLDÜRÜR; canlılık ctypes ile (OpenProcess + GetExitCodeProcess) ölçülür."""
from __future__ import annotations

import json
import os
import pathlib
import time

KILIT_ADI = "klip-cikar.kilit"
BAYAT_SN = 8 * 3600     # PID okunamazsa en çok bu kadar eski kilit geçerli sayılır


class KilitDolu(Exception):
    """Kilit başka bir süreçte; `sahip` kimde olduğunu söyler."""

    def __init__(self, sahip: str):
        super().__init__(sahip)
        self.sahip = sahip


def pid_canli(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        k.OpenProcess.restype = ctypes.c_void_p
        h = k.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            kod = ctypes.c_ulong()
            if not k.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(kod)):
                return True
            return kod.value == 259                    # STILL_ACTIVE
        finally:
            k.CloseHandle(ctypes.c_void_p(h))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _oku(yol: pathlib.Path) -> dict:
    try:
        v = json.loads(yol.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _bayat_mi(yol: pathlib.Path, bayat_sn: float) -> bool:
    try:
        yas = time.time() - yol.stat().st_mtime
    except OSError:
        return True
    v = _oku(yol)
    pid = v.get("pid")
    if isinstance(pid, int):
        return not pid_canli(pid)
    return yas > bayat_sn


class Kilit:
    """`with Kilit(dizin, "panel") as k:` ya da `k.al()` / `k.birak()`. Dolu ise KilitDolu."""

    def __init__(self, dizin: pathlib.Path, sahip: str, bayat_sn: float = BAYAT_SN):
        self.dizin = pathlib.Path(dizin)
        self.yol = self.dizin / KILIT_ADI
        self.sahip = sahip
        self.bayat_sn = bayat_sn
        self.elde = False

    def al(self) -> "Kilit":
        self.dizin.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            try:
                fd = os.open(str(self.yol), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if _bayat_mi(self.yol, self.bayat_sn):
                    try:
                        self.yol.unlink()
                    except OSError:
                        pass
                    continue
                raise KilitDolu(str(_oku(self.yol).get("sahip") or "başka bir klip çıkarma işi")) from None
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"pid": os.getpid(), "sahip": self.sahip, "zaman": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
            self.elde = True
            return self
        raise KilitDolu("başka bir klip çıkarma işi")

    def tazele(self) -> None:
        if self.elde:
            try:
                os.utime(self.yol, None)
            except OSError:
                pass

    def birak(self) -> None:
        if self.elde:
            self.elde = False
            try:
                if _oku(self.yol).get("pid") == os.getpid():
                    self.yol.unlink()
            except OSError:
                pass

    def __enter__(self):
        return self.al()

    def __exit__(self, *a):
        self.birak()
