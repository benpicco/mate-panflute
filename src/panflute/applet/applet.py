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
Implementation of the MATE panel applet for Panflute.

The panel applet provides playback controls, song information, and related
features to the user.  It relies on the Panflute daemon to actually
communicate with the music player, including the extended functions that
Panflute provides over MPRIS.
"""

from __future__ import absolute_import, division

import panflute.applet.conf
import panflute.applet.player
import panflute.applet.prefs
import panflute.applet.stock
import panflute.applet.widget
import panflute.defs
import panflute.mpris

import dbus
import functools
from   gettext     import gettext as _
import mateapplet
import gobject
import gtk
import os.path
import re
import xml.sax.saxutils


class Applet (object):
    """
    The applet itself.

    Technically, this object manages what's inside the actual Applet object
    obtained through the panel applet library, if you want to be
    pedantic about it.
    """

    from panflute.util import log

    TWO_ROW_SIZE_THRESHOLD = 48


    def __init__ (self, applet):
        self.__applet = applet
        self.__connected = False
        self.__player = None
        self.__first_widgets = []
        self.__second_widgets = []

        gtk.window_set_default_icon_from_file (
            os.path.join (panflute.defs.PKG_DATA_DIR, "{0}.svg".format (panflute.applet.stock.PANFLUTE)))
        applet.set_border_width (0)
        applet.set_background_widget (applet)       # the "transparency hack"

        try:
            import pynotify
            pynotify.init ("panflute-applet")
        except ImportError, e:
            self.log.warn ("Couldn't initialize notifications: {0}".format (e))

        applet.add_preferences ("/schemas/apps/panflute/applet/prefs")
        self.__conf = panflute.applet.conf.Conf (applet)

        self.__layout = LayoutManager (self.__conf)
        self.__layout.connect ("notify::layout", self.__layout_changed_cb)

        self.__notification = None
        self.__conf.connect_bool ("show_notifications", self.__show_notifications_changed_cb, call_now = True)

        applet.set_applet_flags (mateapplet.EXPAND_MINOR)
        applet.connect ("change-orient", self.__change_orient_cb)
        applet.connect ("change-size", self.__change_size_cb)
        applet.connect ("destroy", self.__destroy_cb)

        self.__prefs_dialog = None
        self.__about_dialog = None

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.freedesktop.DBus", "/org/freedesktop/DBus")
        self.__bus = dbus.Interface (proxy, "org.freedesktop.DBus")

        proxy = bus.get_object ("org.kuliniewicz.Panflute", "/connectors")
        self.__manager = dbus.Interface (proxy, "org.kuliniewicz.Panflute.Manager")

        self.__bus.connect_to_signal ("NameOwnerChanged", self.__name_owner_changed_cb,
                                      arg0 = "org.mpris.panflute")
        self.__bus.NameHasOwner ("org.mpris.panflute",
                                 reply_handler = self.__name_has_owner_cb,
                                 error_handler = self.log.error)

        self.__menu = ContextMenu (applet, bus, [
            ("Preferences", self.__preferences_cb),
            ("About", self.__about_cb)])
        self.__load_content ()

        applet.show ()


    def __destroy_cb (self, applet):
        """
        Shut down the player, if it exists.
        """

        if self.__player is not None:
            self.__player.shutdown ()


    def __name_has_owner_cb (self, has_owner):
        """
        Display whether a connection to the Panflute daemon is available.
        """

        self.__connected = has_owner
        self.__load_content ()


    def __name_owner_changed_cb (self, name, old_owner, new_owner):
        """
        Looks for the Panflute daemon to change its availability.
        """

        self.__connected = (new_owner != "")
        self.__load_content ()


    def __load_content (self):
        """
        Fill the applet with the appropriate widgets.
        """

        if self.__applet.get_child () is not None:
            self.__applet.remove (self.__applet.get_child ())

        self.__first_widgets = []
        self.__second_widgets = []

        if self.__connected:
            self.log.debug ("Setting layout to connected")

            if self.__player is None:
                self.__player = panflute.applet.player.Player ()
                self.__player.connect ("song-changed", self.__song_changed_cb)
                self.__player.connect ("notify::art-file", self.__notify_art_file_cb)

            for request in self.__layout.props.layout[0]:
                self.__add_widget (self.__first_widgets, request)
            for request in self.__layout.props.layout[1]:
                self.__add_widget (self.__second_widgets, request)
        else:
            self.log.debug ("Setting layout to disconnected")
            widget = LaunchButton (self.__bus)
            widget.show ()
            self.__first_widgets.append (widget)
            if self.__player is not None:
                self.__player.shutdown ()
                self.__player = None

        self.__check_visibility ()
        self.__bundle_widgets ()
        self.__applet.show ()


    def __add_widget (self, widget_list, internal_name):
        """
        Create a new widget and add it to the specified list of widgets.
        """

        widget = self.__layout.create_widget (internal_name, self.__player)
        widget.connect ("notify::visible", lambda widget, pspec: self.__check_visibility ())
        widget_list.append (widget)


    def __change_orient_cb (self, applet, orient):
        """
        Rearrange the widgets to fit the new applet orientation.
        """

        self.log.debug ("Reorienting applet")
        self.__bundle_widgets ()


    def __change_size_cb (self, applet, size):
        """
        Rearrange the widgets to fit the new applet size, if needed.
        """

        self.log.debug ("Resizing applet")
        self.__bundle_widgets ()


    def __bundle_widgets (self):
        """
        Bundle the applet's content widgets into a box according to the
        orientation of the panel.
        """

        # Undo previous bundling before doing the new one

        old_box = self.__applet.get_child ()
        if old_box is not None:
            self.__applet.remove (old_box)

        for widget in self.__first_widgets + self.__second_widgets:
            if widget.get_parent () is not None:
                widget.get_parent ().remove (widget)

        # Now bundle the widgets

        orient = self.__applet.get_orient ()
        size = self.__applet.get_size ()
        self.log.debug ("Applet size is {0}; two-row threshold is {1}".format (size, self.TWO_ROW_SIZE_THRESHOLD))

        if self.__applet.get_size () < self.TWO_ROW_SIZE_THRESHOLD:
            self.log.debug ("Forcing one-row layout due to size constraints")
            all_box = self.__bundle_row (self.__first_widgets + self.__second_widgets)
            self.__applet.add (all_box)
        else:
            first_box = self.__bundle_row (self.__first_widgets)
            second_box = self.__bundle_row (self.__second_widgets)

            if first_box is not None and second_box is not None:
                self.log.debug ("Using a two-row layout")
                if orient == mateapplet.ORIENT_UP or orient == mateapplet.ORIENT_DOWN:
                    big_box = gtk.VBox ()
                else:
                    big_box = gtk.HBox ()
                big_box.set_border_width (0)
                big_box.set_spacing (0)
                big_box.set_homogeneous (True)
                big_box.pack_start (first_box)
                big_box.pack_start (second_box)
                big_box.show ()
                self.__applet.add (big_box)
            elif first_box is not None:
                self.log.debug ("Using an empty-second-row layout")
                self.__applet.add (first_box)
            else:
                assert (second_box is not None)
                self.log.debug ("Using an empty-first-row layout")
                self.__applet.add (second_box)


    def __bundle_row (self, widgets):
        """
        Bundle a list of widgets into a box, according to the applet's
        orientation.
        """

        if len (widgets) > 0:
            orient = self.__applet.get_orient ()
            if orient == mateapplet.ORIENT_UP or orient == mateapplet.ORIENT_DOWN:
                box = gtk.HBox ()
            else:
                box = gtk.VBox ()
            box.set_border_width (0)

            for widget in widgets:
                if orient == mateapplet.ORIENT_RIGHT:
                    widget.set_angle (90)
                elif orient == mateapplet.ORIENT_LEFT:
                    widget.set_angle (270)
                else:
                    widget.set_angle (0)

                if widget.wants_padding:
                    padding = 3
                else:
                    padding = 0

                box.pack_start (widget, expand = widget.is_expandable, padding = padding)

            box.show ()
            return box
        else:
            return None


    def __check_visibility (self):
        """
        Make sure at least one widget is visible, and only make the resize
        handle appear if there's a visible widget that wants it.
        """

        something_visible = False
        need_handle = False

        for widget in self.__first_widgets + self.__second_widgets:
            something_visible |= widget.props.visible
            if widget.is_expandable:
                need_handle |= widget.props.visible

        if not something_visible:
            self.__conf.set_bool ("show_playback_button", True)

        if need_handle:
            self.__applet.set_applet_flags (mateapplet.EXPAND_MAJOR |
                                            mateapplet.EXPAND_MINOR |
                                            mateapplet.HAS_HANDLE)
        else:
            self.__applet.set_applet_flags (mateapplet.EXPAND_MINOR)


    def __layout_changed_cb (self, layout, pspec):
        """
        Redo the applet content if necessary, since the list of widgets to
        display changed.
        """

        # FIXME: This doesn't truly require recreating everything; this ought
        #        to just change the ordering of what widgets already exist.
        self.__load_content ()


    def __show_notifications_changed_cb (self, value):
        """
        Enable or disable display of notifications.
        """

        if value and self.__notification is None:
            self.log.debug ("Enabling notifications")
            self.__notification = self.__create_notification ()
        elif not value and self.__notification is not None:
            self.log.debug ("Disabling notifications")
            try:
                self.__notification.close ()
            except gobject.GError, e:
                pass
            self.__notification = None


    def __create_notification (self):
        """
        Create a new notification object, ready to be populated with content.
        """

        try:
            import pynotify
            notification = pynotify.Notification (" ", "", None, None)
            notification.set_urgency (pynotify.URGENCY_LOW)
            return notification
        except ImportError, e:
            # Already warned about missing pynotify at startup.
            return None


    def __song_changed_cb (self, player):
        """
        When the current song changed, maybe display a notification.
        """

        if self.__notification is not None and player.props.title is not None:
            # The title is automatically escaped, but the body is not.
            body = []
            if player.props.artist is not None:
                body.append (_("<i>by</i> {0}").format (xml.sax.saxutils.escape (player.props.artist)))
            if player.props.album is not None:
                body.append (_("<i>from</i> {0}").format (xml.sax.saxutils.escape (player.props.album)))

            # Notifications let you *replace* art, but not *remove* it.
            # Fake it with a blank image if there's no cover art.

            if player.props.art_file is not None:
                art_file = player.props.art_file
            else:
                art_file = os.path.join (panflute.defs.PKG_DATA_DIR, "panflute.svg")
            self.log.debug ("notification art: {0} --> {1}".format (player.props.art_file, art_file))

            self.__notification.update (player.props.title, "\n".join (body), art_file)
            self.__notification.show ()


    def __notify_art_file_cb (self, player, pspec):
        """
        When new art is available, update the notification.
        """

        if self.__notification.props.summary == player.props.title:
            self.__song_changed_cb (player)


    def __preferences_cb (self, component, verb):
        """
        Display the Preferences dialog.
        """

        def response_cb (dialog, response):
            dialog.hide ()

        def destroy_cb (dialog):
            self.__prefs_dialog = None

        if self.__prefs_dialog is None:
            self.__prefs_dialog = panflute.applet.prefs.create_preferences_dialog (self.__conf, self.__layout)
            self.__prefs_dialog.connect ("response", response_cb)
            self.__prefs_dialog.connect ("destroy", destroy_cb)

        self.__prefs_dialog.present ()


    def __about_cb (self, component, verb):
        """
        Display the About dialog.
        """

        def response_cb (dialog, response):
            dialog.hide ()

        def destroy_cb (dialog):
            self.__about_dialog = None

        if self.__about_dialog is None:
            self.__about_dialog = gtk.AboutDialog ()

            self.__about_dialog.set_name (_("Panflute Applet"))
            self.__about_dialog.set_version (panflute.defs.VERSION)
            self.__about_dialog.set_copyright (_("(C) {0} Paul Kuliniewicz").format (2010))
            self.__about_dialog.set_comments (_("Control your favorite music player from a MATE panel."))
            self.__about_dialog.set_website ("https://launchpad.net/panflute/")
            self.__about_dialog.set_authors (["Paul Kuliniewicz <paul@kuliniewicz.org>"])
            self.__about_dialog.set_translator_credits (_("translator-credits"))

            self.__about_dialog.connect ("response", response_cb)
            self.__about_dialog.connect ("destroy", destroy_cb)

        self.__about_dialog.present ()


##############################################################################


class ContextMenu (object):
    """
    Handles the applet's context menu, especially displaying a list of
    currently available players in order to allow switching between them.
    """

    from panflute.util import log


    def __init__ (self, applet, bus, verb_handlers):
        self.__applet = applet
        self.__bus = bus
        self.__verb_handlers = verb_handlers
        self.__handlers = []
        self.__current = None

        proxy = bus.get_object ("org.kuliniewicz.Panflute", "/connectors")
        self.__manager = dbus.Interface (proxy, "org.kuliniewicz.Panflute.Manager")

        proxy = bus.get_object ("org.freedesktop.DBus", "/org/freedesktop/DBus")
        self.__bus_obj = dbus.Interface (proxy, "org.freedesktop.DBus")

        self.__bus_obj.connect_to_signal ("NameOwnerChanged", self.__kuli_name_owner_changed_cb,
                                          arg0 = "org.kuliniewicz.Panflute")
        self.__bus_obj.connect_to_signal ("NameOwnerChanged", self.__mpris_name_owner_changed_cb,
                                          arg0 = "org.mpris.panflute")
        self.__bus_obj.NameHasOwner ("org.kuliniewicz.Panflute",
                                     reply_handler = self.__kuli_name_has_owner_cb,
                                     error_handler = self.log.warn)

        component = applet.get_popup_component ()
        component.connect ("ui-event", self.__ui_event_cb)


    def __kuli_name_has_owner_cb (self, has_owner):
        """
        Set up the context menu based on whether the daemon is running.
        """

        if has_owner:
            self.__manager.DescribeConnectors (reply_handler = self.__rebuild_menu,
                                               error_handler = lambda msg: (self.log.warn (msg), self.__rebuild_menu ({})))
        else:
            self.__rebuild_menu ({})


    def __kuli_name_owner_changed_cb (self, name, old_owner, new_owner):
        """
        Set up the context menu based on whether the daemon is now running.
        """

        if new_owner != "":
            self.__manager.DescribeConnectors (reply_handler = self.__rebuild_menu,
                                               error_handler = lambda msg: (self.log.warn (msg), self.__rebuild_menu ({})))
        else:
            self.__rebuild_menu ({})


    def __mpris_name_has_owner_cb (self, has_owner):
        """
        Find out which backend player the daemon is exposing.
        """

        if has_owner:
            self.__query_identity ()


    def __mpris_name_owner_changed_cb (self, name, old_owner, new_owner):
        """
        Find out which backend player the daemon is exposing, if the daemon
        is exposing anything.  If it isn't, do nothing; all the radio items
        will be hidden anyway.
        """

        if new_owner != "":
            self.__query_identity ()


    def __query_identity (self):
        """
        Query the active player for its identity.  A one-time object is
        created for this to make sure we don't accidentally launch the
        player merely by creating the D-Bus proxy object for it.  See
        lp:602173
        """

        proxy = self.__bus.get_object ("org.mpris.panflute", "/")
        root = dbus.Interface (proxy, panflute.mpris.INTERFACE)
        root.Identity (reply_handler = self.__identity_cb,
                       error_handler = self.log.warn)


    def __rebuild_menu (self, connectors):
        """
        Rebuild the context menu based on which connectors are available.
        """

        for handler in self.__handlers:
            handler.remove ()
        self.__handlers = []
        self.__names = {}

        if len (connectors) > 0:
            replacements = []
            for internal_name in sorted (connectors.keys ()):
                display_name = connectors[internal_name]["display_name"]
                verb = "Player_{0}".format (internal_name)
                item = '<menuitem name={0} verb={0} label={1} type="radio" group="players"/>'.format (
                        xml.sax.saxutils.quoteattr (verb),
                        xml.sax.saxutils.quoteattr (display_name))
                replacements.append (item)
                self.__names[internal_name] = display_name
            replacement = "".join (replacements) + "<separator/>"
        else:
            replacement = ""

        with file (os.path.join (panflute.defs.DATA_DIR, "mate-2.0", "ui", "MATE_Panflute_Applet.xml"), "r") as f:
            menu_xml = f.read ()

        menu_xml = menu_xml.replace ("<!--PLACEHOLDER-->", replacement)
        menu_xml = menu_xml.replace ("<Root>", "")
        menu_xml = menu_xml.replace ("</Root>", "")
        menu_xml = menu_xml.replace ("<popups>", "")
        menu_xml = menu_xml.replace ("</popups>", "")

        bus = dbus.SessionBus ()

        self.__applet.setup_menu (menu_xml, self.__verb_handlers, None)
        component = self.__applet.get_popup_component ()
        for internal_name in self.__names:
            path = "/commands/Player_{0}".format (internal_name)
            component.set_prop (path, "state", "0")
            component.set_prop (path, "hidden", "1")

            proxy = bus.get_object ("org.kuliniewicz.Panflute", "/connectors/{0}".format (internal_name))
            conn = dbus.Interface (proxy, "org.kuliniewicz.Panflute.Connector")

            callback = functools.partial (self.__connected_changed_cb, internal_name)
            conn.GetConnected (reply_handler = callback,
                               error_handler = self.log.warn)
            self.__handlers.append (conn.connect_to_signal ("ConnectedChanged", callback))

        if len (connectors) > 0:
            self.__bus_obj.NameHasOwner ("org.mpris.panflute",
                                         reply_handler = self.__mpris_name_has_owner_cb,
                                         error_handler = self.log.warn)


    def __ui_event_cb (self, component, path, event_type, state_string):
        """
        Try to expose the selected player when a radio item is selected.
        """

        match = re.match ("^Player_(.*)$", path)
        if match and state_string == "1":
            internal_name = match.group (1)
            if internal_name != self.__current:
                self.log.debug ("Requesting switch to {0}".format (internal_name))
                self.__manager.Expose (internal_name,
                                       reply_handler = lambda: None,
                                       error_handler = self.log.warn)


    def __connected_changed_cb (self, internal_name, connected):
        """
        Show or hide the menu item for the connector based on whether it can
        be switched to.
        """

        component = self.__applet.get_popup_component ()
        if connected:
            hidden = "0"
        else:
            hidden = "1"
        component.set_prop ("/commands/Player_{0}".format (internal_name), "hidden", hidden)


    def __identity_cb (self, identity):
        """
        Mark the currently exposed player in the context menu.
        """

        self.log.debug ("current identity: {0}".format (identity))
        self.__current = None
        component = self.__applet.get_popup_component ()
        display_name = identity.split (" / ", 1)[1]
        for (internal, display) in self.__names.iteritems ():
            if display == display_name:
                state = "1"
                self.__current = internal
            else:
                state = "0"
            component.set_prop ("/commands/Player_{0}".format (internal), "state", state)


##############################################################################


class LayoutManager (gobject.GObject):
    """
    Handles the specification of widgets inside the applet, as well as the
    creation of the widgets themselves.

    More specifically, it cleans up whatever widget order is specified inside
    MateConf and exposes it as a pair of lists: top row and bottom row.  It also
    makes sure the widgets themselves show and hide themselves appropriately.
    """

    from panflute.util import log

    ROW_DIVIDER = "-"


    __gproperties__ = {
        "layout": (gobject.TYPE_PYOBJECT,
                   "layout",
                   "Two-row layout of the widgets in the applet",
                   gobject.PARAM_READABLE)
    }


    def __init__ (self, conf):
        gobject.GObject.__init__ (self)

        self.__conf = conf
        self.__props = {
            "layout": ([], [])
        }

        self.__available = {
            "song_info":       WidgetInfo (_("Song info"),         functools.partial (MetadataScroller, self.__conf)),
            "rating":          WidgetInfo (_("Rating"),            Rating),
            "time_label":      WidgetInfo (_("Time"),              functools.partial (TimeLabel, self.__conf)),
            "time_bar":        WidgetInfo (_("Seek bar"),          TimeBar),
            "previous_button": WidgetInfo (_("Previous button"),   PreviousButton),
            "playback_button": WidgetInfo (_("Play/pause button"), PlaybackButton),
            "stop_button":     WidgetInfo (_("Stop button"),       StopButton),
            "next_button":     WidgetInfo (_("Next button"),       NextButton),
            "volume":          WidgetInfo (_("Volume"),            Volume)
        }

        conf.connect_string_list ("widget_order", self.__widget_order_changed_cb, call_now = True)


    def get_display_name (self, internal_name):
        """
        Get the display name of a widget.
        """

        if internal_name == self.ROW_DIVIDER:
            return self.ROW_DIVIDER * 30
        else:
            return self.__available[internal_name].display_name


    def create_widget (self, internal_name, player):
        """
        Create a new widget to be placed in the applet.
        """

        widget = self.__available[internal_name].construct (player)
        handler = self.__conf.connect_bool ("show_{0}".format (internal_name),
                                            lambda value: widget.set_property ("visible", value),
                                            call_now = True)
        widget.connect ("destroy", lambda widget: self.__conf.disconnect (handler))

        return widget


    def do_get_property (self, property):
        return self.__props[property.name]


    def __set_property (self, name, value):
        """
        Set the value of a property, issuing the notify signal if the value
        does in fact change.

        This is distinct from the set_property provided by gobject in that
        it prevents outsiders from trying to set properties.
        """

        if self.__props[name] != value:
            self.__props[name] = value
            self.notify (name)


    def __widget_order_changed_cb (self, requested_order):
        """
        Sanitize the requested widget order stored in MateConf to ensure that
        all widgets are accounted for with no repeats and that everything
        spans at most two rows.
        """

        seen = {}
        good_order = []

        for request in requested_order:
            if seen.has_key (request):
                self.log.debug ("Skipping duplicate widget \"{0}\"".format (request))
            elif self.__available.has_key (request) or request == self.ROW_DIVIDER:
                seen[request] = True
                good_order.append (request)
            else:
                self.log.debug ("Ignoring unknown widget \"{0}\"".format (request))

        for missing in self.__available:
            if not seen.has_key (missing):
                self.log.debug ("Adding missing widget \"{0}\"".format (missing))
                good_order.append (missing)

        first = []
        second = []
        dest = first
        for widget in good_order:
            if widget == self.ROW_DIVIDER:
                dest = second
            else:
                dest.append (widget)

        self.log.debug ("New first row: {0}".format (first))
        self.log.debug ("New second row: {0}".format (second))
        self.__set_property ("layout", (first, second))


gobject.type_register (LayoutManager)


##############################################################################


class WidgetInfo (object):
    """
    Simple object that collects information about a type of widget usable in
    the applet.
    """

    def __init__ (self, display_name, construct):
        self.display_name = display_name
        self.construct = construct


##############################################################################


class SongTip (gtk.HBox):
    """
    Widget that displays various information about the current song.
    Intended to be used as the content of the applet's tooltip.
    """

    from panflute.util import log

    ART_HEIGHT = 64


    def __init__ (self, player):
        gtk.HBox.__init__ (self)
        self.set_spacing (6)

        self.__art = gtk.Image ()
        self.__art.show ()
        self.pack_start (self.__art)

        vbox = gtk.VBox ()

        self.__title = gtk.Label (_("Not playing"))
        self.__title.set_alignment (0.0, 0.5)
        self.__title.show ()
        vbox.pack_start (self.__title)

        self.__artist = gtk.Label ()
        self.__artist.set_alignment (0.0, 0.5)
        vbox.pack_start (self.__artist)

        self.__album = gtk.Label ()
        self.__album.set_alignment (0.0, 0.5)
        vbox.pack_start (self.__album)

        self.__time = gtk.Label ()
        self.__time.set_alignment (0.0, 0.5)
        vbox.pack_start (self.__time)

        vbox.show ()
        self.pack_start (vbox)

        autodisconnect_gobject_handlers (self, player, [
            player.connect ("notify::title", self.__notify_title_cb),
            player.connect ("notify::artist", self.__notify_artist_cb),
            player.connect ("notify::album", self.__notify_album_cb),
            player.connect ("notify::duration", self.__notify_time_cb),
            player.connect ("notify::elapsed", self.__notify_time_cb),
            player.connect ("notify::art", self.__notify_art_cb)
        ])

        self.__notify_title_cb (player, None)
        self.__notify_artist_cb (player, None)
        self.__notify_album_cb (player, None)
        self.__notify_time_cb (player, None)
        self.__notify_art_cb (player, None)


    def __notify_title_cb (self, player, pspec):
        """
        Update the title displayed.
        """

        if player.props.title is not None:
            self.__title.set_markup ("<big><b>{0}</b></big>".format (
                xml.sax.saxutils.escape (player.props.title)))
        else:
            self.__title.set_label (_("Not playing"))


    def __notify_artist_cb (self, player, pspec):
        """
        Update the artist displayed.
        """

        if player.props.artist is not None:
            self.__artist.set_markup (_("<i>by</i> {0}").format (
                xml.sax.saxutils.escape (player.props.artist)))
            self.__artist.show ()
        else:
            self.__artist.hide ()


    def __notify_album_cb (self, player, pspec):
        """
        Update the album displayed.
        """

        if player.props.album is not None:
            self.__album.set_markup (_("<i>from</i> {0}").format (
                xml.sax.saxutils.escape (player.props.album)))
            self.__album.show ()
        else:
            self.__album.hide ()


    def __notify_time_cb (self, player, pspec):
        """
        Update the displayed time.
        """

        if player.props.duration > 0:
            # To translators: elapsed time and duration of song (e.g. 1:23 of 4:56)
            self.__time.set_text (_("{elapsed} of {duration}").format (
                elapsed = format_time (player.props.elapsed),
                duration = format_time (player.props.duration)))
            self.__time.show ()
        elif player.props.elapsed > 0:
            self.__time.set_text (format_time (player.props.elapsed))
            self.__time.show ()
        else:
            self.__time.hide ()


    def __notify_art_cb (self, player, pspec):
        """
        Update the artwork displayed.
        """

        if player.props.art is not None:
            scaled = panflute.applet.widget.scale_to_height (player.props.art, self.ART_HEIGHT)
            self.__art.set_from_pixbuf (scaled)
            self.__art.show ()
        else:
            self.__art.hide ()


gobject.type_register (SongTip)


##############################################################################


class LaunchButton (panflute.applet.widget.Button):
    """
    Button that launches the preferred music player.
    """

    from panflute.util import log


    def __init__ (self, bus_obj):
        panflute.applet.widget.Button.__init__ (self, panflute.applet.stock.PANFLUTE)
        self.__bus = bus_obj

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.kuliniewicz.Panflute", "/connectors", follow_name_owner_changes = True)
        self.__manager = dbus.Interface (proxy, "org.kuliniewicz.Panflute.Manager")

        proxy = bus.get_object ("org.kuliniewicz.Panflute", "/connectors/preferred", follow_name_owner_changes = True)
        self.__preferred = dbus.Interface (proxy, "org.kuliniewicz.Panflute.Connector")

        autodisconnect_dbus_handlers (self, [
            self.__manager.connect_to_signal ("PreferredChanged", self.__preferred_changed_cb)
        ])
        self.__preferred_changed_cb ()


    def do_clicked (self):
        self.__bus.StartServiceByName ("org.mpris.panflute", 0,
                                       reply_handler = lambda result: None,
                                       error_handler = self.log.warn)


    def __preferred_changed_cb (self):
        """
        Update the appearance of the button to reflect the currently preferred
        player.
        """

        self.__preferred.GetDisplayName (reply_handler = self.__get_display_name_cb,
                                         error_handler = self.__get_display_name_error_cb)
        self.__preferred.GetIconName (reply_handler = self.__get_icon_name_cb,
                                      error_handler = self.__get_icon_name_error_cb)


    def __get_display_name_cb (self, display_name):
        """
        Update the button's tool tip with the name of the preferred player.
        """

        self.set_tooltip_text (_("Launch {0}").format (display_name))


    def __get_display_name_error_cb (self, error):
        """
        Update the button's tool tip with a generic message.
        """

        self.set_tooltip_text (_("Launch music player"))


    def __get_icon_name_cb (self, icon_name):
        """
        Update the button's appearance with the icon of the preferred player.
        """

        if icon_name != "":
            self.set_icon_name (icon_name)
        else:
            self.set_stock_id (panflute.applet.stock.PANFLUTE)


    def __get_icon_name_error_cb (self, error):
        """
        Update the button's appearance with the fallback icon.
        """

        self.set_stock_id (panflute.applet.stock.PANFLUTE)


gobject.type_register (LaunchButton)


##############################################################################


class PlaybackButton (panflute.applet.widget.Button):
    """
    Button that toggles playback of the current song.
    """

    from panflute.util import log


    def __init__ (self, player):
        panflute.applet.widget.Button.__init__ (self, gtk.STOCK_MEDIA_PLAY)
        self.__player = player

        autodisconnect_gobject_handlers (self, player, [
            player.connect ("notify::state", self.__notify_mode_cb),
            player.connect ("notify::can-pause", self.__notify_mode_cb)
        ])

        self.__notify_mode_cb (player, None)


    def do_clicked (self):
        """
        Toggle playback.
        """

        self.__player.pause ()


    def __notify_mode_cb (self, player, pspec):
        """
        Change the advertised purpose of the button based on the player's
        current state.
        """

        if player.props.state == panflute.mpris.STATE_PLAYING:
            # Show Pause even if player.props.can_pause is False, to
            # avoid having two stop buttons side-by-side
            self.set_stock_id (gtk.STOCK_MEDIA_PAUSE)
            if player.props.can_pause:
                self.set_tooltip_text (_("Pause playback"))
            else:
                self.set_tooltip_text (_("Stop playing"))
        else:
            self.set_stock_id (gtk.STOCK_MEDIA_PLAY)
            self.set_tooltip_text (_("Start playing"))


gobject.type_register (PlaybackButton)


##############################################################################


class StopButton (panflute.applet.widget.Button):
    """
    Button that unconditionally stops the current song.
    """

    from panflute.util import log


    def __init__ (self, player):
        panflute.applet.widget.Button.__init__ (self, gtk.STOCK_MEDIA_STOP)
        self.__player = player
        self.set_tooltip_text (_("Stop playing"))


    def do_clicked (self):
        """
        Stop playback.
        """

        self.__player.stop ()


gobject.type_register (StopButton)


##############################################################################


class NextButton (panflute.applet.widget.Button):
    """
    Button that advances playback to the next song.
    """

    from panflute.util import log


    def __init__ (self, player):
        panflute.applet.widget.Button.__init__ (self, gtk.STOCK_MEDIA_NEXT)
        self.__player = player

        self.set_tooltip_text (_("Go to next song"))

        autodisconnect_gobject_handlers (self, player, [
            player.connect ("notify::can-go-next", self.__notify_next_cb)
        ])
        self.__notify_next_cb (player, None)


    def do_clicked (self):
        """
        Advance to the next song.
        """

        self.__player.next ()


    def __notify_next_cb (self, player, pspec):
        """
        Disable the button if the player says it can't advance to the next
        song.
        """

        self.set_sensitive (player.props.can_go_next)


gobject.type_register (NextButton)


##############################################################################


class PreviousButton (panflute.applet.widget.Button):
    """
    Button that goes back to the previous song.
    """

    from panflute.util import log


    def __init__ (self, player):
        panflute.applet.widget.Button.__init__ (self, gtk.STOCK_MEDIA_PREVIOUS)
        self.__player = player

        self.set_tooltip_text (_("Go to previous song"))

        autodisconnect_gobject_handlers (self, player, [
            player.connect ("notify::can-go-previous", self.__notify_previous_cb)
        ])
        self.__notify_previous_cb (player, None)


    def do_clicked (self):
        """
        Go back to the previous song.
        """

        self.__player.previous ()


    def __notify_previous_cb (self, player, pspec):
        """
        Disable the button if the player says it can't go back to the previous
        song.
        """

        self.set_sensitive (player.props.can_go_previous)


gobject.type_register (PreviousButton)


##############################################################################


class TimeLabel (gtk.EventBox):
    """
    Displays the elapsed time in the current song.
    """

    from panflute.util import log

    is_expandable = False
    wants_padding = True


    def __init__ (self, conf, player):
        gtk.EventBox.__init__ (self)
        self.__label = gtk.Label (format_time (0))
        self.__conf = conf
        self.__player = player
        self.__delta = 0

        self.add (self.__label)
        self.__label.show ()

        autodisconnect_conf_handlers (self, conf, [
            conf.connect_bool ("show_remaining_time", self.__show_remaining_time_cb, call_now = True)
        ])

        autodisconnect_gobject_handlers (self, player, [
            player.connect ("notify::duration", self.__notify_time_cb),
            player.connect ("notify::elapsed", self.__notify_time_cb)
        ])

        use_song_info_tooltip (self, player)


    def __show_remaining_time_cb (self, value):
        """
        Change whether elapsed or remaining time is displayed.
        """

        self.__show_remaining = value
        self.__notify_time_cb (self.__player, None)


    def __notify_time_cb (self, player, pspec):
        """
        Update the text shown in the widget.
        """

        if self.__show_remaining and player.props.duration > 0:
            self.__label.set_label (format_negative_time (player.props.duration - player.props.elapsed))
        else:
            self.__label.set_label (format_time (player.props.elapsed))
        self.__delta = 0


    def do_scroll_event (self, event):
        """
        Allow the user to seek via mouse-scroll.
        """

        if event.direction in [gtk.gdk.SCROLL_UP, gtk.gdk.SCROLL_RIGHT]:
            self.__delta += 5000
        elif event.direction in [gtk.gdk.SCROLL_DOWN, gtk.gdk.SCROLL_LEFT]:
            self.__delta -= 5000
        else:
            return False

        new_time = self.__player.props.elapsed + self.__delta
        if new_time < 0:
            new_time = 0
        self.__player.seek (new_time)
        return True


    def set_angle (self, angle):
        self.__label.set_angle (angle)


gobject.type_register (TimeLabel)


##############################################################################


class TimeBar (gtk.HBox):
    """
    Slider bar that allows seeking in the current song.
    """

    from panflute.util import log

    is_expandable = True
    wants_padding = False


    def __init__ (self, player):
        gtk.HBox.__init__ (self)
        self.props.border_width = 0

        self.__player = player
        self.__adj = gtk.Adjustment ()
        self.__orient = None
        self.set_angle (0)

        autodisconnect_gobject_handlers (self, player, [
            player.connect ("notify::duration", self.__notify_duration_cb),
            player.connect ("notify::elapsed", self.__notify_elapsed_cb),
            player.connect ("notify::can-seek", self.__notify_can_seek_cb)
        ])

        self.__notify_duration_cb (player, None)
        self.__notify_elapsed_cb (player, None)
        self.__notify_can_seek_cb (player, None)
        use_song_info_tooltip (self, player)


    def set_angle (self, angle):
        """
        Switch between a horizontal and vertical scale bar.
        """

        self.log.debug ("set_angle: {0}".format (angle))

        if (angle == 0 or angle == 180) and self.__orient != "H":
            new_child = gtk.HScale (self.__adj)
            new_orient = "H"
        elif (angle == 90 or angle == 270) and self.__orient != "V":
            new_child = gtk.VScale (self.__adj)
            new_orient = "V"
        else:
            new_child = None

        if new_child is not None:
            self.log.debug ("New orientation: {0}".format (new_orient))
            for child in self.get_children ():
                self.remove (child)
            new_child.props.update_policy = gtk.UPDATE_DISCONTINUOUS
            new_child.props.draw_value = False
            new_child.connect ("change-value", self.__change_value_cb)
            new_child.connect ("button-press-event", self.__button_press_event_cb)
            new_child.connect ("button-release-event", self.__button_release_event_cb)
            new_child.show ()
            self.pack_start (new_child)
            self.__orient = new_orient


    def __notify_duration_cb (self, player, pspec):
        """
        Update the scale of the scroll bar.
        """

        self.__adj.props.upper = player.props.duration


    def __notify_elapsed_cb (self, player, pspec):
        """
        Update the position of the scroll bar.
        """

        self.__adj.props.value = player.props.elapsed


    def __notify_can_seek_cb (self, player, pspec):
        """
        Disable the seek bar if seeking isn't possible.
        """

        self.log.debug ("can seek: {0}".format (player.props.can_seek))
        self.props.sensitive = player.props.can_seek


    def __change_value_cb (self, range, scroll, value):
        """
        Seek to the desired position within the song.
        """

        self.log.debug ("Seek to {0}".format (value))
        self.__player.seek (value)


    def __button_press_event_cb (self, slider, event):
        """
        Convert left clicks into middle clicks.
        """

        if event.button == 1:
            event.button = 2
        return False


    def __button_release_event_cb (self, slider, event):
        """
        Convert left clicks into middle clicks.
        """

        if event.button == 1:
            event.button = 2
        return False


gobject.type_register (TimeBar)


##############################################################################


class Rating (panflute.applet.widget.Rating):
    """
    Display a user-editable rating of the current song.
    """

    from panflute.util import log


    def __init__ (self, player):
        panflute.applet.widget.Rating.__init__ (self)
        self.__player = player
        self.props.rating = player.props.rating

        self.set_tooltip_text (_("Rate this song"))

        autodisconnect_gobject_handlers (self, player, [
            player.connect ("notify::rating", self.__notify_remote_rating_cb),
            player.connect ("notify::rating-scale", self.__notify_remote_rating_scale_cb),
            player.connect ("feature-added", self.__feature_added_cb)
        ])
        self.connect ("notify::rating", self.__notify_local_rating_cb)
        self.__notify_remote_rating_cb (player, None)

        if player.supports ("SetMetadata:rating"):
            self.__enable_rating ()
        else:
            self.__disable_rating ()


    def __enable_rating (self):
        """
        Enable the control.
        """

        self.set_tooltip_text (_("Rate this song"))
        self.props.can_rate = True


    def __disable_rating (self):
        """
        Disable the control.
        """

        self.set_tooltip_text (_("Rating cannot be changed"))
        self.props.can_rate = False


    def __feature_added_cb (self, player, feature):
        """
        Check if the player now supports setting ratings.
        """

        if feature == "SetMetadata:rating":
            self.__enable_rating ()


    def __notify_remote_rating_cb (self, player, pspec):
        """
        Update the rating displayed with that of the current song.
        """

        if self.props.rating != player.props.rating:
            self.props.rating = player.props.rating


    def __notify_remote_rating_scale_cb (self, player, pspec):
        """
        Update the rating scale to use.
        """

        if self.props.rating_scale != player.props.rating_scale:
            self.props.rating_scale = player.props.rating_scale


    def __notify_local_rating_cb (self, also_self, pspec):
        """
        Push the rating the user just assigned to the player.
        """

        if self.__player.props.rating != self.props.rating:
            self.__player.rate_song (self.props.rating)


gobject.type_register (Rating)


##############################################################################


class MetadataScroller (panflute.applet.widget.Scroller):
    """
    Scroller specialized to display the current song's metadata.
    """

    from panflute.util import log


    def __init__ (self, conf, player):
        panflute.applet.widget.Scroller.__init__ (self)
        self.__player = player
        self.__format_strings = []
        self.__replacements = {}

        autodisconnect_gobject_handlers (self, player, [
            player.connect ("notify::title",        self.__notify_field_cb, "title",        self.__string_formatter),
            player.connect ("notify::artist",       self.__notify_field_cb, "artist",       self.__string_formatter),
            player.connect ("notify::album",        self.__notify_field_cb, "album",        self.__string_formatter),
            player.connect ("notify::track-number", self.__notify_field_cb, "track_number", self.__string_formatter),
            player.connect ("notify::genre",        self.__notify_field_cb, "genre",        self.__string_formatter),
            player.connect ("notify::duration",     self.__notify_field_cb, "duration",     self.__time_formatter),
            player.connect ("notify::year",         self.__notify_field_cb, "year",         self.__number_formatter)
        ])

        for name in ["title", "artist", "album", "track-number", "genre", "duration", "year"]:
            player.notify (name)

        autodisconnect_conf_handlers (self, conf, [
            conf.connect_string_list ("metadata_lines", self.__metadata_lines_cb, call_now = True)
        ])

        use_song_info_tooltip (self, player)


    def __metadata_lines_cb (self, format_strings):
        """
        Update the format strings used by the scroller.
        """

        self.__format_strings = format_strings
        self.__update_strings ()


    def __notify_field_cb (self, player, pspec, field_name, formatter):
        """
        Update a metadata field with a property from the player.
        """

        text = formatter (player.get_property (pspec.name))
        self.__replacements[field_name] = text
        self.__update_strings ()


    def __string_formatter (self, string):
        """
        Format a generic string for display in the scroller.
        """

        if string is not None:
            return xml.sax.saxutils.escape (string)
        else:
            return ""


    def __number_formatter (self, number):
        """
        Format a generic number for display in the scroller.
        """

        if number is not None and number > 0:
            return str (number)
        else:
            return ""


    def __time_formatter (self, time):
        """
        Format a time value for display in the scroller.
        """

        if time is not None and time > 0:
            return xml.sax.saxutils.escape (format_time (time))
        else:
            return ""


    def __update_strings (self):
        """
        Update the strings being displayed.
        """

        strings = []
        if self.__player.props.title is not None:
            for format_string in self.__format_strings:
                try:
                    string = format_string.format (**self.__replacements)
                except Exception, e:
                    # Use malformed format strings verbatim
                    string = format_string
                if len (string) > 0:
                    strings.append (string)
        else:
            strings.append (_("Not playing"))
        self.set_strings (strings)


gobject.type_register (MetadataScroller)


##############################################################################


class Volume (gtk.VolumeButton):
    """
    Volume control for the player.
    """

    from panflute.util import log

    is_expandable = False
    wants_padding = False

    set_angle = panflute.applet.widget.default_set_angle


    def __init__ (self, player):
        gtk.VolumeButton.__init__ (self)
        self.__player = player
        self.props.sensitive = player.supports ("VolumeSet")

        autodisconnect_gobject_handlers (self, player, [
            player.connect ("notify::volume", self.__notify_volume_cb),
            player.connect ("feature-added", self.__feature_added_cb)
        ])
        self.connect ("value-changed", self.__value_changed_cb)
        self.__notify_volume_cb (player, None)


    def do_button_press_event (self, event):
        """
        Allow non-left-clicks to propagate up to the applet for handling.
        """

        if event.button != 1:
            return False
        else:
            return gtk.VolumeButton.do_button_press_event (self, event)


    def __value_changed_cb (self, button, value):
        """
        Change the player volume.
        """

        volume = int (100 * value)
        self.log.debug ("setting volume to {0}".format (volume))
        self.__player.props.volume = volume


    def __notify_volume_cb (self, player, pspec):
        """
        Update the displayed volume.
        """

        self.set_value (player.props.volume / 100.0)


    def __feature_added_cb (self, player, feature):
        """
        Check if the player now supports setting the volume.
        """

        if feature == "VolumeSet":
            self.props.sensitive = True


gobject.type_register (Volume)


##############################################################################


def autodisconnect_conf_handlers (obj, conf, handlers):
    """
    Automatically disconnect a set of MateConf signal handlers when the object
    is destroyed.
    """

    def callback (obj):
        obj.log.debug ("destroy - MateConf handlers")
        for handler in handlers:
            conf.disconnect (handler)

    obj.connect ("destroy", callback)


def autodisconnect_dbus_handlers (obj, handlers):
    """
    Automatically disconnect a set of D-Bus handlers when the object is
    destroyed.
    """

    def callback (obj):
        obj.log.debug ("destroy - D-Bus handlers")
        for handler in handlers:
            handler.remove ()

    obj.connect ("destroy", callback)


def autodisconnect_gobject_handlers (obj, sender, handlers):
    """
    Automatically disconnect a set of GObject signal handlers when the object
    is destroyed.
    """

    def callback (obj):
        obj.log.debug ("destroy - GObject handlers")
        for handler in handlers:
            sender.handler_disconnect (handler)

    obj.connect ("destroy", callback)


def use_song_info_tooltip (widget, player):
    """
    Configure a widget to display song information in its tooltip.

    We configure tooltips per-widget instead of having this be the tooltip
    of the applet itself because assigning a tooltip to the applet itself
    creates a one-pixel border around it, which violates Fitt's Law.
    """

    tip = SongTip (player)

    def query_tooltip_cb (widget, x, y, keyboard_mode, tooltip):
        tip.show ()
        tooltip.set_custom (tip)
        return True

    def discard_tooltip_cb (widget):
        widget.set_has_tooltip (False)
        tip.destroy ()

    widget.set_has_tooltip (True)
    widget.connect ("query-tooltip", query_tooltip_cb)
    widget.connect ("destroy", discard_tooltip_cb)


# Cache these translated strings to avoid making lots and lots of
# redundant calls to gettext.

# To translators: elapsed time, formatted as hours:minutes:seconds
time_format_pos_hms = _("{hours:d}:{minutes:02d}:{seconds:02d}")

# To translators: elapsed time, formatted as minutes:seconds
time_format_pos_ms = _("{minutes:d}:{seconds:02d}")

# To translators: remaining time, formatted as -hours:minutes:seconds
time_format_neg_hms = _("-{hours:d}:{minutes:02d}:{seconds:02d}")

# To translators: remaining time, formatted as -minutes:seconds
time_format_neg_ms = _("-{minutes:d}:{seconds:02d}")


def format_time (milliseconds):
    """
    Format a time value in milliseconds to a more readable representation.
    """

    (minutes, seconds) = divmod (milliseconds // 1000, 60)
    (hours, minutes) = divmod (minutes, 60)

    if hours > 0:
        return time_format_pos_hms.format (hours = hours, minutes = minutes, seconds = seconds)
    else:
        return time_format_pos_ms.format (minutes = minutes, seconds = seconds)


def format_negative_time (milliseconds):
    """
    Format a negative time value in milliseconds to a more readable representation.
    """

    milliseconds = abs (milliseconds)
    (minutes, seconds) = divmod (milliseconds // 1000, 60)
    (hours, minutes) = divmod (minutes, 60)

    if hours > 0:
        return time_format_neg_hms.format (hours = hours, minutes = minutes, seconds = seconds)
    else:
        return time_format_neg_ms.format (minutes = minutes, seconds = seconds)


panflute.applet.stock.register_stock_icons ()
