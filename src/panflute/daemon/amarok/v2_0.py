#! /usr/bin/env python

# Panflute
# Copyright (C) 2009 Paul Kuliniewicz <paul@kuliniewicz.org>
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
Interface translator for Amarok.
"""

from __future__ import absolute_import

import panflute.daemon.passthrough


class Connector (panflute.daemon.passthrough.Connector):
    """
    Connection manager for Amarok.
    """

    def __init__ (self):
        panflute.daemon.passthrough.Connector.__init__ (self, "amarok", "Amarok",
                                                        "amarok")
        self.props.icon_name = "amarok"


    def player (self, **kwargs):
        return panflute.daemon.passthrough.Player ("amarok", True, **kwargs)
