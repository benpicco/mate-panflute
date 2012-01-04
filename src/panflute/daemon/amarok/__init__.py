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
Interface translator for multiple versions of Amarok.
"""

from __future__ import absolute_import

import panflute.daemon.amarok.v2_0
import panflute.daemon.connector


class Connector (panflute.daemon.connector.MultiConnector):
    """
    Connector for multiple incompatible versions of Amarok.
    """

    def __init__ (self):
        # Since Amarok 1.4 support depends on some optional modules, handle
        # exceptions thrown during the import.

        children = [ panflute.daemon.amarok.v2_0.Connector ()
                   ]

        try:
            import panflute.daemon.amarok.v1_4 as v1_4
            children.append (v1_4.Connector ())
        except Exception, e:
            self.log.info ("Failed to load Amarok 1.4 connector: {0}".format (e))

        panflute.daemon.connector.MultiConnector.__init__ (self, "amarok", "Amarok", children)
        self.props.icon_name = "amarok"
