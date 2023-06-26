#==============================================================================
# Copyright Matthew Peters - 2023
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
# netlist_to_vhdl.py
#
# This will take a netlist exported from a kicad project and create the VHDL
# model of the described structure.

from __future__ import annotations

from os import path
import re
import os
import pathlib
import glob
import argparse

from dataclasses import dataclass, field
from typing import List

import netlist

from mako.template import Template

@dataclass
class Generic:
    name        : str = ''
    namepadding : str = ''
    typestr     : str = ''
    default     : str = ''
    defaultstr  : str = ''
    commentstr  : str = ''
    value       : str = ''
    semicolon   : str = ';'
    comma       : str = ','
    # parsed components
    vhdl_type : str = ''
    high      : str = '0'
    low       : str = '0'
    length    : str = '1'


def parse_portsize_part(size_part : str, generic_list : List[Generic]) -> int | str:
    for generic in generic_list:
        if generic.typestr != 'integer': continue # only supporting integer types for size calculation
        if generic.name in size_part:
            try:
                gen_value = int(generic.value)
                size_part = size_part.replace(generic.name, str(gen_value))
            except ValueError:
                return size_part

    # Check if we can simplify this to a number
    if re.search(r'[^+\-*/()0-9]', size_part):
        return size_part        
    
    result = int(eval(size_part))
    return result

@dataclass
class Port:
    name        : str = ''
    namepadding : str = ''
    dirstr      : str = ''
    typestr     : str = ''
    semicolon   : str = ';'
    comma       : str = ','
    commentstr  : str = ''
    num         : str = ''

    # parsed components
    vhdl_type : str = ''
    high      : str = '0'
    low       : str = '0'
    length    : str = '1'

    # Linking
    target    : str = '' # name of the connected signal/constant/port

    @classmethod
    def copy_port(cls, source : Port) -> Port:
        port = cls()
        port.name        = source.name
        port.namepadding = source.namepadding
        port.dirstr      = source.dirstr
        port.typestr     = source.typestr
        port.semicolon   = source.semicolon
        port.comma       = source.comma
        port.commentstr  = source.commentstr
        port.num         = source.num
        port.vhdl_type   = source.vhdl_type
        port.high        = source.high
        port.low         = source.low
        port.length      = source.length
        port.target      = source.target
        return port

    def update_from_name(self, generic_list : List[Generic] = [], do_eval : bool = True) -> Port:
        match = re.search(r'^(.*?)'+     # start of string and name
                          r'\('+         # start bracket
                          r'(.+)'+       # range such as 31:0 or (DW-1):0
                          r'\)$', self.name)  # end bracket and end of string
        if not match:
            self.vhdl_type = 'std_logic'
            self.high      = '0'
            self.low       = '0'
            self.length    = '1'
            return

        parts = match.groups()

        if parts[1] == 'b':
            self.vhdl_type = 'boolean'
            self.high      = '0'
            self.low       = '0'
            self.length    = '1'
            return
        elif parts[1] == 'integer':
            self.vhdl_type = 'integer'
            self.high      = '31'
            self.low       = '0'
            self.length    = '32'
            return

        typestr = parts[1]
        self.name=parts[0]

        # update the vhdl_type and remove the hint from typestr
        if   typestr.startswith('uf'): self.vhdl_type='ufixed';   typestr = typestr[2:]
        elif typestr.startswith('u'):  self.vhdl_type='unsigned'; typestr = typestr[1:]
        elif typestr.startswith('sf'): self.vhdl_type='sfixed';   typestr = typestr[2:]
        elif typestr.startswith('s'):  self.vhdl_type='signed';   typestr = typestr[1:]
        elif ' ' in typestr: typestr_parts = typestr.split(' '); self.vhdl_type=typestr_parts[0]; typestr = typestr_parts[1]
        else: self.vhdl_type='std_logic_vector'

        range_parts = typestr.split(':')
        if len(range_parts) == 1:     # this shouldn't happen, i don't think...
            high_str = range_parts[0]
            low_str  = 0
        else:
            high_str = range_parts[0]
            low_str  = range_parts[1]

        if do_eval:
            high = parse_portsize_part(high_str, generic_list)
            low  = parse_portsize_part(low_str,  generic_list)
        else:
            high = high_str
            low  = low_str
        if type(high) == int and type(low) == int:
            self.length = str(high - low + 1)
        else:
            self.length = f"{high}-{low}"
        self.high = str(high)
        self.low  = str(low)

        self.vhdl_type = f"{self.vhdl_type}({self.high} downto {self.low})"
        

@dataclass
class Component:
    name          : str = ''
    instance_name : str = ''
    ports         : List[Port]    = field(default_factory=list)
    properties    : List[Generic] = field(default_factory=list)
    component     : Component = None

    @classmethod
    def from_libpart(cls, libpart : netlist.Libpart) -> Component:
        obj = cls()
        obj.name = libpart.part

        for field in libpart.fields:
            match = re.search(r'(.*)'+     # name
                              r'\((.*)\)'+ # (<type>)
                              r' -- (.*)', #  -- <desc>
                              field.name)
            if match:
                parts = match.groups()
                gen = Generic(name=parts[0], typestr=parts[1], commentstr=parts[2], default=field.value, value=field.value)
                obj.properties.append(gen)

        for pin in libpart.pins:
            if pin.type == 'input': dirstr = 'in'
            elif pin.type == 'output': dirstr = 'out'
            elif pin.type == 'bidirectional': dirstr = 'inout'
            else:  dirstr = pin.type

            obj.ports.append(Port(name=pin.name, num=pin.num, dirstr=dirstr))
        return obj

    @classmethod
    def from_comp(cls, comp : netlist.Comp) -> Component:
        obj = cls()
        obj.name = comp.libsource.part
        obj.instance_name = comp.ref

        for property in comp.properties:
            match = re.search(r'(.*)'+     # name
                              r'\((.*)\)'+ # (<type>)
                              r' -- (.*)',    #  -- <desc>
                              property.name)
            if match:
                parts = match.groups()
                obj.properties.append(Generic(name=parts[0], typestr=parts[1], commentstr=parts[2], value=property.value))

        return obj
        
    def update_from_libpart(self, libpart : Component):
        self.ports = libpart.ports
        
@dataclass
class Connection:
    ref : str = ''
    pin : str = ''
    port : Port = None

@dataclass
class Signal:
    name        : str = ''
    code        : str = ''
    vhdl_type   : str = ''
    connections : List[Connection] = field(default_factory=list)

def get_porttype(port_typestr : str, generic_list : List[Generic] = []) -> Port:
    port = None
    match = re.search(r'^(.*?)'+         # start of string and name
                      r'\('+             # start bracket
                      r'(.+)'+           # range such as 31:0 or (DW-1):0
                      r'\)$', port_typestr)  # end bracket and end of string
    if not match:
        return Port(name=port_typestr, vhdl_type='std_logic', high=0, low=0, length=1)

    parts = match.groups()
        
    if parts[1] == 'b': 
        return Port(name=parts[0], vhdl_type='boolean', high=0, low=0, length=1)

    typestr = parts[1]
    port = Port(name=parts[0])

    # update the vhdl_type and remove the hint from typestr
    if   typestr.startswith('uf'): port = port.vhdl_type='ufixed';   typestr = typestr[2:]
    elif typestr.startswith('u'):  port = port.vhdl_type='unsigned'; typestr = typestr[1:]
    elif typestr.startswith('sf'): port = port.vhdl_type='sfixed';   typestr = typestr[2:]
    elif typestr.startswith('s'):  port = port.vhdl_type='signed';   typestr = typestr[1:]
    elif ' ' in typestr: typestr_parts = typestr.split(' '); port.vhdl_type=typestr_parts[0]; typestr = typestr_parts[1]
    else: port.vhdl_type='std_logic_vector'

    range_parts = typestr.split(':')
    if len(range_parts) == 1:
        high_str = range_parts[0]
        low_str  = 0
    else:
        high_str = range_parts[0]
        low_str  = range_parts[1]

    port.high = parse_portsize_part(high_str, generic_list)
    port.low  = parse_portsize_part(low_str,  generic_list)
    port.length = port.high - port.low + 1

    return port


def find_property(property_list : List[netlist.CompProperty], name : str, default = None):
    for prop in property_list:
        if prop.name == name:
            return prop.value
    return default

def align_on_pipe(doc : str) -> str:
    n_splits = 0
    segs = []
    cur_seg = []
    for line in doc.splitlines():
        found = line.split('|')
        if len(found) != n_splits:
            n_splits = len(found)
            if cur_seg:
                segs.append(cur_seg)
                cur_seg = []
        cur_seg.append(line)
    if cur_seg:
        segs.append(cur_seg)
    
    # now align the segs
    out = []
    for seg in segs:
        max = [0] * len(seg[0].split('|'))
        for line in seg:
            parts = line.split('|')
            for i in range(len(parts)):
                if len(parts[i]) > max[i]:
                    max[i] = len(parts[i])
        
        for line in seg:
            parts = line.split('|')
            new_line = ''
            for i in range(len(max)):
                new_line += f'{parts[i]:<{max[i]}}'
            #new_line += parts[-1]
            out.append(new_line)
    return '\n'.join(out)

def generate_code(infile:str, outfile:str, template:str):
    nl = netlist.Netlist().from_file(infile)
    
    library_list   = []
    entity_name    = pathlib.Path(nl.design.source).stem
    generic_list   = []
    port_list      = []
    constant_list  = []
    signal_list    = []
    component_list = []
    instance_list  = []
    full_item_list = []

    direct_connects = {}

    for libpart in nl.libparts:
        if libpart.part in ["PARAMETER", "CONSTANT", "IN", "OUT", "INOUT"]:
            continue # skip non-component parts

        component = Component().from_libpart(libpart)
        component_list.append(component)

    for comp in nl.components:
        if comp.libsource.part == "PARAMETER":
            gen = Generic()
            gen.name = comp.value
            gen.typestr = find_property(comp.properties, 'TYPE', default='integer')
            gen.default = find_property(comp.properties, 'DEFAULT', default='0')
            gen.vhdl_type = gen.typestr
            gen.value     = gen.default
            generic_list.append(gen)
            full_item_list.append(gen)
            direct_connects[comp.ref] = gen.name

        elif comp.libsource.part == "CONSTANT":
            const = Generic()
            const.name    = find_property(comp.properties, "NAME", default='ERROR_NO_NAME')
            const.typestr = find_property(comp.properties, "TYPE", default='integer')
            const.default = comp.value
            const.vhdl_type = const.typestr
            constant_list.append(const)
            full_item_list.append(const)
            direct_connects[comp.ref] = const.name

    for comp in nl.components:
        if comp.libsource.part in ["IN", "OUT", "INOUT"]:
            port = Port()
            port.name = comp.value
            port.dirstr = comp.libsource.part.lower()
            port.typestr = find_property(comp.properties, "TYPE", default='std_logic')
            port.update_from_name(generic_list, do_eval=False)
            port_list.append(port)
            full_item_list.append(port)
            direct_connects[comp.ref] = port.name

        elif comp.libsource.part in ["PARAMETER", "CONSTANT"]:
            continue # handled elsewhere

        else:
            component = Component().from_comp(comp)
            for libpart_comp in component_list:
                if libpart_comp.name == component.name:
                    component.component = libpart_comp

                    for port in libpart_comp.ports:
                        component.ports.append(Port().copy_port(port))

            # Go through the properties on the components and process/eval them to integers
            for prop in component.properties:
                if re.search('[^+\-*/()0-9]', prop.value):
                    for sub in component.properties:
                        if sub.name != prop.name and sub.name in prop.value:
                            prop.value = prop.value.replace(sub.name, sub.value)
            for prop in component.properties:
                if not re.search('[^+\-*/()0-9]', prop.value):
                    prop.value = f"{int(eval(prop.value))}"

            # parse the port names into their name and type
            for port in component.ports:
                port.update_from_name(component.properties)

            instance_list.append(component)


    for gen in generic_list:
        gen.vhdl_type = gen.vhdl_type.replace(':', ' downto ')
        gen.vhdl_type = gen.vhdl_type.replace('slv', 'std_logic_vector')
        if gen.default:
            gen.defaultstr = f' := {gen.default}'

    for const in constant_list:
        const.vhdl_type = const.vhdl_type.replace(':', ' downto ')
        const.vhdl_type = const.vhdl_type.replace('slv', 'std_logic_vector')
        if const.default:
            const.defaultstr = f' := {const.default}'

    for component in component_list:
        for gen in component.properties:
            gen.vhdl_type = gen.typestr.replace(':', ' downto ')
            gen.vhdl_type = gen.typestr.replace('slv', 'std_logic_vector')
            if gen.default:
                gen.defaultstr = f' := {gen.default}'
        for port in component.ports:
            port.update_from_name(component.properties, do_eval=False )


    for net in nl.nets:
        if net.name.startswith('unconnected'):
            # Special case - unconnected nets
            for node in net.nodes:
                for component in instance_list:
                    if component.instance_name == node.ref:
                        for port in component.ports:
                            if port.num == node.pin:
                                if port.dirstr == 'in':
                                    if port.vhdl_type == 'boolean':
                                        port.target = "false"
                                    elif port.vhdl_type == "std_logic":
                                        port.target = "'0'"
                                    else:
                                        port.target = "(others => '0')"
                                else:
                                    port.target = 'open'
            continue

        name = net.name.replace('/', '')
        name = re.sub("\(.*?:.*?\)", '', name) # Get rid of bit ranges
        name = name.replace('-', '_') # convert dashes to underscores
        name = name.replace('(', '') # remove all brackets that are left
        name = name.replace(')', '')

        # Check if we connect to an IO port - name will be replaced which is why it's here
        skip = False
        for node in net.nodes:
            if node.ref in direct_connects.keys():
                name = direct_connects[node.ref]
                skip = True
                break

        signal = Signal(name=name, code=net.code)
        for node in net.nodes:
            connection = Connection(ref=node.ref, pin=node.pin)
            for component in instance_list:
                if component.instance_name == connection.ref:
                    for port in component.ports:
                        if port.num == connection.pin:
                            connection.port = port
                            port.target = signal.name
            signal.connections.append(connection)

        for connection in signal.connections:
            if connection.port:
                if signal.vhdl_type == '':
                    signal.vhdl_type = connection.port.vhdl_type
                else:
                    if signal.vhdl_type != connection.port.vhdl_type:
                        print(f"==== Warning! vhdl_type does not match on {signal.name}: {signal.vhdl_type} /= {connection.port.vhdl_type} ==== ")
        if not skip:
            signal_list.append(signal)


    library_list_dict = {'IEEE.std_logic_1164.all':True}
    for item in generic_list + port_list + constant_list:
        if 'unsigned' in item.vhdl_type: library_list_dict['IEEE.numeric_std.all'] = True
        elif 'signed' in item.vhdl_type: library_list_dict['IEEE.numeric_std.all'] = True
        elif 'sfixed' in item.vhdl_type: library_list_dict['IEEE.fixed_pkg.all']   = True
        elif 'ufixed' in item.vhdl_type: library_list_dict['IEEE.fixed_pkg.all']   = True
    for comp in component_list + instance_list:
        for item in comp.properties + comp.ports:
            if 'unsigned' in item.vhdl_type: library_list_dict['IEEE.numeric_std.all'] = True
            elif 'signed' in item.vhdl_type: library_list_dict['IEEE.numeric_std.all'] = True
            elif 'sfixed' in item.vhdl_type: library_list_dict['IEEE.fixed_pkg.all']   = True
            elif 'ufixed' in item.vhdl_type: library_list_dict['IEEE.fixed_pkg.all']   = True
    library_list.extend(library_list_dict.keys())

    # strip off the ending commas and semicolons
    if generic_list:
        generic_list[-1].semicolon = ' '
        generic_list[-1].comma     = ' '
    if port_list:
        port_list[-1].semicolon = ' '
        port_list[-1].comma     = ' '
    for comp in component_list:
        if (comp.properties):
            comp.properties[-1].semicolon = ' '
            comp.properties[-1].comma     = ' '
        if (comp.ports):
            comp.ports[-1].semicolon = ' '
            comp.ports[-1].comma     = ' '
    for comp in instance_list:
        if (comp.properties):
            comp.properties[-1].semicolon = ' '
            comp.properties[-1].comma     = ' '
        if (comp.ports):
            comp.ports[-1].semicolon = ' '
            comp.ports[-1].comma     = ' '

    

    context = {
        'infile':         infile,
        'outfile':        outfile,
        'library_list':   library_list,
        'entity_name':    entity_name,
        'generic_list':   generic_list,
        'port_list':      port_list,
        'constant_list':  constant_list,
        'signal_list':    signal_list,
        'component_list': component_list,
        'instance_list':  instance_list
    }

    hdl_template = Template(filename=template, preprocessor=[lambda x: x.replace("\r\n", "\n")])
    with open(outfile, 'w') as f:
        hdl = hdl_template.render(**context)
        hdl = align_on_pipe(hdl)

        f.write(hdl)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Given a netlist file, this creates an VHDL from the described structure.')
    parser.add_argument('-o', '--out', help="output VHDL file")
    parser.add_argument('-i', '--netlist', help="Netlist file to convert to HDL")
    parser.add_argument('--template', help="Specify the template file to use instead of the default", default="vhdl_template.mako")
    args = parser.parse_args()

    #print(args)

    generate_code(args.netlist, args.out, args.template)

    #lib = get_library(args.out)
    #for filename in args.files:
    #    update_library(lib, glob.glob(filename))

    #print(f"Saving library ({lib.filePath})")
    #lib.to_file()
