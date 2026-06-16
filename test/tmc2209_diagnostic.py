#!/usr/bin/env python3
"""
Complete TMC2209 single stepper motor diagnostic for Raspberry Pi OS.

Hardware assumed:
  Raspberry Pi GPIO17 -> TMC2209 STEP
  Raspberry Pi GPIO27 -> TMC2209 DIR
  Raspberry Pi GPIO5  -> TMC2209 EN / ENABLE
  Raspberry Pi 3.3V   -> TMC2209 VIO
  Raspberry Pi GND    -> TMC2209 GND
  External PSU +      -> TMC2209 VM
  External PSU -      -> TMC2209 GND
  Stepper coil pair 1 -> TMC2209 A1/A2
  Stepper coil pair 2 -> TMC2209 B1/B2

This is intentionally slow, verbose diagnostic code. It is designed for
measuring pins, watching LEDs, listening for motor lock, and isolating wiring
or driver problems. It is not production motion-control code.

Run on the Raspberry Pi with:
  sudo python3 tmc2209_diagnostic.py
"""

import sys
import time
from datetime import datetime

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("ERROR: RPi.GPIO could not be imported.")
    print("Install on Raspberry Pi OS with:")
    print("  sudo apt update")
    print("  sudo apt install python3-rpi.gpio")
    print("Then run this script on the Raspberry Pi, usually with sudo.")
    sys.exit(1)


# Use BCM numbering. These are GPIO numbers, not physical header pin numbers.
STEP_PIN = 17
DIR_PIN = 27
EN_PIN = 5

# Most TMC2209 stepstick-style boards use active-low enable:
#   EN low  = driver outputs enabled
#   EN high = driver outputs disabled
# If your PHASE 2 observations show the opposite, change this to False.
ENABLE_ACTIVE_LOW = True

# Slow STEP pulse timing for PHASE 4. The long high time makes the pulse easier
# to see with basic tools. TMC2209 can accept far shorter pulses than this.
SLOW_STEP_HIGH_TIME_SEC = 0.10
SLOW_STEP_LOW_TIME_SEC = 0.90

# Motion-test pulse high time. Keep this short so the requested step rate mostly
# determines the low time. At 200 steps/sec the period is 5 ms, so 1 ms high is
# still easy for the driver and conservative for Python timing.
RUN_STEP_PULSE_WIDTH_SEC = 0.001

# Each speed in PHASE 5 and PHASE 6 runs for this long.
SPEED_TEST_DURATION_SEC = 5


def log(message=""):
    """Print timestamped logging and flush immediately."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def wait(seconds, reason=None):
    """Wait with a visible countdown so the user has time to observe hardware."""
    if reason:
        log(reason)

    whole_seconds = int(seconds)
    for remaining in range(whole_seconds, 0, -1):
        log(f"Waiting... {remaining} second(s) remaining")
        time.sleep(1)

    fractional_seconds = seconds - whole_seconds
    if fractional_seconds > 0:
        time.sleep(fractional_seconds)


def enabled_level():
    """Return the GPIO output level that should enable the TMC2209."""
    return GPIO.LOW if ENABLE_ACTIVE_LOW else GPIO.HIGH


def disabled_level():
    """Return the GPIO output level that should disable the TMC2209."""
    return GPIO.HIGH if ENABLE_ACTIVE_LOW else GPIO.LOW


def level_text(level):
    """Convert a GPIO level to human-readable voltage text."""
    return "HIGH, about 3.3V" if level == GPIO.HIGH else "LOW, about 0V"


def set_enable(enabled):
    """Set the EN pin and log the assumed driver state."""
    level = enabled_level() if enabled else disabled_level()
    GPIO.output(EN_PIN, level)
    state = "ENABLED" if enabled else "DISABLED"
    polarity = "active-low" if ENABLE_ACTIVE_LOW else "active-high"
    log(f"Driver {state}: EN GPIO{EN_PIN} set {level_text(level)} ({polarity} assumption)")


def set_direction(forward):
    """Set DIR high for forward or low for reverse and log it."""
    level = GPIO.HIGH if forward else GPIO.LOW
    GPIO.output(DIR_PIN, level)
    direction = "FORWARD" if forward else "REVERSE"
    log(f"Direction {direction}: DIR GPIO{DIR_PIN} set {level_text(level)}")


def pulse_step(high_time_sec, low_time_sec):
    """Generate one STEP pulse."""
    GPIO.output(STEP_PIN, GPIO.HIGH)
    time.sleep(high_time_sec)
    GPIO.output(STEP_PIN, GPIO.LOW)
    time.sleep(low_time_sec)


def run_steps_at_speed(steps_per_second, duration_seconds, label):
    """Generate STEP pulses at a requested rate for a fixed time."""
    period_sec = 1.0 / steps_per_second
    high_time_sec = min(RUN_STEP_PULSE_WIDTH_SEC, period_sec / 2.0)
    low_time_sec = max(period_sec - high_time_sec, 0.0)
    total_pulses = int(steps_per_second * duration_seconds)

    log()
    log(f"{label}: {steps_per_second} steps/sec for {duration_seconds} second(s)")
    log(f"Pulse high time: {high_time_sec:.6f}s")
    log(f"Pulse low time:  {low_time_sec:.6f}s")
    log(f"Total pulses:    {total_pulses}")
    log("Observe motor movement, locking force, vibration, skipped steps, heat, and sound.")

    start = time.monotonic()
    report_interval = max(1, steps_per_second)

    for pulse_number in range(1, total_pulses + 1):
        pulse_step(high_time_sec, low_time_sec)

        # Log the first pulse, the last pulse, and about once per second.
        if (
            pulse_number == 1
            or pulse_number == total_pulses
            or pulse_number % report_interval == 0
        ):
            elapsed = time.monotonic() - start
            log(f"{label}: pulse {pulse_number}/{total_pulses}, elapsed {elapsed:.1f}s")


def print_troubleshooting_checklist():
    """Print the required checklist before any GPIO action starts."""
    log()
    log("TROUBLESHOOTING CHECKLIST BEFORE TESTING")
    print(
        """
Read this checklist before the GPIO tests begin.

1. TMC2209 enable polarity
   - Most TMC2209 carrier boards use EN active-low.
   - EN near 0V usually means outputs enabled.
   - EN near 3.3V usually means outputs disabled.
   - In PHASE 2, if the motor locks when EN is LOW and releases when EN is
     HIGH, ENABLE_ACTIVE_LOW = True is correct.
   - If the behavior is reversed, stop the script and set ENABLE_ACTIVE_LOW =
     False near the top of this file.

2. STEP pin activity
   - Measure Raspberry Pi GPIO17 to Raspberry Pi GND.
   - In PHASE 4, STEP should pulse once per second.
   - A scope or logic analyzer should show clean 0V to 3.3V pulses.
   - A multimeter may show changing or averaged voltage because pulses are not
     a steady DC level.
   - If there is no activity, check BCM numbering and the GPIO17-to-STEP wire.

3. DIR pin activity
   - Measure Raspberry Pi GPIO27 to Raspberry Pi GND.
   - In PHASE 3, DIR should be near 3.3V for 5 seconds, then near 0V for 5
     seconds.
   - If DIR does not change, check BCM numbering and the GPIO27-to-DIR wire.

4. VIO voltage
   - Measure TMC2209 VIO to TMC2209 GND.
   - Expected value: about 3.3V.
   - If VIO is missing, the driver may not recognize STEP, DIR, or EN.

5. VM motor voltage
   - Measure TMC2209 VM to TMC2209 GND at the driver.
   - Expected value: your external motor supply voltage.
   - Do not trust only the PSU display; verify at the driver pins.

6. Ground continuity
   - Power off: measure resistance between Raspberry Pi GND and TMC2209 GND.
   - Expected value: very close to 0 ohms.
   - Power on: measure DC voltage between Raspberry Pi GND and TMC2209 GND.
   - Expected value: very close to 0V.

7. Coil pair identification
   - Power off and disconnect the motor from the driver before resistance tests.
   - Measure resistance between every pair of the four motor wires.
   - The two pairs with low resistance are the two coils.
   - Wires from different coils should read open circuit or very high resistance.

8. Correct motor wiring
   - Put one complete coil pair on A1/A2.
   - Put the other complete coil pair on B1/B2.
   - Do not put one wire from each coil on the same A or B output pair.

9. Current limit adjustment on the TMC2209
   - If current is too low, the motor may not lock, may only twitch, or may
     stall as soon as speed increases.
   - If current is too high, the motor and driver can heat quickly.
   - Set the current using your motor rating and your exact TMC2209 board
     documentation. Vref formulas vary with sense resistor value.

10. Whether the motor locks when enabled
    - With VIO and VM powered, enabling the driver should usually make the shaft
      harder to turn by hand.
    - If it never locks, suspect EN polarity, missing VM, missing VIO, bad
      ground, low current limit, sleep/standby configuration, or a damaged driver.

11. Symptoms of swapped coil pairs
    - Motor buzzes, vibrates, twitches, or jumps back and forth.
    - Shaft does not rotate smoothly even at 10 steps/sec.
    - Driver may heat more than expected.

12. Symptoms of insufficient motor current
    - Motor locks weakly or not at all.
    - Motor turns only at very low speed.
    - Motor stalls, skips, or buzzes under little or no load.
    - Increasing speed makes behavior worse.
""",
        flush=True,
    )


def print_wiring_verification_section():
    """Print exact multimeter checks for the no-motion case."""
    log()
    log("WIRING VERIFICATION IF THE MOTOR DOES NOT MOVE")
    print(
        """
Use a multimeter and work through these exact checks.

Power-off checks:
1. Remove motor power before changing any motor wiring.
2. Remove the four motor wires from the TMC2209.
3. Measure resistance between all six possible wire pairs.
4. Identify the two pairs that show low resistance. Those are the two coils.
5. Connect one complete coil pair to A1/A2.
6. Connect the other complete coil pair to B1/B2.
7. Verify Raspberry Pi GND and external PSU negative both connect to TMC2209 GND.
8. Verify there is no short between VM and GND before applying motor power.

Power-on checks:
1. Measure VIO to driver GND.
   - Expected: about 3.3V.
2. Measure VM to driver GND.
   - Expected: your motor supply voltage.
3. Measure EN to driver GND during PHASE 2.
   - Expected: alternating near 0V and near 3.3V every 2 seconds.
4. Measure DIR to driver GND during PHASE 3.
   - Expected: near 3.3V for 5 seconds, then near 0V for 5 seconds.
5. Measure STEP to driver GND during PHASE 4.
   - Expected: 0V/3.3V pulses once per second.
6. When EN is enabled, gently turn the motor shaft by hand.
   - Expected: shaft becomes harder to turn or holds position.
   - If it does not, suspect enable polarity, missing VM, missing VIO, current
     limit, ground wiring, or driver damage.

Safety notes:
- Never connect or disconnect motor coils while VM motor power is on.
- Make sure the driver has cooling if you run higher current.
- If the motor or driver gets very hot, smells wrong, or behaves unexpectedly,
  stop the test and remove power.
""",
        flush=True,
    )


def phase_1_startup_and_gpio_setup():
    log()
    log("PHASE 1: Startup information, GPIO configuration, and initialization check")
    log(f"Python version: {sys.version.split()[0]}")
    log(f"Script start time: {datetime.now().isoformat(timespec='seconds')}")
    log("GPIO numbering mode: BCM")
    log(f"STEP pin: GPIO{STEP_PIN}")
    log(f"DIR pin:  GPIO{DIR_PIN}")
    log(f"EN pin:   GPIO{EN_PIN}")
    log(f"Assumed TMC2209 enable polarity: {'active-low' if ENABLE_ACTIVE_LOW else 'active-high'}")

    GPIO.setwarnings(True)
    GPIO.setmode(GPIO.BCM)

    # Start safe and quiet:
    # - STEP low so no accidental pulse is present.
    # - DIR low so its initial state is known.
    # - EN disabled so the motor is not energized until PHASE 2.
    GPIO.setup(STEP_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(DIR_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(EN_PIN, GPIO.OUT, initial=disabled_level())

    log("GPIO.setup completed for STEP, DIR, and EN.")
    log(f"Readback STEP GPIO{STEP_PIN}: {level_text(GPIO.input(STEP_PIN))}")
    log(f"Readback DIR  GPIO{DIR_PIN}: {level_text(GPIO.input(DIR_PIN))}")
    log(f"Readback EN   GPIO{EN_PIN}: {level_text(GPIO.input(EN_PIN))} (driver should be disabled)")
    log("GPIO initialization verified by reading back the output latch states.")
    wait(3, "Pause before PHASE 2. Confirm wiring and keep hands clear.")


def phase_2_enable_toggle():
    log()
    log("PHASE 2: Toggle EN every 2 seconds for 10 cycles")
    log("Physical observation: the motor should lock when enabled and release when disabled.")
    log("If locking happens on the opposite EN level, change ENABLE_ACTIVE_LOW.")

    for cycle in range(1, 11):
        log(f"Enable cycle {cycle}/10: enabling driver now")
        set_enable(True)
        wait(2)

        log(f"Enable cycle {cycle}/10: disabling driver now")
        set_enable(False)
        wait(2)

    log("PHASE 2 complete. Leaving driver enabled for the remaining tests.")
    set_enable(True)
    wait(3, "Observe whether the motor is now holding position.")


def phase_3_direction_test():
    log()
    log("PHASE 3: Set DIR high for 5 seconds, then low for 5 seconds")
    log("Measure GPIO27 to GND during this phase if you want to verify DIR activity.")

    set_direction(True)
    wait(5, "DIR should measure near 3.3V now.")

    set_direction(False)
    wait(5, "DIR should measure near 0V now.")


def phase_4_slow_step_pulses():
    log()
    log("PHASE 4: Generate slow STEP pulses")
    log("Generating 1 pulse per second for 20 pulses.")
    log("Measure GPIO17 to GND. Scope or logic analyzer should show 0V to 3.3V pulses.")

    GPIO.output(STEP_PIN, GPIO.LOW)
    for pulse_number in range(1, 21):
        log(f"STEP pulse {pulse_number}/20: HIGH {SLOW_STEP_HIGH_TIME_SEC}s, LOW {SLOW_STEP_LOW_TIME_SEC}s")
        pulse_step(SLOW_STEP_HIGH_TIME_SEC, SLOW_STEP_LOW_TIME_SEC)


def phase_5_forward_speed_tests():
    log()
    log("PHASE 5: Forward speed tests")
    set_direction(True)
    wait(2, "Direction is forward. Speed sweep starts after this pause.")

    for speed in (10, 50, 100, 200):
        run_steps_at_speed(speed, SPEED_TEST_DURATION_SEC, "FORWARD speed test")
        wait(3, f"Pause after {speed} steps/sec. Observe motion, sound, heat, and holding force.")


def phase_6_reverse_speed_tests():
    log()
    log("PHASE 6: Reverse direction and repeat all speed tests")
    set_direction(False)
    wait(2, "Direction is reverse. Reverse speed sweep starts after this pause.")

    for speed in (10, 50, 100, 200):
        run_steps_at_speed(speed, SPEED_TEST_DURATION_SEC, "REVERSE speed test")
        wait(3, f"Pause after {speed} steps/sec. Observe motion, sound, heat, and holding force.")


def phase_7_continuous_rotation():
    log()
    log("PHASE 7: Continuous rotation mode")
    log("Running for 30 seconds at 100 steps/sec.")
    log("Elapsed time will be printed every second.")

    steps_per_second = 100
    duration_seconds = 30
    period_sec = 1.0 / steps_per_second
    high_time_sec = min(RUN_STEP_PULSE_WIDTH_SEC, period_sec / 2.0)
    low_time_sec = max(period_sec - high_time_sec, 0.0)

    start = time.monotonic()
    next_report_second = 1
    pulse_count = 0

    while True:
        elapsed = time.monotonic() - start
        if elapsed >= duration_seconds:
            break

        pulse_step(high_time_sec, low_time_sec)
        pulse_count += 1

        elapsed = time.monotonic() - start
        if elapsed >= next_report_second:
            log(f"Continuous rotation elapsed: {next_report_second}/{duration_seconds}s, pulses sent: {pulse_count}")
            next_report_second += 1

    log(f"Continuous rotation finished. Total pulses sent: {pulse_count}")


def phase_8_cleanup():
    log()
    log("PHASE 8: GPIO cleanup")
    try:
        log("Disabling driver before cleanup.")
        set_enable(False)
        GPIO.output(STEP_PIN, GPIO.LOW)
        GPIO.output(DIR_PIN, GPIO.LOW)
        wait(1, "STEP and DIR set LOW.")
    finally:
        GPIO.cleanup()
        log("GPIO.cleanup completed. Pins returned to default/input state.")


def main():
    log("TMC2209 STEPPER MOTOR DIAGNOSTIC STARTING")
    log("This script uses RPi.GPIO with BCM pin numbering.")

    print_troubleshooting_checklist()
    print_wiring_verification_section()

    wait(10, "Testing begins after this delay. Press Ctrl+C now if wiring is not ready.")

    gpio_configured = False

    try:
        phase_1_startup_and_gpio_setup()
        gpio_configured = True

        phase_2_enable_toggle()
        phase_3_direction_test()
        phase_4_slow_step_pulses()
        phase_5_forward_speed_tests()
        phase_6_reverse_speed_tests()
        phase_7_continuous_rotation()

    except KeyboardInterrupt:
        log()
        log("KeyboardInterrupt received. Stopping test and cleaning up.")
    except Exception as exc:
        log()
        log(f"ERROR: {exc!r}")
        log("Stopping test and cleaning up GPIO.")
        raise
    finally:
        if gpio_configured:
            phase_8_cleanup()
        else:
            # If setup failed midway, cleanup is still harmless on Raspberry Pi.
            try:
                GPIO.cleanup()
                log("GPIO.cleanup completed after setup failure.")
            except Exception:
                pass

        log("Diagnostic script finished.")


if __name__ == "__main__":
    main()
