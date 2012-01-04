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
Classes for exposing Connector objects via D-Bus.
"""

from __future__ import absolute_import

import dbus.service


CONNECTOR_INTERFACE = "org.kuliniewicz.Panflute.Connector"
MANAGER_INTERFACE = "org.kuliniewicz.Panflute.Manager"


class ConnectorProxy (dbus.service.Object):
    """
    The MPRIS object that exposes a single Connector object.  By default, it
    will appear at /connectors/{internal-name}.
    """

    def __init__ (self, conn, **kwargs):
        if not kwargs.has_key ("object_path"):
            kwargs["object_path"] = "/connectors/{0}".format (conn.props.internal_name)
        dbus.service.Object.__init__ (self, **kwargs)

        conn.connect ("notify::connected", self.__notify_connected_cb)
        self.__conn = conn


    @dbus.service.method (dbus_interface = CONNECTOR_INTERFACE,
                          in_signature = "",
                          out_signature = "s")
    def GetInternalName (self):
        """
        Get the internal name of the connector.
        """

        return self.__conn.props.internal_name


    @dbus.service.method (dbus_interface = CONNECTOR_INTERFACE,
                          in_signature = "",
                          out_signature = "s")
    def GetDisplayName (self):
        """
        Get the display name of the connector.
        """

        return self.__conn.props.display_name


    @dbus.service.method (dbus_interface = CONNECTOR_INTERFACE,
                          in_signature = "",
                          out_signature = "s")
    def GetIconName (self):
        """
        Get the icon name for the connector.
        """

        return self.__conn.props.icon_name


    @dbus.service.method (dbus_interface = CONNECTOR_INTERFACE,
                          in_signature = "",
                          out_signature = "b")
    def GetConnected (self):
        """
        Get whether or not the connector is currently connected to the
        music player.
        """

        return self.__conn.props.connected


    @dbus.service.signal (dbus_interface = CONNECTOR_INTERFACE,
                          signature = "b")
    def ConnectedChanged (self, connected):
        """
        Signals that the object's Connected state has changed.
        """

        pass


    @dbus.service.method (dbus_interface = CONNECTOR_INTERFACE,
                          in_signature = "",
                          out_signature = "")
    def Launch (self):
        """
        Start the player.
        """

        self.__conn.launch ()


    def __notify_connected_cb (self, conn, pspec):
        """
        Relay the connection-changed notification via D-Bus.
        """

        self.ConnectedChanged (conn.props.connected)


class ManagerProxy (dbus.service.Object):
    """
    The MPRIS object that exposes methods that fetch information about all the
    connectors.  By default, it will appear at /connectors.
    """

    def __init__ (self, manager, **kwargs):
        if not kwargs.has_key ("object_path"):
            kwargs["object_path"] = "/connectors"
        dbus.service.Object.__init__ (self, **kwargs)

        self.__manager = manager


    @dbus.service.method (dbus_interface = MANAGER_INTERFACE,
                          in_signature = "",
                          out_signature = "a{sa{ss}}")
    def DescribeConnectors (self):
        """
        Get a dict of a description of each available connector's
        salient properties.
        """

        result = {}
        for internal_name in self.__manager.connectors:
            connector = self.__manager.connectors[internal_name]
            result[internal_name] = { "display_name": connector.props.display_name }
            if connector.props.icon_name != "":
                result[internal_name]["icon_name"] = connector.props.icon_name
        return result


    @dbus.service.method (dbus_interface = MANAGER_INTERFACE,
                          in_signature = "s",
                          out_signature = "")
    def Expose (self, name):
        """
        Expose a particular player, if it's currently available.
        """

        self.__manager.expose_by_name (name)


    @dbus.service.signal (dbus_interface = MANAGER_INTERFACE,
                          signature = "")
    def PreferredChanged (self):
        """
        Signal that the object at /connectors/preferred has changed.
        """

        pass
