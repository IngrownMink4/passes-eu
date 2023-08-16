# pass_widget.py
#
# Copyright 2022-2023 Pablo Sánchez Rodríguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Adw, Gdk, GObject, Graphene, Gsk, Gtk, Pango

from .barcode_widget import BarcodeWidget
from .digital_pass import Color


PASS_WIDTH = 320
PASS_HEIGHT = 420
PASS_MARGIN = 12
BACKGROUND_BLUR_RADIUS = 30


class PassFont:
    label = Pango.FontDescription.new()
    label.set_size(9 * Pango.SCALE)
    label.set_weight(600)

    value = Pango.FontDescription.new()
    value.set_size(11 * Pango.SCALE)

    big_value = Pango.FontDescription.new()
    big_value.set_size(17 * Pango.SCALE)

    biggest_value = Pango.FontDescription.new()
    biggest_value.set_size(24 * Pango.SCALE)


class FieldLayout:

    def __init__(self,
                 pango_context,
                 field,
                 label_font = PassFont.label,
                 value_font = PassFont.value,
                 alignment = Pango.Alignment.LEFT):

        self.__label = Pango.Layout(pango_context)
        self.__label.set_alignment(alignment)
        self.__label.set_font_description(label_font)
        self.__label.set_text(field.label() if field.label() else '')

        self.__value = Pango.Layout(pango_context)
        self.__value.set_alignment(alignment)
        self.__value.set_font_description(value_font)
        self.__value.set_text(str(field.value()))
        self.__value.set_wrap(Pango.WrapMode.WORD_CHAR)

        width = max(self.__label.get_pixel_size().width,
                    self.__value.get_pixel_size().width)

        width = min(width, PASS_WIDTH - 2 * PASS_MARGIN) * Pango.SCALE

        self.__value.set_width(width)
        self.__label.set_width(width)

    def append(self, snapshot, label_color, value_color):
        label_height = self.__label.get_pixel_size().height
        value_height = self.__value.get_pixel_size().height

        snapshot.save()
        snapshot.append_layout(self.__label, label_color)

        point = Graphene.Point()
        point.y = label_height
        snapshot.translate(point)

        snapshot.append_layout(self.__value, value_color)
        snapshot.restore()

    def get_height(self):
        return self.__label.get_pixel_size().height + self.__value.get_pixel_size().height

    def get_width(self):
        return self.__label.get_width() / Pango.SCALE

    def set_alignment(self, alignment):
        self.__label.set_alignment(alignment)
        self.__value.set_alignment(alignment)

    def set_width(self, width):
        self.__label.set_width(width * Pango.SCALE)
        self.__value.set_width(width * Pango.SCALE)


class PassPlotter:

    def __init__(self, a_pass, pass_widget):
        self._pass_widget = pass_widget
        self._pango_context = pass_widget.get_pango_context()

    def _create_fields_layouts(self, fields):
        rows = []
        spacing_per_row = []

        current_row = []
        accumulated_width = 0

        max_row_width = PASS_WIDTH - 2 * PASS_MARGIN

        for field in fields:
            field_layout = FieldLayout(self._pango_context, field)
            field_width = field_layout.get_width()

            if (accumulated_width + field_width) + len(current_row) * PASS_MARGIN < max_row_width:
                current_row.append(field_layout)
                accumulated_width += field_width
                continue

            spacing = (max_row_width - accumulated_width) / (len(current_row)-1) if len(current_row) > 1 else 0
            spacing_per_row.append(spacing)
            rows.append(current_row)

            accumulated_width = field_width
            current_row = []
            current_row.append(field_layout)

        if current_row:
            spacing = (max_row_width - accumulated_width) / (len(current_row)-1) if len(current_row) > 1 else 0
            spacing_per_row.append(spacing)
            rows.append(current_row)

        return rows, spacing_per_row

    def _plot_background(self):
        rectangle = Graphene.Rect()
        rectangle.init(0, 0, PASS_WIDTH, PASS_HEIGHT)
        self._snapshot.append_color(self._bg_color, rectangle)

    def _plot_fields_layouts(self, fields):
        self._snapshot.save()

        point = Graphene.Point()
        point.x = PASS_MARGIN
        point.y = 0
        self._snapshot.translate(point)

        row_height = 0
        rows, spacing_per_row = self._create_fields_layouts(fields)

        for row in rows:
            row_height = 0
            spacing = spacing_per_row.pop(0)
            amount_of_fields = len(row)

            self._snapshot.save()
            for index, field_layout in enumerate(row):

                # Decide the alignment of the label and value according to the
                # location of the field in the row.

                if index == 0:
                    field_layout.set_alignment(Pango.Alignment.LEFT)
                elif index == amount_of_fields - 1:
                    field_layout.set_alignment(Pango.Alignment.RIGHT)
                else:
                    field_layout.set_alignment(Pango.Alignment.CENTER)

                # Plot the standard field
                field_layout.append(self._snapshot, self._label_color, self._fg_color)

                layout_height = field_layout.get_height()
                if layout_height > row_height:
                    row_height = layout_height

                # Add a horizontal space between fields
                point.x = field_layout.get_width() + spacing
                point.y = 0
                self._snapshot.translate(point)

            self._snapshot.restore()

            # Add a vertical space between rows
            point.x = 0
            point.y = row_height + 6
            self._snapshot.translate(point)

        self._snapshot.restore()

        # Perform a translation so that the next drawing starts below this one
        point.x = 0
        point.y = row_height * len(rows) + PASS_MARGIN
        self._snapshot.translate(point)

    @classmethod
    def new(clss, a_pass, pass_widget):
        if a_pass.format() == 'pkpass':
            return PkPassPlotter.new(a_pass, pass_widget)
        return EsPassPlotter(a_pass, pass_widget)

    def plot(self, snapshot):
        raise NotImplementedError()


class EsPassPlotter(PassPlotter):

    def __init__(self, a_pass, pass_widget):
        super().__init__(a_pass, pass_widget)
        espass = a_pass.adaptee()

        # Accent color
        accent_color = espass.accent_color()
        self._accent_color = accent_color.as_gdk_rgba() \
            if accent_color else Gdk.RGBA()

        # Background color
        self._bg_color = Color.named('white').as_gdk_rgba()

        # Foreground color
        self._fg_color = Color.named('black').as_gdk_rgba()

        # Label color
        self._label_color = self._fg_color.copy()

        # Logo
        self._logo_texture  = None

        if espass.icon():
            self._logo_texture  = espass.icon().as_texture()

        # Fields
        self._fields = espass.front_fields()

    def _plot_background(self):
        rectangle = Graphene.Rect()
        rectangle.init(0, 0, PASS_WIDTH, PASS_HEIGHT)
        self._snapshot.append_color(self._bg_color, rectangle)

    def _plot_fields(self):
        self._plot_fields_layouts(self._fields)

    def _plot_header(self):
        header_height = 32

        rectangle = Graphene.Rect()
        rectangle.init(0, 0, PASS_WIDTH, header_height + 2 * PASS_MARGIN)
        self._snapshot.append_color(self._accent_color, rectangle)

        # Draw the logo if it exists
        if self._logo_texture:
            logo_scale = header_height / self._logo_texture.get_height()
            logo_width = self._logo_texture.get_width() * logo_scale

            rectangle = Graphene.Rect()
            rectangle.init(PASS_MARGIN, PASS_MARGIN, logo_width, header_height)
            self._snapshot.append_texture(self._logo_texture, rectangle)

        # Perform a translation so that the next drawing starts below this one
        point = Graphene.Point()
        point.y = header_height + 3 * PASS_MARGIN
        self._snapshot.translate(point)

    def plot(self, snapshot):
        self._snapshot = snapshot

        self._snapshot.save()
        self._plot_background()
        self._plot_header()
        self._plot_fields()
        self._snapshot.restore()


class PkPassPlotter(PassPlotter):

    PRIMARY_FIELD_LABEL_FONT = PassFont.label
    PRIMARY_FIELD_VALUE_FONT = PassFont.biggest_value

    def __init__(self, a_pass, pass_widget):
        super().__init__(a_pass, pass_widget)

        # At this point we know we are going to plot a PKPass
        pkpass = a_pass.adaptee()

        # Background color
        bg_color = pkpass.background_color()
        self._bg_color = bg_color.as_gdk_rgba() \
            if bg_color else Color.named('white').as_gdk_rgba()

        # Foreground color
        fg_color = pkpass.foreground_color()
        self._fg_color = fg_color.as_gdk_rgba() \
            if fg_color else Color.named('black').as_gdk_rgba()

        # Label color
        label_color = pkpass.label_color()
        self._label_color = label_color.as_gdk_rgba() \
            if label_color else Color.named('black').as_gdk_rgba()

        # Images
        self._background_texture = None
        self._logo_texture = None
        self._strip_texture = None

        if pkpass.background():
            self._background_texture = pkpass.background().as_texture()

        if pkpass.logo():
            self._logo_texture = pkpass.logo().as_texture()

        if pkpass.strip():
            self._strip_texture = pkpass.strip().as_texture()

        # Fields
        self._header_fields = pkpass.header_fields()
        self._primary_fields = pkpass.primary_fields()
        self._secondary_fields = pkpass.secondary_fields()
        self._auxiliary_fields = pkpass.auxiliary_fields()

    @classmethod
    def new(clss, a_pass, pass_widget):
        pkpass = a_pass.adaptee()
        style = pkpass.style()

        if style == 'boardingPass':
            return BoardingPassPlotter(a_pass, pass_widget)
        elif style in ['coupon', 'storeCard']:
            return CouponPlotter(a_pass, pass_widget)
        elif style == 'eventTicket':
            return EventTicketPlotter(a_pass, pass_widget)
        elif style == 'generic':
            return GenericPlotter(a_pass, pass_widget)

    def plot(self, snapshot):
        self._snapshot = snapshot

        self._snapshot.save()
        self._plot_background()
        self._plot_header()
        self._plot_primary_fields()
        self._plot_secondary_and_axiliary_fields()
        self._snapshot.restore()

    def _plot_header(self):
        header_height = 32

        # Draw the logo if it exists
        if self._logo_texture:
            logo_scale = header_height / self._logo_texture.get_height()
            logo_width = self._logo_texture.get_width() * logo_scale

            rectangle = Graphene.Rect()
            rectangle.init(PASS_MARGIN, PASS_MARGIN, logo_width, header_height)
            self._snapshot.append_texture(self._logo_texture, rectangle)

        point = Graphene.Point()
        point.y = PASS_MARGIN

        right_margin = (PASS_WIDTH - PASS_MARGIN)

        self._snapshot.save()
        self._snapshot.translate(point)

        for field in self._header_fields:
            field_layout = FieldLayout(self._pango_context, field,
                                       alignment = Pango.Alignment.RIGHT)

            field_original_width = field_layout.get_width()
            field_layout.set_width(right_margin)

            field_layout.append(self._snapshot,
                                self._label_color,
                                self._fg_color)

            right_margin -= field_original_width + PASS_MARGIN

        self._snapshot.restore()

        # Perform a translation so that the next drawing starts below this one
        point.x = 0
        point.y = header_height + 3 * PASS_MARGIN
        self._snapshot.translate(point)

    def _plot_primary_fields(self):
        raise NotImplementedError

    def _plot_secondary_and_axiliary_fields(self):
        raise NotImplementedError

    def _plot_footer(self):
        raise NotImplementedError


class PkPassWithStripPlotter(PkPassPlotter):
    """
    PkPassWithStripPlotter is a PkPassPlotter for PKPasses that may contain a
    strip image.
    """

    STRIP_IMAGE_MAX_HEIGHT = 123

    def __init__(self, pkpass, pkpass_widget):
        super().__init__(pkpass, pkpass_widget)

    def _plot_primary_fields(self):

        # Draw the strip

        strip_height = 0

        if self._strip_texture and not self._background_texture:
            strip_scale = PASS_WIDTH / self._strip_texture.get_width()
            strip_height = self._strip_texture.get_height() * strip_scale

            rectangle = Graphene.Rect()
            rectangle.init(0, -PASS_MARGIN, PASS_WIDTH, strip_height)

            strip_height = min(self.STRIP_IMAGE_MAX_HEIGHT, strip_height)
            strip_area = Graphene.Rect()
            strip_area.init(0, -PASS_MARGIN, PASS_WIDTH, strip_height)

            self._snapshot.push_clip(strip_area)
            self._snapshot.append_texture(self._strip_texture, rectangle)
            self._snapshot.pop()

        # Draw the primary fields

        point = Graphene.Point()
        field_layout_height = 0

        if self._primary_fields:
            field_layout = FieldLayout(self._pango_context,
                                       self._primary_fields[0],
                                       value_font = self.PRIMARY_FIELD_VALUE_FONT)

            field_layout_height = field_layout.get_height()
            self._snapshot.save()

            point.x = PASS_MARGIN
            point.y = 0
            self._snapshot.translate(point)

            field_layout.append(self._snapshot, self._label_color, self._fg_color)

            self._snapshot.restore()

        # Perform a translation so that the next drawing starts below this one
        point.x = 0
        point.y = strip_height if strip_height > field_layout_height \
                               else field_layout_height + 2 * PASS_MARGIN
        self._snapshot.translate(point)


class BoardingPassPlotter(PkPassPlotter):

    def __init__(self, pkpass, pkpass_widget):
        super().__init__(pkpass, pkpass_widget)

    def _plot_primary_fields(self):

        # Origin
        origin_field = FieldLayout(self._pango_context,
                                   self._primary_fields[0],
                                   value_font = PassFont.biggest_value,
                                   alignment = Pango.Alignment.LEFT)

        # Destination
        destination_field = FieldLayout(self._pango_context,
                                        self._primary_fields[1],
                                        value_font = PassFont.biggest_value,
                                        alignment = Pango.Alignment.RIGHT)

        destination_field.set_width(PASS_WIDTH - 2 * PASS_MARGIN)
        self._snapshot.save()

        point = Graphene.Point()
        point.x = PASS_MARGIN
        point.y = 0
        self._snapshot.translate(point)

        origin_field.append(self._snapshot, self._label_color, self._fg_color)
        destination_field.append(self._snapshot, self._label_color, self._fg_color)

        self._snapshot.restore()

        # Perform a translation so that the next drawing starts below this one
        point.x = 0
        point.y = max(origin_field.get_height(), destination_field.get_height()) + 2 * PASS_MARGIN
        self._snapshot.translate(point)

    def _plot_secondary_and_axiliary_fields(self):
        self._plot_fields_layouts(self._auxiliary_fields)
        self._plot_fields_layouts(self._secondary_fields)


class CouponPlotter(PkPassWithStripPlotter):

    STRIP_IMAGE_MAX_HEIGHT = 144

    def __init__(self, pkpass, pkpass_widget):
        super().__init__(pkpass, pkpass_widget)

    def _plot_secondary_and_axiliary_fields(self):
        self._plot_fields_layouts(self._secondary_fields + \
                                  self._auxiliary_fields)


class EventTicketPlotter(PkPassWithStripPlotter):

    PRIMARY_FIELD_VALUE_FONT = PassFont.big_value
    STRIP_IMAGE_MAX_HEIGHT = 98

    def __init__(self, pkpass, pkpass_widget):
        super().__init__(pkpass, pkpass_widget)

    def _plot_background(self):

        if not self._strip_texture and self._background_texture:
            rectangle = Graphene.Rect()
            rectangle.init(-BACKGROUND_BLUR_RADIUS,
                           -BACKGROUND_BLUR_RADIUS,
                           PASS_WIDTH + 2 * BACKGROUND_BLUR_RADIUS,
                           PASS_HEIGHT + 2 * BACKGROUND_BLUR_RADIUS)

            self._snapshot.push_blur(BACKGROUND_BLUR_RADIUS)
            self._snapshot.append_texture(self._background_texture, rectangle)
            self._snapshot.pop()

        else:
            super()._plot_background()

    def _plot_secondary_and_axiliary_fields(self):
        self._plot_fields_layouts(self._secondary_fields + \
                                  self._auxiliary_fields)



class GenericPlotter(PkPassPlotter):

    def __init__(self, pkpass, pkpass_widget):
        super().__init__(pkpass, pkpass_widget)

    def _plot_primary_fields(self):
        if not self._primary_fields:
            return

        field_layout = FieldLayout(self._pango_context,
                                   self._primary_fields[0],
                                   value_font = PassFont.big_value)
        self._snapshot.save()

        point = Graphene.Point()
        point.x = PASS_MARGIN
        point.y = 0
        self._snapshot.translate(point)

        field_layout.append(self._snapshot, self._label_color, self._fg_color)

        self._snapshot.restore()

        # Perform a translation so that the next drawing starts below this one
        point.x = 0
        point.y = field_layout.get_height() + 2 * PASS_MARGIN
        self._snapshot.translate(point)

    def _plot_secondary_and_axiliary_fields(self):
        self._plot_fields_layouts(self._auxiliary_fields)
        self._plot_fields_layouts(self._secondary_fields)


class PassWidget(Gtk.Fixed):

    __gtype_name__ = 'PassWidget'

    def __init__(self):
        super().__init__()

        self.__pass_plotter = None
        self.__barcode_button = None
        self.__children = []

        self.props.width_request = PASS_WIDTH
        self.props.height_request = PASS_HEIGHT

        self.props.hexpand = False
        self.props.vexpand = True
        self.props.halign = Gtk.Align.CENTER
        self.props.valign = Gtk.Align.CENTER

        self.props.focusable = True

        self.add_css_class('card')

    def __on_barcode_clicked(self, args):
        self.emit('barcode_clicked')

    @GObject.Signal
    def barcode_clicked(self):
        pass

    def do_snapshot(self, snapshot):
        if not self.__pass_plotter:
            return

        self.__pass_plotter.plot(snapshot)

        if self.__barcode_button:
            self.snapshot_child(self.__barcode_button, snapshot)

    def content(self, a_pass):
        if self.__barcode_button:
            self.remove(self.__barcode_button)
            self.__barcode_button = None

        self.__pass_plotter = PassPlotter.new(a_pass, self)
        self.create_barcode_button(a_pass)

        # After changing the plotter, we have to redraw the widget
        self.queue_draw()

    def create_barcode_button(self, a_pass):
        barcode = a_pass.barcodes()[0]

        if not barcode:
            return

        self.__barcode_button = Gtk.Button()
        self.__barcode_button.connect('clicked', self.__on_barcode_clicked)
        self.__barcode_button.add_css_class('barcode-button')
        barcode_widget = BarcodeWidget()
        barcode_widget.encode(barcode.format(),
                              barcode.message(),
                              barcode.message_encoding())

        aspect_ratio = barcode_widget.aspect_ratio()

        # Square codes
        if aspect_ratio == 1:
            max_times = 140 // barcode_widget.minimum_height()

            barcode_button_width = max_times * barcode_widget.minimum_height()
            barcode_button_height = max_times * barcode_widget.minimum_height()

        # Horizontal codes
        elif aspect_ratio > 1:
            max_times = (PASS_WIDTH - 2*PASS_MARGIN) // barcode_widget.minimum_width()

            if max_times * barcode_widget.minimum_height() > 140:
                max_times = 140 // barcode_widget.minimum_height()

            barcode_button_width = max_times * barcode_widget.minimum_width()
            barcode_button_height = max_times * barcode_widget.minimum_height()

        # Vertical codes
        else:
            barcode_button_width = 177
            barcode_button_height = 177

        self.__barcode_button.props.width_request = barcode_button_width
        self.__barcode_button.props.height_request = barcode_button_height

        self.__barcode_button.set_child(barcode_widget)
        self.put(self.__barcode_button,
                 PASS_WIDTH/2 - barcode_button_width/2,
                 PASS_HEIGHT - PASS_MARGIN - barcode_button_height)
