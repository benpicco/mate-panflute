#! /usr/bin/env python

# Panflute
# Copyright (C) 2010 Paul Kuliniewicz <paul@kuliniewicz.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02111-1301, USA.

"""
A graphical debugger for the Panflute daemon.

The debugger displays the current status of the Panflute daemon, making it
easier to determine the root cause of a problem.
"""

from __future__ import absolute_import

import panflute.debugger.debugger
import panflute.defs

import gtk
import os.path


def create_debugger ():
    """
    Create a Debugger and return its main window.
    """

    builder = gtk.Builder ()
    builder.add_from_file (os.path.join (panflute.defs.PKG_DATA_DIR, "debugger.ui"))

    debugger = panflute.debugger.debugger.Debugger (builder)
    return builder.get_object ("debugger")
