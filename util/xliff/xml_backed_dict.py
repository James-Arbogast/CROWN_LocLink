# SEGA Europe
# Gordon.Mckendrick@sega.co.uk
import collections.abc
from util.xliff.xml_backed_list import XMLBackedList
from typing import Callable
from lxml import etree

# Dict that also keeps the underlying xml updated
# extends MutableMapping, giving the same functionality as a normal dict {}
# has almost no error checking, it's assume that the use of this is with well kept data, and unexpected values aren't provided
class XMLBackedDict(collections.abc.MutableMapping):
    def __init__(self, parent_node: etree.Element, element_name: str, item_to_xml: Callable, xml_to_item: Callable, item_to_key: Callable):
        self.item_to_key = item_to_key # function with signature f(item) -> key (e.g. f(myTextRow) -> myTextRow.UniqueStringID)
        self.xml = XMLBackedList(parent_node, element_name, item_to_xml, xml_to_item) # saves us having to modify the xml in two places, plus it keeps order
        self.data = {}

        # build the default mapping
        for item in self.xml:
            self.data[self.item_to_key(item)] = item

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, item): # key can be new, prefer to use set_value, otherwise you can update this with invalid keys and break the dict
        if key != self.item_to_key(item):
            raise KeyError("Key " + key + " does not match mapped value " + self.item_to_key(key) + " from item_to_key mapping function")

        if key in self.data: # replace existing
            index = self.xml.index(self.data[key])
            self.data[key] = item
            self.xml[index] = item
        else:
            self.data[key] = item
            self.xml.append(item)
        
    def set_value(self, item): # preferred way to set items in the dict, ensures the keys are correct
        key = self.item_to_key(item)
        self[key] = item

    def insert(self, item, index):
        key = self.item_to_key(item)
        self.data[key] = item
        self.xml.insert(index, item)

    def __delitem__(self, key):
        index = self.xml.index(self.data[key])
        del self.data[key]
        del self.xml[index]

    def __iter__(self):
        return self.data.__iter__()

    def __len__(self):
        return len(self.data)

    def pop(self, key, default=object()):  # returns the item at this index and removes it from the list
        index = self.xml.index(self.data[key])
        self.xml.pop(index)
        return self.data.pop(key)

    def popitem(self): # pops an arbitrary item from the dict (no key provided)
        item = self.xml.pop(0)
        self.data.pop(self.item_to_key(item))
        return item

    def clear(self):
        while len(self.xml):
            self.popitem()

    def setdefault(self, key, default=None): # acts like get, but returns default if the key doesn't exist. Really weird naming from python.
        if key in self.data:
            return self.data[key]
        else:
            return default