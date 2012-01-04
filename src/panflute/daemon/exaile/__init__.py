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
Interface translator for multiple versions of Exaile.
"""

from __future__ import absolute_import

import panflute.daemon.connector
import panflute.daemon.exaile.v0_2
import panflute.daemon.exaile.v0_3


class Connector (panflute.daemon.connector.MultiConnector):
    """
    Connector for multiple incompatible versions of Exaile.
    """

    def __init__ (self):
        panflute.daemon.connector.MultiConnector.__init__ (self, "exaile", "Exaile",
                [ panflute.daemon.exaile.v0_3.Connector (),
                  panflute.daemon.exaile.v0_2.Connector ()
                ])
        self.props.icon_name = "exaile"
