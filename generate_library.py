#==============================================================================
# This file is part of KicadFPGA
#
# KicadFPGA is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# KicadFPGA is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# KicadFPGA. If not, see <https://www.gnu.org/licenses/>.
#==============================================================================
#
# generate_library.py
#
# This will take a list of vhdl/verilog files and create or update a kicad
# library to include the symbols defined within the files.

from __future__ import annotations

from os import path
import re
import os
import glob
import argparse

from kiutils.symbol import Symbol, SymbolPin, SymbolLib
from kiutils.items.common import Effects, Position, Property, Font
from kiutils.items.syitems import *


# please use hdlparse from https://github.com/hdl/pyHDLParser
# pip install --upgrade https://github.com/hdl/pyhdlparser/tarball/master
from hdlparse import verilog_parser 
from hdlparse import vhdl_parser

vlog_extract = verilog_parser.VerilogExtractor()
vhdl_extract = vhdl_parser.VhdlExtractor()

# Some notes -
#   there are multiple flows required:
#   1) no library present - generate from source files - done
#   2) library present but no source files - generate skeleton modules
#   3) both present - update library from source files
#   4) both present - update source files from library changes (rare)

# Signal types defined:
#  <none> - std_logic or boolean
#  sfixed - sfixed with size inferred from connections
#  ufixed - ufixed with size inferred from connections
#  slv    - std_logic_vector with size inferred from connections
#  s13.2  - sfixed(12 downto -2)
#  s15    - signed(14 downto 0)  or sfixed(14 downto 0)
#  u12.8  - ufixed(11 downto -8)
#  u23    - unsigned(22 downto 0) or ufixed(22 downto 0)
#  14:3   - std_logic_vector(14 downto 3) or unsigned(14 downto 3)
#  DW-1:0 - std_logic_vector(DW-1 downto 0); DW must be a generic or parameter



def find_property(proplist: list[Property], value):
    for x in proplist:
        if x.key == value:
            return x
    return None

def parse_port(port):
    # convert Verilog ports to VHDL type to get the metadata sorted out
    if type(port) == verilog_parser.VerilogParameter:
        # Examples:
        #   wire
        #   wire [AW-1:0]
        #   reg [3:0]
        #   [    15 : 0]
        #   signed [5:0]
        #   reg [8*20:0]
        #vport = verilog_parser.VerilogParameter()

        new_port = vhdl_parser.VhdlParameter(port.name)
        match = re.search(r'\[\s*(.*?)\s*:\s*(.*?)\s*\]', port.data_type) # Match the lbound and rbound if [, : and ] are present but remove all whitespace
        if match:
            name = 'std_logic_vector'
            l_bound, r_bound = match.groups()
            direction = 'downto'
            arange = f'({l_bound} downto {r_bound})'
        else:
            name = 'std_logic'
            l_bound, r_bound = '', ''
            direction = ''
            arange = ''
        new_port.data_type = vhdl_parser.VhdlParameterType(name=name, direction=direction, r_bound=r_bound, l_bound=l_bound, arange=arange)

        new_port.default_value = port.default_value
        new_port.desc          = port.desc
        new_port.mode          = port.mode
        port = new_port

    # now to encode into the shortform version
    return port

def port_name(port : vhdl_parser.VhdlParameter):
    # shortform just to make things quicker
    dt = port.data_type

    if dt.l_bound and dt.r_bound:
        try:
            #l_bound = int(dt.l_bound)
            #r_bound = int(dt.r_bound)
            #if r_bound == 0:  rangestr = f"{l_bound+1}"
            #elif r_bound < 0: rangestr = f"{l_bound+1}.{-r_bound}"
            #else:             rangestr = f"{l_bound}:{r_bound}" # default for positive r_bounds
            rangestr = f"{dt.l_bound}:{dt.r_bound}"
        except ValueError:
            rangestr = f"{dt.l_bound}:{dt.r_bound}"

        if   dt.name.lower() in ['std_logic', 'boolean']:    typestr = ''
        elif dt.name.lower() in ['std_logic_vector', 'slv']: typestr = f"({rangestr})"
        elif dt.name.lower() in ['sfixed', 'signed']:        typestr = f"(s{rangestr})"
        elif dt.name.lower() in ['ufixed', 'unsigned']:      typestr = f"(u{rangestr})"
        else:                                                typestr = f"({dt.name} {rangestr})" # unknown type

    else:
        if dt.name.lower() in ['std_logic', 'boolean']: typestr = ''
        elif dt.name.lower() == 'std_logic_vector':     typestr = '(slv)'
        else: typestr = f"({dt.name})"
    
    return f"{port.name}{typestr}"

def create_symbols(filename : str):
    hdl_info = vlog_extract.extract_objects(filename)
    if not hdl_info:
        hdl_info = []
        sections = vhdl_extract.extract_objects(filename)
        for unit in sections:
            if unit.kind == 'entity':
                hdl_info.append(unit)

    symbols = []
    for component in hdl_info:
        name = component.name
    
        sym = Symbol().create_new(name, reference=f"{name}_", value=f'{name}')
        find_property(sym.properties, 'Value').effects.hide=True

        sym.properties.append(Property(key='hdl', value=filename, id=len(sym.properties), effects=Effects(font=Font(width=1.27), hide=True)))
        for gen in hdl_info[0].generics:
            if not gen.data_type:
                gen.data_type = 'integer'
            sym.properties.append(Property(key=f"{gen.name}({gen.data_type}) -- {gen.desc}",
                                           value=f"{gen.default_value}",
                                           id=len(sym.properties),
                                           effects = Effects(font=Font(width=1.27, height=1.27), hide=True)))

        pins_symbol = Symbol(id=f"{name}_1_1")
        sym.units.append(pins_symbol)

        pin_num = 1
        in_pos_y = -2.54
        out_pos_y = -2.54
        for _,port in enumerate(hdl_info[0].ports):
            pin = SymbolPin()
            port = parse_port(port) # make sure it's in the correct format
            
            pin.name = port_name(port)

            if port.mode in ["input", "in"]: 
                pin.electricalType = "input"
                pin.position.X     = 0.0
                pin.position.Y     = in_pos_y
                pin.position.angle = 0.0
                in_pos_y -= 2.54
            else:
                if   port.mode.lower() == "output": pin.electricalType = "output"
                elif port.mode.lower() ==    "out": pin.electricalType = "output"
                elif port.mode.lower() ==  "inout": pin.electricalType = "bidirectional"
                else:                               pin.electricalType = "unspecified"
                pin.position.X     = 45.72
                pin.position.Y     = out_pos_y
                pin.position.angle = 180.0
                out_pos_y -= 2.54
            pin.length = 2.54
            pin.number = f"{pin_num}"
            pin.numberEffects.hide=True
            pin_num += 1

            pins_symbol.pins.append(pin)
        
        symbols.append(sym)

    return symbols

# given a symbol, update the library to match
def update_symbol(symbol: Symbol, library: SymbolLib):
    # find the matching symbol if it exists
    libsym = None
    for sym in library.symbols:
        if sym.id == symbol.id:
            libsym = sym
            break

    if not libsym:
        # symbol doesn't exist, add to library
        library.symbols.append(symbol)
        return

    # update the properties    
    for prop in symbol.properties:
        found = False
        for libprop in libsym.properties:
            if prop.key.split('(')[0] == libprop.key.split('(')[0]:
                found = True
                libprop.key = prop.key # update key (in case type/desc changed)
                #libprop.value = prop.value # override value with default?... probably not correct
        
        if not found:
            libsym.properties.append(prop)

    # Check if there's extra properties
    for libprop in libsym.properties:
        if re.search(r'.*?\(*?\) -- .*?', libprop.key): # check if this holds the format for generics
            found = False
            for prop in symbol.properties:
                if prop.key.split('(')[0] == libprop.key.split('(')[0]:
                    found = True
                    break
            if not found:
                libsym.properties.remove(libprop)

    # make sure the pins unit is present
    if len(libsym.units) == 0:
        pins_symbol = Symbol(id=f"{sym.id}_1_1")
        sym.units.append(pins_symbol)



    # update the pins
    for unit in symbol.units:
        for pin in unit.pins:
            found = False
            for libunit in libsym.units:
                for libpin in libunit.pins:
                    if libpin.name.split('(')[0] == pin.name.split('(')[0]:
                        libpin.electricalType = pin.electricalType # update the direction
                        libpin.name           = pin.name           # and the typestr
                        found = True
                        break
        
            if not found:
                libsym.units[len(libsym.units)-1].pins.append(pin)

    # check for extra pins
    for libunit in libsym.units:
        for libpin in libunit.pins:
            found = False
            for unit in symbol.units:
                for pin in unit.pins:
                    if libpin.name.split('(')[0] == pin.name.split('(')[0]:
                        found = True
                        break

            if not found:
                print(f"Removing: {libpin.name} from {libunit.id}")
                libunit.pins.remove(libpin)


def new_library():
    lib = SymbolLib()
    lib.version = '20211014' # Hard-coded to be the value in my kicad install - hopefully it's correct
    lib.generator = 'KICADFPGA_generate_library'
    return lib
    

def get_library(filename : str):
    lib = None
    if os.path.isfile(filename):
        print("File found")
        lib = SymbolLib().from_file(filename)
    else:
        print('file not found - generating')
        lib = new_library()
        lib.filePath = filename

    return lib

def update_library(lib : SymbolLib, hdl : list[str]):
    for filename in hdl:
        print(filename)
        symbols = create_symbols(filename)
        for symbol in symbols:
            print(f"    {symbol.id}")
            update_symbol(symbol, lib)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Parses HDL files into a kicad library to do schematic capture for FPGA projects.')
    parser.add_argument('-o', '--out', help="output library file")
    parser.add_argument('files', nargs='*', type=str, action='extend', help="Verilog/VHDL files to import into the library")
    args = parser.parse_args()

    print(args)

    lib = get_library(args.out)
    for filename in args.files:
        update_library(lib, glob.glob(filename))

    print(f"Saving library ({lib.filePath})")
    lib.to_file()
    


