# main.py
#
# Copyright 2023 LostMyByte
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# SPDX-License-Identifier: LGPL-2.1-or-later

import GCode
import logging
import argparse

DEFAULT_PREFIX ="""G1 X0 Y{clearance} Z0
G92 X0 Y0 Z0
G90
G1 Z{clearance} F{travelRate}
G1 X0 Y0
M03 S{spindleSpeed}"""

DEFAULT_SUFFIX = """G1 Z{clearance} F{travelRate}
M05
G1 X0 Y0 M30"""


# Add commmand-line Arguments
parser = argparse.ArgumentParser(description="Convert 3D Printer GCode to CNC GCode")
parser.add_argument("SOURCE", type=argparse.FileType('r'))
parser.add_argument("DEST", type=argparse.FileType('w'))
parser.add_argument("-c", "--clearance", help="Height above the model to use during travels", type=int, default=3)
parser.add_argument("-f", "--feedrate", help="Speed to move while milling", type=int, default=200)
parser.add_argument("-i", "--infill-frequency", help = "How often to keep infill (in layers)", default=10, type=int)
parser.add_argument("-k", "--keep-infill", help="Do not remove excess infill", action="store_true", default=False)
parser.add_argument("-n", "--no-orient", help="Do not move model to origin", action="store_true", default=False)
parser.add_argument("--prefix", type=str, default=DEFAULT_PREFIX, help="GCode to prepend instructions with. Defaults to a generic initialization sequence")
parser.add_argument("--suffix", type=str, default=DEFAULT_SUFFIX, help="GCode to append instructions with. Defaults to a generic ending sequence")
parser.add_argument("-s", "--spindle-speed", help="Spindle rotation speed", type=int, default=10000)
parser.add_argument("--shrink", help="Shrink file size as much as possible", action="store_true", default=False)
parser.add_argument("-t", "--travelrate", help="Speed to move while travelling", type=int, default=500)
parser.add_argument("-v", "--verbose", action="store_true", default=False)

args = parser.parse_args()

# Configure logging
logging.basicConfig(format = "[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger()
if args.verbose: logger.setLevel(logging.DEBUG)
else: logger.setLevel(logging.INFO)

printerGcode = GCode.GCodeScriptPrinter()
printerGcode.loadFromFile(args.SOURCE)

# Load converter
GCodeCNC = GCode.GCodeScriptCNCFromGCodeScriptPrinter(printerGcode)
GCodeCNC.clearance = args.clearance
GCodeCNC.feedSpeed = args.feedrate
GCodeCNC.travelSpeed = args.travelrate
GCodeCNC.spindleSpeed = args.spindle_speed

logging.info("Loaded GCode")

# Do optional transformations
if not args.keep_infill: 
    GCodeCNC.removeInfill(args.infill_frequency)
    logging.debug("Infill Removed")
if not args.no_orient: 
    GCodeCNC.orient()
    logging.debug("Model Oriented")

logging.info("Completed optional transformations")

# Convert
GCodeCNC.convert()

# Add prefix and suffix and export
prefixGcode = GCode.GCodeScript()
prefixGcode.loadFromString(args.prefix.format(clearance=args.clearance, feedRate=args.feedrate, infillFrequency=args.infill_frequency, spindleSpeed=args.spindle_speed, travelRate=args.travelrate))
GCodeCNC.prefixGcode = prefixGcode.lines

suffixGcode = GCode.GCodeScript()
suffixGcode.loadFromString(args.suffix.format(clearance=args.clearance, feedRate=args.feedrate, infillFrequency=args.infill_frequency, spindleSpeed=args.spindle_speed, travelRate=args.travelrate))
GCodeCNC.suffixGcode = suffixGcode.lines

if args.shrink:
    GCodeCNC.shrink()

output = GCodeCNC.export()

logging.info("Done")

args.DEST.truncate()
args.DEST.write(output)