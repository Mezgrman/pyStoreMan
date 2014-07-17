#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Julian Metzler
# See the LICENSE file for the full license.

"""
Main program
"""

from storeman_classes import GUI

import os

def main():
	# Store the database in ~/.pyStoreMan/storeman.db
	db_file = os.path.join(os.path.expanduser("~"), ".pyStoreMan/storeman.db")
	dirname = os.path.dirname(db_file)
	if not os.path.exists(dirname):
		os.makedirs(dirname)
	
	gui = GUI(database = db_file)
	gui.run()

if __name__ == "__main__":
	main()