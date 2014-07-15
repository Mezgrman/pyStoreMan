#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Julian Metzler
# See the LICENSE file for the full license.

"""
Main program
"""

from storeman_classes import GUI

def main():
	gui = GUI(database = "storeman.db")
	gui.run()

if __name__ == "__main__":
	main()