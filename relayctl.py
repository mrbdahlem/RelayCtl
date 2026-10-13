#!/usr/bin/env python3
"""Set a serial relay and verify its reported state."""

import argparse
import math
import sys
import time


def positive_timeout(value):
    """Validate the CLI timeout so serial reads have a finite time limit."""
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number")

    return value


def parse_args(argv=None):
    """Read command-line options and check the channel against the board size."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="serial port, e.g. /dev/ttyUSB0 or COM3")
    parser.add_argument("channel", type=int, choices=range(1, 9), help="relay number (1–8)")
    parser.add_argument("state", type=str.lower, choices=("on", "off"))
    parser.add_argument("--channels", type=int, choices=range(1, 9), default=8,
                        help="number of relays/status bytes on the board (default: 8)")
    parser.add_argument("--timeout", type=positive_timeout, default=2.0,
                        help="status response timeout in seconds (default: 2)")

    args = parser.parse_args(argv)
    if args.channel > args.channels:
        parser.error("channel cannot exceed --channels")

    return args


def set_relay(connection, channel, state, channels, timeout):
    """Return the queried status; raise on incomplete or mismatched responses."""

    # The board represents on as 0x01 and off as 0x00.
    requested = int(state == "on")
    # Command layout: start flag, relay number, state, checksum.
    # The checksum is the sum of the first three bytes, kept to one byte.
    command = bytes((0xA0, channel, requested, (0xA0 + channel + requested) & 0xFF))

    # Discard any unread data left over from earlier communication.
    connection.reset_input_buffer()
    if connection.write(command) != len(command):
        raise RuntimeError("incomplete relay command write")
    connection.flush()  

    # Give the board time to process the command before requesting status.
    time.sleep(0.1)

    # Clear any command response before collecting the status query response.
    connection.reset_input_buffer()
    # A single binary 0xFF requests one status byte per relay, in channel order.
    if connection.write(b"\xff") != 1:
        raise RuntimeError("incomplete status query write")
    connection.flush()

    status = bytearray()
    # Serial reads can return partial responses. Use one overall deadline so
    # receiving several chunks does not restart the timeout each time.
    deadline = time.monotonic() + timeout
    while len(status) < channels:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        connection.timeout = remaining
        chunk = connection.read(channels - len(status))
        if not chunk:
            break
        status.extend(chunk)

    # A short response or a byte other than 0/1 cannot confirm the relay state.
    if len(status) != channels:
        raise RuntimeError(f"status query returned {len(status)} of {channels} expected bytes")
    if any(value not in (0, 1) for value in status):
        raise RuntimeError(f"invalid status response: {status.hex(' ')}")

    # Relay numbers start at 1, while the response byte indexes start at 0.
    if status[channel - 1] != requested:
        actual = "on" if status[channel - 1] else "off"
        raise RuntimeError(f"verification failed: relay {channel} reports {actual}, expected {state}")

    return bytes(status)


def main(argv=None):
    """Open the port, verify the operation, and return a process exit code."""
    args = parse_args(argv)

    # Import after parsing so --help works even before pyserial is installed.
    try:
        import serial
    except ImportError:
        print("Error: pyserial is required; install it with python3 -m pip install pyserial", file=sys.stderr)
        return 1

    try:
        # Use the board's 9600 baud, 8N1 settings without flow control.
        # The context manager closes the port on both success and failure.
        with serial.Serial(args.port, baudrate=9600, bytesize=serial.EIGHTBITS,
                           parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                           timeout=args.timeout, write_timeout=args.timeout,
                           xonxoff=False, rtscts=False, dsrdtr=False) as connection:
            set_relay(connection, args.channel, args.state, args.channels, args.timeout)
    except (serial.SerialException, OSError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Relay {args.channel} verified {args.state} on {args.port}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
