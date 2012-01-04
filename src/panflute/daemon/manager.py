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
Top-level connection manager.

Waits for a music player to become available and then exposes it via D-Bus,
translating the player's native RPC interface to MPRIS.
"""

from __future__ import absolute_import

import panflute.daemon.amarok
import panflute.daemon.audacious
import panflute.daemon.banshee
import panflute.daemon.clementine
import panflute.daemon.connproxy
import panflute.daemon.decibel
import panflute.daemon.exaile
import panflute.daemon.guayadeque
import panflute.daemon.listen
import panflute.daemon.muine
import panflute.daemon.pithos
import panflute.daemon.qmmp
import panflute.daemon.quodlibet
import panflute.daemon.rhythmbox
import panflute.daemon.songbird
import panflute.daemon.vlc

import dbus
import dbus.service
import mateconf
import sys


class Manager (object):
    """
    The top-level connection manager and hub for the Panflute daemon.
    """

    from panflute.util import log


    def __init__ (self):
        self.connectors = {}
        self.__proxies = {}

        bus = dbus.SessionBus ()
        self.__panflute_bus_name = dbus.service.BusName ("org.kuliniewicz.Panflute", bus)

        self.__register_connector (panflute.daemon.rhythmbox.Connector ())
        self.__register_connector (panflute.daemon.banshee.Connector ())
        self.__register_connector (panflute.daemon.amarok.Connector ())
        self.__register_connector (panflute.daemon.audacious.Connector ())
        self.__register_connector (panflute.daemon.clementine.Connector ())
        self.__register_connector (panflute.daemon.decibel.Connector ())
        self.__register_connector (panflute.daemon.exaile.Connector ())
        self.__register_connector (panflute.daemon.guayadeque.Connector ())
        self.__register_connector (panflute.daemon.listen.Connector ())
        self.__register_connector (panflute.daemon.muine.Connector ())
        self.__register_connector (panflute.daemon.pithos.Connector ())
        self.__register_connector (panflute.daemon.qmmp.Connector ())
        self.__register_connector (panflute.daemon.quodlibet.Connector ())
        self.__register_connector (panflute.daemon.songbird.Connector ())
        self.__register_connector (panflute.daemon.vlc.Connector ())

        try:
            import panflute.daemon.moc as moc
            self.__register_connector (moc.Connector ())
        except Exception, e:
            self.log.info ("Failed to load MOC connector: {0}".format (e))

        try:
            import panflute.daemon.mpd as mpd
            self.__register_connector (mpd.Connector ())
        except Exception, e:
            self.log.info ("Failed to load MPD connector: {0}".format (e))

        try:
            import panflute.daemon.xmms as xmms
            self.__register_connector (xmms.Connector ())
        except Exception, e:
            self.log.info ("Failed to load XMMS connector: {0}".format (e))

        try:
            import panflute.daemon.xmms2 as xmms2
            self.__register_connector (xmms2.Connector ())
        except Exception, e:
            self.log.info ("Failed to load XMMS2 connector: {0}".format (e))

        self.__manager_proxy = panflute.daemon.connproxy.ManagerProxy (self, bus_name = self.__panflute_bus_name)

        client = mateconf.client_get_default ()
        client.add_dir ("/apps/panflute/daemon", mateconf.CLIENT_PRELOAD_NONE)
        client.notify_add ("/apps/panflute/daemon/preferred_player", self.__preferred_player_changed_cb)
        self.__expose_preferred (client.get_string ("/apps/panflute/daemon/preferred_player"))

        self.__live = None
        self.__root = None
        self.__track_list = None
        self.__player = None

        self.__scan_for_connected ()


    def __register_connector (self, conn):
        """
        Add a connector to the list of connectors being used.
        """

        proxy = panflute.daemon.connproxy.ConnectorProxy (conn, bus_name = self.__panflute_bus_name)
        self.connectors[conn.props.internal_name] = conn
        self.__proxies[conn.props.internal_name] = proxy

        conn.resume_polling ()
        conn.connect ("notify::connected", self.__notify_connected_cb)


    def __preferred_player_changed_cb (self, client, id, entry, unused):
        """
        Expose the newly selected preferred player via D-Bus.
        """

        self.__expose_preferred (entry.value.get_string ())


    def __expose_preferred (self, preferred_name):
        """
        Expose the preferred player via D-Bus.
        """

        self.log.debug ("Preferred player is now {0}".format (preferred_name))

        if self.__proxies.has_key ("preferred"):
            self.__proxies["preferred"].remove_from_connection ()
            del self.__proxies["preferred"]

        if self.connectors.has_key (preferred_name):
            proxy = panflute.daemon.connproxy.ConnectorProxy (self.connectors[preferred_name],
                                                              object_path = "/connectors/preferred",
                                                              bus_name = self.__panflute_bus_name)
            self.__proxies["preferred"] = proxy
        else:
            self.log.warn ("Couldn't find a player named \"{0}\" to make preferred".format (preferred_name))

        self.__manager_proxy.PreferredChanged ()



    def __scan_for_connected (self):
        """
        Scan through the list of possible connections and expose the first one
        that actually is connected right now.
        """

        self.log.debug ("scanning for connected players")
        for conn in self.connectors.values ():
            if conn.props.connected:
                self.__expose (conn)
                break


    def expose_by_name (self, name):
        """
        Expose a specific named player, if it's currently connected.
        """

        if self.__live is not None and self.__live.props.internal_name != name and name in self.connectors:
            conn = self.connectors[name]
            if conn.props.connected:
                self.log.debug ("explicitly exposing {0}".format (name))
                self.__withdraw ()
                self.__expose (conn)


    def __expose (self, conn):
        """
        Expose the specified music player via Panflute's D-Bus interface.
        """

        assert (conn.props.connected)
        assert (self.__live is None)
        assert (self.__root is None)
        assert (self.__track_list is None)
        assert (self.__player is None)

        self.log.debug ("exposing {0}".format (conn.props.internal_name))

        for other_conn in self.connectors.values ():
            other_conn.stop_polling ()

        # By only acquiring the bus name here, org.mpris.panflute will only
        # exist if a player is available.  Explcitly requesting the bus name
        # is needed if this isn't the first time we've created the BusName
        # object; otherwise the dbus library won't request it automatically.

        bus = dbus.SessionBus ()
        bus_name = dbus.service.BusName ("org.mpris.panflute", bus)
        bus.request_name ("org.mpris.panflute")
        self.__live = conn

        self.__player = conn.player (object_path = "/Player", bus_name = bus_name)
        self.__track_list = conn.track_list (object_path = "/TrackList", bus_name = bus_name)
        self.__root = conn.root (object_path = "/", bus_name = bus_name)


    def __withdraw (self):
        """
        Stop exposing anything via Panflute's D-Bus interface.
        """

        assert (self.__live is not None)
        assert (self.__root is not None)
        assert (self.__track_list is not None)
        assert (self.__player is not None)

        self.log.debug ("withdrawing {0}".format (self.__live.props.internal_name))

        self.__root.remove_from_connection ()
        self.__root = None

        self.__track_list.remove_from_connection ()
        self.__track_list = None

        self.__player.remove_from_connection ()
        self.__player = None

        self.__live = None
        dbus.SessionBus ().release_name ("org.mpris.panflute")

        for conn in self.connectors.values ():
            conn.resume_polling ()


    def __notify_connected_cb (self, conn, pspec):
        """
        Called whenever the "connected" property of a connector changes.

        This method maintains the following invariants:
         * As long as a connector is connected, something is being exposed.
         * Once something is exposed, it stays exposed until the connection to
           its backend is lost.
        """

        self.log.debug ("{0} status is now {1}".format (conn.props.internal_name, conn.props.connected))

        if self.__live is None and conn.props.connected:
            self.__expose (conn)
        elif self.__live is conn and not conn.props.connected:
            self.__withdraw ()
            self.__scan_for_connected ()
