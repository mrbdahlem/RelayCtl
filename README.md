# RelayCtl

Control a CH340 serial relay board and verify its reported state using the `FF` status query.

Install the dependency:

```sh
python3 -m pip install -r requirements.txt
```

Turn relay 1 on or relay 2 off:

```sh
python3 relayctl.py /dev/ttyUSB0 1 on
python3 relayctl.py /dev/ttyUSB0 2 off
python3 relayctl.py COM3 1 on
```

The serial connection uses 9600 baud, 8 data bits, no parity, one stop bit, and no flow control. Commands are sent as binary bytes, with the checksum equal to the sum of the first three bytes. After a 100 ms processing delay, the program sends `FF` and reads the board's status bytes. Each must be `00` or `01`, and the requested relay must match the requested state.

Eight status bytes are expected by default. For a smaller board, specify its relay count:

```sh
python3 relayctl.py /dev/ttyUSB0 2 on --channels 2 --timeout 3
```

Exit status is `0` for verified success, `1` for connection, communication, or verification failure, and `2` for invalid arguments. Verification checks the board's reported state; it cannot confirm physical contact operation. Install the CH340 driver if your operating system does not expose the serial port.
