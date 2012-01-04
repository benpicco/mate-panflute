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
Classes for managing connections to music players.
"""

from __future__ import absolute_import

import dbus
import dbus.exceptions
import mateconf
import gobject
import os
import re
import subprocess
import sys


class Connector (gobject.GObject):
    """
    Base class for objects managing a connection to a music player.

    Objects of this class attempt to establish a connection to a particular
    player, and indicate via a GObject property when one is available.  Upon
    request, they also create the instances of MPRIS interface objects to
    expose via D-Bus.
    """

    __gproperties__ = {
        "connected": (gobject.TYPE_BOOLEAN,
                      "connected",
                      "Whether a connection to the player is currently available.",
                      False,
                      gobject.PARAM_READWRITE),
        "internal-name": (gobject.TYPE_STRING,
                          "internal-name",
                          "Named used internally to identify the connector, guaranteed never to change.",
                          "",
                          gobject.PARAM_READABLE),
        # FIXME: Should this be translatable?
        "display-name": (gobject.TYPE_STRING,
                         "display-name",
                         "Name of the connector, as presented to a user.",
                         "",
                         gobject.PARAM_READABLE),
        "icon-name": (gobject.TYPE_STRING,
                      "icon-name",
                      "Name of the themed icon associated with the player, if any.",
                      "",
                      gobject.PARAM_READWRITE)
    }


    def __init__ (self, internal_name, display_name):
        gobject.GObject.__init__ (self)
        assert re.match (r"^[a-z0-9_]+$", internal_name)

        self.__values = {
            "connected": False,
            "internal-name": internal_name,
            "display-name": display_name,
            "icon-name": ""
        }


    def launch (self):
        """
        Start the player.  Returns False if there was an obvious error, True
        otherwise.

        By default, the appropriate command is looked up in MateConf and executed.
        Subclasses can replace this behavior with other techniques.
        """

        return self.launch_via_command ()


    def launch_via_command (self):
        """
        Start the player via the command stored in MateConf.  This is normally
        used as the if-all-else-fails way to launch a player.
        """

        client = mateconf.client_get_default ()
        key = "/apps/panflute/daemon/{0}/launch_command".format (self.props.internal_name)
        command = client.get_string (key)

        self.log.debug ("Running \"{0}\"".format (command))

        with open ("/dev/null", "r+") as null:
            # Running under the shell means we have no idea if it worked or not,
            # since spawning the shell itself will always succeed.
            subprocess.Popen (command, shell = True, close_fds = True, preexec_fn = os.setsid,
                              stdin = null, stdout = null, stderr = null)

        # No way to tell if the command was successful because of the subshell
        return True


    def root (self, **kwargs):
        """
        Create the / MPRIS object for this player.
        """

        raise NotImplementedError


    def track_list (self, **kwargs):
        """
        Create the /TrackList object for this player.
        """

        raise NotImplementedError


    def player (self, **kwargs):
        """
        Create the /Player object for this player.
        """

        raise NotImplementedError


    def stop_polling (self):
        """
        Stop actively polling for a connection, if polling is needed.
        """

        pass


    def resume_polling (self):
        """
        Start actively polling for a connection, if polling is needed.
        """

        pass


    ##########################################################################
    #
    # GObject overrides
    #
    ##########################################################################


    def do_get_property (self, property):
        return self.__values[property.name]


    def do_set_property (self, property, value):
        self.__values[property.name] = value


gobject.type_register (Connector)


##############################################################################


class DBusConnector (Connector):
    """
    Specialized version of Connector for players that use D-Bus themselves.

    This base class watches for a particular name to be claimed on the
    session bus and updates the "connected" property accordingly.  It is
    still the subclass's responsibility to implement Connector's methods.
    """

    from panflute.util import log


    def __init__ (self, internal_name, display_name, dbus_name):
        Connector.__init__ (self, internal_name, display_name)
        self.__dbus_name = dbus_name

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.freedesktop.DBus", "/org/freedesktop/DBus")
        self.__bus = dbus.Interface (proxy, "org.freedesktop.DBus")

        self.__bus.connect_to_signal ("NameOwnerChanged", self.__name_owner_changed_cb,
                                      arg0 = dbus_name)

        self.__bus.NameHasOwner (dbus_name,
                                reply_handler = self.__name_has_owner_cb,
                                error_handler = self.log.error)


    def launch (self):
        return self.launch_via_dbus () or Connector.launch (self)


    def launch_via_dbus (self):
        """
        Try to launch the player solely via D-Bus activation, returning
        True if it worked and False otherwise.
        """

        try:
            self.log.debug ("Activating {0}".format (self.__dbus_name))
            self.__bus.StartServiceByName (self.__dbus_name, 0)
            return True
        except dbus.exceptions.DBusException, e:
            # Happens if there's no .service file enabling D-Bus activation.
            return False


    def __name_has_owner_cb (self, has_owner):
        """
        Sets the "connected" flag if the target name is already on the bus.
        """

        if has_owner:
            self.props.connected = True


    def __name_owner_changed_cb (self, name, old_owner, new_owner):
        """
        Looks for the target name appearing or disappearing on the bus,
        setting the "connected" flag accordingly.
        """

        # Treat ownership transfers as though the old owner quit and then
        # a new owner appeared.
        if new_owner != "":
            if old_owner != "":
                self.props.connected = False
            self.props.connected = True
        else:
            self.props.connected = False


##############################################################################


class PollingConnector (Connector):
    """
    Specialized version of Connector for players that need to use polling when
    trying to connect.

    This base class periodically calls a function that attempts to connect.
    That function is not called if a connection is available, or if the
    manager has asked polling to cease (because some other player is connected,
    and there's no need to waste resources polling for nothing).
    """

    from panflute.util import log

    POLL_INTERVAL = 5000


    def __init__ (self, internal_name, display_name):
        Connector.__init__ (self, internal_name, display_name)
        self.__should_poll = False
        self.__poll_source = None

        self.connect ("notify::connected", self.__notify_connected_cb)


    def try_connect (self):
        """
        Make an active attempt to connect to the player.
        """

        raise NotImplementedError


    def stop_polling (self):
        self.log.debug ("Stop polling")

        self.__should_poll = False
        if self.__poll_source is not None:
            self.log.debug ("Removing the poll source")
            gobject.source_remove (self.__poll_source)
            self.__poll_source = None


    def resume_polling (self):
        self.log.debug ("Resume polling")

        self.__should_poll = True
        if not self.props.connected and self.__poll_source is None:
            self.log.debug ("Registering the poll source")
            self.__poll_source = gobject.timeout_add (self.POLL_INTERVAL, self.__poll_cb)
            self.try_connect ()


    def __notify_connected_cb (self, conn, pspec):
        """
        Stop or start polling (if allowed) based on whether a connection is
        currently available.
        """

        self.log.debug ("Connection status changed to {0}".format (self.props.connected))

        if self.props.connected and self.__poll_source is not None:
            self.log.debug ("Removing the poll source")
            gobject.source_remove (self.__poll_source)
            self.__poll_source = None
        elif not self.props.connected and self.__poll_source is None and self.__should_poll:
            self.log.debug ("Registering the poll source")
            self.__poll_source = gobject.timeout_add (self.POLL_INTERVAL, self.__poll_cb)
            # Don't bother trying to reconnect immediately.


    def __poll_cb (self):
        """
        Poll for a connection.
        """

        self.try_connect ()
        return True


##############################################################################


class MultiConnector (Connector):
    """
    Specialized version of Connector for players with multiple incompatible
    interfaces requiring their own specialized Connector implementations.

    If multiple children are connected, MultiConnector tries to pick which
    to use based on priority order, but there's no guarantee that will
    happen.  Once it finds one that works, it won't "let go" if a more
    preferred one becomes available.
    """

    from panflute.util import log


    def __init__ (self, internal_name, display_name, children):
        Connector.__init__ (self, internal_name, display_name)
        self.__children = children
        self.__active = None

        for child in children:
            child.connect ("notify::connected", self.__notify_connected_cb)
        self.__scan ()


    def launch (self):
        """
        Try the children in order, stopping once one reports probable
        success.

        It's important that none of the children fall back to the default
        implementation of this method, which runs a shell command and thus
        always seems to succeed.  That behavior should be handled by the
        MultiConnector itself.
        """

        for child in self.__children:
            if child.launch ():
                return True
        return Connector.launch (self)


    def root (self, **kwargs):
        return self.__active.root (**kwargs)


    def track_list (self, **kwargs):
        return self.__active.track_list (**kwargs)


    def player (self, **kwargs):
        return self.__active.player (**kwargs)


    def stop_polling (self):
        for child in self.__children:
            child.stop_polling ()


    def resume_polling (self):
        for child in self.__children:
            child.resume_polling ()


    def __notify_connected_cb (self, child, pspec):
        """
        If something becomes available or the active child goes away, look for
        a new child to make active.
        """

        if not (self.__active is not None and self.__active.props.connected):
            self.__scan ()


    def __scan (self):
        """
        Make the first child found to be connected the active child.
        """

        for child in self.__children:
            if child.props.connected:
                self.__active = child
                self.props.connected = True
                return
        self.__active = None
        self.props.connected = False


gobject.type_register (MultiConnector)
