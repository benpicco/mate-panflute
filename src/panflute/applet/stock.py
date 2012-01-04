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
Stock icons for the Panflute applet.

This module also provides some utility functions for working with stock
icons.
"""

from __future__ import absolute_import

import panflute.defs

import gtk
import os.path
import sys


PANFLUTE = "panflute"
SET_STAR = "panflute-set-star"
UNSET_STAR = "panflute-unset-star"


def register_stock_icons ():
    """
    Register the custom stock icons used by the applet.
    """

    factory = gtk.IconFactory ()
    factory.add_default ()

    for stock_id in [PANFLUTE, SET_STAR, UNSET_STAR]:
        pixbuf = gtk.gdk.pixbuf_new_from_file (os.path.join (panflute.defs.PKG_DATA_DIR, "{0}.svg".format (stock_id)))
        icon_set = gtk.IconSet (pixbuf)
        factory.add (stock_id, icon_set)


def render_icon_pixel_size (widget, stock_id, pixel_size):
    """
    Create a pixbuf out of a stock image, scaled to a specific pixel size.
    """

    # XXX: Is there a less hackish way to find the closest stock size?

    # Put a hard limit on the size, to prevent wasting time on excessive sizes
    # that can happen when the applet is being moved from one orientation to
    # another.
    pixel_size = min (pixel_size, 96)

    sizes = gtk.IconSize.__enum_values__.values ()
    nearest_pixbuf = None
    nearest_deviation = sys.maxint
    for size in sizes:
        if size != gtk.ICON_SIZE_INVALID:
            pixbuf = widget.render_icon (stock_id, size)
            if pixbuf is not None:
                deviation = abs (pixbuf.get_width () - pixel_size)
                if nearest_pixbuf is None or deviation < nearest_deviation:
                    nearest_pixbuf = pixbuf
                    nearest_deviation = deviation

    if nearest_pixbuf is not None:
        return nearest_pixbuf.scale_simple (pixel_size, pixel_size, gtk.gdk.INTERP_BILINEAR)
    else:
        return None
