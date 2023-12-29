# GCode.py
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

import logging
import functools

class GCodeCommand:

    verb:str = '' # String of GCode Command Verb (ex. 'G1', 'M05')
    parameters:dict = {} # Dictionary of parameters to verb and their values (ex. {'X':3.1 'Y':4.1 'Z':5.9})
    comment:str = ''

    def _getNum(self, number:str):
        '''Returns the value as an integer or float based off context'''
        try:
            try:
                return int(number)
            except ValueError:
                return float(number)
        except ValueError:
            return number

    def getFullCommand(self) -> str:
        '''Returns the full command, with comments'''

        text = self.getCommand()

        if self.comment:
            text = text + '; ' + self.comment

        return text

    def getCommand(self) -> str:
        '''Returns just the command, no comments'''
        text = self.verb

        for key, value in self.parameters.items():

            text = text + ' ' + key
            if not type(value) == str:
                text = text + str(round(value,5))

        return text

    def isACommand(self) -> bool:
        '''Returns if the command is actually a command, not just a comment'''
        return self.verb != ''

class StringGCodeCommand(GCodeCommand):
    '''Creates a GCodeCommand based off of string'''


    def __init__(self, string: str):            
        
        self.verb, parameters, self.comment = self._tokenize(string)
        self.parameters = {i[0]:self._getNum(i[1:]) for i in parameters}

    def _tokenize(self, string:str) -> tuple:
        '''Returns the command as a tuple of tokens
        In the format of (Command, [Params], Comment)
        ex. ('G1', ['X3.14', 'Y2.72', 'Z6.28'], ' Go to (pi, e, tau)')
        '''

        sections = string.partition(';')

        command = sections[0].rstrip(' ')

        comment = sections[2].lstrip(' ')
    
        if command:
            commandTokens = command.split()

            verb = commandTokens[0]
            parameters = commandTokens[1:]
        else:
            verb = ''
            parameters = []

        return verb, parameters, comment    

class GCodeScript:

    lines: list[GCodeCommand] = [] # All lines of the script as GCodeCommands

    def loadFromFile(self, file):
        self.loadFromString(file.read())

    def loadFromString(self, string:str):
        lines = string.split('\n')
        self.lines = [StringGCodeCommand(line.rstrip('\n')) for line in lines]

    def orient(self):
        '''Moves model to be in the +X +Y from the start'''

        # Find minimum X and Y
        xArgs = [command.parameters['X'] for command in self.lines if 'X' in command.parameters.keys()]
        yArgs = [command.parameters['Y'] for command in self.lines if 'Y' in command.parameters.keys()]
        minx = min([x for x in xArgs if type(x) != str])
        miny = min([y for y in yArgs if type(y) != str])

        # Translate all commands by minx, miny
        for command in self.lines:
            if 'X' in command.parameters.keys():
                if type(command.parameters['X']) != str: command.parameters['X'] -= minx
            if 'Y' in command.parameters.keys():
                if type(command.parameters['Y']) != str: command.parameters['Y'] -= miny

    def shrink(self):
        '''Removes all unneccessary data from the script (ex. comments)'''

        self._cleanCommandsFromList(self.lines)
        logging.debug("Shrunk Commands")

    def _cleanCommandsFromList(self, lines:list):
        for command in lines:
            if command.isACommand():
                command.comment=''
            else:
                lines.remove(command)

class GCodeScriptCNC(GCodeScript):
    '''GCodeScript with CNC-specific functions'''
    clearance:float = 3.0
    travelSpeed:int = 500
    feedSpeed:int = 200
    spindleSpeed:int = 10000
    prefixGcode: list[GCodeCommand] = []
    suffixGcode: list[GCodeCommand] = []

    def shrink(self):
        super().shrink()
        self._cleanCommandsFromList(self.prefixGcode)
        self._cleanCommandsFromList(self.suffixGcode)


class GCodeScriptPrinter(GCodeScript):
    '''GCodeScript with 3D-Printer specific functions'''

    typeIndicies: dict = []
    layerIndicies: list[int] = []
    
    def computeLayerIndices(self):
        '''Returns the command indicies of layer changes.
        Works with GCode generated by PrusaSlicer and Cura, possibly more'''

        layerIndicies = [] # Lines at which layer shifts occur

        for index, command in enumerate(self.lines):
            if "LAYER" in command.comment and "BEFORE" not in command.comment and "AFTER" not in command.comment:
                layerIndicies.append(index)

        # Cura puts a LAYER_COUNT comment into GCode that causes this 
        # tho think it is a layer shift.
        
        # Remove false layer shift
        if self.getSlicingEngine() == "Cura":
            layerIndicies.pop(1)

        self.layerIndicies = layerIndicies

    def getLayer(self, commandIndex:int, recompute=True) -> int:
        '''Returns the layer command at commandIndex occurs at'''

        if recompute: self.computeLayerIndices()

        for index in range(len(self.layerIndicies)-1, -1, -1):
            if self.layerIndicies[index] <= commandIndex:
                return index
        return None

    def getSlicingEngine(self) -> str:
        '''Returns the slicer used on the GCode'''

        if "PrusaSlicer" in self.lines[0].comment: 
            return "PrusaSlicer"

        for command in self.lines:
            if "Cura" in command.comment: 
                return "Cura"

        logging.warn("Slicer not detected")
        return "Other"

    def computeTypeChanges(self):
        '''Returns dictionary of indices of changes in line types and the new type''' 

        typeIndicies = {0:"None"} # Lines at which line type changes occur

        for index, command in enumerate(self.lines):
            if "TYPE:" in command.comment:
                typeIndicies[index] = command.comment.removeprefix("TYPE:")

        self.typeIndicies = typeIndicies

    def getType(self, commandIndex:int, recompute=True):
        '''Returns the print type at commandIndex'''

        if recompute: self.computeTypeChanges()

        for key, value in list(self.typeIndicies.items())[::-1]:
            if key <= commandIndex:
                return value
        
        raise ValueError("Could not detect types")

class GCodeScriptCNCFromGCodeScriptPrinter(GCodeScriptCNC, GCodeScriptPrinter):
    '''Converts GCodeScriptPrinter to GCodeScriptCNC'''

    USABLE_COMMANDS = ["G1", "G0"] # List of commands that can be converted to CNC GCode commands

    def __init__(self, printerScipt: GCodeScriptPrinter):
        
        self.lines = printerScipt.lines

    def convert(self):
        
        # Remove Printer-specific parameters
        for command in self.lines:
            if 'E' in command.parameters:
                del command.parameters['E']
            if 'F' in command.parameters:
                del command.parameters['F']

        # Remove Printer-Specific Commands
        toRemove = []
        for command in self.lines:
            if self._isPrinterSpecificCommand(command):
                toRemove.append(command)

        for i in toRemove: self.lines.remove(i)

        logging.debug("Removed Printer-Specific Commands")

        # Mirror Z axis to make it carve down
        for command in self.lines:
            if 'Z' in command.parameters.keys():
                command.parameters['Z'] = -1*command.parameters['Z']

        logging.debug("Mirroed Z Axis")

        # Remove multi-line travels
        altered = True
        while altered:
            altered = False
            for index, command in enumerate(self.lines):
                oldCommand = self.getCommandRelativeToIndex(index, -1)
                if 'G0' == command.verb and 'G0' == oldCommand.verb:
                    if 'Z' in oldCommand.parameters.keys():
                        command.parameters['Z'] = oldCommand.parameters['Z']
                    self.lines.remove(self.getCommandRelativeToIndex(index, -1))
                    altered = True

        logging.debug("Removed Multi-Line travels")

        # Convert printer travels to CNC travels
        altitude = 0
        for index, command in enumerate(self.lines):
            if 'Z' in command.parameters.keys():
                altitude = command.parameters['Z']

            if command.verb == "G0":
                oldCommand = self.getCommandRelativeToIndex(index, -1)
                endPosition = command.parameters['X'], command.parameters['Y']
                self.lines.insert(index, StringGCodeCommand(f"G1 Z{self.clearance} F{self.travelSpeed}"))
                self.lines.insert(index+1, StringGCodeCommand(f"G1 X{endPosition[0]} Y{endPosition[1]}"))
                if 'Z' in command.parameters.keys():
                    newAltitude = command.parameters['Z']
                else:
                    newAltitude = altitude
                self.lines[index+2] = StringGCodeCommand(f"G1 Z{newAltitude} F{self.feedSpeed}")

        logging.debug("Converted from Printer travels to CNC travels")

    def export(self) -> str:
        '''Returns the GCode Script as a string'''

        final = self.prefixGcode
        final.extend(self.lines)
        final.extend(self.suffixGcode)
        
        result = ''

        for command in final:
            result = result + command.getFullCommand() + '\n'

        return result

    def getCommandRelativeToIndex(self, index:int, offset:int):
        '''Returns command at index+offset skipping over comments'''

        iteration = offset//abs(offset) # Get sign of offset and use that to iterate
        currentOffset = 0

        while currentOffset != offset:
            index += iteration
            if self.lines[index].isACommand(): currentOffset += iteration

        return self.lines[index]


    def _isPrinterSpecificCommand(self, command: GCodeCommand) -> bool:
        if command.verb not in self.USABLE_COMMANDS: return True
        return False

    def removeInfill(self, infillFrequency:int):
        '''Removes uneccessary infill to speed up Mill time.
        Keeps infill only every infillFrequency layers.
        Call before running convert()'''

        toPop = []

        self.computeLayerIndices()
        self.computeTypeChanges()

        for index in range(len(self.lines)):            
            
            if "fill" in self.getType(index, recompute=False).lower() and self.getLayer(index, recompute=False)%infillFrequency != 0:
                command = self.lines[index]
                if command.verb != "G0": toPop.append(index) # Keep travels so layer shifts aren't broken

        for pop in toPop[::-1]:
            self.lines.pop(pop)