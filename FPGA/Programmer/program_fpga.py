#
# Pi5-Artix50T-Hat FPGA Programming Script (Xilinx Serial Serial)
# Based on Xilinx App Note XAPP583 May 2012
# Python Driver: March 2024 by George Smart, M1GEO
# https://github.com/m1geo/Pi5-Artix-FPGA-Hat
#

### WARNING: THIS CODE HAS UNDERGONE MINIMAL TESTING! BE CAREFUL!


# Requirements
# - spidev
# - lgpio


"""
    HOW IT WORKS

    1. Power-up or Configuration Reset (Wait until INIT_B goes LOW)
    2. Device Initialization (Wait until INIT_B goes HIGH)
    3. Configuration Bitstream Load
        If INIT_B goes LOW at any time during load, this indicates an error
    4. Special Startup Conditions Compensation
        If DONE remains low at this point the process was a failure, goto #0
        Ff DONE goes HIGH, then all good, goto #5
    5. Configuration Complete
    0. Pulse PROGRAM_B to logic LOW to initalise a new programing cycle
"""

# Bitfile path to send
#bitfile = "../Blinky/blinky_example.bit"
bitfile = "../pcie_7x_0_ex/pcie_7x_0_ex.runs/impl_1/xilinx_pcie_2_1_ep_7x.bit"


import time
import lgpio # Linux SBC GPIO Driver: see https://pypi.org/project/lgpio/
import spidev # RasPi SPI Driver: see https://pypi.org/project/spidev/


### lgpio Boilerplate
gpio = lgpio.gpiochip_open(4) # 4 is correct for Pi5 with RP1 dynamic GPIO mem (/dev/gpiochip4). 0 for Pi4/CM4.
FPGA_DONE  = 23 # GPIO23
FPGA_INITB = 24 # GPIO24
FPGA_PROGB = 25 # GPIO25
HIGH = True
LOW = False
# Hi-Z inputs
lgpio.gpio_claim_input(gpio, FPGA_DONE)
lgpio.gpio_claim_input(gpio, FPGA_INITB)
lgpio.gpio_claim_input(gpio, FPGA_PROGB)


### SpiDev Object
# WARNING: SPI Modes 1 and 3 do not appear to work on the auxiliary SPI.
spi = spidev.SpiDev()
spi.open(0, 0) # (bus, dev): bus=0 and device doesn't matter as we aren't using HW nCS.
spi.no_cs # No CS. PROGB and INITB are needed.
#spi.lsbfirst # Xilinx diagrams show LSB first. Works either way.
spi.max_speed_hz = int(100e6) # Xilinx will tollerate fast speeds, but slow for debugging
# 32K-125M (values above 30M are unlikely to work?).
spi.mode = 0 # Xilinx diagram show SPI Mode 0 (CPOL=0, CPHA=0).
#spi.mode = 3 # SPI Mode 3 (CPOL=1, CPHA=1) may also work, but then clock idles high


### Dump Control Pin Status
def pin_status():
    pprog = lgpio.gpio_read(gpio, FPGA_PROGB)
    pinit = lgpio.gpio_read(gpio, FPGA_INITB)
    pdone = lgpio.gpio_read(gpio, FPGA_DONE)
    print("PROG ", pprog)
    print("INIT ", pinit)
    print("DONE ", pdone)
    return (pprog, pinit, pdone)


### Reset FPGA
# TODO: Pythonise this
def reset_fpga():
    lgpio.gpio_claim_input(gpio, FPGA_INITB)
    lgpio.gpio_write(gpio, FPGA_PROGB, HIGH) # Output buffer to high (still Hi-Z)
    lgpio.gpio_claim_output(gpio, FPGA_PROGB) # Drive high onto PROG_B line
    lgpio.gpio_write(gpio, FPGA_PROGB, LOW) # Assert program reset
    waitcount = 0
    while lgpio.gpio_read(gpio, FPGA_INITB) > 0 and waitcount < 20:
        time.sleep(0.1)
        waitcount += 1
    if waitcount >= 10:
        print("Error: FPGA didn't respond to reprogram request")
        pin_status()
        return -1
    lgpio.gpio_write(gpio, FPGA_PROGB, HIGH) # Deassert program reset
    lgpio.gpio_claim_input(gpio, FPGA_PROGB) # Hi-Z PROG_B (hardware pullup)
    waitcount = 0
    while lgpio.gpio_read(gpio, FPGA_INITB) == 0 and waitcount < 20:
        time.sleep(0.1)
        waitcount += 1
    if waitcount >= 10:
        print("Error: FPGA didn't reinitialise after reset")
        pin_status()
        return -1
    print("FPGA reset and ready") # INIT_B now high


### Parse Bitfile Header
# TODO: Do this Pythonically, this is a mess!!
#       Read the spec, and don't guess: missing architecture and bitlength.
def parse_bitfile_header(data):
    # Parse Bitfile Header
    #     in     fnd   st
    a = [False, False, ""]
    b = [False, False, ""]
    c = [False, False, ""]
    d = [False, False, ""]
    
    for idx in range(len(data)):
        # Find A
        if data[idx-1] == 97 and data[idx] == 0 and a[1] == False:
            a[0] = True
            continue
        if a[0]:
            if data[idx] == 0:
                a[0] = False
                a[1] = True
                continue
            a[2] += chr(data[idx])
        # Find B
        if data[idx-1] == 98 and data[idx] == 0 and b[1] == False:
            b[0] = True
            continue
        if b[0]:
            if data[idx] == 0:
                b[0] = False
                b[1] = True
                continue
            b[2] += chr(data[idx])
        # Find C
        if data[idx-1] == 99 and data[idx] == 0 and c[1] == False:
            c[0] = True
            continue
        if c[0]:
            if data[idx] == 0:
                c[0] = False
                c[1] = True
                continue
            c[2] += chr(data[idx])
        # Find D
        if data[idx-1] == 100 and data[idx] == 0 and d[1] == False:
            d[0] = True
            continue
        if d[0]:
            if data[idx] == 0:
                d[0] = False
                d[1] = True
                continue
            d[2] += chr(data[idx])
        if (a[1] and b[1] and c[1] and d[1]):
            break

    return (a[2].strip(), b[2].strip(), c[2].strip() + " " + d[2].strip())


### Program FPGA
# FPGA reads on rising clock edge. Diagrams show clock low at idle. This is SPI-Mode 0.
# TODO: ?
def program_fpga(data):
    timestart = time.time()
    spi.xfer3(data) # send bitstream

    if lgpio.gpio_read(gpio, FPGA_INITB) == 0:
        print("Error: The FPGA got fed up with our junk being sent at it!")
        return -1
    timefinish = time.time()
    timeelapsed = (timefinish - timestart)
    databits = (len(data)*8)
    datarate = (databits/timeelapsed)
    print("Bitstream sent: %u bytes in %.1f seconds (%.1f kbps [%.1f%% of SPI CLK]) " % (databits/8, timeelapsed, datarate/1024, 100*(datarate/spi.max_speed_hz)))
    print("Waiting for Done.")
    waitcount = 0
    while lgpio.gpio_read(gpio, FPGA_DONE) == 0 and waitcount < 20:
        time.sleep(0.1)
        waitcount += 1
    if waitcount >= 20:
        print("Error: The FPGA listened intently, but rejected our bitstream!")
        pin_status()
        return -1
    print("Bitstream Done. Sending SSC CCLK.") # DONE now HIGH
    # Special Start-Up Conditions, apply 8 additional clock cycles after DONE goes HIGH.
    spi.xfer3([0xFF]) # compensate for 'Special Startup Conditions' (send 8 clocks with DIN=1)
    print("All done!")

###
### MAIN CODE
###


### Reset FPGA
reset_fpga()


### Read In Bitstream File
print("Opening '%s'. " % (bitfile))
f = open(bitfile, mode="rb")
bitfiledata = f.read() # read entire file in
f.close()
print("Read '%u' bytes" % (len(bitfiledata)))


### Parse Bitstream Header
(designname,xilpart,bfts) = parse_bitfile_header(bitfiledata)
print("Design Name: %s" % (designname))
print("Xilinx Part: %s" % (xilpart))
print("Timestamp:   %s" % (bfts))


### Send Bitstream to FPGA
program_fpga(bitfiledata)


# Tidy our toys away
spi.close()
lgpio.gpiochip_close(gpio)
