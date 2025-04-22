# SEGA Europe
# Gordon.Mckendrick@sega.co.uk

from lxml import etree
from typing import Dict, List
from util.xliff.xml_backed_dict import XMLBackedDict
from util.xliff.xml_backed_list import XMLBackedList
from pathlib import Path

class XMLNamespaces:
    xml = 'http://www.w3.org/XML/1998/namespace'


class File:
    @classmethod
    def create(cls, relative_filepath: Path, source_language: str, target_language: str):
        xliff_node = etree.Element("xliff")
        file_node = etree.SubElement(xliff_node, "file",
                                     {"source-language": source_language,
                                      "target-language": target_language,
                                      "original": str(relative_filepath.resolve())})
        etree.SubElement(file_node, "body")
        return File(relative_filepath, xliff_node)

    @classmethod
    def from_file(cls, filepath: Path, root: Path):
        with filepath.open("r", encoding="utf-8") as file:
            filedata = file.read()
            if filedata[:5] == "<?xml":
                filedata = filedata[filedata.index(
                    "\n"):]  # remove the initial xml declaration as etree makes a mess of it every time. Putting it back in at the end is far easier given the time we have.
            xml_data = etree.fromstring(filedata)
        return File(filepath.relative_to(root), etree.ElementTree(xml_data))

    def __init__(self, relative_filepath: Path, node: etree.ElementTree):
        self.relative_filepath = relative_filepath
        self.node = node  # expects to be given the "XLIFF" node directly
        self.body_node = self.node.find("file").find("body")
        self.trans_units = XMLBackedDict(self.body_node, "trans-unit", lambda item: item.node,
                                         lambda xml: TransUnit(xml), lambda
                                             item: item.id)  # type: Dict[str, Row] # DO NOT MODIFY THIS COLLECTION DIRECTLY, xml MUST be updated

    @property
    def source_language(self) -> str:
        return self.node.find("file").attrib["source-language"]

    @property
    def target_language(self) -> str:
        return self.node.find("file").attrib["target-language"]

    def save_in_directory(self, directory: Path):
        filepath = directory.joinpath(self.relative_filepath)
        filepath.parents[0].mkdir(parents=True, exist_ok=True)

        with filepath.open("w", encoding="utf-8") as file:
            file.write(str(self))

    def __str__(self):
        return '<?xml version="1.0" encoding="utf-8"?>\n' + etree.tostring(self.node, encoding='unicode',
                                                                           pretty_print=True)

    def __ne__(self, other):
        return not self == other

    def __eq__(self, other):
        return (self.source_language == other.source_language
                and self.target_language == other.target_language
                and len(self.trans_units) == len(other.trans_units)
                and all(pair[0] == pair[1] for pair in zip(self.trans_units.values(), other.trans_units.values())))


class TransUnit:
    @classmethod
    def create(cls, source_language: str, target_language: str, string_id: str, source_text: str, target_text: str,
               notes: List[str], locked: bool = False, state: str = "NS"):
        trans_unit_node = etree.Element("trans-unit", {"resname": string_id})
        source_node = etree.SubElement(trans_unit_node, "source", {"lang": source_language})
        source_node.text = source_text

        target_node = etree.SubElement(trans_unit_node, "target", {"lang": target_language, "state": state})
        target_node.text = target_text

        trans_unit = TransUnit(trans_unit_node)
        trans_unit.locked = locked

        if len(notes):
            for note in notes:
                trans_unit.notes.append(Note.create(note))
                trans_unit.ref_notes.append(RefNote.create(
                    note))  # refnotes that we can use to determine which comments have changed within MemoQ
        return trans_unit

    def __init__(self, node: etree.Element):
        self.node = node
        self.notes = XMLBackedList(self.node, "note", lambda item: item.node, lambda xml: Note(xml))
        self.ref_notes = XMLBackedList(self.node, "ref-note", lambda item: item.node, lambda xml: RefNote(xml))

    @property
    def id(self) -> str:
        return self.node.attrib["resname"]

    @property
    def source(self) -> str:
        text = self.node.find("source").text
        return text if text is not None else ""

    @source.setter
    def source(self, value: str):
        self.node.find("source").text = value

    @property
    def target(self) -> str:
        text = self.node.find("target").text
        return text if text is not None else ""

    @target.setter
    def target(self, value: str):
        self.node.find("target").text = value

    @property
    def source_language(self) -> str:
        return self.node.find("source").attrib["lang"]

    @property
    def target_language(self) -> str:
        return self.node.find("target").attrib["lang"]

    @property
    def locked(self) -> bool:
        return self.node.attrib["translate"] == "no"

    @locked.setter
    def locked(self, value: bool):
        self.node.attrib["translate"] = "no" if value else "yes"

    @property
    def status(self) -> str:
        return self.node.find("target").attrib["state"]

    @status.setter
    def status(self, value: str):
        self.node.find("target").attrib["state"] = value

    def __eq__(self, other):
        return (self.id == other.id
                and self.source_language == other.source_language
                and self.target_language == other.target_language
                and self.source == other.source
                and self.target == other.target
                and self.locked == other.locked
                and self.status == other.status
                and len(self.notes) == len(other.notes)
                and all(pair[0] == pair[1] for pair in zip(self.notes, other.notes)))

    def __ne__(self, other):
        return not self == other


class Note:
    @classmethod
    def create(cls, text: str):
        note_node = etree.Element("note")
        note_node.text = text
        return Note(note_node)

    def __init__(self, node: etree.Element):
        self.node = node

    @property
    def text(self) -> str:
        text = self.node.text
        return text if text is not None else ""

    @text.setter
    def text(self, value: str):
        self.node.text = value

    def __eq__(self, other):
        return self.text == other.text

    def __ne__(self, other):
        return not self == other


class RefNote:
    @classmethod
    def create(cls, text: str):
        note_node = etree.Element("ref-note")
        note_node.text = text
        return Note(note_node)

    def __init__(self, node: etree.Element):
        self.node = node

    @property
    def text(self) -> str:
        text = self.node.text
        return text if text is not None else ""

    @text.setter
    def text(self, value: str):
        self.node.text = value

    def __eq__(self, other):
        return self.text == other.text

    def __ne__(self, other):
        return not self == other
