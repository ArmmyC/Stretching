from __future__ import annotations

import argparse
import asyncio
import json
import time
import urllib.error
import urllib.request

from bleak import BleakClient, BleakScanner


DEFAULT_NAME = "YUEDMAI-NanoIMU"
DEFAULT_SERVICE_UUID = "19b10000-e8f2-537e-4f6c-d104768a1214"
DEFAULT_IMU_CHAR_UUID = "19b10001-e8f2-537e-4f6c-d104768a1214"
DEFAULT_APP_URL = "http://127.0.0.1:8000/api/nano_imu"


def post_json(url: str, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        response.read()


async def find_device(name: str, service_uuid: str, timeout: float):
    print(f"Scanning for {name} service={service_uuid}")

    def match_device(device, advertisement_data):
        device_name = device.name or ""
        local_name = advertisement_data.local_name or ""
        service_uuids = [uuid.lower() for uuid in (advertisement_data.service_uuids or [])]
        name_matches = device_name == name or local_name == name
        service_matches = service_uuid.lower() in service_uuids
        return name_matches or service_matches

    device = await BleakScanner.find_device_by_filter(match_device, timeout=timeout)
    if device:
        print(f"Found {device.name or name} at {device.address}")
    return device


async def forward_loop(args: argparse.Namespace) -> None:
    while True:
        device = await find_device(args.name, args.service_uuid, args.scan_timeout)
        if device is None:
            print(f"{args.name} not found; retrying in {args.retry_sec}s")
            await asyncio.sleep(args.retry_sec)
            continue

        try:
            async with BleakClient(device) as client:
                print(f"Connected to {device.address}")

                def handle_packet(_: int, data: bytearray) -> None:
                    text = bytes(data).decode("utf-8", errors="ignore").strip("\x00\r\n ")
                    if not text:
                        return
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        print(f"Bad Nano JSON: {text[:120]}")
                        return
                    try:
                        post_json(args.app_url, payload)
                        print(
                            "Nano",
                            f"az={payload.get('az')}",
                            f"roll={payload.get('roll')}",
                            f"gyro={payload.get('gyro_mag')}",
                            f"stable={payload.get('stable')}",
                        )
                    except (urllib.error.URLError, TimeoutError) as error:
                        print(f"POST failed: {error}")

                await client.start_notify(args.imu_char_uuid, handle_packet)
                print(f"Subscribed to {args.imu_char_uuid}; forwarding to {args.app_url}")
                while client.is_connected:
                    await asyncio.sleep(1.0)
        except Exception as error:
            print(f"BLE forwarder error: {error}")
        print(f"Disconnected; retrying in {args.retry_sec}s")
        await asyncio.sleep(args.retry_sec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forward Nano BLE IMU packets to the YUEDMAI App Lab API.")
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--service-uuid", default=DEFAULT_SERVICE_UUID)
    parser.add_argument("--imu-char-uuid", default=DEFAULT_IMU_CHAR_UUID)
    parser.add_argument("--app-url", default=DEFAULT_APP_URL)
    parser.add_argument("--scan-timeout", type=float, default=5.0)
    parser.add_argument("--retry-sec", type=float, default=3.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"Nano BLE forwarder starting at {time.strftime('%H:%M:%S')}")
    asyncio.run(forward_loop(args))


if __name__ == "__main__":
    main()
