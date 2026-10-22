#!/usr/bin/env python3
"""Remote firmware flasher for bmorcelli/Launcher WebUI (2.9.x).

Talks to the Launcher's built-in HTTP server, so no USB and no touching the device.

    python flash_ota.py --host 192.168.1.50 --file app.bin
    python flash_ota.py --host launcher.local --probe
    python flash_ota.py --host 192.168.1.50 --file app.bin --reboot

Flow (same as the bundled web UI):
    POST /login          -> ESP32SESSION cookie
    GET  /systeminfo     -> VERSION / partitions sanity check
    POST /OTA            -> command=0, size, manifest=<json>
    POST /OTAFILE        -> multipart field "file1" with the image
    GET  /reboot         -> optional

The image is analysed locally: a merged image (partition table at 0x8000) yields an
"app" part plus optional data parts, a bare app image yields a single "app" part.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import struct
import sys
import urllib.parse
import urllib.request

DEFAULT_USER = "gazdea"
DEFAULT_PASS = "96321qazplm"

APP_SUBTYPES = (0x00, 0x10, 0x20)
DATA_SUBTYPES = (0x81, 0x82, 0x83)


def read_le32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def measure_esp_image_size(data: bytes, offset: int) -> int:
    """Size of an ESP application image starting at `offset`, 0 if it is not one."""
    if offset + 24 > len(data) or data[offset] != 0xE9:
        return 0
    segments = data[offset + 1]
    pos = offset + 24
    for _ in range(segments):
        if pos + 8 > len(data):
            return 0
        seg_len = read_le32(data, pos + 4)
        pos += 8 + seg_len
    pos += 1  # checksum byte
    pos = (pos + 15) & ~15
    if data[offset + 23] & 0x01:  # hash_appended
        pos += 32
    return pos - offset if pos <= len(data) else 0


def parse_image(data: bytes) -> list[dict]:
    """Return the manifest "parts" list for a merged or bare app image."""
    parts: list[dict] = []
    merged = len(data) > 0x8000 + 3 and data[0x8000:0x8003] == b"\xaa\x50\x01"
    app_offset = 0
    app_size = 0

    if merged:
        for i in range(0, 0x1000, 0x20):
            pos = 0x8000 + i
            if pos + 32 > len(data):
                break
            if data[pos] in (0xEB, 0xFF) and data[pos + 1] in (0xEB, 0xFF):
                break
            ptype, subtype = data[pos + 2], data[pos + 3]
            offset = read_le32(data, pos + 4)
            declared = read_le32(data, pos + 8)
            label = data[pos + 12 : pos + 28].split(b"\x00")[0].decode("ascii", "replace")

            if ptype == 0x00 and subtype in APP_SUBTYPES:
                app_offset = offset or 0x10000
                app_size = declared
                if len(data) < app_offset + app_size:
                    app_size = len(data) - app_offset
                measured = measure_esp_image_size(data, app_offset)
                if measured and (app_size == 0 or measured < app_size):
                    app_size = measured
            elif ptype == 0x01 and subtype in DATA_SUBTYPES and offset < len(data):
                size = min(declared, len(data) - offset)
                if subtype in (0x82, 0x83):
                    # empty (formatted only) SPIFFS/LittleFS still has to be announced
                    chunk = data[offset : offset + size]
                    if not chunk or chunk.count(0xFF) == len(chunk) or chunk.count(0x00) == len(chunk):
                        size = 0
                if size > 0 or declared > 0:
                    parts.append(
                        {
                            "kind": "data",
                            "subtype": subtype,
                            "label": label,
                            "sourceOffset": offset,
                            "copySize": size,
                            "declaredSize": declared,
                        }
                    )
    else:
        app_size = measure_esp_image_size(data, 0) or len(data)

    if app_size > 0:
        parts.insert(
            0,
            {
                "kind": "app",
                "subtype": 0,
                "label": "app",
                "sourceOffset": app_offset,
                "copySize": app_size,
                "declaredSize": app_size,
            },
        )
    return parts


class LauncherClient:
    def __init__(self, host: str, user: str, password: str, *, https: bool = False) -> None:
        if "://" not in host:
            host = ("https://" if https else "http://") + host
        self.base = host.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.user = user
        self.password = password

    def _request(self, path: str, data: bytes | None = None, headers: dict | None = None) -> bytes:
        req = urllib.request.Request(self.base + path, data=data, headers=headers or {})
        with self.opener.open(req, timeout=120) as resp:
            return resp.read()

    def login(self) -> None:
        body = urllib.parse.urlencode({"username": self.user, "password": self.password}).encode()
        self._request(
            "/login",
            body,
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        if not any(c.name == "ESP32SESSION" for c in self.jar):
            raise RuntimeError("login failed: no ESP32SESSION cookie (wrong host or credentials)")

    def systeminfo(self) -> dict:
        return json.loads(self._request("/systeminfo").decode("utf-8", "replace") or "{}")

    def prepare_ota(self, size: int, manifest: dict) -> str:
        body = urllib.parse.urlencode(
            {"command": 0, "size": size, "manifest": json.dumps(manifest, separators=(",", ":"))}
        ).encode()
        return self._request("/OTA", body, {"Content-Type": "application/x-www-form-urlencoded"}).decode(
            "utf-8", "replace"
        ).strip()

    def upload(self, filename: str, payload: bytes) -> str:
        boundary = "----launcher" + format(len(payload) & 0xFFFFFF, "06x")
        head = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file1"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        tail = f"\r\n--{boundary}--\r\n".encode()
        body = head + payload + tail
        return self._request(
            "/OTAFILE",
            body,
            {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        ).decode("utf-8", "replace").strip()

    def reboot(self) -> None:
        try:
            self._request("/reboot")
        except Exception:  # device drops the connection while restarting
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Flash firmware over the Launcher WebUI")
    ap.add_argument("--host", required=True, help="IP or launcher.local")
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--passwd", dest="password", default=DEFAULT_PASS)
    ap.add_argument("--file", help="firmware .bin to install")
    ap.add_argument("--probe", action="store_true", help="only log in and print device info")
    ap.add_argument("--dry-run", action="store_true", help="analyse the image, do not upload")
    ap.add_argument("--reboot", action="store_true", help="reboot after a successful install")
    args = ap.parse_args()

    client = LauncherClient(args.host, args.user, args.password)
    client.login()
    info = client.systeminfo()
    print(f"device version: {info.get('VERSION', '?')}")

    if args.probe or not args.file:
        print(json.dumps(info, indent=2)[:1200])
        return 0

    with open(args.file, "rb") as fh:
        payload = fh.read()

    parts = parse_image(payload)
    if not parts:
        print("no installable parts found in this image", file=sys.stderr)
        return 2

    print(f"image: {args.file}  {len(payload)} bytes  ({'merged' if len(parts) > 1 else 'app'})")
    for p in parts:
        print(
            f"  {p['kind']:4} offset=0x{p['sourceOffset']:06x} copy=0x{p['copySize']:06x} "
            f"declared=0x{p['declaredSize']:06x} label={p['label'] or '-'} subtype=0x{p['subtype']:02x}"
        )
    if args.dry_run:
        return 0

    manifest = {"sourceName": args.file.replace("\\", "/").split("/")[-1], "parts": parts}
    status = client.prepare_ota(len(payload), manifest)
    print(f"/OTA -> {status}")
    if status != "OK":
        return 3

    print("uploading...")
    result = client.upload(manifest["sourceName"], payload)
    print(f"/OTAFILE -> {result or '(no body)'}")

    if args.reboot:
        print("rebooting device")
        client.reboot()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
