# -*- coding: utf-8 -*-
# Copyright (C) 2014 Julian Metzler
# See the LICENSE file for the full license.

"""
Class definitions
"""

import gobject
import gtk
import hashlib
import random
import sqlite3
import time

def _generate_id():
	# Generate a unique identifier
	return hashlib.sha1(str(time.time() + random.getrandbits(16))).hexdigest()

class StoragePlace(object):
	"""
	A class representing a place where you can store stuff (e.g. a box, a shelf etc.)
	"""
	
	def __init__(self, id, name, location, type):
		self.id = id if id is not None else _generate_id()
		self.name = name
		self.location = location
		self.type = type
	
	def __str__(self):
		return "%s: %s @ %s (%s)" % (self.id, self.name, self.location, self.type)
	
	def save_to_db(self, db_cursor):
		# Save the object to a database
		return db_cursor.execute("INSERT INTO `places` (id, name, location, type) VALUES(?, ?, ?, ?)", (self.id, self.name.decode('utf-8'), self.location.decode('utf-8'), self.type.decode('utf-8')))
	
	@classmethod
	def from_db_entry(cls, entry):
		# Create an object from a database entry
		return cls(**entry)
	
	def add_item(self, item):
		# Add a single item to the storage place
		item.set_place(self)
	
	def add_items(self, items):
		# Add multiple items to the storage place
		for item in items:
			item.set_place(self)

# A dummy place to use if no place has been set on an item
DUMMY_PLACE = StoragePlace("-1", "DUMMY", "DUMMY", "DUMMY")

class Item(object):
	"""
	A class representing an arbitrary item that can be stored in a StoragePlace
	"""
	
	def __init__(self, id, name, place = DUMMY_PLACE, details = None, amount = 1):
		self.id = id if id is not None else _generate_id()
		self.name = name
		self.details = details
		self.amount = amount
		
		if place is None:
			place = DUMMY_PLACE
		
		self.set_place(place)
	
	def __str__(self):
		return "%s: %s @ %s (%s, %i pcs.)" % (self.id, self.name, self.place.name, self.details, self.amount)
	
	def save_to_db(self, db_cursor):
		# Save the object to a database
		return db_cursor.execute("INSERT INTO `items` (id, name, place_id, details, amount) VALUES(?, ?, ?, ?, ?)", (self.id, self.name.decode('utf-8'), self.place.id, self.details.decode('utf-8'), self.amount))
	
	@classmethod
	def from_db_entry(cls, entry):
		# Create an object from a database entry
		
		# Lookup the place for the given id
		if entry['place_id'] == DUMMY_PLACE.id:
			place = DUMMY_PLACE
		else:
			place = StoragePlace(entry['place_id'], "UNKNOWN", "UNKNOWN", "UNKNOWN")
		
		return cls(entry['id'], entry['name'], place, entry['details'], entry['amount'])
	
	def load_place_data(self, db_cursor):
		# Load the place data from the database
		db_cursor.execute("SELECT * FROM `places` WHERE id = ?", (self.place.id, ))
		entry = db_cursor.fetchone()
		
		if entry is None:
			raise KeyError("No place found with id %s" % self.place.id)
		
		self.set_place(StoragePlace.from_db_entry(entry))
		return True
	
	def set_place(self, place):
		# Put the item into a storage place
		self.place = place

class GUI(object):
	"""
	A class representing the graphical user interface
	"""
	
	FILTER_OVERVIEW_ITEMS_PLACE_ID = None
	
	COL_NAMES_PLACE = {
		"ID": 0,
		"NAME": 1,
		"LOCATION": 2,
		"TYPE": 3
	}
	
	COL_NAMES_ITEM = {
		"ID": 0,
		"PLACE_ID": 1,
		"PLACE_NAME": 2,
		"NAME": 3,
		"DETAILS": 4,
		"AMOUNT": 5
	}
	
	def __init__(self, database):
		self.db = sqlite3.connect(database)
		self.db.row_factory = sqlite3.Row
		self.cur = self.db.cursor()
		self.cur.execute("CREATE TABLE IF NOT EXISTS `places` (id, name, location, type)")
		self.cur.execute("CREATE TABLE IF NOT EXISTS `items` (id, name, place_id, details, amount)")
		self.db.commit()
		
		self.window = gtk.Window()
		self.window.connect('destroy', self.quit)
		self.window.set_title("pyStoreMan")
		self.window.set_border_width(10)
		# self.window.set_position(gtk.WIN_POS_CENTER_ALWAYS)
		self.window.set_size_request(600, 400)
		self.icon = self.window.render_icon(gtk.STOCK_PREFERENCES, gtk.ICON_SIZE_MENU)
		self.window.set_icon(self.icon)
		self.build_ui()
		
		self.load_data()
	
	def load_data(self):
		self.cur.execute("SELECT * FROM `places`")
		place_entries = self.cur.fetchall()
		for entry in place_entries:
			self.add_place(StoragePlace.from_db_entry(entry), save_to_db = False)
		
		self.cur.execute("SELECT * FROM `items`")
		item_entries = self.cur.fetchall()
		for entry in item_entries:
			self.add_item(Item.from_db_entry(entry), save_to_db = False)
		
		self._reload_place_names()
	
	def _get_path(self, store, id):
		# Get the path for the row with the given ID in the given ListStore
		for index, row in enumerate(store):
			if row[0] == id:
				return (index, )
		
		return None
	
	def _get_iter(self, store, id):
		# Get the Iter object for the row with the given ID in the given ListStore
		path = self._get_path(store, id)
		if path is None:
			return None
		
		return store.get_iter(path)
	
	def _reload_place_names(self):
		places = {}
		
		for entry in self.liststore_places:
			places[entry[self.COL_NAMES_PLACE["ID"]]] = entry[self.COL_NAMES_PLACE["NAME"]]
		
		for item in self.liststore_items:
			try:
				item[self.COL_NAMES_ITEM["PLACE_NAME"]] = places[item[self.COL_NAMES_ITEM["PLACE_ID"]]]
			except KeyError:
				item[self.COL_NAMES_ITEM["PLACE_NAME"]] = "UNKNOWN"
	
	def _update_item(self, entry):
		self.cur.execute("UPDATE `items` SET `name` = ?, `place_id` = ?, `details` = ?, `amount` = ? WHERE `id` = ?", (entry[self.COL_NAMES_ITEM["NAME"]].decode('utf-8'), entry[self.COL_NAMES_ITEM["PLACE_ID"]], entry[self.COL_NAMES_ITEM["DETAILS"]].decode('utf-8'), entry[self.COL_NAMES_ITEM["AMOUNT"]], entry[self.COL_NAMES_ITEM["ID"]]))
	
	def _update_place(self, entry):
		self.cur.execute("UPDATE `places` SET `name` = ?, `location` = ?, `type` = ? WHERE `id` = ?", (entry[self.COL_NAMES_PLACE["NAME"]].decode('utf-8'), entry[self.COL_NAMES_PLACE["LOCATION"]].decode('utf-8'), entry[self.COL_NAMES_PLACE["TYPE"]].decode('utf-8'), entry[self.COL_NAMES_PLACE["ID"]]))
	
	def add_place(self, place, save_to_db = True):
		# Add a place to all place lists
		self.liststore_places.append([place.id, place.name, place.location, place.type])
		
		if save_to_db:
			place.save_to_db(self.cur)
			self.db.commit()
	
	def add_item(self, item, save_to_db = True):
		# Add an item to all item lists
		self.liststore_items.append([item.id, item.place.id, item.place.name, item.name, item.details, item.amount])
		
		if save_to_db:
			item.save_to_db(self.cur)
			self.db.commit()
	
	def callback_treeview_overview_places_changed(self, selection):
		# A row has been clicked in the overview place list, show contained items in the item list
		id = None
		
		model, pathlist = selection.get_selected_rows()
		for path in pathlist:
			tree_iter = model.get_iter(path)
			id = model.get_value(tree_iter, self.COL_NAMES_PLACE["ID"])
		
		self.FILTER_OVERVIEW_ITEMS_PLACE_ID = id
		self.liststore_filter_overview_items.refilter()
	
	def callback_treeview_overview_items_changed(self, selection):
		# A row has been clicked in the overview item list
		"""model, pathlist = selection.get_selected_rows()
		for path in pathlist:
			tree_iter = model.get_iter(path)
			id = model.get_value(tree_iter, self.COL_NAMES_ITEM["ID"])"""
	
	def callback_entry_search_term_changed(self, entry):
		# Text has been deleted from the search term entry
		self.liststore_filter_search_items.refilter()
	
	def callback_treeview_search_items_changed(self, selection):
		# A row has been clicked in the search item list
		"""model, pathlist = selection.get_selected_rows()
		for path in pathlist:
			tree_iter = model.get_iter(path)
			id = model.get_value(tree_iter, self.COL_NAMES_ITEM["ID"])"""
	
	def callback_treeview_cell_edited(self, cell, path, new_text, user_data):
		# A cell has been edited
		from_model, for_model, column = user_data
		_entry = None
		
		id = from_model[path][0]
		
		if for_model is self.liststore_items and column == self.COL_NAMES_ITEM["AMOUNT"]:
			try:
				new_text = int(new_text)
			except ValueError:
				return
		
		for entry in for_model:
			if entry[0] == id:
				_entry = entry
				entry[column] = new_text
		
		if for_model is self.liststore_places:
			self._update_place(_entry)
		elif for_model is self.liststore_items:
			self._update_item(_entry)
		
		if for_model is self.liststore_places and column == self.COL_NAMES_PLACE["NAME"]:
			# We need to tell the item ListStore about the change of a place's name
			self._reload_place_names()
	
	def callback_treeview_cell_item_place_changed(self, combo, path, new_iter, user_data):
		# A new place has been selected for an item
		from_model, for_model = user_data
		place_id = combo.get_property('model')[new_iter][0]
		item_id = from_model[path][self.COL_NAMES_ITEM["ID"]]
		
		for entry in for_model:
			if entry[0] == item_id:
				entry[self.COL_NAMES_ITEM["PLACE_ID"]] = place_id
				self._update_item(entry)
		
		#self._reload_place_names()
	
	def callback_button_clicked(self, button, user_data = None):
		# A button has been clicked
		if button is self.button_overview_add_place:
			new_place = StoragePlace(None, "Name", "Location", "Type")
			self.add_place(new_place)
		elif button is self.button_overview_remove_place:
			model, pathlist = self.treeview_overview_places_selection.get_selected_rows()
			try:
				id = model[pathlist[0]][self.COL_NAMES_PLACE["ID"]]
				del model[pathlist[0]]
				self.cur.execute("DELETE FROM `places` WHERE `id` = ?", (id, ))
			except IndexError:
				pass
		elif button is self.button_search_add_item:
			new_item = Item(None, "Name", None, "Details", 1)
			self.add_item(new_item)
		elif button is self.button_search_remove_item:
			model, pathlist = self.treeview_search_items_selection.get_selected_rows()
			try:
				id = model[pathlist[0]][self.COL_NAMES_ITEM["ID"]]
				del model[pathlist[0]]
				self.cur.execute("DELETE FROM `items` WHERE `id` = ?", (id, ))
			except IndexError:
				pass
	
	def build_ui(self):
		"""
		ITEM: Place ListStore
		"""
		self.liststore_places = gtk.ListStore(str, str, str, str) # ID (not displayed), Name, Location, Type
		
		"""
		ITEM: Item ListStore
		"""
		self.liststore_items = gtk.ListStore(str, str, str, str, str, int) # ID (not displayed), Place ID (not displayed), Place Name (not always displayed), Name, Details, Amount
		
		"""
		PAGE: Overview
		ITEM: Place TreeView
		"""
		# CellRenderer for the TreeView columns
		self.tvcolumn_overview_places_name_renderer = gtk.CellRendererText()
		self.tvcolumn_overview_places_location_renderer = gtk.CellRendererText()
		self.tvcolumn_overview_places_type_renderer = gtk.CellRendererText()
		
		# Make the renderers editable
		self.tvcolumn_overview_places_name_renderer.set_property('editable', True)
		self.tvcolumn_overview_places_location_renderer.set_property('editable', True)
		self.tvcolumn_overview_places_type_renderer.set_property('editable', True)
		
		# Connect the renderer signals (the number is the column affected by the edit)
		self.tvcolumn_overview_places_name_renderer.connect('edited', self.callback_treeview_cell_edited, (self.liststore_places, self.liststore_places, self.COL_NAMES_PLACE["NAME"]))
		self.tvcolumn_overview_places_location_renderer.connect('edited', self.callback_treeview_cell_edited, (self.liststore_places, self.liststore_places, self.COL_NAMES_PLACE["LOCATION"]))
		self.tvcolumn_overview_places_type_renderer.connect('edited', self.callback_treeview_cell_edited, (self.liststore_places, self.liststore_places, self.COL_NAMES_PLACE["TYPE"]))
		
		# Define TreeView columns
		self.tvcolumn_overview_places_name = gtk.TreeViewColumn("Name")
		self.tvcolumn_overview_places_location = gtk.TreeViewColumn("Location")
		self.tvcolumn_overview_places_type = gtk.TreeViewColumn("Type")
		
		# Add renderers to the columns
		self.tvcolumn_overview_places_name.pack_start(self.tvcolumn_overview_places_name_renderer, True)
		self.tvcolumn_overview_places_location.pack_start(self.tvcolumn_overview_places_location_renderer, True)
		self.tvcolumn_overview_places_type.pack_start(self.tvcolumn_overview_places_type_renderer, True)
		
		# Link the renderers to the ListStore
		self.tvcolumn_overview_places_name.add_attribute(self.tvcolumn_overview_places_name_renderer, 'text', self.COL_NAMES_PLACE["NAME"])
		self.tvcolumn_overview_places_location.add_attribute(self.tvcolumn_overview_places_location_renderer, 'text', self.COL_NAMES_PLACE["LOCATION"])
		self.tvcolumn_overview_places_type.add_attribute(self.tvcolumn_overview_places_type_renderer, 'text', self.COL_NAMES_PLACE["TYPE"])
		
		# Set extras for the columns
		self.tvcolumn_overview_places_name.set_sort_column_id(self.COL_NAMES_PLACE["NAME"])
		self.tvcolumn_overview_places_location.set_sort_column_id(self.COL_NAMES_PLACE["LOCATION"])
		self.tvcolumn_overview_places_type.set_sort_column_id(self.COL_NAMES_PLACE["TYPE"])
		
		# Build the TreeView
		self.treeview_overview_places = gtk.TreeView(self.liststore_places)
		self.treeview_overview_places.append_column(self.tvcolumn_overview_places_name)
		self.treeview_overview_places.append_column(self.tvcolumn_overview_places_location)
		self.treeview_overview_places.append_column(self.tvcolumn_overview_places_type)
		
		# Connect the signals
		self.treeview_overview_places_selection = self.treeview_overview_places.get_selection()
		self.treeview_overview_places_selection.connect('changed', self.callback_treeview_overview_places_changed)
		
		# Scrolled Window
		self.scroll_treeview_overview_places = gtk.ScrolledWindow()
		
		self.scroll_treeview_overview_places.set_property('hscrollbar-policy', gtk.POLICY_AUTOMATIC)
		self.scroll_treeview_overview_places.set_property('vscrollbar-policy', gtk.POLICY_AUTOMATIC)
		
		self.scroll_treeview_overview_places.add(self.treeview_overview_places)
		
		# Padding
		self.padding_overview_place_list = gtk.HBox()
		self.padding_overview_place_list.pack_start(self.scroll_treeview_overview_places, padding = 10)
		
		# Frame
		self.frame_overview_place_list = gtk.Frame(label = "Places")
		self.frame_overview_place_list.add(self.padding_overview_place_list)
		
		"""
		PAGE: Overview
		ITEM: Item TreeView
		"""
		# ListStore filter (for filtering based on place)
		def _filter_overview_items(model, iter, user_data = None):
			if self.FILTER_OVERVIEW_ITEMS_PLACE_ID is None:
				return True
			
			return model[iter][self.COL_NAMES_ITEM["PLACE_ID"]] == self.FILTER_OVERVIEW_ITEMS_PLACE_ID
		
		self.liststore_filter_overview_items = self.liststore_items.filter_new()
		self.liststore_filter_overview_items.set_visible_func(_filter_overview_items, data = None)
		
		# CellRenderer for the TreeView columns
		self.tvcolumn_overview_items_name_renderer = gtk.CellRendererText()
		self.tvcolumn_overview_items_details_renderer = gtk.CellRendererText()
		self.tvcolumn_overview_items_amount_renderer = gtk.CellRendererText()
		
		# Make the renderers editable
		self.tvcolumn_overview_items_name_renderer.set_property('editable', True)
		self.tvcolumn_overview_items_details_renderer.set_property('editable', True)
		self.tvcolumn_overview_items_amount_renderer.set_property('editable', True)
		
		# Connect the renderer signals (the number is the column affected by the edit)
		self.tvcolumn_overview_items_name_renderer.connect('edited', self.callback_treeview_cell_edited, (self.liststore_filter_overview_items, self.liststore_items, self.COL_NAMES_ITEM["NAME"]))
		self.tvcolumn_overview_items_details_renderer.connect('edited', self.callback_treeview_cell_edited, (self.liststore_filter_overview_items, self.liststore_items, self.COL_NAMES_ITEM["DETAILS"]))
		self.tvcolumn_overview_items_amount_renderer.connect('edited', self.callback_treeview_cell_edited, (self.liststore_filter_overview_items, self.liststore_items, self.COL_NAMES_ITEM["AMOUNT"]))
		
		# Define TreeView columns
		self.tvcolumn_overview_items_name = gtk.TreeViewColumn("Name")
		self.tvcolumn_overview_items_details = gtk.TreeViewColumn("Details")
		self.tvcolumn_overview_items_amount = gtk.TreeViewColumn("Amount")
		
		# Add renderers to the columns
		self.tvcolumn_overview_items_name.pack_start(self.tvcolumn_overview_items_name_renderer, True)
		self.tvcolumn_overview_items_details.pack_start(self.tvcolumn_overview_items_details_renderer, True)
		self.tvcolumn_overview_items_amount.pack_start(self.tvcolumn_overview_items_amount_renderer, True)
		
		# Link the renderers to the ListStore
		self.tvcolumn_overview_items_name.add_attribute(self.tvcolumn_overview_items_name_renderer, 'text', self.COL_NAMES_ITEM["NAME"])
		self.tvcolumn_overview_items_details.add_attribute(self.tvcolumn_overview_items_details_renderer, 'text', self.COL_NAMES_ITEM["DETAILS"])
		self.tvcolumn_overview_items_amount.add_attribute(self.tvcolumn_overview_items_amount_renderer, 'text', self.COL_NAMES_ITEM["AMOUNT"])
		
		# Set extras for the columns
		self.tvcolumn_overview_items_name.set_sort_column_id(self.COL_NAMES_ITEM["NAME"])
		self.tvcolumn_overview_items_details.set_sort_column_id(self.COL_NAMES_ITEM["DETAILS"])
		self.tvcolumn_overview_items_amount.set_sort_column_id(self.COL_NAMES_ITEM["AMOUNT"])
		
		# Build the TreeView
		self.treeview_overview_items = gtk.TreeView(self.liststore_filter_overview_items)
		self.treeview_overview_items.append_column(self.tvcolumn_overview_items_name)
		self.treeview_overview_items.append_column(self.tvcolumn_overview_items_details)
		self.treeview_overview_items.append_column(self.tvcolumn_overview_items_amount)
		
		# Connect the signals
		self.treeview_overview_items_selection = self.treeview_overview_items.get_selection()
		self.treeview_overview_items_selection.connect('changed', self.callback_treeview_overview_items_changed)
		
		# Scrolled Window
		self.scroll_treeview_overview_items = gtk.ScrolledWindow()
		
		self.scroll_treeview_overview_items.set_property('hscrollbar-policy', gtk.POLICY_AUTOMATIC)
		self.scroll_treeview_overview_items.set_property('vscrollbar-policy', gtk.POLICY_AUTOMATIC)
		
		self.scroll_treeview_overview_items.add(self.treeview_overview_items)
		
		# Padding
		self.padding_overview_item_list = gtk.HBox()
		self.padding_overview_item_list.pack_start(self.scroll_treeview_overview_items, padding = 10)
		
		# Frame
		self.frame_overview_item_list = gtk.Frame(label = "Items")
		self.frame_overview_item_list.add(self.padding_overview_item_list)
		
		"""
		PAGE: Overview
		ITEM: Frame HBox
		"""
		self.hbox_overview_frames = gtk.HBox(spacing = 10)
		self.hbox_overview_frames.pack_start(self.frame_overview_place_list)
		self.hbox_overview_frames.pack_start(self.frame_overview_item_list)
		
		"""
		PAGE: Overview
		ITEM: Buttons
		"""
		self.button_overview_add_place = gtk.Button("Add Place")
		self.button_overview_add_place.connect('clicked', self.callback_button_clicked)
		self.button_overview_remove_place = gtk.Button("Remove Place")
		self.button_overview_remove_place.connect('clicked', self.callback_button_clicked)
		
		"""
		PAGE: Overview
		ITEM: Button HBox
		"""
		self.hbox_overview_buttons = gtk.HBox(spacing = 5)
		self.hbox_overview_buttons.pack_start(self.button_overview_add_place)
		self.hbox_overview_buttons.pack_start(self.button_overview_remove_place)
		
		"""
		PAGE: Overview
		ITEM: Main VBox
		"""
		self.vbox_overview = gtk.VBox(spacing = 5)
		self.vbox_overview.pack_start(self.hbox_overview_frames)
		self.vbox_overview.pack_start(self.hbox_overview_buttons, expand = False)
		
		"""
		PAGE: Search
		ITEM: Search Term Input
		"""
		self.entry_search_term = gtk.Entry()
		self.entry_search_term.connect('changed', self.callback_entry_search_term_changed)
		
		self.label_search_term = gtk.Label("Search:")
		
		self.hbox_search_term = gtk.HBox(spacing = 5)
		self.hbox_search_term.pack_start(self.label_search_term, expand = False)
		self.hbox_search_term.pack_start(self.entry_search_term)
		
		"""
		PAGE: Search
		ITEM: Results TreeView
		"""
		# ListStore filter (for filtering based on search term)
		def _filter_search_items(model, iter, user_data = None):
			if model[iter][3] is None:
				return True
			
			return self.entry_search_term.get_text().lower() in model[iter][3].lower()
		
		self.liststore_filter_search_items = self.liststore_items.filter_new()
		self.liststore_filter_search_items.set_visible_func(_filter_search_items, data = None)
		
		# CellRenderer for the TreeView columns
		self.tvcolumn_search_items_name_renderer = gtk.CellRendererText()
		self.tvcolumn_search_items_place_renderer = gtk.CellRendererCombo()
		self.tvcolumn_search_items_details_renderer = gtk.CellRendererText()
		self.tvcolumn_search_items_amount_renderer = gtk.CellRendererText()
		
		# Make the renderers editable
		self.tvcolumn_search_items_name_renderer.set_property('editable', True)
		self.tvcolumn_search_items_place_renderer.set_property('editable', True)
		
		self.tvcolumn_search_items_place_renderer.set_property('has-entry', False)
		self.tvcolumn_search_items_place_renderer.set_property('model', self.liststore_places)
		self.tvcolumn_search_items_place_renderer.set_property('text-column', self.COL_NAMES_PLACE["NAME"])
		
		self.tvcolumn_search_items_details_renderer.set_property('editable', True)
		self.tvcolumn_search_items_amount_renderer.set_property('editable', True)
		
		# Connect the renderer signals (the number is the column affected by the edit)
		self.tvcolumn_search_items_name_renderer.connect('edited', self.callback_treeview_cell_edited, (self.liststore_filter_search_items, self.liststore_items, self.COL_NAMES_ITEM["NAME"]))
		
		self.tvcolumn_search_items_place_renderer.connect('edited', self.callback_treeview_cell_edited, (self.liststore_filter_search_items, self.liststore_items, self.COL_NAMES_ITEM["PLACE_NAME"]))
		self.tvcolumn_search_items_place_renderer.connect('changed', self.callback_treeview_cell_item_place_changed, (self.liststore_filter_search_items, self.liststore_items))
		
		self.tvcolumn_search_items_details_renderer.connect('edited', self.callback_treeview_cell_edited, (self.liststore_filter_search_items, self.liststore_items, self.COL_NAMES_ITEM["DETAILS"]))
		self.tvcolumn_search_items_amount_renderer.connect('edited', self.callback_treeview_cell_edited, (self.liststore_filter_search_items, self.liststore_items, self.COL_NAMES_ITEM["AMOUNT"]))
		
		# Define TreeView columns
		self.tvcolumn_search_items_name = gtk.TreeViewColumn("Name")
		self.tvcolumn_search_items_place = gtk.TreeViewColumn("Place")
		self.tvcolumn_search_items_details = gtk.TreeViewColumn("Details")
		self.tvcolumn_search_items_amount = gtk.TreeViewColumn("Amount")
		
		# Add renderers to the columns
		self.tvcolumn_search_items_name.pack_start(self.tvcolumn_search_items_name_renderer, True)
		self.tvcolumn_search_items_place.pack_start(self.tvcolumn_search_items_place_renderer, True)
		self.tvcolumn_search_items_details.pack_start(self.tvcolumn_search_items_details_renderer, True)
		self.tvcolumn_search_items_amount.pack_start(self.tvcolumn_search_items_amount_renderer, True)
		
		# Link the renderers to the ListStore
		self.tvcolumn_search_items_name.add_attribute(self.tvcolumn_search_items_name_renderer, 'text', self.COL_NAMES_ITEM["NAME"])
		self.tvcolumn_search_items_place.add_attribute(self.tvcolumn_search_items_place_renderer, 'text', self.COL_NAMES_ITEM["PLACE_NAME"])
		self.tvcolumn_search_items_details.add_attribute(self.tvcolumn_search_items_details_renderer, 'text', self.COL_NAMES_ITEM["DETAILS"])
		self.tvcolumn_search_items_amount.add_attribute(self.tvcolumn_search_items_amount_renderer, 'text', self.COL_NAMES_ITEM["AMOUNT"])
		
		# Set extras for the columns
		self.tvcolumn_search_items_name.set_sort_column_id(self.COL_NAMES_ITEM["NAME"])
		self.tvcolumn_search_items_place.set_sort_column_id(self.COL_NAMES_ITEM["PLACE_NAME"])
		self.tvcolumn_search_items_details.set_sort_column_id(self.COL_NAMES_ITEM["DETAILS"])
		self.tvcolumn_search_items_amount.set_sort_column_id(self.COL_NAMES_ITEM["AMOUNT"])
		
		# Build the TreeView
		self.treeview_search_items = gtk.TreeView(self.liststore_filter_search_items)
		self.treeview_search_items.append_column(self.tvcolumn_search_items_name)
		self.treeview_search_items.append_column(self.tvcolumn_search_items_place)
		self.treeview_search_items.append_column(self.tvcolumn_search_items_details)
		self.treeview_search_items.append_column(self.tvcolumn_search_items_amount)
		
		# Connect the signals
		self.treeview_search_items_selection = self.treeview_search_items.get_selection()
		self.treeview_search_items_selection.connect('changed', self.callback_treeview_search_items_changed)
		
		# Scrolled Window
		self.scroll_treeview_search_items = gtk.ScrolledWindow()
		
		self.scroll_treeview_search_items.set_property('hscrollbar-policy', gtk.POLICY_AUTOMATIC)
		self.scroll_treeview_search_items.set_property('vscrollbar-policy', gtk.POLICY_AUTOMATIC)
		
		self.scroll_treeview_search_items.add(self.treeview_search_items)
		
		# Frame
		self.frame_search_item_list = gtk.Frame(label = "Matching Items")
		self.frame_search_item_list.add(self.scroll_treeview_search_items)
		
		"""
		PAGE: Search
		ITEM: Buttons
		"""
		self.button_search_add_item = gtk.Button("Add Item")
		self.button_search_add_item.connect('clicked', self.callback_button_clicked)
		self.button_search_remove_item = gtk.Button("Remove Item")
		self.button_search_remove_item.connect('clicked', self.callback_button_clicked)
		
		"""
		PAGE: Search
		ITEM: Button HBox
		"""
		self.hbox_search_buttons = gtk.HBox(spacing = 5)
		self.hbox_search_buttons.pack_start(self.button_search_add_item)
		self.hbox_search_buttons.pack_start(self.button_search_remove_item)
		
		"""
		PAGE: Search
		ITEM: Main VBox
		"""
		self.vbox_search = gtk.VBox(spacing = 5)
		self.vbox_search.pack_start(self.hbox_search_term, expand = False)
		self.vbox_search.pack_start(self.frame_search_item_list)
		self.vbox_search.pack_start(self.hbox_search_buttons, expand = False)
		
		"""
		ITEM: Main Notebook
		"""
		self.notebook_main = gtk.Notebook()
		self.notebook_main.set_tab_pos(gtk.POS_TOP)
		self.notebook_main.append_page(self.vbox_overview, gtk.Label("Places"))
		self.notebook_main.append_page(self.vbox_search, gtk.Label("Items"))
		
		"""
		ITEM: Main HBox
		"""
		self.hbox_main = gtk.HBox(spacing = 10)
		self.hbox_main.pack_start(self.notebook_main)
		
		"""
		ITEM: Main Window
		"""
		self.window.add(self.hbox_main)
		self.window.show_all()
	
	def run(self):
		gtk.main()
	
	def quit(self, widget, data = None):
		# The user wants to quit the application
		self.db.commit()
		self.cur.close()
		self.db.close()
		gtk.main_quit()