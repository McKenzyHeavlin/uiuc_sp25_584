#!/usr/bin/env python3
"""Pymodbus asynchronous client example.

usage::

    client_async.py [-h] [-c {tcp,udp,serial,tls}]
                    [-f {ascii,rtu,socket,tls}]
                    [-l {critical,error,warning,info,debug}] [-p PORT]
                    [--baudrate BAUDRATE] [--host HOST]

    -h, --help
        show this help message and exit
    -c, -comm {tcp,udp,serial,tls}
        set communication, default is tcp
    -f, --framer {ascii,rtu,socket,tls}
        set framer, default depends on --comm
    -l, --log {critical,error,warning,info,debug}
        set log level, default is info
    -p, --port PORT
        set port
    --baudrate BAUDRATE
        set serial device baud rate
    --host HOST
        set host, default is 127.0.0.1

The corresponding server must be started before e.g. as:
    python3 server_sync.py
"""
import asyncio
import logging
import sys
import pdb

try:
    import helper
except ImportError:
    print("*** ERROR --> THIS EXAMPLE needs the example directory, please see \n\
          https://pymodbus.readthedocs.io/en/latest/source/examples.html\n\
          for more information.")
    sys.exit(-1)

import pymodbus.client as modbusClient
from pymodbus import ModbusException


_logger = logging.getLogger(__file__)
logging.basicConfig(filename='async_client.log', level=logging.DEBUG)
_logger.setLevel("DEBUG")


def setup_async_client(description=None, cmdline=None):
    """Run client setup."""
    args = helper.get_commandline(
        server=False, description=description, cmdline=cmdline
    )
    _logger.info("### Create client object")
    client = None
    if args.comm == "tcp":
        client = modbusClient.AsyncModbusTcpClient(
            args.host,
            port=args.port,  # on which port
            # Common optional parameters:
            framer=args.framer,
            timeout=args.timeout,
            retries=3,
            reconnect_delay=1,
            reconnect_delay_max=10,
            #    source_address=("localhost", 0),
        )
    elif args.comm == "udp":
        client = modbusClient.AsyncModbusUdpClient(
            args.host,
            port=args.port,
            # Common optional parameters:
            framer=args.framer,
            timeout=args.timeout,
            #    retries=3,
            # UDP setup parameters
            #    source_address=None,
        )
    elif args.comm == "serial":
        client = modbusClient.AsyncModbusSerialClient(
            args.port,
            # Common optional parameters:
            #    framer=ModbusRtuFramer,
            timeout=args.timeout,
            #    retries=3,
            # Serial setup parameters
            baudrate=args.baudrate,
            #    bytesize=8,
            #    parity="N",
            #    stopbits=1,
            #    handle_local_echo=False,
        )
    elif args.comm == "tls":
        client = modbusClient.AsyncModbusTlsClient(
            args.host,
            port=args.port,
            # Common optional parameters:
            framer=args.framer,
            timeout=args.timeout,
            #    retries=3,
            # TLS setup parameters
            sslctx=modbusClient.AsyncModbusTlsClient.generate_ssl(
                certfile=helper.get_certificate("crt"),
                keyfile=helper.get_certificate("key"),
            #    password="none",
            ),
        )
    else:
        raise RuntimeError(f"Unknown commtype {args.comm}")
    return client


async def run_async_client(client, modbus_calls=None):
    """Run sync client."""
    _logger.info("### Client starting")
    await client.connect()
    assert client.connected
    if modbus_calls:
        await modbus_calls(client)
    client.close()
    _logger.info("### End of Program")


async def run_a_few_calls(client):
    """Test connection works."""
    try:
        guard = False
        prev_level = 0
        inputGuessRate = 0
        outputGuessRate = 0
        update = 5.0
        avg_flow_out = 0

        while True:
            await asyncio.sleep(update)

            # Get current state of the system from the coils and registers
            rr = await client.read_coils(0, 2, slave=1)
            output_coils = rr.bits
            rr = await client.read_discrete_inputs(3, 4, slave=1)
            discrete_inputs = rr.bits
            rr = await client.read_holding_registers(8, 1, slave=1)
            registers = rr.registers

            prev_input_coil_value = output_coils[0]
            prev_output_coil_value = output_coils[1]
            current_level = registers[0]

            input_coil_value = False
            output_coil_value = False
            # Logic for checking/printing unofficial alerts
            if discrete_inputs[2]:
                print(f"\t*** WARNING: Tank Level Above HIGH Threshold at {registers[0]}.")
                if not output_coils[0] and registers[0] == 1000:
                    print(f"ALERT: Tank Level at Capacity at 1000 Levels.")
            if not discrete_inputs[3]:
                print(f"\t*** WARNING: Tank Level Below LOW Threshold at {registers[0]}.")
                if not output_coils[1] and registers[0] == 0:
                    print("!!! ALERT: Tank Level is Empty at 0 Levels.")

            # Logic for setting the input/output coils
            if discrete_inputs[0] and discrete_inputs[1]:
                if guard:
                    if (current_level - prev_level) >= 0:
                        inputGuessRate = (current_level - prev_level) / update
                    else:
                        outputGuessRate = (current_level - prev_level) / update
                if prev_input_coil_value:
                    if (avg_flow_out + inputGuessRate*update)/2 < 0.45*outputGuessRate:
                        input_coil_value = prev_input_coil_value
                        output_coil_value = not prev_input_coil_value
                        avg_flow_out = (avg_flow_out + inputGuessRate*update)/2
                    elif (avg_flow_out + inputGuessRate*update)/2 > 0.55*outputGuessRate:
                        input_coil_value = not prev_input_coil_value
                        output_coil_value = prev_input_coil_value
                        avg_flow_out = (avg_flow_out + inputGuessRate*update)/2
                elif prev_output_coil_value:
                    if (avg_flow_out + outputGuessRate*update)/2 > 0.55*outputGuessRate:
                        input_coil_value = not prev_output_coil_value
                        output_coil_value = prev_output_coil_value
                        avg_flow_out = (avg_flow_out + inputGuessRate*update)/2
                    elif (avg_flow_out + outputGuessRate*update)/2 < 0.45*outputGuessRate:
                        input_coil_value = prev_output_coil_value
                        output_coil_value = not prev_output_coil_value
                        avg_flow_out = (avg_flow_out + inputGuessRate*update)/2
                elif discrete_inputs[2]:
                    input_coil_value = 0
                    output_coil_value = 1
                    avg_flow_out = (avg_flow_out + outputGuessRate*update)/2
                elif not discrete_inputs[3]:
                    input_coil_value = 1
                    output_coil_value = 0
                    avg_flow_out = (avg_flow_out + inputGuessRate*update)/2
                else:
                    print("\t*** WARNING: BRB and DRAIN set but discrete input combination not recognized.")
            elif discrete_inputs[0]: 
                avg_flow_out = 0 # BRB and DRAIN not pushed, so reset avg_flow_out to prep for next time
                if not discrete_inputs[2]:
                    # print("BRB AND NOT HIGH")
                    input_coil_value = True
                    output_coil_value = False
                else:
                    input_coil_value = False
                    output_coil_value = True
            elif discrete_inputs[1]:
                avg_flow_out = 0 # BRB and DRAIN not pushed, so reset avg_flow_out to prep for next time
                if discrete_inputs[3]:
                    # print("DRAIN AND LOW")
                    input_coil_value = False
                    output_coil_value = True
                else:
                    input_coil_value = True
                    output_coil_value = False

            # Enforce restriction that input and output valves cannot be open simultaneously
            if input_coil_value == output_coil_value and input_coil_value:
                print("!!! ALERT: Attempted to open input and output valves simultaneously. Resetting coils to previous values.")
                input_coil_value = prev_input_coil_value
                output_coil_value = prev_output_coil_value
            
            prev_level = current_level
            guard = True
            await client.write_coil(0, input_coil_value, slave=1)
            await client.write_coil(1, output_coil_value, slave=1)

    except ModbusException:
        pass


async def main(cmdline=None):
    """Combine setup and run."""
    testclient = setup_async_client(description="Run client.", cmdline=cmdline)
    print
    await run_async_client(testclient, modbus_calls=run_a_few_calls)


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
