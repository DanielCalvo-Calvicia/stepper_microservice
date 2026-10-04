#!/usr/bin/env python3
"""
Manual hardware test: three full rotations of one motor, through the running stepper microservice.

It calls the service's POST /control/<stepper_id>/rotate, so it tests the whole path (HTTP, service, TMC2209
driver, pins), not just the wiring. The service must be running with MOCK_HARDWARE=0 on the Raspberry Pi.
Nothing moves until you press Enter, so you can be watching the motor when it starts.

Run it on the Pi (stdlib only, no virtualenv needed):
  python3 test/three_rotations_via_service.py --url http://<stepper-host>:8005

Options:
  --stepper-id stepper_2   which motor (default stepper_1)
  --rotations 3            full turns (default 3)
  --rpm 30                 shaft speed (default 30; 400 steps per turn, the service caps the step rate)
  --reverse                turn the other way
  --return-back            after the test, turn the same amount back to the starting position

Ctrl+C at any moment sends the emergency stop to the motor.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def call(base_url: str, path: str, query: dict[str, object], timeout: float) -> dict:
    url = f"{base_url.rstrip('/')}{path}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise SystemExit(f"The service answered HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"Cannot reach the stepper service at {base_url}: {error.reason}") from error


def get(base_url: str, path: str) -> dict:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def rotate(base_url: str, stepper_id: str, rotations: float, rpm: float, direction: str) -> float:
    expected = rotations * 60.0 / rpm
    print(f"  turning {rotations:g} rotation(s) {direction} at {rpm:g} rpm (about {expected:.1f} s)...", flush=True)
    start = time.perf_counter()
    answer = call(
        base_url,
        f"/control/{stepper_id}/rotate",
        {"rotations": rotations, "rpm": rpm, "direction": direction},
        timeout=expected + 30,
    )
    took = time.perf_counter() - start
    print(f"  done in {took:.1f} s: {answer.get('message')}")
    if answer.get("status") != "success":
        raise SystemExit(f"The service did not report success: {answer}")
    return took


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", help="base URL of the stepper service (no host is assumed)")
    parser.add_argument("--stepper-id", default="stepper_1")
    parser.add_argument("--rotations", type=float, default=3.0)
    parser.add_argument("--rpm", type=float, default=30.0)
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--return-back", action="store_true")
    args = parser.parse_args()
    if not args.url:
        parser.error("give --url (no host is assumed)")
    if args.rotations <= 0 or args.rpm <= 0:
        parser.error("--rotations and --rpm must be greater than 0")

    base_url = args.url
    direction = "reverse" if args.reverse else "forward"
    print(f"Stepper service: {base_url}")
    print(f"Health:      {get(base_url, '/health').get('message')}")
    print(f"Availability: {get(base_url, '/available').get('data')}")
    print()
    print(f"This will turn {args.stepper_id} {args.rotations:g} full rotation(s) {direction} at {args.rpm:g} rpm.")
    print("Make sure the motor power is on and nothing is in the way of the arm.")
    try:
        input("Press Enter to START (Ctrl+C to cancel)... ")
        for remaining in (3, 2, 1):
            print(f"  starting in {remaining}...", flush=True)
            time.sleep(1)
        print("MOVING NOW")
        rotate(base_url, args.stepper_id, args.rotations, args.rpm, direction)
        if args.return_back:
            time.sleep(1)
            print("Returning to the starting position")
            rotate(base_url, args.stepper_id, args.rotations, args.rpm, "forward" if args.reverse else "reverse")
    except KeyboardInterrupt:
        print("\nStopping the motor...")
        try:
            call(base_url, f"/control/{args.stepper_id}/stop", {}, timeout=5)
            print("Emergency stop sent.")
        except SystemExit as error:
            print(f"Could not send the stop: {error}")
        return 130
    print("Test finished. Did the motor turn the expected number of times, smoothly and in the right direction?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
