#!/usr/bin/env python3
"""
Manual hardware diagnostic: which pulse timing makes the TMC2209 move the motor?

The service's TMC2209 driver starts pulsing the instant it enables the driver, with a 1 ms STEP pulse and (for
Brain's usual moves) a few hundred steps per second. The old standalone script (simple_rotation_test.py) waits
50 ms after enabling, uses a 10 microsecond pulse and runs at thousands of steps per second. This script runs
those combinations one at a time on ONE motor so you can see which of them turns it. Each variant turns the
shaft forward and then back by the same amount, so the arm ends where it started.

Stop the stepper service first (it holds the pins), then run it on the Raspberry Pi:
  /home/pi/oblivion/venvs/stepper/bin/python test/driver_timing_diagnostic.py [--motor 1|2] [--ladder]

--ladder runs the service's own timing at 100, 267, 533, 800, 1000 and 1500 steps/s instead (about 3 s each way
per rung) to find the slowest step rate at which your motor still turns.

Press Enter before each variant, watch the shaft, and write down which variants moved it. Ctrl+C stops at once
and leaves the driver disabled.
"""

import argparse
import time

import RPi.GPIO as GPIO

PINS = {1: dict(step=17, dir=27, en=5), 2: dict(step=23, dir=24, en=25)}
STEPS_PER_REVOLUTION = 3200  # 400 full steps x 1/8 microstepping

# name, steps, steps per second, STEP high seconds, wait after enable (seconds), what it imitates
VARIANTS = [
    ("A: like the service (no wait, 1 ms pulse, 800 steps/s)", 1600, 800, 0.001, 0.0),
    ("B: A + 50 ms wait after enabling the driver", 1600, 800, 0.001, 0.05),
    ("C: A with a 10 microsecond pulse", 1600, 800, 0.00001, 0.0),
    ("D: 10 microsecond pulse + 50 ms wait, 800 steps/s", 1600, 800, 0.00001, 0.05),
    ("E: like the old script (10 us pulse, 50 ms wait, 6400 steps/s = 120 rpm)", 6400, 6400, 0.00001, 0.05),
]


# --ladder: the service's own timing (no wait, 1 ms pulse) at rising step rates, about 3 s each way per rung
LADDER_SECONDS = 3
LADDER_RATES = (100, 267, 533, 800, 1000, 1500)
LADDER = [
    (f"R{rate}: the service's timing at {rate} steps/s ({rate * 60 / STEPS_PER_REVOLUTION:.1f} rpm)", rate * LADDER_SECONDS, rate, 0.001, 0.0)
    for rate in LADDER_RATES
]


def run(pins: dict[str, int], steps: int, rate: float, high: float, settle: float, forward: bool) -> None:
    period = 1.0 / rate
    low = max(period - high, 0.0)
    GPIO.output(pins["dir"], GPIO.HIGH if forward else GPIO.LOW)
    GPIO.output(pins["en"], GPIO.LOW)  # active low: outputs on
    if settle:
        time.sleep(settle)
    try:
        for _ in range(steps):
            GPIO.output(pins["step"], GPIO.HIGH)
            time.sleep(high)
            GPIO.output(pins["step"], GPIO.LOW)
            time.sleep(low)
    finally:
        GPIO.output(pins["en"], GPIO.HIGH)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--motor", type=int, choices=(1, 2), default=1)
    parser.add_argument("--ladder", action="store_true", help="test the service's timing at rising step rates")
    args = parser.parse_args()
    variants = LADDER if args.ladder else VARIANTS
    pins = PINS[args.motor]
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pins["step"], GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(pins["dir"], GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(pins["en"], GPIO.OUT, initial=GPIO.HIGH)
    print(f"Motor {args.motor}: STEP=GPIO{pins['step']} DIR=GPIO{pins['dir']} EN=GPIO{pins['en']}")
    print("Each variant turns forward, pauses 1 s, then turns back. Watch the shaft (a tape marker helps).\n")
    try:
        for name, steps, rate, high, settle in variants:
            turns = steps / STEPS_PER_REVOLUTION
            print(f"{name}\n   {steps} steps = {turns:g} rotation(s) each way, {steps / rate:.1f} s each way")
            input("   Press Enter to run it (Ctrl+C to quit)... ")
            print("   forward...", flush=True)
            run(pins, steps, rate, high, settle, forward=True)
            time.sleep(1.0)
            print("   back...", flush=True)
            run(pins, steps, rate, high, settle, forward=False)
            print("   done\n")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        GPIO.output(pins["en"], GPIO.HIGH)
        GPIO.output(pins["step"], GPIO.LOW)
        GPIO.cleanup()
        print("Driver disabled, GPIO released.")


if __name__ == "__main__":
    main()
