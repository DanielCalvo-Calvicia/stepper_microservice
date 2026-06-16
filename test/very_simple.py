#!/usr/bin/env python3
"""
TMC2209 single stepper motor diagnostic script for Raspberry Pi OS.

Hardware assumed by this script:
  - Raspberry Pi GPIO17 -> TMC2209 STEP
  - Raspberry Pi GPIO27 -> TMC2209 DIR
  - Raspberry Pi GPIO5  -> TMC2209 EN / ENABLE
  - Raspberry Pi 3.3V   -> TMC2209 VIO
  - Raspberry Pi GND    -> TMC2209 GND
  - External motor PSU  -> TMC2209 VM and GND
  - 4-wire bipolar stepper connected to one coil pair on A1/A2 and one coil
    pair on B1/B2

This is a debugging script, not production motion-control code. It intentionally
uses long delays and lots of console output so you can measure pins, watch LEDs,
listen for motor locking, and compare observations against the checklist.
"""

import sys
import time
from datetime import datetime

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("ERROR: Could not import RPi.GPIO.")
    print("Install it on Raspberry Pi OS with: sudo apt install python3-rpi.gpio")
    print("This script must be run on a Raspberry Pi, usually with sudo.")
    sys.exit(1)


# BCM GPIO numbering. These are GPIO numbers, not physical header pin numbers.
STEP_PIN = 17
DIR_PIN = 27
EN_PIN = 5

# Most TMC2209 stepstick-style boards use active-low enable:
#   EN low  = driver outputs enabled
#   EN high = driver outputs disabled
#
# If your board is different, change this to False.
ENABLE_ACTIVE_LOW = True

# Pulse timing. TMC2209 accepts short STEP pulses, but long pulses are easier to
# see on a meter or oscilloscope during diagnostics.
SLOW_STEP_HIGH_TIME_SEC = 0.10
SLOW_STEP_LOW_TIME_SEC = 0.90
RUN_STEP_PULSE_WIDTH_SEC = 0.001


def log(message):
    """Print a timestamped message immediately."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def wait(seconds, reason=None):
    """Sleep with a visible countdown so the user can observe hardware."""
    if reason:
        log(reason)
    for remaining in range(int(seconds), 0, -1):
        log(f"Waiting... {remaining} second(s) remaining")
        time.sleep(1)
    fractional = seconds - int(seconds)
    if fractional > 0:
        time.sleep(fractional)


def enabled_level():
    return GPIO.LOW if ENABLE_ACTIVE_LOW else GPIO.HIGH


def disabled_level():
    return GPIO.HIGH if ENABLE_ACTIVE_LOW else GPIO.LOW


def describe_level(level):
    return "HIGH / 3.3V" if level == GPIO.HIGH else "LOW / 0V"


def set_enable(enabled):
    level = enabled_level() if enabled else disabled_level()
    GPIO.output(EN_PIN, level)
    state = "ENABLED" if enabled else "DISABLED"
    polarity = "active-low" if ENABLE_ACTIVE_LOW else "active-high"
    log(f"Driver {state}: EN pin set to {describe_level(level)} ({polarity} enable assumption)")


def set_direction(forward):
    level = GPIO.HIGH if forward else GPIO.LOW
    GPIO.output(DIR_PIN, level)
    direction_name = "FORWARD / DIR HIGH" if forward else "REVERSE / DIR LOW"
    log(f"Direction set to {direction_name} ({describe_level(level)})")


def single_step(high_time, low_time):
    GPIO.output(STEP_PIN, GPIO.HIGH)
    time.sleep(high_time)
    GPIO.output(STEP_PIN, GPIO.LOW)
    time.sleep(low_time)


def run_steps(steps_per_second, duration_seconds, label):
    """Generate STEP pulses at the requested speed for a fixed duration."""
    period = 1.0 / steps_per_second
    high_time = min(RUN_STEP_PULSE_WIDTH_SEC, period / 2.0)
    low_time = max(period - high_time, 0.0)
    total_steps = int(steps_per_second * duration_seconds)

    log("")
    log(f"{label}: {steps_per_second} steps/sec for {duration_seconds} second(s)")
    log(f"Pulse timing: HIGH {high_time:.6f}s, LOW {low_time:.6f}s, total pulses {total_steps}")
    log("Observe: motor may rotate, vibrate, twitch, or lock depending on wiring/current/load.")

    start_time = time.monotonic()
    for step_number in range(1, total_steps + 1):
        single_step(high_time, low_time)
        if step_number == 1 or step_number == total_steps or step_number % max(1, steps_per_second) == 0:
            elapsed = time.monotonic() - start_time
            log(f"{label}: pulse {step_number}/{total_steps}, elapsed {elapsed:.1f}s")


def print_troubleshooting_checklist():
    log("")
    log("TROUBLESHOOTING CHECKLIST BEFORE TESTING")
    print(
        """
Read this before the GPIO tests begin.

1. TMC2209 enable polarity
   - Most TMC2209 carrier boards use EN active-low.
   - EN near 0V usually means outputs enabled.
   - EN near 3.3V usually means outputs disabled.
   - In PHASE 2, if the motor locks when EN is LOW and releases when EN is HIGH,
     the default polarity in this script is correct.
   - If behavior is reversed, set ENABLE_ACTIVE_LOW = False near the top.

2. STEP pin activity
   - Measure Raspberry Pi GPIO17 to Raspberry Pi GND.
   - In PHASE 4, the voltage should alternate once per second.
   - A multimeter may show changing/averaged voltage; an oscilloscope or logic
     analyzer should show clean 0V to 3.3V pulses.
   - If there is no activity, check GPIO numbering and the wire from GPIO17 to STEP.

3. DIR pin activity
   - Measure Raspberry Pi GPIO27 to Raspberry Pi GND.
   - In PHASE 3, it should sit near 3.3V for 5 seconds, then near 0V for 5 seconds.
   - If DIR does not change, check GPIO numbering and the wire from GPIO27 to DIR.

4. VIO voltage
   - Measure TMC2209 VIO to TMC2209 GND.
   - It should be about 3.3V.
   - If VIO is missing, the driver will not reliably recognize STEP, DIR, or EN.

5. VM motor voltage
   - Measure TMC2209 VM to TMC2209 GND.
   - It should match your external motor supply voltage.
   - Do not rely only on the PSU display; measure at the driver screw/header pins.

6. Ground continuity
   - With power off, measure resistance between Raspberry Pi GND and TMC2209 GND.
   - It should be very close to 0 ohms.
   - With power on, measure DC voltage between Raspberry Pi GND and TMC2209 GND.
   - It should be very close to 0V.

7. Coil pair identification
   - Disconnect the motor from the driver before resistance testing.
   - Use ohms mode to find the two wire pairs that have low resistance.
   - Wires in the same coil pair show continuity.
   - Wires from different coils show open circuit or very high resistance.

8. Correct motor wiring
   - One coil pair must go to A1/A2.
   - The other coil pair must go to B1/B2.
   - Do not put one wire from each coil on the same A or B output pair.

9. Current limit adjustment
   - If current limit is too low, the motor may not lock or may only twitch.
   - If current limit is too high, the driver and motor may get hot quickly.
   - Set current according to your motor rating and your specific TMC2209 board
     documentation. Board Vref formulas vary by sense resistor value.

10. Motor locking when enabled
    - With VM and VIO powered, the motor should usually become harder to turn by
      hand when the driver is enabled.
    - If it never locks, suspect EN polarity, missing VM, missing VIO, bad ground,
      driver fault, sleep/standby configuration, or current limit set too low.

11. Symptoms of swapped coil pairs
    - Motor buzzes, vibrates, twitches, or moves erratically.
    - Shaft may jump forward/back instead of rotating smoothly.
    - Driver may heat more than expected.

12. Symptoms of insufficient motor current
    - Motor locks weakly or not at all.
    - Motor turns only at very low speed.
    - Motor stalls, skips, or buzzes under tiny load.
    - Increasing speed makes movement worse.
""",
        flush=True,
    )


def print_wiring_verification_section():
    log("")
    log("WIRING VERIFICATION IF THE MOTOR DOES NOT MOVE")
    print(
        """
Use a multimeter and work through these exact checks.

Power-off checks:
1. Disconnect motor power before changing motor wiring.
2. Remove the motor wires from the TMC2209.
3. Measure resistance between every pair of motor wires.
4. Identify the two pairs that show low resistance. Those are the two coils.
5. Connect one complete coil pair to A1/A2.
6. Connect the other complete coil pair to B1/B2.
7. Verify Raspberry Pi GND and external PSU negative both connect to TMC2209 GND.

Power-on checks:
1. Measure VIO to driver GND: expected about 3.3V.
2. Measure VM to driver GND: expected your motor supply voltage.
3. Measure EN to driver GND during PHASE 2:
   - Expected alternating near 0V and near 3.3V every 2 seconds.
4. Measure DIR to driver GND during PHASE 3:
   - Expected near 3.3V for 5 seconds, then near 0V for 5 seconds.
5. Measure STEP to driver GND during PHASE 4:
   - Expected 0V/3.3V pulses once per second.
6. When EN is in the enabled state, gently turn the motor shaft by hand:
   - Expected: shaft becomes harder to turn or holds position.
   - If not: suspect enable polarity, missing VM, missing VIO, current limit,
     ground, or damaged driver.

Important safety notes:
- Never connect or disconnect motor coils while VM motor power is on.
- Make sure the driver has adequate cooling if you run higher current.
- If anything gets very hot or smells wrong, stop the test and remove power.
""",
        flush=True,
    )


def phase_1_startup_and_gpio_setup():
    log("")
    log("PHASE 1: Startup information and GPIO setup")
    log(f"Python version: {sys.version.split()[0]}")
    log(f"Script start time: {datetime.now().isoformat(timespec='seconds')}")
    log("GPIO numbering mode: BCM")
    log(f"STEP = GPIO{STEP_PIN}")
    log(f"DIR  = GPIO{DIR_PIN}")
    log(f"EN   = GPIO{EN_PIN}")
    log(f"Assumed enable polarity: {'active-low' if ENABLE_ACTIVE_LOW else 'active-high'}")

    GPIO.setwarnings(True)
    GPIO.setmode(GPIO.BCM)

    # Start in a conservative state: STEP low, DIR low, driver disabled.
    GPIO.setup(STEP_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(DIR_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(EN_PIN, GPIO.OUT, initial=disabled_level())

    log("GPIO pins configured as outputs.")
    log(f"Initial STEP state: {describe_level(GPIO.input(STEP_PIN))}")
    log(f"Initial DIR state:  {describe_level(GPIO.input(DIR_PIN))}")
    log(f"Initial EN state:   {describe_level(GPIO.input(EN_PIN))} (driver should be disabled)")
    log("GPIO initialization verified by reading back output latch states.")
    wait(3, "Pause before enable test. Confirm wiring before continuing.")


def phase_2_enable_toggle():
    log("")
    log("PHASE 2: Toggle EN every 2 seconds for 10 cycles")
    log("What to observe: motor should lock when enabled and release when disabled if VM/VIO/current are correct.")
    log("If the opposite happens, your enable polarity is likely reversed.")

    for cycle in range(1, 11):
        log(f"Enable cycle {cycle}/10: enabling driver")
        set_enable(True)
        wait(2)

        log(f"Enable cycle {cycle}/10: disabling driver")
        set_enable(False)
        wait(2)

    log("PHASE 2 complete. Leaving driver enabled for motion tests.")
    set_enable(True)
    wait(3, "Observe whether the motor is now holding position.")


def phase_3_direction_test():
    log("")
    log("PHASE 3: DIR pin high/low test")
    log("Measure GPIO27 to GND now if you want to confirm DIR voltage.")

    set_direction(True)
    wait(5, "DIR should measure near 3.3V.")

    set_direction(False)
    wait(5, "DIR should measure near 0V.")


def phase_4_slow_step_pulses():
    log("")
    log("PHASE 4: Slow STEP pulses, 1 pulse per second for 20 pulses")
    log("Measure GPIO17 to GND. Oscilloscope/logic analyzer should show 0V to 3.3V pulses.")
    log("A multimeter may show a visible change or averaged voltage because pulses are slow and wide.")

    GPIO.output(STEP_PIN, GPIO.LOW)
    for pulse in range(1, 21):
        log(f"Slow STEP pulse {pulse}/20: HIGH for {SLOW_STEP_HIGH_TIME_SEC}s, then LOW")
        single_step(SLOW_STEP_HIGH_TIME_SEC, SLOW_STEP_LOW_TIME_SEC)


def phase_5_forward_speed_tests():
    log("")
    log("PHASE 5: Forward speed tests")
    set_direction(True)
    wait(2, "Direction set forward. Starting speed sweep after this pause.")

    for speed in (10, 50, 100, 200):
        run_steps(speed, duration_seconds=5, label="FORWARD speed test")
        wait(3, f"Pause after {speed} steps/sec. Observe motor temperature, sound, and motion.")


def phase_6_reverse_speed_tests():
    log("")
    log("PHASE 6: Reverse direction and repeat speed tests")
    set_direction(False)
    wait(2, "Direction set reverse. Starting reverse speed sweep after this pause.")

    for speed in (10, 50, 100, 200):
        run_steps(speed, duration_seconds=5, label="REVERSE speed test")
        wait(3, f"Pause after {speed} steps/sec. Observe motor temperature, sound, and motion.")


def phase_7_continuous_rotation():
    log("")
    log("PHASE 7: Continuous rotation mode for 30 seconds")
    log("Running at 100 steps/sec. This is slow enough for many basic wiring tests.")
    log("If motor only buzzes, re-check coil pairs and current limit.")

    steps_per_second = 100
    duration_seconds = 30
    period = 1.0 / steps_per_second
    high_time = min(RUN_STEP_PULSE_WIDTH_SEC, period / 2.0)
    low_time = max(period - high_time, 0.0)

    start_time = time.monotonic()
    next_report_second = 1
    pulse_count = 0

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed >= duration_seconds:
            break

        single_step(high_time, low_time)
        pulse_count += 1

        elapsed = time.monotonic() - start_time
        if elapsed >= next_report_second:
            log(f"Continuous mode elapsed: {next_report_second}/{duration_seconds} seconds, pulses: {pulse_count}")
            next_report_second += 1

    log(f"Continuous rotation complete. Total pulses sent: {pulse_count}")


def phase_8_cleanup():
    log("")
    log("PHASE 8: Cleanup")
    try:
        log("Disabling driver before cleanup.")
        set_enable(False)
        GPIO.output(STEP_PIN, GPIO.LOW)
        GPIO.output(DIR_PIN, GPIO.LOW)
        wait(1, "STEP and DIR set LOW.")
    finally:
        GPIO.cleanup()
        log("GPIO cleanup complete. Pins returned to input/default state.")


def main():
    log("TMC2209 STEPPER MOTOR DIAGNOSTIC STARTING")
    print_troubleshooting_checklist()
    print_wiring_verification_section()
    wait(10, "Testing will begin after this delay. Press Ctrl+C now if wiring is not ready.")

    gpio_was_configured = False
    try:
        phase_1_startup_and_gpio_setup()
        gpio_was_configured = True
        phase_2_enable_toggle()
        phase_3_direction_test()
        phase_4_slow_step_pulses()
        phase_5_forward_speed_tests()
        phase_6_reverse_speed_tests()
        phase_7_continuous_rotation()
    except KeyboardInterrupt:
        log("")
        log("KeyboardInterrupt received. Stopping test and cleaning up.")
    except Exception as exc:
        log("")
        log(f"ERROR: {exc!r}")
        log("Stopping test and cleaning up GPIO.")
        raise
    finally:
        if gpio_was_configured:
            phase_8_cleanup()
        else:
            try:
                GPIO.cleanup()
            except Exception:
                pass
        log("Diagnostic script finished.")


if __name__ == "__main__":
    main()
