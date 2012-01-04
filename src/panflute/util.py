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
Generic utility functions used throughout Panflute.
"""

from __future__ import absolute_import

import panflute.defs

import gettext
import locale
import logging
import os.path
import urllib


@property
def log (self):
    """
    Produce a logger for a class.  This should be imported into the
    class's namespace.
    """

    return logging.getLogger ("{0}.{1}".format (self.__module__,
                                                self.__class__.__name__))


def init_i18n ():
    """
    Initialize internationalization support.
    """

    domain = "panflute"
    for module in [gettext, locale]:
        module.bindtextdomain (domain, os.path.join (panflute.defs.DATA_DIR, "locale"))
        module.bind_textdomain_codeset (domain, "UTF-8")
        module.textdomain (domain)


def make_url (path):
    """
    Convert a local path into a properly-formed URL.  If the path is already
    a URL (file:// or otherwise), do nothing.
    """

    if path.startswith ("/"):
        # pathname2url chokes on non-8-bit characters
        return "file://{0}".format (urllib.pathname2url (path.encode ("utf-8")))
    else:
        return path


def get_xdg_data_home_directory ():
    """
    Determine the place to save Panflute's log files, creating it if it
    doesn't already exist.
    """

    data_home = os.getenv ("XDG_DATA_HOME", os.path.expanduser ("~/.local/share"))
    dirname = os.path.join (data_home, "panflute")

    try:
        os.makedirs (dirname, 0700)
    except OSError:
        # Directory already existing is not a failure
        pass

    return dirname
