#!/usr/bin/env python3
"""
Simple TMC2209 stepper rotation test for Raspberry Pi OS.

Pins, using BCM numbering:
  STEP = GPIO17
  DIR  = GPIO27
  EN   = GPIO5

Run on the Raspberry Pi with:
  sudo python3 simple_rotation_test.py
"""

import time

import RPi.GPIO as GPIO


# These are BCM GPIO numbers, not physical Raspberry Pi header pin numbers.
# GPIO17 sends STEP pulses, GPIO27 chooses direction, and GPIO5 enables/disables
# the TMC2209 output stage.
STEP_PIN = 17
DIR_PIN = 27
EN_PIN = 5

# Most TMC2209 carrier boards use an active-low enable pin:
#   EN = LOW  -> motor driver outputs are ON
#   EN = HIGH -> motor driver outputs are OFF
# If your motor only locks when EN is HIGH, change this to False.
ENABLE_ACTIVE_LOW = True

# Your 36H012HM-03043043 motor specification says 0.9 degrees per full step:
#   360 degrees / 0.9 degrees = 400 full steps per mechanical revolution.
FULL_STEPS_PER_REVOLUTION = 400

# MICROSTEPS must match the TMC2209 configuration, not the motor itself.
# Examples:
#   full-step mode:       MICROSTEPS = 1
#   1/8 microstepping:    MICROSTEPS = 8
#   1/16 microstepping:   MICROSTEPS = 16
#   1/256 microstepping:  MICROSTEPS = 256
#
# Total STEP pulses for one shaft revolution are:
#   FULL_STEPS_PER_REVOLUTION * MICROSTEPS
#
# If 400 pulses does not make one full revolution, your TMC2209 is almost
# certainly using microstepping. For example, if it is set to 1/16 microstepping,
# one full shaft revolution needs 400 * 16 = 6400 STEP pulses.
#
# Your product specification says "256 microsteps". Some TMC2209 boards use
# that as the actual STEP/DIR input resolution, while others use a lower input
# resolution and internally interpolate to 256. If the motion is far too slow,
# check the board's MS1/MS2 jumpers or UART configuration and lower this value.
MICROSTEPS = 8
STEPS_PER_REVOLUTION = FULL_STEPS_PER_REVOLUTION * MICROSTEPS

# The script moves this many complete shaft revolutions forward, then the same
# number back in reverse.
ROTATIONS_PER_DIRECTION = 2

# STEP pulse timing:
#   1. Set STEP HIGH.
#   2. Optionally wait STEP_HIGH_SECONDS.
#   3. Set STEP LOW.
#   4. Optionally wait STEP_LOW_SECONDS.
#
# Target speed for the movement. With this 0.9 degree motor and 1/8
# microstepping, 1 revolution needs 3200 STEP pulses. A value of 120 RPM means
# 2 rotations per second, or 6400 STEP pulses per second.
#
# If the motor skips, buzzes, or rotates less than expected, reduce this value.
# If it moves reliably and you want more speed, increase it.
TARGET_RPM = 120

# The TMC2209 only needs a very short high pulse. The low time is calculated from
# TARGET_RPM so the full STEP pulse rate matches the requested motor speed.
STEP_HIGH_SECONDS = 0.00001

# Extra waits around the motion. These are kept near zero because this is meant
# to be a fast movement test, not a long diagnostic script.
START_DELAY_SECONDS = 0.0
ENABLE_SETTLE_SECONDS = 0.05
DIRECTION_PAUSE_SECONDS = 0.0


def enable_driver():
    """Turn on the TMC2209 motor outputs."""
    GPIO.output(EN_PIN, GPIO.LOW if ENABLE_ACTIVE_LOW else GPIO.HIGH)


def disable_driver():
    """Turn off the TMC2209 motor outputs."""
    GPIO.output(EN_PIN, GPIO.HIGH if ENABLE_ACTIVE_LOW else GPIO.LOW)


def step_once(step_low_seconds):
    """Send one STEP pulse to the TMC2209.

    Each pulse advances the motor by one configured driver step. In full-step
    mode that is one full motor step. In microstepping mode it is one microstep.
    """
    GPIO.output(STEP_PIN, GPIO.HIGH)
    if STEP_HIGH_SECONDS > 0:
        time.sleep(STEP_HIGH_SECONDS)
    GPIO.output(STEP_PIN, GPIO.LOW)
    if step_low_seconds > 0:
        time.sleep(step_low_seconds)


def rotate(label, direction, step_low_seconds):
    """Rotate a fixed number of revolutions in one direction."""
    total_steps = STEPS_PER_REVOLUTION * ROTATIONS_PER_DIRECTION

    print(f"Rotating {label}")

    # DIR is sampled by the driver when STEP pulses arrive. HIGH and LOW are
    # just opposite directions; which one is "forward" depends on motor wiring.
    GPIO.output(DIR_PIN, direction)

    # Send exactly enough STEP pulses for ROTATIONS_PER_DIRECTION full shaft
    # rotations, according to STEPS_PER_REVOLUTION above.
    for step in range(1, total_steps + 1):
        step_once(step_low_seconds)
        if step % STEPS_PER_REVOLUTION == 0:
            print(f"{label.title()}: {step // STEPS_PER_REVOLUTION}/{ROTATIONS_PER_DIRECTION} rotations")


def main():
    total_steps = STEPS_PER_REVOLUTION * ROTATIONS_PER_DIRECTION
    target_steps_per_second = (TARGET_RPM / 60.0) * STEPS_PER_REVOLUTION
    seconds_per_step = 1.0 / target_steps_per_second
    step_low_seconds = max(seconds_per_step - STEP_HIGH_SECONDS, 0.0)
    estimated_seconds_each_direction = total_steps / target_steps_per_second

    # Print the important configuration before moving the motor so mistakes in
    # microstepping or pin selection are visible immediately.
    print("Simple TMC2209 rotation test")
    print(f"STEP=GPIO{STEP_PIN}, DIR=GPIO{DIR_PIN}, EN=GPIO{EN_PIN}")
    print(f"Full steps per revolution: {FULL_STEPS_PER_REVOLUTION}")
    print(f"Microsteps: {MICROSTEPS}")
    print(f"Steps per revolution: {STEPS_PER_REVOLUTION}")
    print(f"Rotations each direction: {ROTATIONS_PER_DIRECTION}")
    print(f"Steps each direction: {total_steps}")
    print(f"Target speed: {TARGET_RPM:g} RPM")
    print(f"Target step rate: {target_steps_per_second:g} steps/sec")
    print(f"Pulse high time: {STEP_HIGH_SECONDS:g} seconds")
    print(f"Calculated pulse low time: {step_low_seconds:g} seconds")
    print(f"Estimated time each direction: {estimated_seconds_each_direction:g} seconds")
    print(f"Starting in {START_DELAY_SECONDS:g} seconds...")
    if START_DELAY_SECONDS > 0:
        time.sleep(START_DELAY_SECONDS)

    # Configure the Raspberry Pi GPIO library to use BCM GPIO numbers and start
    # STEP/DIR in known LOW states before enabling the driver.
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(STEP_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(DIR_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(EN_PIN, GPIO.OUT)

    try:
        # Enable the driver shortly before motion. The small settle time gives
        # the TMC2209 outputs a moment to energize the motor coils.
        print("Enabling driver")
        enable_driver()
        time.sleep(ENABLE_SETTLE_SECONDS)

        rotate("forward", GPIO.HIGH, step_low_seconds)

        print("Pause")
        if DIRECTION_PAUSE_SECONDS > 0:
            time.sleep(DIRECTION_PAUSE_SECONDS)

        rotate("reverse", GPIO.LOW, step_low_seconds)

        print("Done")

    finally:
        # Always leave the hardware in a quiet state, even if Ctrl+C or an error
        # interrupts the script.
        print("Disabling driver and cleaning up GPIO")
        disable_driver()
        GPIO.output(STEP_PIN, GPIO.LOW)
        GPIO.output(DIR_PIN, GPIO.LOW)
        GPIO.cleanup()


if __name__ == "__main__":
    main()
