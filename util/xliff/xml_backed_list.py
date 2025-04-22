# SEGA Europe
# Gordon.Mckendrick@sega.co.uk
import collections.abc
from typing import Callable
from lxml import etree

# List that also keeps the underlying xml updated
# extends MutableSequence, as List itself has a lot of quirks that will take forever to debug
# has little error checking, it's assumed data exists in this list and non-child items won't be attempted to be removed etc.
class XMLBackedList(collections.abc.MutableSequence):
    def __init__(self, parent_node: etree.Element, element_name: str, item_to_xml: Callable, xml_to_item: Callable):
        self.parent_node = parent_node # parent xml node that contains these children 
        self.element_name = element_name # xml tag name of the children contained here
        self.item_to_xml = item_to_xml # function with signature f(item) -> xml_node
        self.xml_to_item = xml_to_item # function with signature f(xml_node) -> item
        self.data = [] # underlying list holding the item data

        # find the existing children in the xml tree
        for xml_node in parent_node.iter(element_name):
            self.data.append(xml_to_item(xml_node))

    def __getitem__(self, index):
            return self.data[index]

    def __setitem__(self, index, item): # only applies within range, meaning this is always a replace
        self.data[index] = item
        self.parent_node[index] = self.item_to_xml(item)
        
    def __delitem__(self, index):
        del self.data[index]
        del self.parent_node[index]

    def __len__(self):
        return len(self.data)

    def insert(self, index, value):
        self.data.insert(index, value)
        self.parent_node.insert(index, self.item_to_xml(value))

    def append(self, value):
        self.data.append(value)
        self.parent_node.append(self.item_to_xml(value))

    def reverse(self): # in-place reverse, does not return new copy
        self.data.reverse()
        for i, item in enumerate(self.data):
            self.parent_node[i] = self.item_to_xml(item)

    def extend(self, values):  # equvilent of C# AddRange(...)
        for item in values:
            self.append(item)

    def pop(self, index=-1): # returns the item at this index and removes it from the list
        item = self.data.pop(index)
        node = self.item_to_xml(item)
        self.parent_node.remove(node)
        return item

    def remove(self, value): # returns ValueError if value doesn't exist in data
        self.data.remove(value)
        self.parent_node.remove(self.item_to_xml(value))

    def __iadd__(self, values):  # adds a new element in-place
        self.extend(values)
        return self