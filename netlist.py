#==============================================================================
# Copyright Matthew Peters - 2023
#==============================================================================
# This file is part of KicadFPGA
#
# KicadFPGA is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version. As well, if this specific file (netlist.py) is included in the
# kiutils project or a variant thereof, the license would be changed to the
# LGPL-3.0 to match that project.
#
# KicadFPGA is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# KicadFPGA. If not, see <https://www.gnu.org/licenses/>.
#==============================================================================
#
# netlist.py
#
# This will parse a netlist file exported from Kicad project

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from os import path

from kiutils.items.schitems import *
from kiutils.utils import sexpr
from kiutils.misc.config import KIUTILS_CREATE_NEW_GENERATOR_STR, KIUTILS_CREATE_NEW_VERSION_STR

#============================================================================================
# Netlists are made up of a few components
#   design     - generation and schematic sheet info
#   components - list of components used within the design
#   libparts   - details about the parts
#   libraries  - List of libraries used
#   nets       - netlist itself

#============================================================================================
# Design


@dataclass
class Design():
    """The `design` token includes information about what generated the netlist
    """

    source: str = ""
    """Source schematic file root
    """

    date: str = ""
    """Date of netlist creation. Format is YYYY-MM-DD HH:MM:SS PM".
    """

    tool: str = ""
    """Tool used to generate the netlist
    """

    sheet: List[HierarchicalSheet] = field(default_factory=list)
    """The `sheetInstances` token defines a list of instances of hierarchical sheets used in
    the netlist"""

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a Design object

        Args:
            exp (list): Part of parsed S-Expression `(design ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not design

        Returns:
            Design: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'design':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'source': object.source = item[1]
            if item[0] == 'date': object.date = item[1]
            if item[0] == 'tool': object.tool = item[1]
            if item[0] == 'sheet':
                object.sheet.append(HierarchicalSheet().from_sexpr(item))
        return object

#============================================================================================
#   components - list of components used within the design
@dataclass
class Libsource():
    """The `sheetpath` token within the comp
    """

    lib: str = ""
    """Library source name
    """

    part: str = ""
    """Part name".
    """

    description: str = ""
    """Description field of the libsource fields".
    """

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a Libsource object

        Args:
            exp (list): Part of parsed S-Expression `(libsource ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not libsource

        Returns:
            Design: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'libsource':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'lib': object.lib = item[1]
            if item[0] == 'part': object.part = item[1]
            if item[0] == 'desciption': object.description = item[1]
        return object

@dataclass
class Sheetpath():
    """The `sheetpath` token within the comp
    """

    names: str = ""
    """names - unsure what this is. Test file only included "/" in this field
    """

    tstamps: str = ""
    """tstamps - unsure what this is. Test file only included "/" in this field
    """

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a Design object

        Args:
            exp (list): Part of parsed S-Expression `(sheetpath ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not sheetpath

        Returns:
            Design: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'sheetpath':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'names': object.names = item[1]
            if item[0] == 'tstamps': object.tstamps = item[1]
        return object

@dataclass
class CompProperty():
    """The `sheetpath` token within the comp
    """

    name: str = ""
    """Property name
    """

    value: str = ""
    """Value for the property
    """

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a CompProperty object

        Args:
            exp (list): Part of parsed S-Expression `(property ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not property

        Returns:
            Design: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'property':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'name': object.name = item[1]
            if item[0] == 'value': object.value = item[1]
        return object

@dataclass
class Comp():
    """The `comp` token includes component information
    """

    ref: str = ""
    """Reference
    """

    value: str = ""
    """Value
    """

    footprint: str = ""
    """Footprint
    """

    datasheet: str = ""
    """Datasheet link
    """

    libsource: Libsource = field(default_factory=lambda: Libsource())
    """Library source object
    """

    properties: List[CompProperty] = field(default_factory=list)
    """
    """

    sheetpath: Sheetpath = field(default_factory=lambda: Sheetpath)
    """The `sheetInstances` token defines a list of instances of hierarchical sheets used in
    the netlist"""

    tstamps: str = ""
    """Timestamp from the component"""

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a Comp object

        Args:
            exp (list): Part of parsed S-Expression `(comp ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not comp

        Returns:
            Comp: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'comp':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'ref': object.ref = item[1]
            if item[0] == 'value': object.value = item[1]
            if item[0] == 'footprint': object.footprint = item[1]
            if item[0] == 'ref': object.ref = item[1]
            if item[0] == 'datasheet': object.datasheet = item[1]
            if item[0] == 'libsource': object.libsource = Libsource().from_sexpr(item)
            if item[0] == 'property': object.properties.append(CompProperty().from_sexpr(item))
            if item[0] == 'sheetpath': object.sheetpath = Sheetpath().from_sexpr(item)
            if item[0] == 'tstamps': object.tstamps = item[1]
        return object


#============================================================================================
#   libparts   - details about the parts
@dataclass
class Field():
    """The `field` token within each libpart
    """

    name: str = ""
    """Field name
    """

    value: str = ""
    """Value for the field
    """

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a Field object

        Args:
            exp (list): Part of parsed S-Expression `(field ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not field

        Returns:
            Design: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'field':
            raise Exception("Expression does not have the correct type")

        object = cls()
        if exp[1][0] != 'name' or len(exp) < 3:
            raise Exception("Expression does not have the correct format (field (name ...) <value>)")
        
        object.name = exp[1][1]
        object.value = exp[2]
            
        return object

@dataclass
class Pin():
    """The `pin` token within the pins list in a libpart
    """

    num: str = ""
    """Pin number
    """

    name: str = ""
    """Pin name
    """

    type: str = ""
    """Pin type
    """

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a Pin object

        Args:
            exp (list): Part of parsed S-Expression `(pin ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not pin

        Returns:
            Design: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'pin':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'num': object.num = item[1]
            if item[0] == 'name': object.name = item[1]
            if item[0] == 'type': object.type = item[1]
        return object


@dataclass
class Libpart():
    """The `Libpart` token
    """

    lib: str = ""
    """Library name
    """

    part: str = ""
    """Part name
    """

    description: str = ""
    """Description for the pin
    """

    docs: str = ""
    """Link to the documentation for the part
    """

    footprints: list[str] = field(default_factory=list)
    """List of footprints - generally a single one
    """

    fields: list[Field] = field(default_factory=list)
    """List of fields for the pin
    """

    pins: list[Pin] = field(default_factory=list)
    """List of pins for the part
    """

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a Libpart object

        Args:
            exp (list): Part of parsed S-Expression `(libpart ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not libpart

        Returns:
            Design: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'libpart':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'lib': object.lib = item[1]
            if item[0] == 'part': object.part = item[1]
            if item[0] == 'description': object.description = item[1]
            if item[0] == 'docs': object.docs = item[1]
            if item[0] == 'footprints':
                for footprint in item[1:]:
                    if footprint[0] == 'fp':
                        object.footprints.append(footprint[1])
            if item[0] == 'fields':
                for field in item[1:]:
                    if field[0] == 'field':
                        object.fields.append(Field().from_sexpr(field))
            if item[0] == 'pins':
                for pin in item[1:]:
                    if pin[0] == 'pin':
                        object.pins.append(Pin().from_sexpr(pin))
        return object

#============================================================================================
#   libraries  - List of libraries used
@dataclass
class Library():
    """The `Library` token within the libraries list
    """

    logical: str = ""
    """Logical library name
    """

    uri: str = ""
    """URI to library
    """

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a Library object

        Args:
            exp (list): Part of parsed S-Expression `(library ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not library

        Returns:
            Design: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'library':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'logical': object.logical = item[1]
            if item[0] == 'uri': object.uri = item[1]
        return object


#============================================================================================
#   nets       - netlist itself
@dataclass
class Node():
    """The `Node` token within a net of the nets
    """

    ref: str = ""
    """Component reference
    """

    pin: str = ""
    """Component pin
    """

    pintype: str = ""
    """Pin type
    """

    pinfunction: str = ""
    """Pin function
    """

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a Node object

        Args:
            exp (list): Part of parsed S-Expression `(node ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not node

        Returns:
            Design: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'node':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'ref': object.ref = item[1]
            if item[0] == 'pin': object.pin = item[1]
            if item[0] == 'pintype': object.pintype = item[1]
            if item[0] == 'pinfunction': object.pinfunction = item[1]
        return object

@dataclass
class Net():
    """The `net` token within the list of nets
    """

    code: str = ""
    """Unique number for the net
    """

    name: str = ""
    """Name of the net
    """

    nodes: list[Node] = field(default_factory=list)
    """Pin function
    """

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expresstion into a Net object

        Args:
            exp (list): Part of parsed S-Expression `(net ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not net

        Returns:
            Design: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'net':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'code': object.code = item[1]
            if item[0] == 'name': object.name = item[1]
            if item[0] == 'node': object.nodes.append(Node().from_sexpr(item))
        return object

        


#============================================================================================
@dataclass
class Netlist():
    """The `export` token represents a KiCad schematic netlist export
    """

    version: str = "E"
    """The `version` token attribute defines the netlist format"""

    design: Design = field(default_factory=lambda: Design())
    """Design object
    """

    components: list[Comp] = field(default_factory=list)
    """
    """

    libparts: list[Libpart] = field(default_factory=list)
    """
    """

    libraries: list[Library] = field(default_factory=list)
    """
    """

    nets: list[Net] = field(default_factory=list)
    """
    """

    @classmethod
    def from_sexpr(cls, exp: str):
        """Convert the given S-Expression into a Netlist object

        Args:
            exp (list): Part of parsed S-Expression `(export ...)`

        Raises:
            Exception: When given parameter's type is not a list
            Exception: When the first item of the list is not export

        Returns:
            Netlist: Object of the class initialized with the given S-Expression
        """
        if not isinstance(exp, list):
            raise Exception("Expression does not have the correct type")

        if exp[0] != 'export':
            raise Exception("Expression does not have the correct type")

        object = cls()
        for item in exp:
            if item[0] == 'version': object.version = item[1]
            if item[0] == 'design': object.design = Design().from_sexpr(item)
            if item[0] == 'components':
                for comp in item[1:]:
                    object.components.append(Comp().from_sexpr(comp))
            if item[0] == 'libparts':
                for libpart in item[1:]:
                    object.libparts.append(Libpart().from_sexpr(libpart))
            if item[0] == 'libraries':
                for library in item[1:]:
                    object.libraries.append(Library().from_sexpr(library))
            if item[0] == 'nets':
                for net in item[1:]:
                    object.nets.append(Net().from_sexpr(net))
        return object

    @classmethod
    def from_file(cls, filepath: str):
        """Load a netlist directly from a KiCad netlist file (`.net`) and sets the
        `self.filePath` attribute to the given file path.

        Args:
            filepath (str): Path or path-like object that points to the file

        Raises:
            Exception: If the given path is not a file

        Returns:
            Netlist: Object of the Netlist class initialized with the given KiCad netlist
        """
        if not path.isfile(filepath):
            raise Exception("Given path is not a file!")

        with open(filepath, 'r') as infile:
            item = cls.from_sexpr(sexpr.parse_sexp(infile.read()))
            item.filePath = filepath
            return item

