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
Base custom widgets used in the applet.

None of these widgets know anything about the Panflute daemon -- those
details are handled by subclasses.  These just implement the widget
functionality itself, and in principle could be used by other programs
too.
"""

from __future__ import absolute_import, division

import panflute.applet.stock

import gnomeapplet
import gobject
import gtk
import numpy
import pango


def default_set_angle (self, angle):
    """
    Default implementation of a set_angle function for widgets that go into
    the applet but don't actually need to be rotated.
    """

    pass


class Button (gtk.Button):
    """
    Specialized version of gtk.Button that plays nicely inside an applet.

    This class takes care of all the actual rendering of the button, in order
    to mimic the behavior of launcher buttons and eliminate the border that
    would normally appear around one.
    """

    from panflute.util import log

    DISPLACEMENT = 2
    HIGHLIGHT_SHIFT = 30

    is_expandable = False
    wants_padding = False


    def __init__ (self, stock):
        gtk.Button.__init__ (self)
        self.__stock_id = stock
        self.__icon_name = None
        self.__angle = 0
        self.__normal_pixbuf = None
        self.__mouseover_pixbuf = None
        self.__pressed = False
        self.__inside = False
        self.__icon_theme = gtk.icon_theme_get_default ()

        self.connect ("notify::sensitive", self.__sensitive_changed_cb)
        self.__icon_theme.connect ("changed", lambda theme: self.__reload_image ())

        self.__reload_image ()


    def set_stock_id (self, stock):
        """
        Change the stock image displayed in the button.
        """

        self.__stock_id = stock
        self.__icon_name = None
        self.__reload_image ()


    def set_icon_name (self, icon_name):
        """
        Change the themed icon displayed in the button.
        """

        self.__stock_id = None
        self.__icon_name = icon_name
        self.__reload_image ()


    def set_angle (self, angle):
        """
        Decide which dimension (width or height) to expand the icon to, based
        on the rotation angle of the button.
        """

        self.__angle = angle
        self.__reload_image ()


    def do_size_request (self, requisition):
        """
        Request enough space to display the button image.
        """

        gtk.Button.do_size_request (self, requisition)
        requisition.width = max (requisition.width, self.__preferred_size ())
        requisition.height = max (requisition.height, self.__preferred_size ())


    def do_size_allocate (self, allocation):
        """
        Reload the image for the current size of the button.
        """

        # If the dimension that determines the image size changed, reload it
        # after propagating the allocation to the base class.

        if (self.__angle == 0 or self.__angle == 180) and self.allocation.height != allocation.height:
            need_reload = True
        elif (self.__angle == 90 or self.__angle == 270) and self.allocation.width != allocation.width:
            need_reload = True
        else:
            need_reload = False

        gtk.Button.do_size_allocate (self, allocation)

        if need_reload:
            self.__reload_image ()


    def do_button_press_event (self, event):
        """
        Allow non-left-clicks to propagate up to the applet for handling.
        """

        if event.button != 1:
            return False
        else:
            return gtk.Button.do_button_press_event (self, event)


    def do_pressed (self):
        """
        Start drawing the button as pressed down.
        """

        self.__pressed = True
        self.queue_draw ()
        gtk.Button.do_pressed (self)


    def do_released (self):
        """
        Stop drawing the button as pressed down.
        """

        self.__pressed = False
        self.queue_draw ()
        gtk.Button.do_released (self)


    def do_enter (self):
        """
        Start drawing the button as being moused over.
        """

        self.__inside = True
        self.queue_draw ()
        gtk.Button.do_enter (self)


    def do_leave (self):
        """
        Stop drawing the button as being moused over.
        """

        self.__inside = False
        self.queue_draw ()
        gtk.Button.do_leave (self)


    def __sensitive_changed_cb (self, widget, pspec):
        """
        Prevent the appearance of the button from getting stuck in the wrong
        state when the sensitivity state changes.
        """

        # pressed/released and enter/leave don't always get paired correctly
        # across sensitivity changes.
        self.__pressed = False
        self.__inside = False

        # Reload the image to apply or remove the "disabled widget" effect.
        self.__reload_image ()


    def do_expose_event (self, event):
        """
        Draw the button image, appropriately adjusted for the button state.
        """

        if self.__inside:
            pixbuf = self.__mouseover_pixbuf
        else:
            pixbuf = self.__normal_pixbuf

        if pixbuf is None:
            return True

        # Center the pixbuf in the button's allocated area

        width = pixbuf.get_width ()
        height = pixbuf.get_height ()
        x = self.allocation.x + (self.allocation.width - width) // 2
        y = self.allocation.y + (self.allocation.height - height) // 2

        if self.__pressed and self.__inside:
            x += self.DISPLACEMENT
            y += self.DISPLACEMENT

        # Clip to the visible area and the area that needs to be redrawn

        target_area = gtk.gdk.Rectangle (x, y, width, height)
        draw_area = event.area.intersect (self.allocation)
        draw_area = draw_area.intersect (target_area)

        if draw_area.width > 0 and draw_area.height > 0:
            self.window.draw_pixbuf (None, pixbuf,
                                     draw_area.x - target_area.x, draw_area.y - target_area.y,
                                     draw_area.x, draw_area.y,
                                     draw_area.width, draw_area.height,
                                     gtk.gdk.RGB_DITHER_NORMAL,
                                     0, 0)

        return False


    def __reload_image (self):
        """
        Load the image specified by stock ID or icon name so it can be
        displayed.
        """

        self.__normal_pixbuf = None
        self.__mouseover_pixbuf = None
        size = self.__preferred_size ()

        if self.__stock_id is not None:
            self.__normal_pixbuf = panflute.applet.stock.render_icon_pixel_size (self, self.__stock_id, size)
            if self.__normal_pixbuf is None:
                self.log.warn ("Unable to render stock icon '{0}'".format (self.__stock_id))
        elif self.__icon_name is not None:
            try:
                pixbuf = self.__icon_theme.load_icon (self.__icon_name, size, 0)
                # Named icons don't automatically have the "disabled widget" effect applied to them,
                # so do it manually if needed.
                if not self.props.sensitive:
                    source = gtk.IconSource ()
                    source.set_pixbuf (pixbuf)
                    source.set_size (gtk.ICON_SIZE_LARGE_TOOLBAR)
                    source.set_size_wildcarded (False)
                    self.__normal_pixbuf = self.style.render_icon (source,
                                                                   self.get_direction (),
                                                                   self.state,
                                                                   -1,
                                                                   self,
                                                                   "button")
                else:
                    self.__normal_pixbuf = pixbuf
            except gobject.GError, e:
                self.log.warn ("Unable to load icon '{0}': {1}".format (self.__icon_name, e))

        if self.__normal_pixbuf is None:
            # Fallback to a (hopefully) safe default.
            self.__normal_pixbuf = panflute.applet.stock.render_icon_pixel_size (self, panflute.applet.stock.PANFLUTE, size)

        if self.__normal_pixbuf is not None:
            self.__mouseover_pixbuf = self.__normal_pixbuf.copy ()
            self.__shift_pixbuf_colors (self.__mouseover_pixbuf, self.HIGHLIGHT_SHIFT)
        else:
            self.log.error ("All attempts to load an icon failed")

        self.queue_resize ()
        self.queue_draw ()


    def __shift_pixbuf_colors (self, pixbuf, shift):
        """
        Shift a pixbuf's colors by a set amount in place.
        """

        def clamp (val, lo, hi):
            return min (hi, max (lo, val))

        pixels = pixbuf.get_pixels_array ()
        for row in range (pixbuf.get_height ()):
            for col in range (pixbuf.get_width ()):
                for chan in range (3):
                    # The type depends on whether PyGTK was built with NumPy.
                    if type (pixels[row][col][chan]) == numpy.uint8:
                        pixels[row][col][chan] = clamp (pixels[row][col][chan] + shift, 0, 255)
                    else:
                        pixels[row][col][chan][0] = clamp (pixels[row][col][chan][0] + shift, 0, 255)


    def __preferred_size (self):
        """
        Get the preferred size, in pixels, of the image to be displayed in the
        button.
        """

        if self.allocation is not None:
            if self.__angle == 0 or self.__angle == 180:
                return max (self.allocation.height, gnomeapplet.SIZE_X_SMALL)
            else:
                return max (self.allocation.width, gnomeapplet.SIZE_X_SMALL)
        else:
            return gnomeapplet.SIZE_MEDIUM


gobject.type_register (Button)


##############################################################################


class Scroller (gtk.EventBox):
    """
    Display multiple lines of text, one at a time, scrolling from one to the
    next.

    This uses gtk.Fixed instead of gtk.ScrolledWindow because the gtk.Viewport
    which would otherwise be needed insists on drawing its own background,
    ruining panel background effects.
    """

    from panflute.util import log

    LINGER_INTERVAL = 5000
    SCROLL_STEP_INTERVAL = 50

    is_expandable = True
    wants_padding = True


    def __init__ (self):
        gtk.EventBox.__init__ (self)
        self.set_visible_window (False)
        self.set_border_width (0)

        self.__fixed = gtk.Fixed ()
        self.__fixed.set_border_width (0)
        self.__fixed.show ()
        self.add (self.__fixed)

        self.__labels = []
        self.__angle = 0
        self.__stops = []
        self.__offset = 0
        self.__immediately_refresh = False

        self.__update_source = None
        self.connect ("destroy", self.__destroy_cb)


    def __destroy_cb (self, widget):
        """
        Make sure the scroller stops trying to animate.
        """

        if self.__update_source is not None:
            gobject.source_remove (self.__update_source)
            self.__update_source = None


    def set_strings (self, strings):
        """
        Set the list of strings to display.
        """

        # Be careful to ensure that self.__labels *only* contains labels
        # that are currently children, to avoid lp:476500.
        labels = self.__labels
        self.__labels = []
        for label in labels:
            self.__fixed.remove (label)

        for str in strings:
            self.__add_string (str)
        if len (strings) > 1:
            self.__add_string (strings[0])
        self.__pack_labels ()


    def __add_string (self, str):
        """
        Add a single string to the scroller.
        """

        label = gtk.Label (str)
        label.connect ("size-allocate", self.__refresh_if_heightened)
        label.set_use_markup (True)
        label.set_padding (0, 0)
        label.set_alignment (0.5, 0.5)
        label.set_single_line_mode (True)
        self.__fixed.put (label, 0, 0)
        self.__labels.append (label)


    def set_angle (self, angle):
        """
        Reorient the scroller's content to display text at the given angle.
        """

        self.__angle = angle
        self.__pack_labels ()


    def __pack_labels (self):
        """
        Re-pack the labels according to the current orientation.
        """

        # Stop any scroll in progress

        if self.__update_source is not None:
            gobject.source_remove (self.__update_source)
            self.__update_source = None

        # Arrange the labels inside the space available

        sizes = []

        for label in self.__labels:
            # gtk.Label only supports non-zero angles if the ellipsize mode is NONE.
            if self.__angle == 0:
                label.set_ellipsize (pango.ELLIPSIZE_END)
            else:
                label.set_ellipsize (pango.ELLIPSIZE_NONE)
            label.set_angle (self.__angle)
            label.set_size_request (-1, -1)
            if self.__angle == 90 or self.__angle == 270:
                label.set_size_request (label.size_request ()[0], self.allocation.height)
            else:
                label.set_size_request (self.allocation.width, label.size_request ()[1])

        # Figure out which offsets to linger on

        if self.__angle == 90 or self.__angle == 270:
            delta = self.allocation.width
        else:
            delta = self.allocation.height
        self.__stops = [i * delta for i in range (len (self.__labels))]

        # Actually add the content to the scroller

        self.__immediately_refresh = True
        self.__set_offset (0)
        for label in self.__labels:
            label.show ()

        # Initialize the scroll position

        self.__path = self.__stops[1:]
        if len (self.__stops) > 1:
            self.__update_source = gobject.timeout_add (self.LINGER_INTERVAL, self.__begin_scroll)


    def do_size_request (self, requisition):
        """
        Always request the minimum amount of size, to prevent the scroller
        from forcing the applet to overlap other applets in the panel.
        """

        requisition.width = 1
        requisition.height = 1


    def do_size_allocate (self, allocation):
        """
        Redo the padding between labels when the allocation changes.
        """

        width_changed = (self.allocation.width != allocation.width)
        height_changed = (self.allocation.height != allocation.height)
        gtk.EventBox.do_size_allocate (self, allocation)

        if width_changed and height_changed:
            self.__pack_labels ()
        elif width_changed:
            if self.__angle == 90 or self.__angle == 270:
                self.__pack_labels ()
            else:
                for label in self.__labels:
                    label.set_size_request (self.allocation.width, -1)
        elif height_changed:
            if self.__angle == 90 or self.__angle == 270:
                for label in self.__labels:
                    label.set_size_request (-1, self.allocation.height)
            else:
                self.__pack_labels ()


    def do_button_press_event (self, event):
        """
        Allow the user to click through the strings.
        """

        # Make sure the skip only happens once per button press, ignoring
        # any double- or triple-click events that this handler also gets.
        if event.button == 1 and event.type == gtk.gdk.BUTTON_PRESS:
            self.__skip_forward ()
            return True
        else:
            return False


    def do_scroll_event (self, event):
        """
        Allow the user to mouse-scroll through the strings.
        """

        if event.direction == gtk.gdk.SCROLL_UP or \
                (self.__angle == 90 and event.direction == gtk.gdk.SCROLL_LEFT) or \
                (self.__angle == 270 and event.direction == gtk.gdk.SCROLL_RIGHT):
            self.__skip_backward ()
            return True
        elif event.direction == gtk.gdk.SCROLL_DOWN or \
                (self.__angle == 90 and event.direction == gtk.gdk.SCROLL_RIGHT) or \
                (self.__angle == 270 and event.direction == gtk.gdk.SCROLL_LEFT):
            self.__skip_forward ()
            return True
        else:
            return False


    def __begin_scroll (self):
        """
        Begin scrolling to the next string to display.
        """

        self.__scroll_content ()
        if self.__update_source is not None:
            gobject.source_remove (self.__update_source)
        self.__update_source = gobject.timeout_add (self.SCROLL_STEP_INTERVAL, self.__continue_scroll)
        return False


    def __continue_scroll (self):
        """
        Continue scrolling to the next string to display.
        """

        keep_going = self.__scroll_content ()
        if not keep_going:
            if self.__update_source is not None:
                gobject.source_remove (self.__update_source)
            self.__update_source = gobject.timeout_add (self.LINGER_INTERVAL, self.__begin_scroll)
            return False
        else:
            return True


    def __scroll_content (self):
        """
        Scroll the widget's contents by one increment, and return whether
        more scrolling is needed to reach the next linger point.
        """

        if len (self.__path) == 0:
            # at the end, so wrap around to the (same-looking) beginning
            self.__set_offset (self.__stops[0])
            self.__path = self.__stops[1:]
        else:
            self.__set_offset (self.__offset + 1)

        if self.__path[0] == self.__offset:
            self.__path = self.__path[1:]
            return False
        else:
            return True


    def __skip_forward (self):
        """
        Skip forward to the next string to be displayed.
        """

        if len (self.__path) > 0:
            self.__set_offset (self.__path[0])
            self.__path = self.__path[1:]
        elif len (self.__stops) > 1:
            self.__set_offset (self.__stops[1])
            self.__path = self.__stops[2:]

        if self.__update_source is not None:
            gobject.source_remove (self.__update_source)

        if len (self.__stops) > 1:
            self.__update_source = gobject.timeout_add (self.LINGER_INTERVAL, self.__begin_scroll)
        else:
            self.__update_source = None


    def __skip_backward (self):
        """
        Skip backward to the previous string to be displayed.
        """

        # Quick and dirty, taking advantage of the cycle
        for i in range (len (self.__labels) - 2):
            self.__skip_forward ()


    def __set_offset (self, offset):
        """
        Move the labels according to the new offset.
        """

        self.__offset = offset
        num_labels = len (self.__labels)

        for i in range (num_labels):
            label = self.__labels[i]
            # Be extra paranoid about lp:476500
            if label.get_parent () == self.__fixed:
                if self.__angle == 90:
                    padding = (self.allocation.width - label.allocation.width) // 2
                    self.__fixed.move (label, i * self.allocation.width - self.__offset + padding, 0)
                elif self.__angle == 270:
                    padding = (self.allocation.width - label.allocation.width) // 2
                    self.__fixed.move (label, i * -self.allocation.width + self.__offset + padding, 0)
                else:
                    padding = (self.allocation.height - label.allocation.height) // 2
                    self.__fixed.move (label, 0, i * self.allocation.height - self.__offset + padding)


    def __refresh_if_heightened (self, label, allocation):
        """
        Immediately re-do the offsets the first time a new set of labels is
        allocated space, to make sure the padding in __set_offset is
        calculated relative to a non-empty widget.
        """

        if self.__immediately_refresh:
            gobject.idle_add (lambda: self.__set_offset (self.__offset) and False)
            self.__immediately_refresh = False


    def do_expose_event (self, event):
        """
        Clip the area to draw to the scroller's allocation, so that off-edge
        labels don't get drawn on top of a second row just because the
        underlying window extends that far even though the scroller doesn't.
        """

        clipped = event.area.intersect (self.allocation)
        self.window.begin_paint_rect (clipped)
        gtk.EventBox.do_expose_event (self, event)
        self.window.end_paint ()


gobject.type_register (Scroller)


##############################################################################


class Star (gtk.EventBox):
    """
    A single star displayed within a Rating widget.

    A Star has a notion of its threshold and a rating.  A big star is shown
    if the rating meets the threshold.
    """

    from panflute.util import log


    def __init__ (self, threshold):
        gtk.EventBox.__init__ (self)
        self.set_visible_window (False)

        self.__image = gtk.Image ()
        self.__image.set_alignment (0.5, 0.5)
        self.__image.show ()
        self.add (self.__image)

        self.__set_pixbuf = None
        self.__unset_pixbuf = None
        self.__threshold = threshold
        self.__rating = 0


    def get_threshold (self):
        """
        Return the threshold of the Star.
        """

        return self.__threshold


    def set_rating (self, rating):
        """
        Set the current rating.
        """

        self.__rating = rating
        self.__update ()


    def set_pixbufs (self, set, unset):
        """
        Set the pixbufs used for displaying the two types of star.
        """

        self.__set_pixbuf = set
        self.__unset_pixbuf = unset
        self.__update ()


    def __update (self):
        """
        Update the image being displayed.
        """

        if self.__rating >= self.__threshold:
            self.__image.set_from_pixbuf (self.__set_pixbuf)
        else:
            self.__image.set_from_pixbuf (self.__unset_pixbuf)


    def do_button_press_event (self, event):
        """
        Signal a user attempt to set the rating to the star's threshold.
        """

        if event.button == 1:
            self.emit ("clicked")
            return True
        else:
            return False    # gtk.EventBox does not implement


gobject.type_register (Star)
gobject.signal_new ("clicked", Star,
                    gobject.SIGNAL_RUN_LAST,
                    gobject.TYPE_NONE,
                    ())


##############################################################################


class Rating (gtk.Table):
    """
    Displays a row (or column) of stars to represent a song's rating.
    """

    is_expandable = False
    wants_padding = False

    SPACING = 4

    __gproperties__ = {
        "rating": (gobject.TYPE_UINT,
                   "rating",
                   "Rating displayed in the widget",
                   0, 10,
                   0,
                   gobject.PARAM_READWRITE),

        "rating-scale": (gobject.TYPE_UINT,
                         "rating-scale",
                         "The number of available rating stars",
                         0, 10,
                         5,
                         gobject.PARAM_READWRITE),

        "can-rate": (gobject.TYPE_BOOLEAN,
                     "can-rate",
                     "User can change rating",
                     True,
                     gobject.PARAM_READWRITE)
    }


    def __init__ (self):
        gtk.Table.__init__ (self)
        self.__angle = 0
        self.__rating = 0
        self.__can_rate = True
        self.__children = []

        self.__set_rating_scale (5)



    def __set_rating_scale (self, rating_scale):
        """
        Change the rating scale being used.
        """

        if rating_scale <= 0:
            return

        for star in self.__children:
            if star.get_parent () is not None:
                self.remove (star)

        self.__rating_scale = rating_scale
        self.__children = []

        for threshold in range (1, self.__rating_scale + 1):
            star = Star (threshold)
            star.set_rating (self.__rating)
            star.connect ("clicked", self.__star_clicked_cb)
            star.show ()
            self.__children.append (star)
        self.__repack_stars ()


    def do_get_property (self, property):
        if property.name == "rating":
            return self.__rating
        elif property.name == "rating-scale":
            return self.__rating_scale
        elif property.name == "can-rate":
            return self.__can_rate


    def do_set_property (self, property, value):
        if property.name == "rating":
            self.__rating = value
            for star in self.__children:
                star.set_rating (value)
        elif property.name == "rating-scale":
            self.__set_rating_scale (value)
        elif property.name == "can-rate":
            self.__can_rate = value


    def do_size_allocate (self, allocation):
        """
        Reload the pixbufs for the new size, if needed.
        """

        if self.__angle == 0 or self.__angle == 180:
            if self.allocation.height != allocation.height:
                self.__reload_pixbufs (allocation.height)
        elif self.__angle == 90 or self.__angle == 270:
            if self.allocation.width != allocation.width:
                self.__reload_pixbufs (allocation.width)

        gtk.Table.do_size_allocate (self, allocation)


    def __reload_pixbufs (self, padded_size):
        """
        Reload the pixbufs for the rating stars, recolor them according to the
        current style, and give them to the child widgets.
        """

        size = padded_size - 2 * self.SPACING
        if size > 0:
            set = panflute.applet.stock.render_icon_pixel_size (self, panflute.applet.stock.SET_STAR, size)
            unset = panflute.applet.stock.render_icon_pixel_size (self, panflute.applet.stock.UNSET_STAR, size)

            color = self.get_style ().fg[gtk.STATE_NORMAL]
            self.__colorize (set, color)
            self.__colorize (unset, color)

            for star in self.__children:
                star.set_pixbufs (set, unset)


    def __colorize (self, pixbuf, color):
        """
        Apply the current style's color to a pixbuf for a rating star.
        """

        if pixbuf is not None:
            red_scale   = color.red   / 65535
            green_scale = color.green / 65535
            blue_scale  = color.blue  / 65535

            for row in pixbuf.get_pixels_array ():
                for pixel in row:
                    # The type depends on whether PyGTK was built with NumPy.
                    if type (pixel) == numpy.ndarray:
                        pixel[0] *= red_scale
                        pixel[1] *= green_scale
                        pixel[2] *= blue_scale
                    else:
                        pixel[0][0] *= red_scale
                        pixel[1][0] *= green_scale
                        pixel[2][0] *= blue_scale


    def do_style_set (self, old_style):
        """
        Update the color used to draw the rating stars.

        This will be invoked from the base class's constructor, so use it to
        initialize the pixbufs with the proper style right away.
        """

        gtk.Table.do_style_set (self, old_style)
        if len (self.__children) > 0:
            if self.__angle == 0 or self.__angle == 180:
                self.__reload_pixbufs (self.allocation.height)
            else:
                self.__reload_pixbufs (self.allocation.width)


    def set_angle (self, angle):
        """
        Reorient the rating widget according to the angle.
        """

        self.__angle = angle
        self.__repack_stars ()


    def __repack_stars (self):
        """
        Repack the stars in the table according to the current orientation.
        """

        for star in self.__children:
            if star.get_parent () is not None:
                self.remove (star)

        if self.__angle == 0 or self.__angle == 180:
            self.resize (1, self.__rating_scale)
            for star in self.__children:
                self.attach (star, star.get_threshold () - 1, star.get_threshold (), 0, 1)
        else:
            self.resize (self.__rating_scale, 1)
            for star in self.__children:
                self.attach (star, 0, 1, self.__rating_scale - star.get_threshold (),
                                         self.__rating_scale - star.get_threshold () + 1)


    def __star_clicked_cb (self, star):
        """
        Update the rating when a star is clicked.
        """

        if self.props.can_rate:
            if self.props.rating == star.get_threshold ():
                # Clicking the existing rating clears it
                self.props.rating = 0
            else:
                self.props.rating = star.get_threshold ()


gobject.type_register (Rating)


##############################################################################


def scale_to_width (pixbuf, width):
    """
    Return a new pixbuf scaled to the desired width.
    """

    height = width * pixbuf.get_height () // pixbuf.get_width ()
    return pixbuf.scale_simple (width, height, gtk.gdk.INTERP_BILINEAR)


def scale_to_height (pixbuf, height):
    """
    Return a new pixbuf scaled to the desired height.
    """

    width = height * pixbuf.get_width () // pixbuf.get_height ()
    return pixbuf.scale_simple (width, height, gtk.gdk.INTERP_BILINEAR)
