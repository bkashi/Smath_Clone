import os
import sys
import math
import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo


GREEK_AUTOCOMPLETE = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "Delta": "Δ",
    "epsilon": "ε",
    "zeta": "ζ",
    "eta": "η",
    "theta": "θ",
    "Theta": "Θ",
    "lambda": "λ",
    "Lambda": "Λ",
    "mu": "μ",
    "nu": "ν",
    "xi": "ξ",
    "pi": "π",
    "Pi": "Π",
    "rho": "ρ",
    "sigma": "σ",
    "Sigma": "Σ",
    "tau": "τ",
    "phi": "φ",
    "Phi": "Φ",
    "chi": "χ",
    "psi": "ψ",
    "Psi": "Ψ",
    "omega": "ω",
    "Omega": "Ω",
    "inf": "∞",
}


THEMES = {
    "dark": {
        "desk_bg": (0.07, 0.08, 0.09),
        "page_shadow": (0.0, 0.0, 0.0, 0.55),
        "page_border": (0.32, 0.36, 0.42),
        "margin_guide": (0.26, 0.30, 0.36),
        "canvas_bg": (0.12, 0.13, 0.15),
        "grid_minor": (0.18, 0.20, 0.23),
        "grid_major": (0.24, 0.27, 0.32),
        "title_text": (0.98, 0.99, 1.00),
        "heading_text": (0.58, 0.80, 0.98),
        "text": (0.90, 0.92, 0.95),
        "muted_text": (0.52, 0.57, 0.65),
        "operator": (0.45, 0.75, 0.98),
        "result": (0.42, 0.85, 0.55),
        "error": (0.95, 0.40, 0.40),
        "placeholder_fill": (0.22, 0.25, 0.30),
        "placeholder_border": (0.45, 0.50, 0.58),
        "box_editing_bg": (0.16, 0.18, 0.22, 0.92),
        "box_selected_border": (0.34, 0.61, 0.84),
        "box_editing_border": (0.40, 0.72, 0.98),
        "cursor": (0.98, 0.80, 0.25),
    },
    "light": {
        "desk_bg": (0.78, 0.80, 0.83),
        "page_shadow": (0.0, 0.0, 0.0, 0.25),
        "page_border": (0.52, 0.56, 0.62),
        "margin_guide": (0.72, 0.78, 0.86),
        "canvas_bg": (0.99, 0.99, 0.98),
        "grid_minor": (0.89, 0.92, 0.95),
        "grid_major": (0.78, 0.84, 0.90),
        "title_text": (0.05, 0.12, 0.24),
        "heading_text": (0.08, 0.30, 0.62),
        "text": (0.10, 0.12, 0.16),
        "muted_text": (0.48, 0.53, 0.60),
        "operator": (0.05, 0.35, 0.75),
        "result": (0.08, 0.52, 0.22),
        "error": (0.80, 0.15, 0.15),
        "placeholder_fill": (0.90, 0.92, 0.96),
        "placeholder_border": (0.55, 0.62, 0.72),
        "box_editing_bg": (1.0, 1.0, 1.0, 0.92),
        "box_selected_border": (0.15, 0.48, 0.82),
        "box_editing_border": (0.10, 0.42, 0.85),
        "cursor": (0.85, 0.15, 0.15),
    },
}


TEXT_STYLES = {
    "title": {
        "label": "Title",
        "font": "Ubuntu, DejaVu Sans, sans-serif Bold 22",
        "color_key": "title_text",
        "underline_bar": True,
    },
    "heading1": {
        "label": "Heading 1",
        "font": "Ubuntu, DejaVu Sans, sans-serif Bold 17",
        "color_key": "heading_text",
        "underline_bar": False,
    },
    "heading2": {
        "label": "Heading 2",
        "font": "Ubuntu, DejaVu Sans, sans-serif Bold 14",
        "color_key": "heading_text",
        "underline_bar": False,
    },
    "heading3": {
        "label": "Heading 3",
        "font": "Ubuntu, DejaVu Sans, sans-serif Bold Italic 12",
        "color_key": "heading_text",
        "underline_bar": False,
    },
    "normal": {
        "label": "Normal",
        "font": "Ubuntu, DejaVu Sans, sans-serif 11.5",
        "color_key": "text",
        "underline_bar": False,
    },
}


# ============================================================================
# 2D Equation AST Model (SMath Studio / Mathcad / MS Equation style)
# ============================================================================


class MathSeq:
    """A horizontal sequence of MathNode items, with layout metrics (width, ascent, descent)."""

    def __init__(self, parent_node=None):
        self.parent_node = parent_node
        self.items = []
        # Layout metrics computed during measure()
        self.width = 0.0
        self.ascent = 0.0
        self.descent = 0.0
        self.scale = 1.0
        # Absolute coordinates inside the MathBox for mouse hit-testing
        self.abs_x = 0.0
        self.abs_y = 0.0
        self.caret_positions = []  # x offsets for index 0..len(items)

    @property
    def height(self):
        return self.ascent + self.descent

    def insert(self, index, node):
        node.parent_seq = self
        self.items.insert(index, node)

    def append(self, node):
        node.parent_seq = self
        self.items.append(node)

    def is_empty(self):
        return len(self.items) == 0


class MathNode:
    """Base class for an element inside a MathSeq."""

    def __init__(self):
        self.parent_seq = None
        self.width = 0.0
        self.ascent = 0.0
        self.descent = 0.0
        self.abs_x = 0.0
        self.abs_y = 0.0

    @property
    def height(self):
        return self.ascent + self.descent

    def slots(self):
        return []


class CharNode(MathNode):
    """A single character or multi-char operator token (e.g. 'x', '2', '+', ':=', 'π')."""

    def __init__(self, text):
        super().__init__()
        self.text = text

    def is_operator(self):
        return self.text in ("+", "-", "·", ":=", "=", "<", ">", "≤", "≥", "≠", ",")


class FracNode(MathNode):
    """2D vertical stacked fraction: num / den."""

    def __init__(self, num=None, den=None):
        super().__init__()
        self.num = num if num is not None else MathSeq(self)
        self.den = den if den is not None else MathSeq(self)
        self.num.parent_node = self
        self.den.parent_node = self

    def slots(self):
        return [self.num, self.den]


class SupNode(MathNode):
    """Superscript / Exponent box."""

    def __init__(self, exp=None):
        super().__init__()
        self.exp = exp if exp is not None else MathSeq(self)
        self.exp.parent_node = self

    def slots(self):
        return [self.exp]


class SubNode(MathNode):
    """Subscript box."""

    def __init__(self, sub=None):
        super().__init__()
        self.sub = sub if sub is not None else MathSeq(self)
        self.sub.parent_node = self

    def slots(self):
        return [self.sub]


class SqrtNode(MathNode):
    """Square root / N-th root with dynamic radical symbol."""

    def __init__(self, radicand=None, degree=None):
        super().__init__()
        self.radicand = radicand if radicand is not None else MathSeq(self)
        self.radicand.parent_node = self
        self.degree = degree
        if self.degree is not None:
            self.degree.parent_node = self

    def slots(self):
        if self.degree is not None:
            return [self.degree, self.radicand]
        return [self.radicand]


class ParenNode(MathNode):
    """Auto-scaling parentheses around an inner sequence."""

    def __init__(self, inner=None):
        super().__init__()
        self.inner = inner if inner is not None else MathSeq(self)
        self.inner.parent_node = self

    def slots(self):
        return [self.inner]


class SumNode(MathNode):
    """2D Summation operator ∑ with lower limit, upper limit, and body."""

    def __init__(self, lower=None, upper=None, body=None):
        super().__init__()
        self.lower = lower if lower is not None else MathSeq(self)
        self.upper = upper if upper is not None else MathSeq(self)
        self.body = body if body is not None else MathSeq(self)
        self.lower.parent_node = self
        self.upper.parent_node = self
        self.body.parent_node = self

    def slots(self):
        return [self.lower, self.upper, self.body]


class IntNode(MathNode):
    """2D Definite/Indefinite Integral ∫ with lower limit, upper limit, integrand, and d-variable."""

    def __init__(self, lower=None, upper=None, body=None, var=None):
        super().__init__()
        self.lower = lower if lower is not None else MathSeq(self)
        self.upper = upper if upper is not None else MathSeq(self)
        self.body = body if body is not None else MathSeq(self)
        self.var = var if var is not None else MathSeq(self)
        self.lower.parent_node = self
        self.upper.parent_node = self
        self.body.parent_node = self
        self.var.parent_node = self

    def slots(self):
        return [self.lower, self.upper, self.body, self.var]


# ============================================================================
# Layout & Cairo Renderer for 2D Equations
# ============================================================================


class MathRenderer:
    BASE_FONT_SIZE = 15.0  # pt

    @classmethod
    def _make_layout(cls, pango_ctx, text, scale=1.0, italic=False, bold=False):
        layout = Pango.Layout.new(pango_ctx)
        font_size = max(8.0, cls.BASE_FONT_SIZE * scale)
        style_str = "Italic " if italic else ""
        weight_str = "Bold " if bold else ""
        desc = Pango.FontDescription.from_string(
            f"Ubuntu Mono, DejaVu Sans Mono, monospace {style_str}{weight_str}{font_size:.1f}"
        )
        layout.set_font_description(desc)
        layout.set_text(text, -1)
        ink, logical = layout.get_pixel_extents()
        baseline = layout.get_baseline() / Pango.SCALE
        width = max(logical.width, 1)
        ascent = max(baseline, logical.height * 0.75)
        descent = max(logical.height - ascent, logical.height * 0.25)
        return layout, float(width), float(ascent), float(descent)

    @classmethod
    def measure_seq(cls, pango_ctx, seq: MathSeq, scale=1.0):
        seq.scale = scale
        if not seq.items:
            # Empty placeholder box size
            w = 13.0 * scale
            asc = 11.0 * scale
            desc = 4.0 * scale
            seq.width = w
            seq.ascent = asc
            seq.descent = desc
            return

        total_w = 0.0
        max_asc = 10.0 * scale
        max_desc = 3.0 * scale

        for idx, item in enumerate(seq.items):
            prev_item = seq.items[idx - 1] if idx > 0 else None
            cls.measure_node(pango_ctx, item, scale, prev_item)
            total_w += item.width
            max_asc = max(max_asc, item.ascent)
            max_desc = max(max_desc, item.descent)

        seq.width = total_w
        seq.ascent = max_asc
        seq.descent = max_desc

    @classmethod
    def measure_node(cls, pango_ctx, node: MathNode, scale=1.0, prev_item=None):
        if isinstance(node, CharNode):
            display_text = f" {node.text} " if node.is_operator() and node.text != "," else (
                ", " if node.text == "," else node.text
            )
            is_var = len(node.text) == 1 and node.text.isalpha()
            _, w, asc, desc = cls._make_layout(pango_ctx, display_text, scale, italic=is_var)
            node.width = w
            node.ascent = asc
            node.descent = desc

        elif isinstance(node, FracNode):
            sub_scale = max(0.75, scale * 0.88)
            cls.measure_seq(pango_ctx, node.num, sub_scale)
            cls.measure_seq(pango_ctx, node.den, sub_scale)
            pad = 6.0 * scale
            axis_shift = 5.0 * scale  # Height of fraction bar above baseline
            gap = 3.0 * scale
            node.width = max(node.num.width, node.den.width) + pad * 2
            node.ascent = axis_shift + gap + node.num.height
            node.descent = max(0.0, node.den.height + gap - axis_shift)

        elif isinstance(node, SupNode):
            sub_scale = max(0.62, scale * 0.72)
            cls.measure_seq(pango_ctx, node.exp, sub_scale)
            base_asc = prev_item.ascent if prev_item is not None else 12.0 * scale
            shift_up = max(6.0 * scale, base_asc * 0.55)
            node.width = node.exp.width + 2.0 * scale
            node.ascent = shift_up + node.exp.ascent
            node.descent = max(0.0, node.exp.descent - shift_up)

        elif isinstance(node, SubNode):
            sub_scale = max(0.62, scale * 0.72)
            cls.measure_seq(pango_ctx, node.sub, sub_scale)
            base_desc = prev_item.descent if prev_item is not None else 3.0 * scale
            shift_down = max(5.0 * scale, base_desc + 4.0 * scale)
            node.width = node.sub.width + 2.0 * scale
            node.ascent = max(0.0, node.sub.ascent - shift_down)
            node.descent = shift_down + node.sub.descent

        elif isinstance(node, SqrtNode):
            cls.measure_seq(pango_ctx, node.radicand, scale)
            deg_w = 0.0
            deg_asc = 0.0
            if node.degree is not None:
                cls.measure_seq(pango_ctx, node.degree, max(0.58, scale * 0.65))
                deg_w = max(0.0, node.degree.width - 4.0 * scale)
                deg_asc = node.degree.height + 4.0 * scale
            hook_w = 13.0 * scale
            pad_right = 4.0 * scale
            top_pad = 4.0 * scale
            node.width = deg_w + hook_w + node.radicand.width + pad_right
            node.ascent = max(node.radicand.ascent + top_pad, deg_asc)
            node.descent = node.radicand.descent + 2.0 * scale

        elif isinstance(node, ParenNode):
            cls.measure_seq(pango_ctx, node.inner, scale)
            paren_w = 8.0 * scale
            node.width = paren_w * 2 + node.inner.width
            node.ascent = node.inner.ascent + 2.0 * scale
            node.descent = node.inner.descent + 2.0 * scale

        elif isinstance(node, SumNode):
            lim_scale = max(0.60, scale * 0.68)
            cls.measure_seq(pango_ctx, node.lower, lim_scale)
            cls.measure_seq(pango_ctx, node.upper, lim_scale)
            cls.measure_seq(pango_ctx, node.body, scale)
            sym_w = 22.0 * scale
            sym_half = 12.0 * scale
            axis_shift = 5.0 * scale
            op_w = max(sym_w, node.lower.width, node.upper.width) + 6.0 * scale
            node.width = op_w + node.body.width + 4.0 * scale
            node.ascent = max(
                node.body.ascent,
                axis_shift + sym_half + 2.0 * scale + node.upper.height,
            )
            node.descent = max(
                node.body.descent,
                sym_half - axis_shift + 2.0 * scale + node.lower.height,
            )

        elif isinstance(node, IntNode):
            lim_scale = max(0.60, scale * 0.68)
            cls.measure_seq(pango_ctx, node.lower, lim_scale)
            cls.measure_seq(pango_ctx, node.upper, lim_scale)
            cls.measure_seq(pango_ctx, node.body, scale)
            cls.measure_seq(pango_ctx, node.var, scale)
            _, d_w, d_asc, d_desc = cls._make_layout(pango_ctx, " d", scale, italic=True)
            sym_w = 16.0 * scale
            sym_half = 16.0 * scale
            axis_shift = 5.0 * scale
            lim_w = max(node.lower.width, node.upper.width)
            node.width = sym_w + lim_w + 4.0 * scale + node.body.width + d_w + node.var.width + 2.0 * scale
            node.ascent = max(
                node.body.ascent,
                d_asc,
                node.var.ascent,
                axis_shift + sym_half + node.upper.ascent,
            )
            node.descent = max(
                node.body.descent,
                d_desc,
                node.var.descent,
                sym_half - axis_shift + node.lower.descent,
            )

    @classmethod
    def draw_seq(cls, cr, pango_ctx, seq: MathSeq, x: float, baseline_y: float, theme: dict):
        seq.abs_x = x
        seq.abs_y = baseline_y - seq.ascent
        seq.caret_positions = [x]

        if not seq.items:
            # Draw SMath/Mathcad-style placeholder rectangle
            pw = seq.width - 2.0
            ph = seq.height - 2.0
            px = x + 1.0
            py = baseline_y - seq.ascent + 1.0
            cr.save()
            cr.set_source_rgb(*theme["placeholder_fill"])
            cr.rectangle(px, py, pw, ph)
            cr.fill_preserve()
            cr.set_source_rgb(*theme["placeholder_border"])
            cr.set_line_width(1.0)
            cr.set_dash([2.0, 2.0])
            cr.stroke()
            cr.restore()
            seq.caret_positions.append(x + seq.width)
            return

        cur_x = x
        for idx, item in enumerate(seq.items):
            prev_item = seq.items[idx - 1] if idx > 0 else None
            cls.draw_node(cr, pango_ctx, item, cur_x, baseline_y, seq.scale, theme, prev_item)
            cur_x += item.width
            seq.caret_positions.append(cur_x)

    @classmethod
    def draw_node(
        cls,
        cr,
        pango_ctx,
        node: MathNode,
        x: float,
        baseline_y: float,
        scale: float,
        theme: dict,
        prev_item=None,
    ):
        node.abs_x = x
        node.abs_y = baseline_y - node.ascent

        if isinstance(node, CharNode):
            display_text = f" {node.text} " if node.is_operator() and node.text != "," else (
                ", " if node.text == "," else node.text
            )
            is_var = len(node.text) == 1 and node.text.isalpha()
            layout, _, asc, _ = cls._make_layout(pango_ctx, display_text, scale, italic=is_var)
            cr.save()
            if node.is_operator():
                cr.set_source_rgb(*theme["operator"])
            else:
                cr.set_source_rgb(*theme["text"])
            cr.move_to(x, baseline_y - asc)
            PangoCairo.show_layout(cr, layout)
            cr.restore()

        elif isinstance(node, FracNode):
            axis_shift = 5.0 * scale
            gap = 3.0 * scale
            bar_y = baseline_y - axis_shift

            # Draw numerator centered
            num_x = x + (node.width - node.num.width) / 2.0
            num_baseline = bar_y - gap - node.num.descent
            cls.draw_seq(cr, pango_ctx, node.num, num_x, num_baseline, theme)

            # Draw fraction bar
            cr.save()
            cr.set_source_rgb(*theme["text"])
            cr.set_line_width(max(1.2, 1.4 * scale))
            cr.move_to(x + 2.0 * scale, bar_y)
            cr.line_to(x + node.width - 2.0 * scale, bar_y)
            cr.stroke()
            cr.restore()

            # Draw denominator centered
            den_x = x + (node.width - node.den.width) / 2.0
            den_baseline = bar_y + gap + node.den.ascent
            cls.draw_seq(cr, pango_ctx, node.den, den_x, den_baseline, theme)

        elif isinstance(node, SupNode):
            base_asc = prev_item.ascent if prev_item is not None else 12.0 * scale
            shift_up = max(6.0 * scale, base_asc * 0.55)
            cls.draw_seq(cr, pango_ctx, node.exp, x + 1.0 * scale, baseline_y - shift_up, theme)

        elif isinstance(node, SubNode):
            base_desc = prev_item.descent if prev_item is not None else 3.0 * scale
            shift_down = max(5.0 * scale, base_desc + 4.0 * scale)
            cls.draw_seq(cr, pango_ctx, node.sub, x + 1.0 * scale, baseline_y + shift_down, theme)

        elif isinstance(node, SqrtNode):
            deg_w = 0.0
            if node.degree is not None:
                deg_w = max(0.0, node.degree.width - 4.0 * scale)
                deg_baseline = baseline_y - node.radicand.ascent * 0.55
                cls.draw_seq(cr, pango_ctx, node.degree, x, deg_baseline, theme)

            hook_w = 13.0 * scale
            rad_x = x + deg_w + hook_w
            cls.draw_seq(cr, pango_ctx, node.radicand, rad_x, baseline_y, theme)

            # Draw radical symbol around radicand
            top_y = baseline_y - node.radicand.ascent - 2.5 * scale
            bot_y = baseline_y + node.radicand.descent + 1.0 * scale
            mid_y = top_y + (bot_y - top_y) * 0.60

            cr.save()
            cr.set_source_rgb(*theme["text"])
            cr.set_line_width(max(1.2, 1.4 * scale))
            cr.move_to(x + deg_w + 1.0 * scale, mid_y)
            cr.line_to(x + deg_w + 3.5 * scale, mid_y - 2.0 * scale)
            cr.line_to(x + deg_w + 7.5 * scale, bot_y)
            cr.line_to(rad_x - 1.5 * scale, top_y)
            cr.line_to(rad_x + node.radicand.width + 2.5 * scale, top_y)
            cr.line_to(rad_x + node.radicand.width + 2.5 * scale, top_y + 3.5 * scale)
            cr.stroke()
            cr.restore()

        elif isinstance(node, ParenNode):
            paren_w = 8.0 * scale
            cls.draw_seq(cr, pango_ctx, node.inner, x + paren_w, baseline_y, theme)

            top_y = baseline_y - node.ascent + 2.0 * scale
            bot_y = baseline_y + node.descent - 2.0 * scale
            mid_y = (top_y + bot_y) / 2.0
            curve_dx = 5.0 * scale

            cr.save()
            cr.set_source_rgb(*theme["text"])
            cr.set_line_width(max(1.3, 1.5 * scale))
            # Left paren
            lx = x + paren_w - 1.5 * scale
            cr.move_to(lx, top_y)
            cr.curve_to(lx - curve_dx, top_y + (bot_y - top_y) * 0.25, lx - curve_dx, bot_y - (bot_y - top_y) * 0.25, lx, bot_y)
            cr.stroke()
            # Right paren
            rx = x + node.width - paren_w + 1.5 * scale
            cr.move_to(rx, top_y)
            cr.curve_to(rx + curve_dx, top_y + (bot_y - top_y) * 0.25, rx + curve_dx, bot_y - (bot_y - top_y) * 0.25, rx, bot_y)
            cr.stroke()
            cr.restore()

        elif isinstance(node, SumNode):
            sym_w = 22.0 * scale
            sym_half = 12.0 * scale
            axis_shift = 5.0 * scale
            op_w = max(sym_w, node.lower.width, node.upper.width) + 6.0 * scale
            center_x = x + op_w / 2.0
            axis_y = baseline_y - axis_shift

            # Draw Sigma symbol
            sx0 = center_x - sym_w / 2.0
            sx1 = center_x + sym_w / 2.0
            sy0 = axis_y - sym_half
            sy1 = axis_y + sym_half
            cr.save()
            cr.set_source_rgb(*theme["operator"])
            cr.set_line_width(max(1.5, 1.8 * scale))
            cr.move_to(sx1, sy0 + 3.0 * scale)
            cr.line_to(sx1, sy0)
            cr.line_to(sx0, sy0)
            cr.line_to(center_x + 1.0 * scale, axis_y)
            cr.line_to(sx0, sy1)
            cr.line_to(sx1, sy1)
            cr.line_to(sx1, sy1 - 3.0 * scale)
            cr.stroke()
            cr.restore()

            # Upper and lower limits
            up_x = center_x - node.upper.width / 2.0
            up_base = sy0 - 2.0 * scale - node.upper.descent
            cls.draw_seq(cr, pango_ctx, node.upper, up_x, up_base, theme)

            low_x = center_x - node.lower.width / 2.0
            low_base = sy1 + 2.0 * scale + node.lower.ascent
            cls.draw_seq(cr, pango_ctx, node.lower, low_x, low_base, theme)

            # Body
            cls.draw_seq(cr, pango_ctx, node.body, x + op_w + 2.0 * scale, baseline_y, theme)

        elif isinstance(node, IntNode):
            sym_w = 16.0 * scale
            sym_half = 16.0 * scale
            axis_shift = 5.0 * scale
            axis_y = baseline_y - axis_shift
            lim_w = max(node.lower.width, node.upper.width)

            # Draw Integral curve ∫
            ix = x + sym_w * 0.5
            top_y = axis_y - sym_half
            bot_y = axis_y + sym_half
            cr.save()
            cr.set_source_rgb(*theme["operator"])
            cr.set_line_width(max(1.6, 1.9 * scale))
            cr.move_to(ix + 5.0 * scale, top_y + 3.0 * scale)
            cr.curve_to(ix + 3.0 * scale, top_y - 2.0 * scale, ix, top_y, ix, axis_y)
            cr.curve_to(ix, bot_y, ix - 3.0 * scale, bot_y + 2.0 * scale, ix - 5.0 * scale, bot_y - 3.0 * scale)
            cr.stroke()
            cr.restore()

            # Limits
            cls.draw_seq(cr, pango_ctx, node.upper, x + sym_w, top_y + 4.0 * scale, theme)
            cls.draw_seq(cr, pango_ctx, node.lower, x + sym_w, bot_y - 2.0 * scale, theme)

            # Body
            body_x = x + sym_w + lim_w + 4.0 * scale
            cls.draw_seq(cr, pango_ctx, node.body, body_x, baseline_y, theme)

            # 'd' + variable
            d_x = body_x + node.body.width
            layout, d_w, d_asc, _ = cls._make_layout(pango_ctx, " d", scale, italic=True)
            cr.save()
            cr.set_source_rgb(*theme["operator"])
            cr.move_to(d_x, baseline_y - d_asc)
            PangoCairo.show_layout(cr, layout)
            cr.restore()

            cls.draw_seq(cr, pango_ctx, node.var, d_x + d_w, baseline_y, theme)


# ============================================================================
# Worksheet Evaluation Engine (SMath Studio / Mathcad top-down evaluator)
# ============================================================================


BUILTIN_MATH_FUNCS = {
    "sin", "cos", "tan", "asin", "acos", "atan",
    "sinh", "cosh", "tanh", "sqrt", "ln", "log", "exp", "abs",
    "rows", "cols", "col", "row", "len", "total", "mean", "max", "min",
}


def seq_to_python_expr(seq: MathSeq, env: dict = None, is_lhs: bool = False) -> str:
    """Convert a 2D MathSeq into a valid Python math expression string."""
    parts = []
    items = seq.items
    i = 0
    while i < len(items):
        node = items[i]
        # Insert implicit multiplication when needed (e.g. 2x, 2(x+1), a(x+1), (a)(b), 2 sqrt(x))
        if i > 0:
            prev = items[i - 1]
            prev_is_val = (
                (isinstance(prev, CharNode) and (prev.text.isalnum() or prev.text in GREEK_AUTOCOMPLETE.values()))
                or isinstance(prev, (ParenNode, FracNode, SqrtNode, SupNode, SubNode))
            )
            curr_is_val = (
                (isinstance(node, CharNode) and (node.text.isalpha() or node.text in GREEK_AUTOCOMPLETE.values()))
                or isinstance(node, (ParenNode, FracNode, SqrtNode, SumNode, IntNode))
            )
            if prev_is_val and curr_is_val:
                if isinstance(node, ParenNode) and isinstance(prev, (CharNode, SubNode)):
                    # Gather preceding identifier word to check if it is a function call vs constant*(...)
                    k = i - 1
                    ident_chars = []
                    if isinstance(items[k], SubNode):
                        ident_chars.append("_" + seq_to_python_expr(items[k].sub, env))
                        k -= 1
                    while k >= 0 and isinstance(items[k], CharNode) and (
                        items[k].text.isalnum() or items[k].text in GREEK_AUTOCOMPLETE.values()
                    ):
                        ident_chars.append(items[k].text)
                        k -= 1
                    # Names may end in digits (e.g. T1), but cannot start with them (2x -> x)
                    ident = "".join(reversed(ident_chars)).lstrip("0123456789")
                    is_fn_call = (
                        is_lhs
                        or ident in BUILTIN_MATH_FUNCS
                        or (env is not None and callable(env.get(ident)))
                        or (env is not None and ident not in env and len(ident) == 1)
                    )
                    if not is_fn_call:
                        parts.append("*")
                elif isinstance(prev, CharNode) and prev.text.isdigit() and isinstance(node, CharNode) and node.text.isdigit():
                    pass
                elif isinstance(prev, CharNode) and prev.text.isalpha() and isinstance(node, CharNode) and node.text.isalpha():
                    pass
                else:
                    parts.append("*")

        if isinstance(node, CharNode):
            t = node.text
            if t == "·":
                parts.append("*")
            elif t == "π":
                parts.append("pi")
            elif t == "∞":
                parts.append("inf")
            elif t == "≤":
                parts.append("<=")
            elif t == "≥":
                parts.append(">=")
            elif t == "≠":
                parts.append("!=")
            else:
                parts.append(t)
        elif isinstance(node, SubNode):
            # Subscript acts as part of variable identifier: x_1
            sub_txt = seq_to_python_expr(node.sub, env).strip()
            parts.append(f"_{sub_txt}")
        elif isinstance(node, SupNode):
            exp_txt = seq_to_python_expr(node.exp, env)
            parts.append(f"**({exp_txt})")
        elif isinstance(node, FracNode):
            num_txt = seq_to_python_expr(node.num, env)
            den_txt = seq_to_python_expr(node.den, env)
            parts.append(f"(({num_txt})/({den_txt}))")
        elif isinstance(node, SqrtNode):
            rad_txt = seq_to_python_expr(node.radicand, env)
            if node.degree is not None and not node.degree.is_empty():
                deg_txt = seq_to_python_expr(node.degree, env)
                parts.append(f"(({rad_txt})**(1.0/({deg_txt})))")
            else:
                parts.append(f"sqrt({rad_txt})")
        elif isinstance(node, ParenNode):
            inner_txt = seq_to_python_expr(node.inner, env)
            parts.append(f"({inner_txt})")
        elif isinstance(node, SumNode):
            low_txt = seq_to_python_expr(node.lower, env)
            up_txt = seq_to_python_expr(node.upper, env)
            body_txt = seq_to_python_expr(node.body, env)
            if "=" in low_txt:
                var_name, start_expr = low_txt.split("=", 1)
                var_name = var_name.strip()
            else:
                var_name, start_expr = "k", low_txt
            parts.append(f"_smath_sum(lambda {var_name}: ({body_txt}), {start_expr}, {up_txt})")
        elif isinstance(node, IntNode):
            low_txt = seq_to_python_expr(node.lower, env).strip()
            up_txt = seq_to_python_expr(node.upper, env).strip()
            body_txt = seq_to_python_expr(node.body, env)
            var_name = seq_to_python_expr(node.var, env).strip() or "x"
            parts.append(f"_smath_int(lambda {var_name}: ({body_txt}), {low_txt}, {up_txt})")

        i += 1
    return "".join(parts)


def _smath_sum(fn, start, end):
    s = int(round(float(start)))
    e = int(round(float(end)))
    return sum(fn(k) for k in range(s, e + 1))


def _smath_int(fn, a, b, n=200):
    a = float(a)
    b = float(b)
    if a == b:
        return 0.0
    h = (b - a) / n
    total = fn(a) + fn(b)
    for i in range(1, n):
        x = a + i * h
        total += (4.0 if i % 2 == 1 else 2.0) * fn(x)
    return total * h / 3.0


def format_number(val, decimals=None) -> str:
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, (list, tuple)):
        return "[" + ", ".join(format_number(v, decimals=decimals) for v in val) + "]"
    if isinstance(val, (int, float)):
        if math.isnan(val):
            return "NaN"
        if math.isinf(val):
            return "∞" if val > 0 else "-∞"
        if decimals is not None:
            d = max(0, min(15, int(decimals)))
            v_clean = 0.0 if abs(float(val)) < 1e-15 else float(val)
            return f"{v_clean:.{d}f}"
        if abs(val - round(val)) < 1e-10 and abs(val) < 1e14:
            return str(int(round(val)))
        return f"{val:.6g}"
    return str(val)


def _normalize_seq_ast(seq: MathSeq):
    """
    Auto-repair common 2D entry traps:
    1) If ':=' was typed inside a top-level ParenNode (e.g. f(x := x^2 + a)), promote ':=' and its RHS out of ParenNode.
    2) If '+' or '-' or '=' or ':=' was typed inside SupNode.exp after the exponent term (e.g. x^(2+a)),
       promote '+ a' out of SupNode.exp back to the parent sequence baseline (so x^2+a -> x² + a).
    """
    idx = 0
    while idx < len(seq.items):
        node = seq.items[idx]
        if isinstance(node, ParenNode) and seq.parent_node is None:
            # Check if ':=' was typed inside ParenNode
            for sub_i, sub_it in enumerate(node.inner.items):
                if isinstance(sub_it, CharNode) and sub_it.text == ":=":
                    trailing = node.inner.items[sub_i:]
                    del node.inner.items[sub_i:]
                    for offset, tr in enumerate(trailing):
                        seq.insert(idx + 1 + offset, tr)
                    break
        elif isinstance(node, SupNode):
            # Check if '+' / '-' / '=' / ':=' was typed after at least 1 token in SupNode.exp
            exp_items = node.exp.items
            for sub_i in range(1, len(exp_items)):
                sub_it = exp_items[sub_i]
                if isinstance(sub_it, CharNode) and sub_it.text in ("+", "-", "=", ":="):
                    trailing = exp_items[sub_i:]
                    del exp_items[sub_i:]
                    for offset, tr in enumerate(trailing):
                        seq.insert(idx + 1 + offset, tr)
                    break
        elif isinstance(node, SubNode):
            sub_items = node.sub.items
            for sub_i in range(1, len(sub_items)):
                sub_it = sub_items[sub_i]
                if isinstance(sub_it, CharNode) and sub_it.text in ("+", "-", "·", "*", "=", ":="):
                    trailing = sub_items[sub_i:]
                    del sub_items[sub_i:]
                    for offset, tr in enumerate(trailing):
                        seq.insert(idx + 1 + offset, tr)
                    break

        for child_slot in node.slots():
            _normalize_seq_ast(child_slot)
        idx += 1


def _format_symbolic_rhs(rhs_str: str, args: list, env: dict, decimals=None) -> str:
    """Format a function body with known constants from env substituted for display."""
    import re
    disp = rhs_str.replace("**", "^").replace("*", "·")
    disp = re.sub(r"\^\(([A-Za-z0-9_]+)\)", r"^\1", disp)

    def _repl(match):
        word = match.group(0)
        if word in args or word in BUILTIN_MATH_FUNCS:
            return word
        if word in env and isinstance(env[word], (int, float)):
            return format_number(env[word], decimals=decimals)
        return word

    return re.sub(r"\b[A-Za-z_]\w*\b", _repl, disp)


def evaluate_box_ast(
    root: MathSeq,
    env: dict,
    is_editing: bool = False,
    decimals=None,
):
    """
    Inspect top-level tokens of root for ':=' (or '=') assignment and trailing '=' (evaluation).
    Updates env if ':=' (or mid-box '=') is present, and returns a result string if trailing '=' is present.
    """
    if not is_editing:
        _normalize_seq_ast(root)

    items = root.items
    if not items:
        return None, False

    # Check if last token is '=' (requesting evaluation display)
    wants_eval = isinstance(items[-1], CharNode) and items[-1].text == "="
    work_items = items[:-1] if wants_eval else items

    # Find top-level ':=' (or top-level '=' if ':=' is not present)
    assign_idx = None
    for idx, it in enumerate(work_items):
        if isinstance(it, CharNode) and it.text == ":=":
            assign_idx = idx
            break
    if assign_idx is None:
        for idx, it in enumerate(work_items):
            if isinstance(it, CharNode) and it.text == "=" and 0 < idx < len(work_items) - 1:
                assign_idx = idx
                break

    env.setdefault("__builtins__", {})
    sheet_funcs = env.setdefault("_sheet_functions", [])
    sheet_vecs = env.setdefault("_sheet_vectors", [])
    sheet_func_defs = env.setdefault("_sheet_func_defs", {})

    try:
        if assign_idx is not None:
            lhs_seq = MathSeq()
            lhs_seq.items = work_items[:assign_idx]
            rhs_seq = MathSeq()
            rhs_seq.items = work_items[assign_idx + 1 :]
            lhs_str = seq_to_python_expr(lhs_seq, env, is_lhs=True).strip()
            rhs_str = seq_to_python_expr(rhs_seq, env, is_lhs=False).strip()
            if not lhs_str or not rhs_str:
                return ("?" if wants_eval else None), False

            # Support function definitions like f(x) := x^2 + a
            if "(" in lhs_str and lhs_str.endswith(")"):
                fn_name, arg_part = lhs_str[:-1].split("(", 1)
                fn_name = fn_name.strip()
                args = [a.strip() for a in arg_part.split(",") if a.strip()]
                fn_code = f"lambda {', '.join(args)}: ({rhs_str})"
                fn_obj = eval(fn_code, env)
                # Test-evaluate with dummy 1.0 args to verify constants in rhs_str are defined
                test_args = [1.0 for _ in args]
                try:
                    fn_obj(*test_args)
                except ZeroDivisionError:
                    pass
                env[fn_name] = fn_obj
                sheet_func_defs[fn_name] = (args, rhs_str)
                if fn_name not in sheet_funcs:
                    sheet_funcs.append(fn_name)
                if wants_eval:
                    return _format_symbolic_rhs(rhs_str, args, env, decimals=decimals), False
                return None, False
            else:
                val = eval(rhs_str, env)
                env[lhs_str] = val
                if isinstance(val, (list, tuple)) and lhs_str not in sheet_vecs:
                    sheet_vecs.append(lhs_str)
                return (format_number(val, decimals=decimals) if wants_eval else None), False
        elif wants_eval:
            expr_seq = MathSeq()
            expr_seq.items = work_items
            expr_str = seq_to_python_expr(expr_seq, env, is_lhs=False).strip()
            if not expr_str:
                return "?", False
            try:
                val = eval(expr_str, env)
                return format_number(val, decimals=decimals), False
            except NameError:
                # If user wrote f(x) = where f is a sheet function and x is an undefined symbolic identifier
                if "(" in expr_str and expr_str.endswith(")"):
                    fn_name, arg_part = expr_str[:-1].split("(", 1)
                    fn_name = fn_name.strip()
                    call_args = [a.strip() for a in arg_part.split(",") if a.strip()]
                    if fn_name in sheet_func_defs and all(ca.isidentifier() and ca not in env for ca in call_args):
                        f_args, f_rhs = sheet_func_defs[fn_name]
                        return _format_symbolic_rhs(f_rhs, f_args, env, decimals=decimals), False
                raise
    except Exception:
        if wants_eval:
            return "?", True
    return None, False


# ============================================================================
# AST JSON Serialization & Deserialization (for File -> Save / Open)
# ============================================================================

import base64
import json


def serialize_math_seq(seq: MathSeq) -> list:
    items = []
    for it in seq.items:
        if isinstance(it, CharNode):
            items.append({"t": "char", "v": it.text})
        elif isinstance(it, FracNode):
            items.append({"t": "frac", "num": serialize_math_seq(it.num), "den": serialize_math_seq(it.den)})
        elif isinstance(it, SupNode):
            items.append({"t": "sup", "exp": serialize_math_seq(it.exp)})
        elif isinstance(it, SubNode):
            items.append({"t": "sub", "sub": serialize_math_seq(it.sub)})
        elif isinstance(it, SqrtNode):
            items.append({
                "t": "sqrt",
                "rad": serialize_math_seq(it.radicand),
                "deg": serialize_math_seq(it.degree) if it.degree is not None else None,
            })
        elif isinstance(it, ParenNode):
            items.append({"t": "paren", "in": serialize_math_seq(it.inner)})
        elif isinstance(it, SumNode):
            items.append({
                "t": "sum",
                "low": serialize_math_seq(it.lower),
                "up": serialize_math_seq(it.upper),
                "body": serialize_math_seq(it.body),
            })
        elif isinstance(it, IntNode):
            items.append({
                "t": "int",
                "low": serialize_math_seq(it.lower),
                "up": serialize_math_seq(it.upper),
                "body": serialize_math_seq(it.body),
                "var": serialize_math_seq(it.var),
            })
    return items


def deserialize_math_seq(data: list, parent_node=None) -> MathSeq:
    seq = MathSeq(parent_node)
    for entry in data or []:
        kind = entry.get("t")
        if kind == "char":
            seq.append(CharNode(entry.get("v", "")))
        elif kind == "frac":
            num = deserialize_math_seq(entry.get("num", []))
            den = deserialize_math_seq(entry.get("den", []))
            seq.append(FracNode(num=num, den=den))
        elif kind == "sup":
            seq.append(SupNode(exp=deserialize_math_seq(entry.get("exp", []))))
        elif kind == "sub":
            seq.append(SubNode(sub=deserialize_math_seq(entry.get("sub", []))))
        elif kind == "sqrt":
            rad = deserialize_math_seq(entry.get("rad", []))
            deg_data = entry.get("deg")
            deg = deserialize_math_seq(deg_data) if deg_data is not None else None
            seq.append(SqrtNode(radicand=rad, degree=deg))
        elif kind == "paren":
            seq.append(ParenNode(inner=deserialize_math_seq(entry.get("in", []))))
        elif kind == "sum":
            node = SumNode(
                lower=deserialize_math_seq(entry.get("low", [])),
                upper=deserialize_math_seq(entry.get("up", [])),
                body=deserialize_math_seq(entry.get("body", [])),
            )
            seq.append(node)
        elif kind == "int":
            node = IntNode(
                lower=deserialize_math_seq(entry.get("low", [])),
                upper=deserialize_math_seq(entry.get("up", [])),
                body=deserialize_math_seq(entry.get("body", [])),
                var=deserialize_math_seq(entry.get("var", [])),
            )
            seq.append(node)
    return seq


# ============================================================================
# Interactive 2D MathBox Widget
# ============================================================================


class MathBox(Gtk.DrawingArea):
    PADDING_X = 8.0
    PADDING_Y = 6.0

    def __init__(self, canvas, x, y):
        super().__init__()
        self.canvas = canvas
        self.x = int(x)
        self.y = int(y)
        self.logical_w = 28
        self.logical_h = 28

        self.root = MathSeq(None)
        self.cursor_seq = self.root
        self.cursor_idx = 0

        self.editing = False
        self.selected = False
        self.dragging = False
        self.drag_start_root_x = 0
        self.drag_start_root_y = 0
        self.drag_start_box_x = 0
        self.drag_start_box_y = 0

        self.eval_result = None
        self.eval_error = False
        self.decimal_places = None  # None = Auto (6 sig figs), or int 0..15 fixed decimals
        self.boxed = False  # Draw permanent solid frame around equation (also exported to PDF)

        self.set_can_focus(True)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
            | Gdk.EventMask.FOCUS_CHANGE_MASK
        )

        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("key-press-event", self.on_key_press)
        self.connect("focus-out-event", self.on_focus_out)

        self.update_layout()

    def is_empty(self):
        return self.root.is_empty()

    def set_selected(self, selected):
        self.selected = selected
        self.queue_draw()

    def set_decimal_places(self, decimals):
        self.decimal_places = None if decimals is None else max(0, min(15, int(decimals)))
        self.canvas.recalculate_worksheet()
        self.update_layout()
        self.queue_draw()
        if callable(getattr(self.canvas, "on_selection_changed", None)):
            self.canvas.on_selection_changed(self.canvas.selected_box)

    def _open_custom_decimals_dialog(self):
        toplevel = self.get_toplevel()
        parent = toplevel if isinstance(toplevel, Gtk.Window) else None
        dlg = Gtk.Dialog(
            title="Result Decimal Places",
            transient_for=parent,
            flags=0,
        )
        dlg.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK,
            Gtk.ResponseType.OK,
        )
        dlg.set_default_size(300, 120)
        box = dlg.get_content_area()
        box.set_spacing(10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(14)
        box.set_margin_end(14)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl = Gtk.Label(label="Decimal places (0–15):")
        lbl.set_xalign(0.0)
        adj = Gtk.Adjustment(
            value=float(self.decimal_places if self.decimal_places is not None else 4),
            lower=0.0,
            upper=15.0,
            step_increment=1.0,
            page_increment=2.0,
            page_size=0.0,
        )
        spin = Gtk.SpinButton(adjustment=adj, climb_rate=1.0, digits=0)
        spin.set_numeric(True)
        row.pack_start(lbl, True, True, 0)
        row.pack_start(spin, False, False, 0)
        box.pack_start(row, False, False, 0)
        dlg.show_all()

        if dlg.run() == Gtk.ResponseType.OK:
            val = spin.get_value_as_int()
            dlg.destroy()
            self.canvas.set_decimal_places_for_selected(val, fallback_box=self)
        else:
            dlg.destroy()

    def _show_context_menu(self, event):
        menu = Gtk.Menu()
        cur = self.decimal_places

        box_prefix = "✓ " if self.boxed else "    "
        box_mi = Gtk.MenuItem(label=f"{box_prefix}Box Equation (Border Frame)")
        box_mi.connect(
            "activate",
            lambda _mi: self.canvas.toggle_boxed_for_selected(fallback_box=self),
        )
        menu.append(box_mi)
        menu.append(Gtk.SeparatorMenuItem())

        header_item = Gtk.MenuItem(label="Result Decimal Places")
        header_item.set_sensitive(False)
        menu.append(header_item)
        menu.append(Gtk.SeparatorMenuItem())

        presets = [
            (None, "Auto (Default)"),
            (0, "0 Decimal Places  (12)"),
            (1, "1 Decimal Place   (12.3)"),
            (2, "2 Decimal Places  (12.34)"),
            (3, "3 Decimal Places  (12.345)"),
            (4, "4 Decimal Places  (12.3456)"),
            (5, "5 Decimal Places"),
            (6, "6 Decimal Places"),
            (8, "8 Decimal Places"),
            (10, "10 Decimal Places"),
        ]
        for dec_val, label in presets:
            prefix = "✓ " if cur == dec_val else "    "
            mi = Gtk.MenuItem(label=f"{prefix}{label}")
            mi.connect(
                "activate",
                lambda _mi, d=dec_val: self.canvas.set_decimal_places_for_selected(d, fallback_box=self),
            )
            menu.append(mi)

        menu.append(Gtk.SeparatorMenuItem())
        custom_mi = Gtk.MenuItem(label="    Custom Decimal Places...")
        custom_mi.connect("activate", lambda _mi: self._open_custom_decimals_dialog())
        menu.append(custom_mi)

        menu.append(Gtk.SeparatorMenuItem())
        del_mi = Gtk.MenuItem(label="Delete Selected")
        del_mi.connect("activate", lambda _mi: self.canvas.remove_selected_boxes(self))
        menu.append(del_mi)

        menu.show_all()
        menu.popup_at_pointer(event)

    def start_editing(self):
        self.editing = True
        self.dragging = False
        self.selected = True
        self.canvas.focus_without_scroll(self)
        self.update_layout()
        self.queue_draw()

    def stop_editing(self):
        if not self.editing:
            return
        self.editing = False
        if self.is_empty():
            self.canvas.remove_box(self)
            return
        self.canvas.recalculate_worksheet()
        self.update_layout()
        self.queue_draw()

    def update_layout(self):
        pango_ctx = self.get_pango_context()
        MathRenderer.measure_seq(pango_ctx, self.root, 1.0)
        extra_w = 0.0
        if self.eval_result is not None:
            _, rw, _, _ = MathRenderer._make_layout(pango_ctx, f" {self.eval_result}", 1.0, bold=True)
            extra_w = rw + 6.0
        w = max(28, int(math.ceil(self.root.width + extra_w + self.PADDING_X * 2)))
        h = max(28, int(math.ceil(self.root.height + self.PADDING_Y * 2)))
        self.logical_w = w
        self.logical_h = h
        z = getattr(self.canvas, "zoom", 1.0)
        self.set_size_request(max(16, int(math.ceil(w * z))), max(16, int(math.ceil(h * z))))
        self.queue_draw()

    def draw_content(self, cr, theme=None, for_export=False):
        if theme is None:
            theme = THEMES[self.canvas.theme_name]
        w, h = self.logical_w, self.logical_h

        # Background fill when editing
        if self.editing and not for_export:
            cr.save()
            cr.set_source_rgba(*theme["box_editing_bg"])
            cr.rectangle(0, 0, w, h)
            cr.fill()
            cr.restore()

        # Permanent equation box border (visible on sheet and in PDF export)
        if self.boxed:
            cr.save()
            cr.set_source_rgba(*theme["heading_text"], 0.08 if not for_export else 0.05)
            cr.rectangle(1.0, 1.0, w - 2.0, h - 2.0)
            cr.fill()
            cr.set_source_rgb(*theme["heading_text"])
            cr.set_line_width(1.6)
            cr.rectangle(1.0, 1.0, w - 2.0, h - 2.0)
            cr.stroke()
            cr.restore()

        # Render 2D equation tree
        pango_ctx = self.get_pango_context()
        MathRenderer.measure_seq(pango_ctx, self.root, 1.0)
        baseline_y = self.PADDING_Y + self.root.ascent
        MathRenderer.draw_seq(cr, pango_ctx, self.root, self.PADDING_X, baseline_y, theme)

        # Render evaluation result (if expression ends with '=')
        if self.eval_result is not None:
            res_x = self.PADDING_X + self.root.width
            layout, _, r_asc, _ = MathRenderer._make_layout(
                pango_ctx, f" {self.eval_result}", 1.0, bold=True
            )
            cr.save()
            cr.set_source_rgb(*(theme["error"] if self.eval_error else theme["result"]))
            cr.move_to(res_x, baseline_y - r_asc)
            PangoCairo.show_layout(cr, layout)
            cr.restore()

        if for_export:
            return

        # Render active 2D cursor & slot highlight
        if self.editing:
            seq = self.cursor_seq
            idx = max(0, min(self.cursor_idx, len(seq.caret_positions) - 1))
            if seq.caret_positions:
                cx = seq.caret_positions[idx]
                cy_top = seq.abs_y
                cy_bot = seq.abs_y + seq.height
                cr.save()
                cr.set_source_rgb(*theme["cursor"])
                cr.set_line_width(1.8)
                cr.move_to(cx, cy_top)
                cr.line_to(cx, cy_bot)
                cr.stroke()
                cr.restore()

        # Selection or Editing frame
        if self.editing:
            cr.save()
            cr.set_source_rgb(*theme["box_editing_border"])
            cr.set_line_width(1.2)
            cr.rectangle(0.6, 0.6, w - 1.2, h - 1.2)
            cr.stroke()
            cr.restore()
        elif self.selected:
            cr.save()
            cr.set_source_rgb(*theme["box_selected_border"])
            cr.set_line_width(1.2)
            cr.set_dash([4.0, 3.0])
            cr.rectangle(0.6, 0.6, w - 1.2, h - 1.2)
            cr.stroke()
            cr.restore()

    def on_draw(self, widget, cr):
        z = getattr(self.canvas, "zoom", 1.0)
        cr.save()
        cr.scale(z, z)
        self.draw_content(cr, for_export=False)
        cr.restore()
        return True

    # ------------------------------------------------------------------------
    # Mouse Handling (Single-click select/drag, Double-click or click-inside edit)
    # ------------------------------------------------------------------------

    def _hit_test_seq(self, seq: MathSeq, mx: float, my: float):
        """Find the deepest (MathSeq, index) closest to mouse (mx, my)."""
        for item in seq.items:
            for child_seq in item.slots():
                if (
                    child_seq.abs_x - 3 <= mx <= child_seq.abs_x + child_seq.width + 3
                    and child_seq.abs_y - 3 <= my <= child_seq.abs_y + child_seq.height + 3
                ):
                    return self._hit_test_seq(child_seq, mx, my)

        best_idx = 0
        best_dist = float("inf")
        for idx, cx in enumerate(seq.caret_positions):
            d = abs(mx - cx)
            if d < best_dist:
                best_dist = d
                best_idx = idx
        return seq, best_idx

    def on_button_press(self, widget, event):
        if event.button == 1:
            z = getattr(self.canvas, "zoom", 1.0)
            lx, ly = event.x / z, event.y / z
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self.canvas.select_box(self)
                self.start_editing()
                seq, idx = self._hit_test_seq(self.root, lx, ly)
                self.cursor_seq = seq
                self.cursor_idx = idx
                self.queue_draw()
                return True

            if self.editing:
                seq, idx = self._hit_test_seq(self.root, lx, ly)
                self.cursor_seq = seq
                self.cursor_idx = idx
                self.canvas.focus_without_scroll(self)
                self.queue_draw()
                return True
            else:
                self.canvas.handle_box_button_press(self, event)
                self.dragging = True
                self.drag_start_root_x = event.x_root
                self.drag_start_root_y = event.y_root
                self.drag_start_box_x = self.x
                self.drag_start_box_y = self.y
                return True
        elif event.button == 3:
            if self not in self.canvas.selected_boxes:
                self.canvas.select_box(self)
            self._show_context_menu(event)
            return True
        return False

    def on_motion_notify(self, widget, event):
        if self.dragging and not self.editing:
            z = getattr(self.canvas, "zoom", 1.0)
            dx = int((event.x_root - self.drag_start_root_x) / z)
            dy = int((event.y_root - self.drag_start_root_y) / z)
            self.canvas.drag_box_or_group(self, dx, dy)
            return True
        return False

    def on_button_release(self, widget, event):
        if event.button == 1 and self.dragging:
            self.dragging = False
            self.canvas.recalculate_worksheet()
            return True
        return False

    def on_focus_out(self, widget, event):
        # Note: toolbar clicks keep editing active via can_focus=False on toolbar buttons
        self.stop_editing()
        return False

    # ------------------------------------------------------------------------
    # 2D Structural Keyboard Editing & Navigation
    # ------------------------------------------------------------------------

    def _extract_preceding_term(self, seq: MathSeq, idx: int) -> MathSeq:
        """Pop the contiguous term immediately before idx (for '/' fraction creation)."""
        start = idx
        while start > 0:
            prev = seq.items[start - 1]
            if isinstance(prev, CharNode) and prev.is_operator():
                break
            start -= 1
        extracted = MathSeq()
        for it in seq.items[start:idx]:
            extracted.append(it)
        del seq.items[start:idx]
        self.cursor_idx = start
        return extracted

    def _trailing_word(self, seq: MathSeq, idx: int):
        """Return (start_idx, word_str) of contiguous ASCII letters before idx."""
        start = idx
        chars = []
        while start > 0 and isinstance(seq.items[start - 1], CharNode):
            ch = seq.items[start - 1].text
            if len(ch) == 1 and ch.isalpha():
                chars.append(ch)
                start -= 1
            else:
                break
        chars.reverse()
        return start, "".join(chars)

    def _try_convert_trailing_word(self):
        """Convert trailing 'sqrt', 'sum', 'int', or Greek name into 2D symbol/node."""
        start, word = self._trailing_word(self.cursor_seq, self.cursor_idx)
        if not word:
            return False
        if word == "sqrt":
            del self.cursor_seq.items[start : self.cursor_idx]
            self.cursor_idx = start
            self.insert_sqrt()
            return True
        if word == "root":
            del self.cursor_seq.items[start : self.cursor_idx]
            self.cursor_idx = start
            self.insert_nth_root()
            return True
        if word == "sum":
            del self.cursor_seq.items[start : self.cursor_idx]
            self.cursor_idx = start
            self.insert_sum()
            return True
        if word == "int":
            del self.cursor_seq.items[start : self.cursor_idx]
            self.cursor_idx = start
            self.insert_integral()
            return True
        if word in GREEK_AUTOCOMPLETE:
            del self.cursor_seq.items[start : self.cursor_idx]
            self.cursor_idx = start
            self.insert_char(GREEK_AUTOCOMPLETE[word])
            return True
        return False

    def insert_char(self, text: str):
        node = CharNode(text)
        self.cursor_seq.insert(self.cursor_idx, node)
        self.cursor_idx += 1
        self._after_edit()

    def insert_fraction(self):
        num_seq = self._extract_preceding_term(self.cursor_seq, self.cursor_idx)
        frac = FracNode(num=num_seq)
        self.cursor_seq.insert(self.cursor_idx, frac)
        if num_seq.is_empty():
            self.cursor_seq = frac.num
            self.cursor_idx = 0
        else:
            self.cursor_seq = frac.den
            self.cursor_idx = 0
        self._after_edit()

    def insert_superscript(self):
        sup = SupNode()
        self.cursor_seq.insert(self.cursor_idx, sup)
        self.cursor_seq = sup.exp
        self.cursor_idx = 0
        self._after_edit()

    def insert_subscript(self):
        sub = SubNode()
        self.cursor_seq.insert(self.cursor_idx, sub)
        self.cursor_seq = sub.sub
        self.cursor_idx = 0
        self._after_edit()

    def insert_sqrt(self):
        sq = SqrtNode()
        self.cursor_seq.insert(self.cursor_idx, sq)
        self.cursor_seq = sq.radicand
        self.cursor_idx = 0
        self._after_edit()

    def insert_nth_root(self):
        sq = SqrtNode(degree=MathSeq())
        self.cursor_seq.insert(self.cursor_idx, sq)
        self.cursor_seq = sq.degree
        self.cursor_idx = 0
        self._after_edit()

    def insert_parens(self):
        p = ParenNode()
        self.cursor_seq.insert(self.cursor_idx, p)
        self.cursor_seq = p.inner
        self.cursor_idx = 0
        self._after_edit()

    def insert_vector_brackets(self):
        """Insert [ ] brackets and place the cursor between them for entering a discrete vector."""
        self.cursor_seq.insert(self.cursor_idx, CharNode("["))
        self.cursor_seq.insert(self.cursor_idx + 1, CharNode("]"))
        self.cursor_idx += 1
        self._after_edit()

    def insert_text_tokens(self, text: str):
        """Insert a sequence of characters/tokens directly at the cursor."""
        for ch in text:
            self.cursor_seq.insert(self.cursor_idx, CharNode(ch))
            self.cursor_idx += 1
        self._after_edit()

    def insert_sum(self):
        s = SumNode()
        s.lower.append(CharNode("k"))
        s.lower.append(CharNode("="))
        s.lower.append(CharNode("1"))
        self.cursor_seq.insert(self.cursor_idx, s)
        self.cursor_seq = s.upper
        self.cursor_idx = 0
        self._after_edit()

    def insert_integral(self):
        it = IntNode()
        it.var.append(CharNode("x"))
        self.cursor_seq.insert(self.cursor_idx, it)
        self.cursor_seq = it.lower
        self.cursor_idx = 0
        self._after_edit()

    def move_left(self):
        if self.cursor_idx > 0:
            prev_node = self.cursor_seq.items[self.cursor_idx - 1]
            slots = prev_node.slots()
            if slots:
                self.cursor_seq = slots[-1]
                self.cursor_idx = len(self.cursor_seq.items)
            else:
                self.cursor_idx -= 1
        elif self.cursor_seq.parent_node is not None:
            parent_node = self.cursor_seq.parent_node
            slots = parent_node.slots()
            s_idx = slots.index(self.cursor_seq)
            if s_idx > 0:
                self.cursor_seq = slots[s_idx - 1]
                self.cursor_idx = len(self.cursor_seq.items)
            else:
                parent_seq = parent_node.parent_seq
                self.cursor_idx = parent_seq.items.index(parent_node)
                self.cursor_seq = parent_seq
        self.queue_draw()

    def move_right(self):
        if self.cursor_idx < len(self.cursor_seq.items):
            next_node = self.cursor_seq.items[self.cursor_idx]
            slots = next_node.slots()
            if slots:
                self.cursor_seq = slots[0]
                self.cursor_idx = 0
            else:
                self.cursor_idx += 1
        elif self.cursor_seq.parent_node is not None:
            parent_node = self.cursor_seq.parent_node
            slots = parent_node.slots()
            s_idx = slots.index(self.cursor_seq)
            if s_idx + 1 < len(slots):
                self.cursor_seq = slots[s_idx + 1]
                self.cursor_idx = 0
            else:
                parent_seq = parent_node.parent_seq
                self.cursor_idx = parent_seq.items.index(parent_node) + 1
                self.cursor_seq = parent_seq
        self.queue_draw()

    def step_out_slot(self):
        """Step out of the current 2D construct (Space / Tab), like SMath & MS Equation."""
        if self.cursor_seq.parent_node is not None:
            parent_node = self.cursor_seq.parent_node
            slots = parent_node.slots()
            s_idx = slots.index(self.cursor_seq)
            if s_idx + 1 < len(slots):
                self.cursor_seq = slots[s_idx + 1]
                self.cursor_idx = len(self.cursor_seq.items)
            else:
                parent_seq = parent_node.parent_seq
                self.cursor_idx = parent_seq.items.index(parent_node) + 1
                self.cursor_seq = parent_seq
            self.queue_draw()

    def move_up(self):
        seq = self.cursor_seq
        while seq is not None and seq.parent_node is not None:
            p = seq.parent_node
            if isinstance(p, FracNode) and seq is p.den:
                self.cursor_seq = p.num
                self.cursor_idx = min(self.cursor_idx, len(p.num.items))
                self.queue_draw()
                return
            if isinstance(p, (SumNode, IntNode)) and seq is p.lower:
                self.cursor_seq = p.upper
                self.cursor_idx = min(self.cursor_idx, len(p.upper.items))
                self.queue_draw()
                return
            seq = p.parent_seq

    def move_down(self):
        seq = self.cursor_seq
        while seq is not None and seq.parent_node is not None:
            p = seq.parent_node
            if isinstance(p, FracNode) and seq is p.num:
                self.cursor_seq = p.den
                self.cursor_idx = min(self.cursor_idx, len(p.den.items))
                self.queue_draw()
                return
            if isinstance(p, (SumNode, IntNode)) and seq is p.upper:
                self.cursor_seq = p.lower
                self.cursor_idx = min(self.cursor_idx, len(p.lower.items))
                self.queue_draw()
                return
            seq = p.parent_seq

    def handle_backspace(self):
        if self.cursor_idx > 0:
            prev_node = self.cursor_seq.items[self.cursor_idx - 1]
            slots = prev_node.slots()
            if not slots:
                del self.cursor_seq.items[self.cursor_idx - 1]
                self.cursor_idx -= 1
            else:
                if all(s.is_empty() for s in slots):
                    del self.cursor_seq.items[self.cursor_idx - 1]
                    self.cursor_idx -= 1
                else:
                    self.cursor_seq = slots[-1]
                    self.cursor_idx = len(self.cursor_seq.items)
        elif self.cursor_seq.parent_node is not None:
            parent_node = self.cursor_seq.parent_node
            parent_seq = parent_node.parent_seq
            p_idx = parent_seq.items.index(parent_node)
            if isinstance(parent_node, FracNode) and self.cursor_seq is parent_node.den and parent_node.den.is_empty():
                # Unwrap numerator back into parent_seq
                num_items = parent_node.num.items
                del parent_seq.items[p_idx]
                for offset, it in enumerate(num_items):
                    parent_seq.insert(p_idx + offset, it)
                self.cursor_seq = parent_seq
                self.cursor_idx = p_idx + len(num_items)
            elif all(s.is_empty() for s in parent_node.slots()):
                del parent_seq.items[p_idx]
                self.cursor_seq = parent_seq
                self.cursor_idx = p_idx
            else:
                self.move_left()
                return
        self._after_edit()

    def _after_edit(self):
        self.canvas.recalculate_worksheet()
        self.update_layout()

    def _step_out_to_root_if_needed(self):
        """Step out of ParenNode / SupNode / SubNode / SqrtNode / FracNode to root before ':=' or '='."""
        seq = self.cursor_seq
        while seq.parent_node is not None:
            if isinstance(seq.parent_node, (SumNode, IntNode)) and seq is seq.parent_node.lower:
                return
            p_node = seq.parent_node
            p_seq = p_node.parent_seq
            self.cursor_idx = p_seq.items.index(p_node) + 1
            self.cursor_seq = p_seq
            seq = self.cursor_seq

    def on_key_press(self, widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            return False
        keyname = Gdk.keyval_name(event.keyval)

        if not self.editing:
            if keyname in ("Delete", "BackSpace"):
                self.canvas.remove_selected_boxes(self)
                return True
            if keyname in ("Return", "KP_Enter"):
                self.start_editing()
                return True
            return False

        # Navigation keys
        if keyname == "Left":
            self.move_left()
            return True
        if keyname == "Right":
            self.move_right()
            return True
        if keyname == "Up":
            self.move_up()
            return True
        if keyname == "Down":
            self.move_down()
            return True
        if keyname in ("Tab", "ISO_Left_Tab"):
            if not self._try_convert_trailing_word():
                self.step_out_slot()
            return True
        if keyname == "space":
            if not self._try_convert_trailing_word():
                self.step_out_slot()
            return True
        if keyname == "Escape":
            self._try_convert_trailing_word()
            self.stop_editing()
            return True
        if keyname in ("Return", "KP_Enter"):
            self._try_convert_trailing_word()
            self.canvas.exit_box_and_move_down(self)
            return True
        if keyname == "BackSpace":
            self.handle_backspace()
            return True

        # Structural 2D math shortcuts (SMath / Mathcad / MS Equation style)
        ch = chr(Gdk.keyval_to_unicode(event.keyval)) if Gdk.keyval_to_unicode(event.keyval) else ""

        # Auto-step-out of SubNode on any operator or delimiter
        if isinstance(self.cursor_seq.parent_node, SubNode) and len(self.cursor_seq.items) > 0:
            if ch in ("+", "-", "*", "/", "^", "(", ")", ":", "=", ",", ";"):
                self.step_out_slot()

        # Auto-step-out of SupNode when typing '+', '-', ',', ';' after at least 1 token (so x^2+a -> x² + a)
        if isinstance(self.cursor_seq.parent_node, SupNode) and len(self.cursor_seq.items) > 0:
            if ch in ("+", "-", ",", ";"):
                self._try_convert_trailing_word()
                self.step_out_slot()

        if ch == "/":
            self._try_convert_trailing_word()
            self.insert_fraction()
            return True
        if ch == "^":
            self._try_convert_trailing_word()
            self.insert_superscript()
            return True
        if ch == "_":
            self._try_convert_trailing_word()
            self.insert_subscript()
            return True
        if ch == "\\":
            self._try_convert_trailing_word()
            self.insert_sqrt()
            return True
        if ch == "(":
            if not self._try_convert_trailing_word():
                self.insert_parens()
            return True
        if ch == ")":
            self._try_convert_trailing_word()
            seq = self.cursor_seq
            while seq is not None and seq.parent_node is not None:
                if isinstance(seq.parent_node, ParenNode):
                    parent_node = seq.parent_node
                    parent_seq = parent_node.parent_seq
                    self.cursor_idx = parent_seq.items.index(parent_node) + 1
                    self.cursor_seq = parent_seq
                    self.queue_draw()
                    break
                seq = seq.parent_node.parent_seq
            return True
        if ch == ":":
            self._try_convert_trailing_word()
            self._step_out_to_root_if_needed()
            self.insert_char(":=")
            return True
        if ch == "=":
            self._try_convert_trailing_word()
            self._step_out_to_root_if_needed()
            # If user types '=' right after ':=', ignore duplicate '='
            if self.cursor_idx > 0 and isinstance(self.cursor_seq.items[self.cursor_idx - 1], CharNode):
                prev_txt = self.cursor_seq.items[self.cursor_idx - 1].text
                if prev_txt == ":=":
                    return True
                if prev_txt == "<":
                    self.cursor_seq.items[self.cursor_idx - 1].text = "≤"
                    self._after_edit()
                    return True
                if prev_txt == ">":
                    self.cursor_seq.items[self.cursor_idx - 1].text = "≥"
                    self._after_edit()
                    return True
                if prev_txt == "!":
                    self.cursor_seq.items[self.cursor_idx - 1].text = "≠"
                    self._after_edit()
                    return True
            self.insert_char("=")
            return True
        if ch == "*":
            self._try_convert_trailing_word()
            self.insert_char("·")
            return True
        if ch == '"' and self.is_empty():
            # SMath Studio shortcut: typing '"' in an empty box converts it into a TextBox (defaulting to normal style)
            x, y = self.x, self.y
            canvas = self.canvas
            self.editing = False
            canvas.remove_box(self)
            canvas.create_text_box(x, y, style_name="normal", edit=True)
            return True

        # Printable characters (digits, letters, +, -, ., ,, etc.)
        if ch and ch.isprintable():
            if not ch.isalpha():
                self._try_convert_trailing_word()
            self.insert_char(ch)
            return True

        return False


# ============================================================================
# Styled Text Box Widget (Title, Heading 1, Heading 2, Heading 3, Normal)
# ============================================================================


class TextBox(Gtk.DrawingArea):
    PADDING_X = 8.0
    PADDING_Y = 5.0

    def __init__(self, canvas, x, y, style_name="normal", text=""):
        super().__init__()
        self.canvas = canvas
        self.x = int(x)
        self.y = int(y)
        self.logical_w = 60
        self.logical_h = 28
        self.style_name = style_name if style_name in TEXT_STYLES else "normal"
        self.text = text
        self.cursor_pos = len(text)

        self.editing = False
        self.selected = False
        self.dragging = False
        self.drag_start_root_x = 0
        self.drag_start_root_y = 0
        self.drag_start_box_x = 0
        self.drag_start_box_y = 0

        self.set_can_focus(True)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
            | Gdk.EventMask.FOCUS_CHANGE_MASK
        )

        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("key-press-event", self.on_key_press)
        self.connect("focus-out-event", self.on_focus_out)

        self.update_layout()

    def is_empty(self):
        return len(self.text.strip()) == 0

    def set_style_name(self, style_name: str):
        if style_name in TEXT_STYLES:
            self.style_name = style_name
            self.update_layout()
            self.queue_draw()

    def set_selected(self, selected):
        self.selected = selected
        self.queue_draw()

    def start_editing(self):
        self.editing = True
        self.dragging = False
        self.selected = True
        self.canvas.focus_without_scroll(self)
        self.update_layout()
        self.queue_draw()

    def stop_editing(self):
        if not self.editing:
            return
        self.editing = False
        if self.is_empty():
            self.canvas.remove_box(self)
            return
        self.update_layout()
        self.queue_draw()

    def _create_pango_layout(self, display_text=None):
        pango_ctx = self.get_pango_context()
        layout = Pango.Layout.new(pango_ctx)
        style_cfg = TEXT_STYLES[self.style_name]
        desc = Pango.FontDescription.from_string(style_cfg["font"])
        layout.set_font_description(desc)
        max_w = max(120, self.canvas.A4_WIDTH - self.x - self.canvas.PAGE_MARGIN - int(self.PADDING_X * 2))
        layout.set_width(max_w * Pango.SCALE)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        txt = self.text if display_text is None else display_text
        layout.set_text(txt, -1)
        return layout

    def update_layout(self):
        style_cfg = TEXT_STYLES[self.style_name]
        placeholder = f"[{style_cfg['label']}]"
        shown = self.text if self.text else placeholder
        layout = self._create_pango_layout(shown)
        _, logical = layout.get_pixel_extents()
        extra_h = 6 if style_cfg["underline_bar"] else 0
        w = int(math.ceil(max(logical.width, 40) + self.PADDING_X * 2 + 4))
        h = int(math.ceil(max(logical.height, 20) + self.PADDING_Y * 2 + extra_h))
        self.logical_w = w
        self.logical_h = h
        z = getattr(self.canvas, "zoom", 1.0)
        self.set_size_request(max(16, int(math.ceil(w * z))), max(16, int(math.ceil(h * z))))
        self.queue_draw()
        self.canvas.notify_toc_changed()

    def draw_content(self, cr, theme=None, for_export=False):
        if theme is None:
            theme = THEMES[self.canvas.theme_name]
        style_cfg = TEXT_STYLES[self.style_name]
        w, h = self.logical_w, self.logical_h

        if self.editing and not for_export:
            cr.save()
            cr.set_source_rgba(*theme["box_editing_bg"])
            cr.rectangle(0, 0, w, h)
            cr.fill()
            cr.restore()

        if self.text:
            layout = self._create_pango_layout(self.text)
            color = theme[style_cfg["color_key"]]
        else:
            if for_export:
                return
            layout = self._create_pango_layout(f"[{style_cfg['label']}]")
            color = theme["muted_text"]

        cr.save()
        cr.set_source_rgb(*color)
        cr.move_to(self.PADDING_X, self.PADDING_Y)
        PangoCairo.show_layout(cr, layout)
        cr.restore()

        # Optional bottom accent line for Title style
        if style_cfg["underline_bar"]:
            _, logical = layout.get_pixel_extents()
            bar_y = self.PADDING_Y + logical.height + 3.5
            cr.save()
            cr.set_source_rgb(*theme["heading_text"])
            cr.set_line_width(1.8)
            cr.move_to(self.PADDING_X, bar_y)
            cr.line_to(max(self.PADDING_X + logical.width, w - self.PADDING_X), bar_y)
            cr.stroke()
            cr.restore()

        if for_export:
            return

        # Draw caret when editing
        if self.editing:
            edit_layout = self._create_pango_layout(self.text)
            byte_idx = len(self.text[: self.cursor_pos].encode("utf-8"))
            strong_pos, _ = edit_layout.get_cursor_pos(byte_idx)
            cx = self.PADDING_X + strong_pos.x / Pango.SCALE
            cy = self.PADDING_Y + strong_pos.y / Pango.SCALE
            ch = max(14.0, strong_pos.height / Pango.SCALE)
            cr.save()
            cr.set_source_rgb(*theme["cursor"])
            cr.set_line_width(1.8)
            cr.move_to(cx, cy)
            cr.line_to(cx, cy + ch)
            cr.stroke()
            cr.restore()

        # Selection / Editing border
        if self.editing:
            cr.save()
            cr.set_source_rgb(*theme["box_editing_border"])
            cr.set_line_width(1.2)
            cr.rectangle(0.6, 0.6, w - 1.2, h - 1.2)
            cr.stroke()
            cr.restore()
        elif self.selected:
            cr.save()
            cr.set_source_rgb(*theme["box_selected_border"])
            cr.set_line_width(1.2)
            cr.set_dash([4.0, 3.0])
            cr.rectangle(0.6, 0.6, w - 1.2, h - 1.2)
            cr.stroke()
            cr.restore()

    def on_draw(self, widget, cr):
        z = getattr(self.canvas, "zoom", 1.0)
        cr.save()
        cr.scale(z, z)
        self.draw_content(cr, for_export=False)
        cr.restore()
        return True

    def _set_cursor_from_xy(self, mx: float, my: float):
        layout = self._create_pango_layout(self.text)
        lx = int((mx - self.PADDING_X) * Pango.SCALE)
        ly = int((my - self.PADDING_Y) * Pango.SCALE)
        inside, byte_index, trailing = layout.xy_to_index(lx, ly)
        char_idx = len(self.text.encode("utf-8")[:byte_index].decode("utf-8", errors="ignore"))
        self.cursor_pos = max(0, min(len(self.text), char_idx + (1 if trailing > 0 else 0)))

    def on_button_press(self, widget, event):
        if event.button == 1:
            z = getattr(self.canvas, "zoom", 1.0)
            lx, ly = event.x / z, event.y / z
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self.canvas.select_box(self)
                self.start_editing()
                self._set_cursor_from_xy(lx, ly)
                self.queue_draw()
                return True

            if self.editing:
                self._set_cursor_from_xy(lx, ly)
                self.canvas.focus_without_scroll(self)
                self.queue_draw()
                return True
            else:
                self.canvas.handle_box_button_press(self, event)
                self.dragging = True
                self.drag_start_root_x = event.x_root
                self.drag_start_root_y = event.y_root
                self.drag_start_box_x = self.x
                self.drag_start_box_y = self.y
                return True
        return False

    def on_motion_notify(self, widget, event):
        if self.dragging and not self.editing:
            z = getattr(self.canvas, "zoom", 1.0)
            dx = int((event.x_root - self.drag_start_root_x) / z)
            dy = int((event.y_root - self.drag_start_root_y) / z)
            self.canvas.drag_box_or_group(self, dx, dy)
            return True
        return False

    def on_button_release(self, widget, event):
        if event.button == 1 and self.dragging:
            self.dragging = False
            self.canvas.recalculate_worksheet()
            return True
        return False

    def on_focus_out(self, widget, event):
        self.stop_editing()
        return False

    def on_key_press(self, widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            return False
        keyname = Gdk.keyval_name(event.keyval)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)

        if not self.editing:
            if keyname in ("Delete", "BackSpace"):
                self.canvas.remove_selected_boxes(self)
                return True
            if keyname in ("Return", "KP_Enter"):
                self.start_editing()
                return True
            return False

        if keyname == "Escape":
            self.stop_editing()
            return True
        if keyname in ("Return", "KP_Enter"):
            if shift:
                self.text = self.text[: self.cursor_pos] + "\n" + self.text[self.cursor_pos :]
                self.cursor_pos += 1
                self.update_layout()
            else:
                self.canvas.exit_box_and_move_down(self)
            return True
        if keyname == "Left":
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
                self.queue_draw()
            return True
        if keyname == "Right":
            if self.cursor_pos < len(self.text):
                self.cursor_pos += 1
                self.queue_draw()
            return True
        if keyname == "Home":
            line_start = self.text.rfind("\n", 0, self.cursor_pos)
            self.cursor_pos = 0 if line_start == -1 else line_start + 1
            self.queue_draw()
            return True
        if keyname == "End":
            line_end = self.text.find("\n", self.cursor_pos)
            self.cursor_pos = len(self.text) if line_end == -1 else line_end
            self.queue_draw()
            return True
        if keyname == "BackSpace":
            if self.cursor_pos > 0:
                self.text = self.text[: self.cursor_pos - 1] + self.text[self.cursor_pos :]
                self.cursor_pos -= 1
                self.update_layout()
            return True
        if keyname == "Delete":
            if self.cursor_pos < len(self.text):
                self.text = self.text[: self.cursor_pos] + self.text[self.cursor_pos + 1 :]
                self.update_layout()
            return True

        ch = chr(Gdk.keyval_to_unicode(event.keyval)) if Gdk.keyval_to_unicode(event.keyval) else ""
        if ch and ch.isprintable():
            self.text = self.text[: self.cursor_pos] + ch + self.text[self.cursor_pos :]
            self.cursor_pos += 1
            self.update_layout()
            return True

        return False


# ============================================================================
# 2D Plot Box (Functions as Lines + Discrete Values as Symbols + Axis/Scale)
# ============================================================================


SERIES_COLORS = [
    (0.30, 0.72, 0.98),  # Blue
    (0.98, 0.55, 0.25),  # Orange
    (0.42, 0.88, 0.52),  # Green
    (0.92, 0.42, 0.78),  # Magenta
    (0.98, 0.85, 0.30),  # Yellow
]


# ============================================================================
# Figure Caption Helpers (shared by PlotBox and ImageBox)
# ============================================================================

CAPTION_BTN_LABEL = "✎ Caption"


def draw_figure_caption_button(fig, cr, theme, bx=6.0, by=6.0):
    """Draw the on-figure caption button (top-left). It is drawn inside the figure,
    so it always moves with it. Stores its hit rectangle in logical coordinates."""
    pango_ctx = fig.get_pango_context()
    label = CAPTION_BTN_LABEL if fig.title.strip() else "＋ Caption"
    lay, lw, la, ld = MathRenderer._make_layout(pango_ctx, label, 0.62, bold=True)
    bw, bh = lw + 12.0, la + ld + 6.0
    cr.save()
    cr.set_source_rgb(*theme["canvas_bg"])
    cr.rectangle(bx, by, bw, bh)
    cr.fill()
    cr.set_source_rgb(*theme["box_editing_border"])
    cr.set_line_width(1.2)
    cr.rectangle(bx, by, bw, bh)
    cr.stroke()
    cr.set_source_rgb(*theme["heading_text"])
    cr.move_to(bx + 6.0, by + 3.0)
    PangoCairo.show_layout(cr, lay)
    cr.restore()
    fig._caption_btn_rect = (bx, by, bw, bh)


def hit_figure_caption_button(fig, lx, ly) -> bool:
    rect = getattr(fig, "_caption_btn_rect", None)
    if not fig.selected or rect is None:
        return False
    bx, by, bw, bh = rect
    return bx <= lx <= bx + bw and by <= ly <= by + bh


def open_figure_caption_dialog(fig):
    """Small dialog to add / edit / remove a figure's caption."""
    toplevel = fig.get_toplevel()
    parent = toplevel if isinstance(toplevel, Gtk.Window) else None
    prefix = getattr(fig, "CAPTION_PREFIX", "Figure")
    where = getattr(fig, "CAPTION_WHERE", "beneath")
    dlg = Gtk.Dialog(title=f"{prefix} {fig.fig_num} Caption", transient_for=parent, flags=0)
    dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_APPLY, Gtk.ResponseType.OK)
    dlg.set_default_response(Gtk.ResponseType.OK)
    dlg.set_default_size(420, -1)

    box = dlg.get_content_area()
    box.set_spacing(6)
    for side in ("start", "end", "top", "bottom"):
        getattr(box, f"set_margin_{side}")(12)
    hint = Gtk.Label(
        label=f"Shown as “{prefix} {fig.fig_num}: …” {where} the {prefix.lower()}. Leave empty to remove."
    )
    hint.set_xalign(0.0)
    hint.set_line_wrap(True)
    entry = Gtk.Entry(text=fig.title)
    entry.set_activates_default(True)
    box.pack_start(hint, False, False, 0)
    box.pack_start(entry, False, False, 0)

    dlg.show_all()
    entry.grab_focus()
    if dlg.run() == Gtk.ResponseType.OK:
        fig.title = entry.get_text().strip()
        fig.update_layout()
        fig.canvas.recalculate_worksheet()
        fig.canvas.notify_toc_changed()
        fig.queue_draw()
    dlg.destroy()


class PlotBox(Gtk.DrawingArea):
    """
    2D Plot region on the A4 worksheet where:
    - Lines correspond to functions defined in the sheet (e.g. 'f; g' or 'f(x); g(x)')
    - Symbols correspond to vectors with discrete values defined in the sheet (e.g. 'vx, vy')
    - Configurable X and Y axis limits (x_min, x_max, y_min, y_max) and scale (Linear or Log10)
    """

    def __init__(
        self,
        canvas,
        x,
        y,
        width=460,
        height=275,
        title="Sine wave",
        func_expr="f; g",
        discrete_data="vx, vy",
        symbol_style="circle",
        connect_discrete=False,
        x_min=-6.0,
        x_max=6.0,
        y_min=-1.5,
        y_max=1.5,
        x_scale="linear",
        y_scale="linear",
        show_grid=True,
        show_legend=True,
    ):
        super().__init__()
        self.canvas = canvas
        self.x = int(x)
        self.y = int(y)
        self.plot_w = int(width)
        self.plot_h = int(height)
        self.logical_w = self.plot_w
        self.logical_h = self.plot_h

        self.fig_num = 1
        self.title = title
        self.func_expr = func_expr
        self.discrete_data = discrete_data
        self.symbol_style = symbol_style
        self.connect_discrete = connect_discrete

        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.y_min = float(y_min)
        self.y_max = float(y_max)
        self.x_scale = x_scale
        self.y_scale = y_scale
        self.show_grid = show_grid
        self.show_legend = show_legend

        self.editing = False
        self.selected = False
        self.dragging = False
        self.drag_start_root_x = 0
        self.drag_start_root_y = 0
        self.drag_start_box_x = 0
        self.drag_start_box_y = 0
        self.env = {}

        self.set_can_focus(True)
        self.update_layout()
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
            | Gdk.EventMask.SCROLL_MASK
        )

        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("key-press-event", self.on_key_press)
        self.connect("scroll-event", self.on_scroll)

    def _make_caption_layout(self, pango_ctx=None):
        if pango_ctx is None:
            pango_ctx = self.get_pango_context()
        caption_str = self.get_caption_text()
        t_layout, _, _, _ = MathRenderer._make_layout(pango_ctx, caption_str, 0.78, bold=True)
        wrap_w = max(80, int(self.plot_w - 20))
        t_layout.set_width(wrap_w * Pango.SCALE)
        t_layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        t_layout.set_alignment(Pango.Alignment.CENTER)
        _, logical = t_layout.get_pixel_extents()
        return t_layout, wrap_w, max(18, int(math.ceil(logical.height)))

    def update_layout(self):
        _, _, cap_h = self._make_caption_layout()
        extra_cap_h = max(0, cap_h - 20)
        self.logical_w = self.plot_w
        self.logical_h = self.plot_h + extra_cap_h
        z = getattr(self.canvas, "zoom", 1.0)
        self.set_size_request(
            max(60, int(math.ceil(self.logical_w * z))),
            max(40, int(math.ceil(self.logical_h * z))),
        )
        self.queue_draw()

    def is_empty(self):
        return False

    def set_selected(self, selected):
        self.selected = selected
        self.queue_draw()

    def start_editing(self):
        self.open_config_dialog()

    def stop_editing(self):
        self.editing = False
        self.queue_draw()

    def update_env(self, env: dict, fig_num: int = 1):
        self.env = env
        old_fig = getattr(self, "fig_num", None)
        self.fig_num = int(fig_num)
        if old_fig != self.fig_num:
            self.update_layout()
        else:
            self.queue_draw()

    def get_caption_text(self) -> str:
        raw = self.title.strip()
        if raw.lower().startswith("figure "):
            parts = raw.split(":", 1)
            if len(parts) == 2 and parts[0][7:].strip().isdigit():
                raw = parts[1].strip()
        return f"Figure {self.fig_num}: {raw}" if raw else f"Figure {self.fig_num}"

    def _transform_x(self, val: float):
        if self.x_scale == "log":
            if val <= 0:
                return None
            return math.log10(val)
        return val

    def _transform_y(self, val: float):
        if self.y_scale == "log":
            if val <= 0:
                return None
            return math.log10(val)
        return val

    def _resolve_sheet_functions(self):
        resolved = []
        entries = [e.strip() for e in self.func_expr.replace(",", ";").split(";") if e.strip()]
        for entry in entries:
            fn_name = entry.split("(", 1)[0].strip() if "(" in entry else entry
            fn_obj = self.env.get(fn_name)
            if callable(fn_obj):
                resolved.append((f"{fn_name}(x)", fn_obj))
                continue
            rhs = entry.split(":=", 1)[1].strip() if ":=" in entry else (
                entry.split("=", 1)[1].strip() if "=" in entry else entry
            )
            py_rhs = rhs.replace("^", "**").replace("·", "*")
            try:
                inline_fn = eval(f"lambda x: ({py_rhs})", self.env)
                resolved.append((entry, inline_fn))
            except Exception:
                pass
        return resolved

    def _resolve_sheet_vector_series(self):
        series_list = []
        raw = self.discrete_data.strip()
        if not raw:
            return series_list

        chunks = [c.strip() for c in raw.replace("\n", ";").split(";") if c.strip()]
        if len(chunks) == 2 and "," not in chunks[0] and "," not in chunks[1]:
            v0 = self.env.get(chunks[0])
            v1 = self.env.get(chunks[1])
            if isinstance(v0, (list, tuple)) and isinstance(v1, (list, tuple)):
                pts = [(float(px), float(py)) for px, py in zip(v0, v1)]
                return [(f"({chunks[0]}, {chunks[1]})", pts)]

        for chunk in chunks:
            cleaned = chunk.strip().lstrip("(").rstrip(")")
            if "," in cleaned:
                x_name, y_name = [p.strip() for p in cleaned.split(",", 1)]
                xs = self.env.get(x_name)
                ys = self.env.get(y_name)
                if isinstance(xs, (list, tuple)) and isinstance(ys, (list, tuple)):
                    try:
                        pts = [(float(px), float(py)) for px, py in zip(xs, ys)]
                        series_list.append((f"({x_name}, {y_name})", pts))
                    except Exception:
                        pass
            else:
                v_name = cleaned.strip()
                ys = self.env.get(v_name)
                if isinstance(ys, (list, tuple)):
                    try:
                        pts = [(float(i + 1), float(py)) for i, py in enumerate(ys)]
                        series_list.append((v_name, pts))
                    except Exception:
                        pass
        return series_list

    def _draw_symbol(self, cr, sx: float, sy: float, r: float = 4.2):
        style = self.symbol_style
        if style == "circle":
            cr.arc(sx, sy, r, 0, 2 * math.pi)
            cr.fill()
        elif style == "square":
            cr.rectangle(sx - r, sy - r, r * 2, r * 2)
            cr.fill()
        elif style == "diamond":
            cr.move_to(sx, sy - r * 1.25)
            cr.line_to(sx + r * 1.25, sy)
            cr.line_to(sx, sy + r * 1.25)
            cr.line_to(sx - r * 1.25, sy)
            cr.close_path()
            cr.fill()
        elif style == "triangle":
            cr.move_to(sx, sy - r * 1.25)
            cr.line_to(sx + r * 1.2, sy + r)
            cr.line_to(sx - r * 1.2, sy + r)
            cr.close_path()
            cr.fill()
        elif style == "cross":
            cr.set_line_width(2.0)
            cr.move_to(sx - r, sy - r)
            cr.line_to(sx + r, sy + r)
            cr.move_to(sx - r, sy + r)
            cr.line_to(sx + r, sy - r)
            cr.stroke()
        elif style == "plus":
            cr.set_line_width(2.0)
            cr.move_to(sx - r * 1.1, sy)
            cr.line_to(sx + r * 1.1, sy)
            cr.move_to(sx, sy - r * 1.1)
            cr.line_to(sx, sy + r * 1.1)
            cr.stroke()

    def draw_content(self, cr, theme=None, for_export=False):
        if theme is None:
            theme = THEMES[self.canvas.theme_name]
        pango_ctx = self.get_pango_context()
        t_layout, wrap_w, cap_h = self._make_caption_layout(pango_ctx)
        extra_cap_h = max(0, cap_h - 20)
        w = self.plot_w
        h = self.plot_h + extra_cap_h

        # Plot frame background
        if not for_export:
            cr.save()
            cr.set_source_rgba(*theme["box_editing_bg"])
            cr.rectangle(0, 0, w, h)
            cr.fill()
            cr.restore()

        pad_left = 52.0
        pad_right = 18.0
        pad_top = 24.0
        pad_bot = 54.0
        pw = max(60.0, w - pad_left - pad_right)
        ph = max(50.0, self.plot_h - pad_top - pad_bot)

        if not for_export:
            cfg_layout, cfg_w, _, _ = MathRenderer._make_layout(pango_ctx, "[⚙ Axis/Scale]", 0.62)
            cr.save()
            cr.set_source_rgb(*theme["muted_text"])
            cr.move_to(w - cfg_w - 8, 5)
            PangoCairo.show_layout(cr, cfg_layout)
            cr.restore()

        cr.save()
        cr.set_source_rgb(*theme["heading_text"])
        caption_x = (w - wrap_w) / 2.0
        caption_y = pad_top + ph + 26.0
        cr.move_to(caption_x, caption_y)
        PangoCairo.show_layout(cr, t_layout)
        cr.restore()

        if not for_export and self.selected:
            draw_figure_caption_button(self, cr, theme, bx=pad_left, by=2.0)

        tx_min = math.log10(max(1e-12, self.x_min)) if self.x_scale == "log" else self.x_min
        tx_max = math.log10(max(1e-11, self.x_max)) if self.x_scale == "log" else self.x_max
        ty_min = math.log10(max(1e-12, self.y_min)) if self.y_scale == "log" else self.y_min
        ty_max = math.log10(max(1e-11, self.y_max)) if self.y_scale == "log" else self.y_max
        if tx_max <= tx_min:
            tx_max = tx_min + 1.0
        if ty_max <= ty_min:
            ty_max = ty_min + 1.0

        def to_screen_x(tx):
            return pad_left + (tx - tx_min) / (tx_max - tx_min) * pw

        def to_screen_y(ty):
            return pad_top + ph - (ty - ty_min) / (ty_max - ty_min) * ph

        cr.save()
        cr.set_source_rgb(*theme["canvas_bg"])
        cr.rectangle(pad_left, pad_top, pw, ph)
        cr.fill()
        cr.restore()

        num_ticks = 5
        for i in range(num_ticks + 1):
            frac = i / num_ticks
            gx = pad_left + frac * pw
            gy = pad_top + (1.0 - frac) * ph
            tx_val = tx_min + frac * (tx_max - tx_min)
            ty_val = ty_min + frac * (ty_max - ty_min)

            if self.show_grid:
                cr.save()
                cr.set_source_rgb(*theme["grid_major"])
                cr.set_line_width(0.8)
                cr.set_dash([2.0, 2.0])
                cr.move_to(gx, pad_top)
                cr.line_to(gx, pad_top + ph)
                cr.move_to(pad_left, gy)
                cr.line_to(pad_left + pw, gy)
                cr.stroke()
                cr.restore()

            x_disp = (10.0 ** tx_val) if self.x_scale == "log" else tx_val
            y_disp = (10.0 ** ty_val) if self.y_scale == "log" else ty_val
            xlbl, xlw, _, _ = MathRenderer._make_layout(pango_ctx, f"{x_disp:.3g}", 0.58)
            ylbl, ylw, yla, _ = MathRenderer._make_layout(pango_ctx, f"{y_disp:.3g}", 0.58)
            cr.save()
            cr.set_source_rgb(*theme["muted_text"])
            cr.move_to(gx - xlw / 2.0, pad_top + ph + 4)
            PangoCairo.show_layout(cr, xlbl)
            cr.move_to(max(2.0, pad_left - ylw - 5), gy - yla / 2.0)
            PangoCairo.show_layout(cr, ylbl)
            cr.restore()

        cr.save()
        cr.set_source_rgb(*theme["page_border"])
        cr.set_line_width(1.1)
        if self.x_scale == "linear" and tx_min <= 0 <= tx_max:
            zx = to_screen_x(0.0)
            cr.move_to(zx, pad_top)
            cr.line_to(zx, pad_top + ph)
        if self.y_scale == "linear" and ty_min <= 0 <= ty_max:
            zy = to_screen_y(0.0)
            cr.move_to(pad_left, zy)
            cr.line_to(pad_left + pw, zy)
        cr.stroke()
        cr.restore()

        cr.save()
        cr.rectangle(pad_left, pad_top, pw, ph)
        cr.clip()

        legend_items = []
        sheet_funcs = self._resolve_sheet_functions()
        samples = 220
        for f_idx, (fn_label, fn_callable) in enumerate(sheet_funcs):
            color = SERIES_COLORS[f_idx % len(SERIES_COLORS)]
            legend_items.append((fn_label, color, "line"))
            cr.save()
            cr.set_source_rgb(*color)
            cr.set_line_width(2.0)
            pen_down = False
            for s in range(samples + 1):
                tx = tx_min + (s / samples) * (tx_max - tx_min)
                x_val = (10.0 ** tx) if self.x_scale == "log" else tx
                try:
                    y_val = float(fn_callable(x_val))
                    if math.isnan(y_val) or math.isinf(y_val):
                        pen_down = False
                        continue
                    ty = self._transform_y(y_val)
                    if ty is None:
                        pen_down = False
                        continue
                    sx = to_screen_x(tx)
                    sy = to_screen_y(ty)
                    if not (-2000 <= sy <= 4000):
                        pen_down = False
                        continue
                    if not pen_down:
                        cr.move_to(sx, sy)
                        pen_down = True
                    else:
                        cr.line_to(sx, sy)
                except Exception:
                    pen_down = False
            cr.stroke()
            cr.restore()

        vec_series = self._resolve_sheet_vector_series()
        for v_idx, (vec_label, pts) in enumerate(vec_series):
            sym_color = SERIES_COLORS[(len(sheet_funcs) + v_idx) % len(SERIES_COLORS)]
            legend_items.append((vec_label, sym_color, "symbol"))
            screen_pts = []
            for px, py in pts:
                tx = self._transform_x(px)
                ty = self._transform_y(py)
                if tx is not None and ty is not None:
                    screen_pts.append((to_screen_x(tx), to_screen_y(ty)))

            if self.connect_discrete and len(screen_pts) >= 2:
                cr.save()
                cr.set_source_rgb(*sym_color)
                cr.set_line_width(1.2)
                cr.set_dash([4.0, 3.0])
                cr.move_to(screen_pts[0][0], screen_pts[0][1])
                for sx, sy in screen_pts[1:]:
                    cr.line_to(sx, sy)
                cr.stroke()
                cr.restore()

            cr.save()
            cr.set_source_rgb(*sym_color)
            for sx, sy in screen_pts:
                self._draw_symbol(cr, sx, sy, r=4.2)
            cr.restore()

        cr.restore()  # End clip

        cr.save()
        cr.set_source_rgb(*theme["page_border"])
        cr.set_line_width(1.2)
        cr.rectangle(pad_left, pad_top, pw, ph)
        cr.stroke()
        cr.restore()

        if self.show_legend and legend_items:
            lx = pad_left + 8
            ly = pad_top + 6
            for label_txt, col, kind in legend_items:
                lbl_lay, lw, la, ld = MathRenderer._make_layout(pango_ctx, label_txt, 0.58)
                cr.save()
                cr.set_source_rgb(*col)
                if kind == "line":
                    cr.set_line_width(2.2)
                    cr.move_to(lx, ly + la * 0.6)
                    cr.line_to(lx + 14, ly + la * 0.6)
                    cr.stroke()
                else:
                    self._draw_symbol(cr, lx + 7, ly + la * 0.6, r=3.5)
                cr.set_source_rgb(*theme["text"])
                cr.move_to(lx + 18, ly)
                PangoCairo.show_layout(cr, lbl_lay)
                cr.restore()
                ly += la + ld + 2

        if self.selected and not for_export:
            cr.save()
            cr.set_source_rgb(*theme["box_selected_border"])
            cr.set_line_width(1.4)
            cr.set_dash([4.0, 3.0])
            cr.rectangle(0.7, 0.7, w - 1.4, h - 1.4)
            cr.stroke()
            cr.restore()

    def on_draw(self, widget, cr):
        z = getattr(self.canvas, "zoom", 1.0)
        cr.save()
        cr.scale(z, z)
        self.draw_content(cr, for_export=False)
        cr.restore()
        return True

    def on_button_press(self, widget, event):
        if event.button == 1:
            z = getattr(self.canvas, "zoom", 1.0)
            lx, ly = event.x / z, event.y / z
            was_selected = self.selected
            self.canvas.handle_box_button_press(self, event)
            self.canvas.focus_without_scroll(self)
            if was_selected and hit_figure_caption_button(self, lx, ly):
                self.dragging = False
                GLib.idle_add(lambda: open_figure_caption_dialog(self) and False)
                return True
            if event.type == Gdk.EventType._2BUTTON_PRESS or (lx >= self.plot_w - 95 and ly <= 26):
                self.dragging = False
                GLib.idle_add(self._open_config_dialog_idle)
                return True
            self.dragging = True
            self.drag_start_root_x = event.x_root
            self.drag_start_root_y = event.y_root
            self.drag_start_box_x = self.x
            self.drag_start_box_y = self.y
            return True
        return False

    def _open_config_dialog_idle(self):
        self.dragging = False
        self.open_config_dialog()
        return False

    def on_motion_notify(self, widget, event):
        if self.dragging:
            if not (event.state & Gdk.ModifierType.BUTTON1_MASK):
                self.dragging = False
                return False
            z = getattr(self.canvas, "zoom", 1.0)
            dx = int((event.x_root - self.drag_start_root_x) / z)
            dy = int((event.y_root - self.drag_start_root_y) / z)
            self.canvas.drag_box_or_group(self, dx, dy)
            return True
        return False

    def on_button_release(self, widget, event):
        if event.button == 1 and self.dragging:
            self.dragging = False
            self.canvas.recalculate_worksheet()
            return True
        return False

    def on_key_press(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname in ("Delete", "BackSpace"):
            self.canvas.remove_selected_boxes(self)
            return True
        if keyname in ("Return", "KP_Enter"):
            self.open_config_dialog()
            return True
        return False

    def on_scroll(self, widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            return self.canvas.on_scroll_zoom(widget, event)
        return False

    def open_config_dialog(self):
        self.dragging = False
        toplevel = self.get_toplevel()
        parent = toplevel if isinstance(toplevel, Gtk.Window) else None
        dlg = Gtk.Dialog(
            title="Plot Options - Sheet Functions (Lines), Sheet Vectors (Symbols), Limits & Scale",
            transient_for=parent,
            flags=0,
        )
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_APPLY, Gtk.ResponseType.OK)
        dlg.set_default_size(540, 440)

        content = dlg.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        grid.set_margin_start(14)
        grid.set_margin_end(14)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        content.add(grid)

        row = 0

        def add_row(label_text, widget_item):
            nonlocal row
            lbl = Gtk.Label(label=label_text)
            lbl.set_xalign(0.0)
            grid.attach(lbl, 0, row, 1, 1)
            widget_item.set_hexpand(True)
            grid.attach(widget_item, 1, row, 3, 1)
            row += 1

        title_entry = Gtk.Entry(text=self.title)
        add_row(f"Figure {self.fig_num} Title:", title_entry)

        avail_funcs = self.env.get("_sheet_functions", [])
        avail_vecs = self.env.get("_sheet_vectors", [])

        func_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        func_entry = Gtk.Entry(text=self.func_expr)
        func_entry.set_tooltip_text("Function name(s) defined in the sheet separated by ';', e.g. f; g")
        func_vbox.pack_start(func_entry, False, False, 0)
        fn_hint = Gtk.Label()
        fn_list_str = ", ".join(f"{fn}(x)" for fn in avail_funcs) if avail_funcs else "none defined above plot yet"
        fn_hint.set_markup(f"<small>Sheet functions available: <b>{GLib_markup_escape(fn_list_str)}</b></small>")
        fn_hint.set_xalign(0.0)
        func_vbox.pack_start(fn_hint, False, False, 0)
        add_row("Sheet Functions [Lines]:", func_vbox)

        disc_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        disc_entry = Gtk.Entry(text=self.discrete_data)
        disc_entry.set_tooltip_text("Vector pair(s) defined in the sheet, e.g. vx, vy")
        disc_vbox.pack_start(disc_entry, False, False, 0)
        vec_hint = Gtk.Label()
        vec_list_str = (
            ", ".join(f"{vn} ({len(self.env.get(vn, []))} pts)" for vn in avail_vecs)
            if avail_vecs
            else "none defined above plot yet (define e.g. vx := [1, 2, 3])"
        )
        vec_hint.set_markup(f"<small>Sheet vectors available: <b>{GLib_markup_escape(vec_list_str)}</b></small>")
        vec_hint.set_xalign(0.0)
        disc_vbox.pack_start(vec_hint, False, False, 0)
        add_row("Sheet Vectors [Symbols]:", disc_vbox)

        sym_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sym_combo = Gtk.ComboBoxText()
        for sid, sname in [
            ("circle", "Circle (●)"),
            ("square", "Square (■)"),
            ("diamond", "Diamond (◆)"),
            ("triangle", "Triangle (▲)"),
            ("cross", "Cross (✕)"),
            ("plus", "Plus (+)"),
        ]:
            sym_combo.append(sid, sname)
        sym_combo.set_active_id(self.symbol_style)
        conn_chk = Gtk.CheckButton(label="Connect discrete points with dashed line")
        conn_chk.set_active(self.connect_discrete)
        sym_box.pack_start(sym_combo, False, False, 0)
        sym_box.pack_start(conn_chk, False, False, 0)
        add_row("Symbol Style:", sym_box)

        x_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        xmin_entry = Gtk.Entry(text=str(self.x_min))
        xmin_entry.set_width_chars(8)
        xmax_entry = Gtk.Entry(text=str(self.x_max))
        xmax_entry.set_width_chars(8)
        xscale_combo = Gtk.ComboBoxText()
        xscale_combo.append("linear", "Linear Scale")
        xscale_combo.append("log", "Log10 Scale")
        xscale_combo.set_active_id(self.x_scale)
        x_box.pack_start(Gtk.Label(label="Min:"), False, False, 0)
        x_box.pack_start(xmin_entry, False, False, 0)
        x_box.pack_start(Gtk.Label(label="Max:"), False, False, 0)
        x_box.pack_start(xmax_entry, False, False, 0)
        x_box.pack_start(Gtk.Label(label="Scale:"), False, False, 0)
        x_box.pack_start(xscale_combo, False, False, 0)
        add_row("X-Axis Limits & Scale:", x_box)

        y_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ymin_entry = Gtk.Entry(text=str(self.y_min))
        ymin_entry.set_width_chars(8)
        ymax_entry = Gtk.Entry(text=str(self.y_max))
        ymax_entry.set_width_chars(8)
        yscale_combo = Gtk.ComboBoxText()
        yscale_combo.append("linear", "Linear Scale")
        yscale_combo.append("log", "Log10 Scale")
        yscale_combo.set_active_id(self.y_scale)
        y_box.pack_start(Gtk.Label(label="Min:"), False, False, 0)
        y_box.pack_start(ymin_entry, False, False, 0)
        y_box.pack_start(Gtk.Label(label="Max:"), False, False, 0)
        y_box.pack_start(ymax_entry, False, False, 0)
        y_box.pack_start(Gtk.Label(label="Scale:"), False, False, 0)
        y_box.pack_start(yscale_combo, False, False, 0)
        add_row("Y-Axis Limits & Scale:", y_box)

        opt_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        w_entry = Gtk.Entry(text=str(self.plot_w))
        w_entry.set_width_chars(6)
        h_entry = Gtk.Entry(text=str(self.plot_h))
        h_entry.set_width_chars(6)
        grid_chk = Gtk.CheckButton(label="Grid")
        grid_chk.set_active(self.show_grid)
        leg_chk = Gtk.CheckButton(label="Legend")
        leg_chk.set_active(self.show_legend)
        opt_box.pack_start(Gtk.Label(label="W×H:"), False, False, 0)
        opt_box.pack_start(w_entry, False, False, 0)
        opt_box.pack_start(h_entry, False, False, 0)
        opt_box.pack_start(grid_chk, False, False, 0)
        opt_box.pack_start(leg_chk, False, False, 0)
        add_row("Size & Display:", opt_box)

        dlg.show_all()
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            self.title = title_entry.get_text().strip()
            self.func_expr = func_entry.get_text().strip()
            self.discrete_data = disc_entry.get_text().strip()
            self.symbol_style = sym_combo.get_active_id() or "circle"
            self.connect_discrete = conn_chk.get_active()
            self.x_scale = xscale_combo.get_active_id() or "linear"
            self.y_scale = yscale_combo.get_active_id() or "linear"
            try:
                self.x_min = float(eval(xmin_entry.get_text(), self.env))
                self.x_max = float(eval(xmax_entry.get_text(), self.env))
                self.y_min = float(eval(ymin_entry.get_text(), self.env))
                self.y_max = float(eval(ymax_entry.get_text(), self.env))
            except Exception:
                pass
            if self.x_scale == "log" and self.x_min <= 0:
                self.x_min = 0.1
                self.x_max = max(self.x_max, 10.0)
            if self.y_scale == "log" and self.y_min <= 0:
                self.y_min = 0.1
                self.y_max = max(self.y_max, 10.0)
            try:
                self.plot_w = max(220, min(self.canvas.A4_WIDTH - 40, int(w_entry.get_text())))
                self.plot_h = max(150, min(600, int(h_entry.get_text())))
            except ValueError:
                pass
            self.show_grid = grid_chk.get_active()
            self.show_legend = leg_chk.get_active()
            self.update_layout()
            centered_x = max(0, (self.canvas.A4_WIDTH - self.plot_w) // 2)
            self.canvas.move_box(self, centered_x, self.y)
            self.canvas.notify_toc_changed()
            self.queue_draw()
        self.dragging = False
        dlg.destroy()


# ============================================================================
# Pasted / Inserted Picture Box (ImageBox) with Interactive Drag-Resize Handles
# ============================================================================

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf


class ImageBox(Gtk.DrawingArea):
    """
    Picture / Image box on the A4 worksheet.
    - Supports pasting directly from clipboard (Ctrl+V) or inserting from file.
    - Interactive drag-resize handles on the bottom-right corner, right edge, and bottom edge.
    - Scroll wheel scales the picture proportionally; double-click configures caption & size.
    """

    CAPTION_HEIGHT = 28
    HANDLE_SIZE = 10

    def __init__(self, canvas, x, y, pixbuf: GdkPixbuf.Pixbuf, title="", width=None, height=None):
        super().__init__()
        self.canvas = canvas
        self.orig_pixbuf = pixbuf
        orig_w = max(1, pixbuf.get_width())
        orig_h = max(1, pixbuf.get_height())
        self.aspect = orig_w / float(orig_h)

        if width is not None and height is not None:
            self.img_w = max(32, int(width))
            self.img_h = max(24, int(height))
        else:
            max_init_w = min(480, self.canvas.A4_WIDTH - 80)
            if orig_w > max_init_w:
                self.img_w = int(max_init_w)
                self.img_h = max(32, int(round(self.img_w / self.aspect)))
            else:
                self.img_w = int(orig_w)
                self.img_h = int(orig_h)

        self.title = title
        self.fig_num = 1
        self.editing = False
        self.selected = False
        self.dragging = False
        self.resizing_mode = None  # None, "corner", "right", "bottom"
        self.drag_start_root_x = 0
        self.drag_start_root_y = 0
        self.drag_start_box_x = 0
        self.drag_start_box_y = 0
        self.resize_start_w = self.img_w
        self.resize_start_h = self.img_h

        self.x = int(x)
        self.y = int(y)
        self.box_w = self.img_w + 8
        self.box_h = self.img_h + 8
        self.logical_w = self.box_w
        self.logical_h = self.box_h
        self._scaled_cache = None
        self.update_layout()

        self.set_can_focus(True)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
            | Gdk.EventMask.SCROLL_MASK
        )
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("leave-notify-event", self.on_leave_notify)
        self.connect("key-press-event", self.on_key_press)
        self.connect("scroll-event", self.on_scroll)

    def get_caption_text(self) -> str:
        raw = self.title.strip()
        if not raw:
            return ""
        if raw.lower().startswith("figure "):
            parts = raw.split(":", 1)
            if len(parts) == 2 and parts[0][7:].strip().isdigit():
                raw = parts[1].strip()
        return f"Figure {self.fig_num}: {raw}" if raw else f"Figure {self.fig_num}"

    def _make_caption_layout(self, pango_ctx=None):
        caption_str = self.get_caption_text()
        if not caption_str:
            return None, 0, 0
        if pango_ctx is None:
            pango_ctx = self.get_pango_context()
        t_layout, _, _, _ = MathRenderer._make_layout(pango_ctx, caption_str, 0.76, bold=True)
        wrap_w = max(48, int(self.img_w))
        t_layout.set_width(wrap_w * Pango.SCALE)
        t_layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        t_layout.set_alignment(Pango.Alignment.CENTER)
        _, logical = t_layout.get_pixel_extents()
        return t_layout, wrap_w, max(20, int(math.ceil(logical.height)) + 8)

    def update_layout(self):
        _, _, extra_h = self._make_caption_layout()
        self.box_w = self.img_w + 8
        self.box_h = self.img_h + 8 + extra_h
        self.logical_w = self.box_w
        self.logical_h = self.box_h
        self._scaled_cache = self.orig_pixbuf.scale_simple(
            max(1, self.img_w), max(1, self.img_h), GdkPixbuf.InterpType.BILINEAR
        )
        z = getattr(self.canvas, "zoom", 1.0)
        self.set_size_request(
            max(24, int(math.ceil(self.box_w * z))),
            max(24, int(math.ceil(self.box_h * z))),
        )
        self.queue_draw()

    def _update_size_request(self):
        self.update_layout()

    def is_empty(self):
        return False

    def set_selected(self, selected):
        self.selected = selected
        self.queue_draw()

    def start_editing(self):
        self.open_config_dialog()

    def stop_editing(self):
        self.editing = False
        self.queue_draw()

    def _hit_resize_handle(self, lx: float, ly: float):
        """Detect if logical coordinates (lx, ly) are over corner, right, or bottom resize grips."""
        w = self.box_w
        img_bot = self.img_h + 8
        g = 14.0
        if lx >= w - g and (img_bot - g <= ly <= self.box_h):
            return "corner"
        if lx >= w - g and 0 <= ly <= img_bot:
            return "right"
        if (img_bot - g <= ly <= self.box_h) and 0 <= lx <= w:
            return "bottom"
        return None

    def _set_cursor_by_name(self, name):
        win = self.get_window()
        if win is None:
            return
        if name is None:
            win.set_cursor(None)
            return
        display = win.get_display()
        try:
            cursor = Gdk.Cursor.new_from_name(display, name)
            win.set_cursor(cursor)
        except Exception:
            win.set_cursor(None)

    def draw_content(self, cr, theme=None, for_export=False):
        if theme is None:
            theme = THEMES[self.canvas.theme_name]
        w, h = self.box_w, self.box_h

        if self._scaled_cache is not None:
            cr.save()
            Gdk.cairo_set_source_pixbuf(cr, self._scaled_cache, 4, 4)
            cr.paint()
            cr.restore()

        if self.title.strip():
            pango_ctx = self.get_pango_context()
            t_layout, wrap_w, _ = self._make_caption_layout(pango_ctx)
            if t_layout is not None:
                cr.save()
                cr.set_source_rgb(*theme["heading_text"])
                cr.move_to((w - wrap_w) / 2.0, self.img_h + 8)
                PangoCairo.show_layout(cr, t_layout)
                cr.restore()

        if for_export:
            return

        if self.selected or self.resizing_mode is not None:
            cr.save()
            cr.set_source_rgb(*theme["box_selected_border"])
            cr.set_line_width(1.4)
            cr.set_dash([4.0, 3.0])
            cr.rectangle(0.7, 0.7, w - 1.4, h - 1.4)
            cr.stroke()
            cr.restore()

            # Draw interactive resize handles (bottom-right corner, right midpoint, bottom midpoint)
            hs = 8.0
            img_bot = self.img_h + 4
            handles = [
                (w - hs - 1, img_bot - hs / 2.0),  # bottom-right corner
                (w - hs - 1, max(4.0, (img_bot - hs) / 2.0)),  # right edge
                (max(4.0, (w - hs) / 2.0), img_bot - hs / 2.0),  # bottom edge
            ]
            cr.save()
            for hx, hy in handles:
                cr.set_source_rgb(*theme["canvas_bg"])
                cr.rectangle(hx, hy, hs, hs)
                cr.fill()
                cr.set_source_rgb(*theme["box_editing_border"])
                cr.set_line_width(1.4)
                cr.rectangle(hx, hy, hs, hs)
                cr.stroke()
            cr.restore()

            if self.resizing_mode is None:
                draw_figure_caption_button(self, cr, theme)

            # Live dimension badge while resizing
            if self.resizing_mode is not None:
                pango_ctx = self.get_pango_context()
                dim_lay, dw, da, dd = MathRenderer._make_layout(
                    pango_ctx, f"{self.img_w} × {self.img_h} px", 0.62, bold=True
                )
                cr.save()
                cr.set_source_rgba(0.1, 0.12, 0.16, 0.82)
                cr.rectangle(6, 6, dw + 10, da + dd + 6)
                cr.fill()
                cr.set_source_rgb(0.95, 0.97, 1.0)
                cr.move_to(11, 9)
                PangoCairo.show_layout(cr, dim_lay)
                cr.restore()

    def on_draw(self, widget, cr):
        z = getattr(self.canvas, "zoom", 1.0)
        cr.save()
        cr.scale(z, z)
        self.draw_content(cr, for_export=False)
        cr.restore()
        return True

    def on_button_press(self, widget, event):
        if event.button == 1:
            z = getattr(self.canvas, "zoom", 1.0)
            lx, ly = event.x / z, event.y / z
            was_selected = self.selected
            self.canvas.handle_box_button_press(self, event)
            self.canvas.focus_without_scroll(self)
            if was_selected and hit_figure_caption_button(self, lx, ly):
                self.dragging = False
                self.resizing_mode = None
                GLib.idle_add(lambda: open_figure_caption_dialog(self) and False)
                return True
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self.dragging = False
                self.resizing_mode = None
                GLib.idle_add(self._open_config_dialog_idle)
                return True

            handle = self._hit_resize_handle(lx, ly)
            if handle is not None:
                self.resizing_mode = handle
                self.drag_start_root_x = event.x_root
                self.drag_start_root_y = event.y_root
                self.resize_start_w = self.img_w
                self.resize_start_h = self.img_h
                self.queue_draw()
                return True

            self.dragging = True
            self.drag_start_root_x = event.x_root
            self.drag_start_root_y = event.y_root
            self.drag_start_box_x = self.x
            self.drag_start_box_y = self.y
            return True
        return False

    def _open_config_dialog_idle(self):
        self.dragging = False
        self.resizing_mode = None
        self.open_config_dialog()
        return False

    def on_motion_notify(self, widget, event):
        z = getattr(self.canvas, "zoom", 1.0)
        lx, ly = event.x / z, event.y / z

        if self.resizing_mode is not None:
            if not (event.state & Gdk.ModifierType.BUTTON1_MASK):
                self.resizing_mode = None
                return False
            dx = (event.x_root - self.drag_start_root_x) / z
            dy = (event.y_root - self.drag_start_root_y) / z
            free_aspect = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
            max_w = max(80, self.canvas.A4_WIDTH - self.x - 16)
            max_h = max(60, self.canvas.total_height - self.y - 36)

            if self.resizing_mode == "corner":
                new_w = max(36, min(max_w, int(round(self.resize_start_w + dx))))
                if free_aspect:
                    new_h = max(24, min(max_h, int(round(self.resize_start_h + dy))))
                else:
                    new_h = max(24, min(max_h, int(round(new_w / self.aspect))))
                    new_w = max(36, min(max_w, int(round(new_h * self.aspect))))
                self.img_w, self.img_h = new_w, new_h
            elif self.resizing_mode == "right":
                new_w = max(36, min(max_w, int(round(self.resize_start_w + dx))))
                self.img_w = new_w
                if not free_aspect:
                    self.img_h = max(24, min(max_h, int(round(new_w / self.aspect))))
            elif self.resizing_mode == "bottom":
                new_h = max(24, min(max_h, int(round(self.resize_start_h + dy))))
                self.img_h = new_h
                if not free_aspect:
                    self.img_w = max(36, min(max_w, int(round(new_h * self.aspect))))

            self.update_layout()
            return True

        if self.dragging:
            if not (event.state & Gdk.ModifierType.BUTTON1_MASK):
                self.dragging = False
                return False
            dx = int((event.x_root - self.drag_start_root_x) / z)
            dy = int((event.y_root - self.drag_start_root_y) / z)
            self.canvas.drag_box_or_group(self, dx, dy)
            return True

        # Update hover cursor over resize handles
        handle = self._hit_resize_handle(lx, ly)
        if handle == "corner":
            self._set_cursor_by_name("nwse-resize")
        elif handle == "right":
            self._set_cursor_by_name("ew-resize")
        elif handle == "bottom":
            self._set_cursor_by_name("ns-resize")
        else:
            self._set_cursor_by_name(None)
        return False

    def on_leave_notify(self, widget, event):
        if self.resizing_mode is None:
            self._set_cursor_by_name(None)
        return False

    def on_button_release(self, widget, event):
        if event.button == 1:
            if self.resizing_mode is not None:
                self.resizing_mode = None
                self.aspect = max(1, self.img_w) / float(max(1, self.img_h))
                self.queue_draw()
                return True
            if self.dragging:
                self.dragging = False
                self.canvas.recalculate_worksheet()
                return True
        return False

    def on_key_press(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname in ("Delete", "BackSpace"):
            self.canvas.remove_selected_boxes(self)
            return True
        if keyname in ("Return", "KP_Enter"):
            self.open_config_dialog()
            return True
        return False

    def on_scroll(self, widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            return self.canvas.on_scroll_zoom(widget, event)
        factor = 1.10 if event.direction == Gdk.ScrollDirection.UP else (
            0.90 if event.direction == Gdk.ScrollDirection.DOWN else 1.0
        )
        if factor != 1.0:
            new_w = max(36, min(self.canvas.A4_WIDTH - 40, int(round(self.img_w * factor))))
            self.img_w = new_w
            self.img_h = max(24, int(round(self.img_w / self.aspect)))
            self.update_layout()
            return True
        return False

    def open_config_dialog(self):
        toplevel = self.get_toplevel()
        parent = toplevel if isinstance(toplevel, Gtk.Window) else None
        dlg = Gtk.Dialog(title="Picture Options & Size", transient_for=parent, flags=0)
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_APPLY, Gtk.ResponseType.OK)

        content = dlg.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        grid.set_margin_start(14)
        grid.set_margin_end(14)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        content.add(grid)

        title_entry = Gtk.Entry(text=self.title)
        w_entry = Gtk.Entry(text=str(self.img_w))
        h_entry = Gtk.Entry(text=str(self.img_h))
        lock_chk = Gtk.CheckButton(label="Preserve aspect ratio")
        lock_chk.set_active(True)
        center_chk = Gtk.CheckButton(label="Center horizontally on A4 page")
        center_chk.set_active(abs(self.x - (self.canvas.A4_WIDTH - self.box_w) // 2) <= 10)

        grid.attach(Gtk.Label(label="Caption (optional):"), 0, 0, 1, 1)
        grid.attach(title_entry, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label="Width (px):"), 0, 1, 1, 1)
        grid.attach(w_entry, 1, 1, 1, 1)
        grid.attach(Gtk.Label(label="Height (px):"), 0, 2, 1, 1)
        grid.attach(h_entry, 1, 2, 1, 1)
        grid.attach(lock_chk, 0, 3, 2, 1)
        grid.attach(center_chk, 0, 4, 2, 1)

        dlg.show_all()
        if dlg.run() == Gtk.ResponseType.OK:
            self.title = title_entry.get_text().strip()
            try:
                new_w = max(36, min(self.canvas.A4_WIDTH - 40, int(w_entry.get_text())))
                if lock_chk.get_active():
                    new_h = max(24, int(round(new_w / self.aspect)))
                else:
                    new_h = max(24, min(self.canvas.A4_HEIGHT - 60, int(h_entry.get_text())))
                    self.aspect = new_w / float(new_h)
                self.img_w, self.img_h = new_w, new_h
            except ValueError:
                pass
            self.update_layout()
            if center_chk.get_active():
                self.canvas.move_box(self, max(0, (self.canvas.A4_WIDTH - self.box_w) // 2), self.y)
            self.canvas.recalculate_worksheet()
            self.canvas.notify_toc_changed()
            self.queue_draw()
        dlg.destroy()


# ============================================================================
# Data Table Box (cell data usable in calculations anywhere on the sheet)
# ============================================================================


_TABLE_CELL_ENV = {
    "__builtins__": {},
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "sqrt": math.sqrt, "ln": math.log, "log": math.log10, "exp": math.exp,
    "abs": abs, "pi": math.pi, "π": math.pi, "e": math.e,
}


def parse_table_cell(raw: str):
    """Convert a cell's text to a value: '' -> None, numbers -> float,
    constant expressions (e.g. 2*pi, 1e-3, sqrt(2)) -> float, anything else -> str."""
    txt = (raw or "").strip()
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        pass
    expr = txt.replace("^", "**").replace("·", "*").replace("×", "*").replace("−", "-")
    if any(ch.isdigit() for ch in expr) or "pi" in expr or "π" in expr:
        try:
            val = eval(expr, dict(_TABLE_CELL_ENV))
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return float(val)
        except Exception:
            pass
    return txt


class SheetTable:
    """Value bound to a table's name on the sheet.
    T(i, j) -> cell at row i, column j (1-based; j may also be the column header text)
    T(i)    -> row i as a vector
    """

    def __init__(self, name, headers, values):
        self.name = name
        self.headers = list(headers)
        self.values = values  # list of rows, each a list of parsed cell values

    def _col_index(self, j):
        if isinstance(j, str):
            if j in self.headers:
                return self.headers.index(j)
            raise KeyError(f"{self.name} has no column '{j}'")
        jj = int(round(float(j)))
        if not 1 <= jj <= len(self.headers):
            raise IndexError(f"{self.name}: column {jj} out of range 1..{len(self.headers)}")
        return jj - 1

    def _row_index(self, i):
        ii = int(round(float(i)))
        if not 1 <= ii <= len(self.values):
            raise IndexError(f"{self.name}: row {ii} out of range 1..{len(self.values)}")
        return ii - 1

    def __call__(self, i, j=None):
        row = self.values[self._row_index(i)]
        if j is None:
            return [math.nan if v is None else v for v in row]
        v = row[self._col_index(j)]
        if v is None:
            raise ValueError(f"{self.name}({i}, {j}) is empty")
        return v

    def column(self, j):
        c = self._col_index(j)
        col = [r[c] for r in self.values]
        while col and col[-1] is None:
            col.pop()
        return [math.nan if v is None else v for v in col]

    def __len__(self):
        return len(self.values)

    def __repr__(self):
        return f"<table {self.name}: {len(self.values)}×{len(self.headers)}>"


def _tbl_rows(t):
    return len(t)


def _tbl_cols(t):
    return len(t.headers) if isinstance(t, SheetTable) else 1


def _tbl_col(t, j):
    return t.column(j)


def _tbl_row(t, i):
    return t(i)


def _vec_mean(v):
    vals = [float(x) for x in v]
    return sum(vals) / len(vals) if vals else math.nan


# Functions made available to every math box (useful on table columns / vectors)
TABLE_SHEET_FUNCS = {
    "rows": _tbl_rows,
    "cols": _tbl_cols,
    "col": _tbl_col,
    "row": _tbl_row,
    "len": len,
    "total": lambda v: sum(float(x) for x in v),
    "mean": _vec_mean,
    "max": max,
    "min": min,
}


class TableBox(Gtk.DrawingArea):
    """
    Data table on the A4 worksheet.
    - The table name (e.g. T1) is a sheet variable: T1(i, j) gives the cell in row i, column j (1-based).
    - Every column whose header is a valid name (e.g. Re, Nu, x_1) becomes a vector variable
      holding that column's values, usable in math boxes and plots anywhere on the sheet.
    - Click a cell to edit; Enter / Tab / arrows move between cells; right-click for row/column options.
    - The name is shown only in the Table Options dialog (double-click the bar above the table).
    - An optional caption ("Table N: ...") is drawn above the table and moves with it.
    - Drag the table by the bar / caption above it.
    """

    HANDLE_H = 22  # drag bar above the table; holds the caption button when selected
    CAPTION_PREFIX = "Table"
    CAPTION_WHERE = "above"
    PAD = 4
    MIN_COL_W = 56
    CELL_PAD_X = 6

    def __init__(self, canvas, x, y, name="T1", headers=None, cells=None, rows=4, cols=3, title=""):
        super().__init__()
        self.canvas = canvas
        self.name = name
        self.title = title
        self.fig_num = 1  # table number, assigned by the canvas
        self.grid_top = self.HANDLE_H
        self.caption_h = 0
        if headers is None:
            headers = [f"c{j + 1}" for j in range(cols)]
        self.headers = [str(h) for h in headers]
        ncols = len(self.headers)
        if cells is None:
            cells = [["" for _ in range(ncols)] for _ in range(rows)]
        self.cells = [[str(v) if v is not None else "" for v in (list(r) + [""] * ncols)[:ncols]] for r in cells]

        self.x = int(x)
        self.y = int(y)
        self.editing = False
        self.selected = False
        self.dragging = False
        self.drag_start_root_x = 0
        self.drag_start_root_y = 0
        self.drag_start_box_x = 0
        self.drag_start_box_y = 0
        self.active = None  # (row, col); row -1 is the header row
        self.cursor_pos = 0
        self.col_widths = []
        self.row_h = 24
        self.logical_w = 100
        self.logical_h = 60

        self.set_can_focus(True)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
            | Gdk.EventMask.SCROLL_MASK
            | Gdk.EventMask.FOCUS_CHANGE_MASK
        )
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("key-press-event", self.on_key_press)
        self.connect("scroll-event", self.on_scroll)
        self.update_layout()

    # ---------------------------------------------------------------- data
    @property
    def n_rows(self):
        return len(self.cells)

    @property
    def n_cols(self):
        return len(self.headers)

    def _cell_text(self, r, c):
        return self.headers[c] if r < 0 else self.cells[r][c]

    def _set_cell_text(self, r, c, text):
        if r < 0:
            self.headers[c] = text
        else:
            self.cells[r][c] = text

    @staticmethod
    def header_var_name(header: str):
        h = header.strip().replace(" ", "_")
        return h if h.isidentifier() else None

    def to_sheet_table(self) -> SheetTable:
        values = [[parse_table_cell(t) for t in row] for row in self.cells]
        while values and all(v is None for v in values[-1]):
            values.pop()  # trailing blank rows don't count as data
        return SheetTable(self.name, [h.strip() for h in self.headers], values)

    # -------------------------------------------------------------- layout
    def _layout(self, text, bold=False, header=False, pango_ctx=None):
        if pango_ctx is None:
            pango_ctx = self.get_pango_context()
        layout, _, _, _ = MathRenderer._make_layout(pango_ctx, "", 0.8, bold=bold)
        if header and "_" in text.strip():
            base, sub = text.strip().split("_", 1)
            layout.set_markup(
                f"{GLib.markup_escape_text(base)}<sub>{GLib.markup_escape_text(sub)}</sub>", -1
            )
        else:
            layout.set_text(text, -1)
        return layout

    def _display_text(self, r, c, for_export=False):
        raw = self._cell_text(r, c)
        if r < 0 or (self.editing and self.active == (r, c) and not for_export):
            return raw
        val = parse_table_cell(raw)
        if isinstance(val, float):
            try:
                float(raw.strip())
                return raw.strip()
            except ValueError:
                return format_number(val)
        return raw

    def update_layout(self):
        pango_ctx = self.get_pango_context()
        probe = self._layout("Xg", pango_ctx=pango_ctx)
        _, logical = probe.get_pixel_extents()
        self.row_h = max(20, logical.height + 8)
        widths = []
        for c in range(self.n_cols):
            w = self.MIN_COL_W
            for r in range(-1, self.n_rows):
                # Fit both the typed text and its computed value (they differ for e.g. 2*pi)
                for txt in {self._cell_text(r, c), self._display_text(r, c, for_export=True)}:
                    lay = self._layout(txt + " ", bold=(r < 0), header=(r < 0), pango_ctx=pango_ctx)
                    _, lg = lay.get_pixel_extents()
                    w = max(w, lg.width + 2 * self.CELL_PAD_X)
            widths.append(int(math.ceil(w)))
        self.col_widths = widths
        grid_w = sum(widths)
        cap_lay = self._make_caption_layout(pango_ctx)
        if cap_lay is not None:
            _, cl = cap_lay.get_pixel_extents()
            self.caption_h = int(math.ceil(cl.height)) + 6
        else:
            self.caption_h = 0
        self.grid_top = self.HANDLE_H + self.caption_h
        self.logical_w = int(max(grid_w, 90) + 2 * self.PAD)
        self.logical_h = int(self.grid_top + self.row_h * (self.n_rows + 1) + self.PAD)
        z = getattr(self.canvas, "zoom", 1.0)
        self.set_size_request(
            max(24, int(math.ceil(self.logical_w * z))),
            max(24, int(math.ceil(self.logical_h * z))),
        )
        self.queue_draw()

    def _update_size_request(self):
        self.update_layout()

    def get_caption_text(self) -> str:
        raw = self.title.strip()
        if not raw:
            return ""
        if raw.lower().startswith("table "):
            parts = raw.split(":", 1)
            if len(parts) == 2 and parts[0][6:].strip().isdigit():
                raw = parts[1].strip()
        return f"Table {self.fig_num}: {raw}" if raw else f"Table {self.fig_num}"

    def _make_caption_layout(self, pango_ctx=None):
        caption_str = self.get_caption_text()
        if not caption_str:
            return None
        if pango_ctx is None:
            pango_ctx = self.get_pango_context()
        lay, _, _, _ = MathRenderer._make_layout(pango_ctx, caption_str, 0.76, bold=True)
        lay.set_width(max(90, sum(self.col_widths)) * Pango.SCALE)
        lay.set_wrap(Pango.WrapMode.WORD_CHAR)
        lay.set_alignment(Pango.Alignment.CENTER)
        return lay

    def _cell_rect(self, r, c):
        x0 = self.PAD + sum(self.col_widths[:c])
        y0 = self.grid_top + (r + 1) * self.row_h
        return x0, y0, self.col_widths[c], self.row_h

    def _hit_cell(self, lx, ly):
        if ly < self.grid_top:
            return None
        r = int((ly - self.grid_top) // self.row_h) - 1
        if r >= self.n_rows:
            return None
        x = self.PAD
        for c, w in enumerate(self.col_widths):
            if x <= lx < x + w:
                return (r, c)
            x += w
        return None

    # -------------------------------------------------------------- drawing
    def draw_content(self, cr, theme=None, for_export=False):
        if theme is None:
            theme = THEMES[self.canvas.theme_name]
        pango_ctx = self.get_pango_context()
        w, h = self.logical_w, self.logical_h
        grid_w = sum(self.col_widths)
        gx, gy = self.PAD, self.grid_top
        grid_h = self.row_h * (self.n_rows + 1)

        # Caption above the table (moves with it)
        cap_lay = self._make_caption_layout(pango_ctx)
        if cap_lay is not None:
            cr.save()
            cr.set_source_rgb(*theme["heading_text"])
            cr.move_to(gx, self.HANDLE_H)
            PangoCairo.show_layout(cr, cap_lay)
            cr.restore()

        # Background & header band
        cr.save()
        cr.set_source_rgb(*theme["canvas_bg"])
        cr.rectangle(gx, gy, grid_w, grid_h)
        cr.fill()
        cr.set_source_rgb(*theme["placeholder_fill"])
        cr.rectangle(gx, gy, grid_w, self.row_h)
        cr.fill()
        cr.restore()

        # Cell text
        for r in range(-1, self.n_rows):
            for c in range(self.n_cols):
                x0, y0, cw, ch = self._cell_rect(r, c)
                txt = self._display_text(r, c, for_export=for_export)
                if not txt:
                    continue
                is_active = self.editing and self.active == (r, c) and not for_export
                lay = self._layout(txt, bold=(r < 0), header=(r < 0 and not is_active), pango_ctx=pango_ctx)
                _, lg = lay.get_pixel_extents()
                val = None if r < 0 else parse_table_cell(self._cell_text(r, c))
                if r < 0:
                    tx = x0 + (cw - lg.width) / 2.0
                    color = theme["heading_text"]
                elif isinstance(val, float) and not is_active:
                    tx = x0 + cw - self.CELL_PAD_X - lg.width
                    color = theme["text"]
                else:
                    tx = x0 + self.CELL_PAD_X
                    color = theme["text"]
                if is_active:
                    tx = x0 + self.CELL_PAD_X
                cr.save()
                cr.set_source_rgb(*color)
                cr.move_to(tx, y0 + (ch - lg.height) / 2.0)
                PangoCairo.show_layout(cr, lay)
                cr.restore()

        # Grid lines
        cr.save()
        cr.set_source_rgb(*theme["page_border"])
        cr.set_line_width(1.0)
        for r in range(self.n_rows + 2):
            yy = gy + r * self.row_h + 0.5
            cr.move_to(gx, yy)
            cr.line_to(gx + grid_w, yy)
        xx = gx
        for c in range(self.n_cols + 1):
            cr.move_to(xx + 0.5, gy)
            cr.line_to(xx + 0.5, gy + grid_h)
            if c < self.n_cols:
                xx += self.col_widths[c]
        cr.stroke()
        # Heavier rule under the header row
        cr.set_line_width(1.8)
        cr.move_to(gx, gy + self.row_h + 0.5)
        cr.line_to(gx + grid_w, gy + self.row_h + 0.5)
        cr.stroke()
        cr.restore()

        if for_export:
            return

        # Active cell frame + text cursor
        if self.editing and self.active is not None:
            r, c = self.active
            x0, y0, cw, ch = self._cell_rect(r, c)
            cr.save()
            cr.set_source_rgb(*theme["box_editing_border"])
            cr.set_line_width(2.0)
            cr.rectangle(x0 + 1, y0 + 1, cw - 2, ch - 2)
            cr.stroke()
            prefix = self._cell_text(r, c)[: self.cursor_pos]
            pl = self._layout(prefix, bold=(r < 0), pango_ctx=pango_ctx)
            _, plg = pl.get_pixel_extents()
            cx = x0 + self.CELL_PAD_X + plg.width + 0.5
            cr.set_source_rgb(*theme["cursor"])
            cr.set_line_width(1.5)
            cr.move_to(cx, y0 + 4)
            cr.line_to(cx, y0 + ch - 4)
            cr.stroke()
            cr.restore()

        if self.selected:
            cr.save()
            cr.set_source_rgb(*theme["box_selected_border"])
            cr.set_line_width(1.4)
            cr.set_dash([4.0, 3.0])
            cr.rectangle(0.7, 0.7, w - 1.4, h - 1.4)
            cr.stroke()
            cr.restore()
            draw_figure_caption_button(self, cr, theme, bx=gx, by=1.0)

    def on_draw(self, widget, cr):
        z = getattr(self.canvas, "zoom", 1.0)
        cr.save()
        cr.scale(z, z)
        self.draw_content(cr, for_export=False)
        cr.restore()
        return True

    # ------------------------------------------------------ canvas protocol
    def is_empty(self):
        return False

    def set_selected(self, selected):
        self.selected = selected
        if not selected and self.editing:
            self.stop_editing()
        self.queue_draw()

    def start_editing(self, cell=None):
        if cell is None:
            cell = self.active if self.active is not None else (0 if self.n_rows else -1, 0)
        self.active = cell
        self.cursor_pos = len(self._cell_text(*cell))
        self.editing = True
        self.canvas.focus_without_scroll(self)
        self.update_layout()

    def stop_editing(self):
        if not self.editing:
            return
        self.editing = False
        self.update_layout()
        self.canvas.recalculate_worksheet()

    def _commit_edit(self):
        self.update_layout()
        self.canvas.recalculate_worksheet()

    # --------------------------------------------------------------- mouse
    def on_button_press(self, widget, event):
        z = getattr(self.canvas, "zoom", 1.0)
        lx, ly = event.x / z, event.y / z
        if event.button == 3:
            if self not in self.canvas.selected_boxes:
                self.canvas.select_box(self)
            cell = self._hit_cell(lx, ly)
            self._show_context_menu(event, cell)
            return True
        if event.button != 1:
            return False

        cell = self._hit_cell(lx, ly)
        was_selected = self.selected
        self.canvas.handle_box_button_press(self, event)
        if event.state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK):
            return True
        if was_selected and hit_figure_caption_button(self, lx, ly):
            self.dragging = False
            GLib.idle_add(lambda: open_figure_caption_dialog(self) and False)
            return True
        if cell is None:
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self.dragging = False
                if self.caption_h and self.HANDLE_H <= ly < self.grid_top:
                    GLib.idle_add(lambda: open_figure_caption_dialog(self) and False)
                else:
                    GLib.idle_add(self._open_options_idle)
                return True
            self.canvas.focus_without_scroll(self)
            self.dragging = True
            self.drag_start_root_x = event.x_root
            self.drag_start_root_y = event.y_root
            self.drag_start_box_x = self.x
            self.drag_start_box_y = self.y
            return True

        self.selected = True
        self.start_editing(cell)
        # Place the text cursor near the click position
        x0, _, _, _ = self._cell_rect(*cell)
        txt = self._cell_text(*cell)
        best, best_d = len(txt), None
        for i in range(len(txt) + 1):
            lay = self._layout(txt[:i], bold=(cell[0] < 0))
            _, lg = lay.get_pixel_extents()
            d = abs(x0 + self.CELL_PAD_X + lg.width - lx)
            if best_d is None or d < best_d:
                best, best_d = i, d
        self.cursor_pos = best
        self.queue_draw()
        return True

    def _open_options_idle(self):
        self.open_options_dialog()
        return False

    def _update_hover_cursor(self, event):
        win = self.get_window()
        if win is None:
            return
        z = getattr(self.canvas, "zoom", 1.0)
        lx, ly = event.x / z, event.y / z
        over_bar = ly < self.grid_top and not hit_figure_caption_button(self, lx, ly)
        try:
            win.set_cursor(Gdk.Cursor.new_from_name(win.get_display(), "move") if over_bar else None)
        except Exception:
            win.set_cursor(None)

    def on_motion_notify(self, widget, event):
        if not self.dragging:
            self._update_hover_cursor(event)
        if self.dragging:
            if not (event.state & Gdk.ModifierType.BUTTON1_MASK):
                self.dragging = False
                return False
            z = getattr(self.canvas, "zoom", 1.0)
            dx = int((event.x_root - self.drag_start_root_x) / z)
            dy = int((event.y_root - self.drag_start_root_y) / z)
            self.canvas.drag_box_or_group(self, dx, dy)
            return True
        return False

    def on_button_release(self, widget, event):
        if event.button == 1 and self.dragging:
            self.dragging = False
            self.canvas.recalculate_worksheet()
            return True
        return False

    def on_scroll(self, widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            return self.canvas.on_scroll_zoom(widget, event)
        return False

    # ------------------------------------------------------------ keyboard
    def _move_active(self, dr, dc, grow=False):
        r, c = self.active
        r2, c2 = r + dr, c + dc
        if c2 >= self.n_cols:
            c2, r2 = 0, r2 + 1
        elif c2 < 0:
            c2, r2 = self.n_cols - 1, r2 - 1
        if r2 >= self.n_rows:
            if not grow:
                return
            self.cells.append(["" for _ in range(self.n_cols)])
        r2 = max(-1, r2)
        self.active = (r2, c2)
        self.cursor_pos = len(self._cell_text(r2, c2))
        self._commit_edit()

    def on_key_press(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)

        if not self.editing:
            if ctrl:
                return False
            if keyname in ("Delete", "BackSpace"):
                self.canvas.remove_selected_boxes(self)
                return True
            if keyname in ("Return", "KP_Enter", "F2"):
                self.start_editing()
                return True
            return False

        if ctrl:
            return False
        r, c = self.active
        text = self._cell_text(r, c)

        if keyname == "Escape":
            self.stop_editing()
            return True
        if keyname in ("Return", "KP_Enter"):
            self._move_active(-1 if shift else 1, 0, grow=not shift)
            return True
        if keyname in ("Tab", "ISO_Left_Tab"):
            self._move_active(0, -1 if (shift or keyname == "ISO_Left_Tab") else 1, grow=True)
            return True
        if keyname == "Up":
            self._move_active(-1, 0)
            return True
        if keyname == "Down":
            self._move_active(1, 0)
            return True
        if keyname == "Left":
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
                self.queue_draw()
            elif c > 0:
                self._move_active(0, -1)
            return True
        if keyname == "Right":
            if self.cursor_pos < len(text):
                self.cursor_pos += 1
                self.queue_draw()
            elif c < self.n_cols - 1:
                self._move_active(0, 1)
                self.cursor_pos = 0
                self.queue_draw()
            return True
        if keyname == "Home":
            self.cursor_pos = 0
            self.queue_draw()
            return True
        if keyname == "End":
            self.cursor_pos = len(text)
            self.queue_draw()
            return True
        if keyname == "BackSpace":
            if self.cursor_pos > 0:
                self._set_cell_text(r, c, text[: self.cursor_pos - 1] + text[self.cursor_pos:])
                self.cursor_pos -= 1
                self._commit_edit()
            return True
        if keyname == "Delete":
            if self.cursor_pos < len(text):
                self._set_cell_text(r, c, text[: self.cursor_pos] + text[self.cursor_pos + 1:])
                self._commit_edit()
            return True

        uni = Gdk.keyval_to_unicode(event.keyval)
        ch = chr(uni) if uni else ""
        if ch and ch.isprintable():
            self._set_cell_text(r, c, text[: self.cursor_pos] + ch + text[self.cursor_pos:])
            self.cursor_pos += 1
            self._commit_edit()
            return True
        return True  # swallow other keys while editing a cell

    # ----------------------------------------------------- row/col editing
    def insert_row(self, at):
        at = max(0, min(self.n_rows, at))
        self.cells.insert(at, ["" for _ in range(self.n_cols)])
        self._commit_edit()

    def delete_row(self, r):
        if self.n_rows > 1 and 0 <= r < self.n_rows:
            del self.cells[r]
            if self.active is not None and self.active[0] >= self.n_rows:
                self.active = (self.n_rows - 1, self.active[1])
            self._commit_edit()

    def _unique_header(self):
        k = self.n_cols + 1
        while f"c{k}" in self.headers:
            k += 1
        return f"c{k}"

    def insert_col(self, at):
        at = max(0, min(self.n_cols, at))
        self.headers.insert(at, self._unique_header())
        for row in self.cells:
            row.insert(at, "")
        self._commit_edit()

    def delete_col(self, c):
        if self.n_cols > 1 and 0 <= c < self.n_cols:
            del self.headers[c]
            for row in self.cells:
                del row[c]
            if self.active is not None and self.active[1] >= self.n_cols:
                self.active = (self.active[0], self.n_cols - 1)
            self._commit_edit()

    def _show_context_menu(self, event, cell):
        menu = Gtk.Menu()

        def add(label, cb, sensitive=True):
            mi = Gtk.MenuItem(label=label)
            mi.set_sensitive(sensitive)
            mi.connect("activate", lambda _m: cb())
            menu.append(mi)

        r, c = cell if cell is not None else (self.n_rows - 1, self.n_cols - 1)
        rr = max(0, r)
        add("Insert Row Above", lambda: self.insert_row(rr), r >= 0)
        add("Insert Row Below", lambda: self.insert_row(rr + 1))
        add("Delete Row", lambda: self.delete_row(rr), r >= 0 and self.n_rows > 1)
        menu.append(Gtk.SeparatorMenuItem())
        add("Insert Column Left", lambda: self.insert_col(c))
        add("Insert Column Right", lambda: self.insert_col(c + 1))
        add("Delete Column", lambda: self.delete_col(c), self.n_cols > 1)
        menu.append(Gtk.SeparatorMenuItem())
        add("Caption…", lambda: open_figure_caption_dialog(self))
        add("Table Options…", self.open_options_dialog)
        add("Delete Table", lambda: self.canvas.remove_selected_boxes(self))
        menu.show_all()
        menu.attach_to_widget(self, None)
        menu.popup_at_pointer(event)

    # ------------------------------------------------------------ dialogs
    def open_options_dialog(self):
        toplevel = self.get_toplevel()
        parent = toplevel if isinstance(toplevel, Gtk.Window) else None
        dlg = Gtk.Dialog(title="Table Options", transient_for=parent, flags=0)
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_APPLY, Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)

        content = dlg.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        for side in ("start", "end", "top", "bottom"):
            getattr(grid, f"set_margin_{side}")(12)
        content.add(grid)

        name_entry = Gtk.Entry(text=self.name)
        name_entry.set_activates_default(True)
        name_entry.set_tooltip_text("Used in math boxes, e.g. name(2, 1). Not shown on the sheet.")
        cap_entry = Gtk.Entry(text=self.title)
        cap_entry.set_activates_default(True)
        cap_entry.set_placeholder_text("optional – shown above the table")
        rows_spin = Gtk.SpinButton.new_with_range(1, 500, 1)
        rows_spin.set_value(self.n_rows)
        cols_spin = Gtk.SpinButton.new_with_range(1, 26, 1)
        cols_spin.set_value(self.n_cols)
        err_lbl = Gtk.Label()
        err_lbl.set_xalign(0.0)
        help_lbl = Gtk.Label()
        help_lbl.set_xalign(0.0)
        help_lbl.set_line_wrap(True)
        help_lbl.set_max_width_chars(52)
        help_lbl.set_markup(
            "<small>Use in any math box:\n"
            "  <tt>name(i, j)</tt> – cell in row i, column j (1-based)\n"
            "  <tt>Header</tt> – a column's values as a vector (e.g. <tt>Re</tt>, <tt>x_1</tt>)\n"
            "  <tt>rows(name)</tt>, <tt>cols(name)</tt>, <tt>col(name, j)</tt>, <tt>row(name, i)</tt>\n"
            "  <tt>total</tt>, <tt>mean</tt>, <tt>min</tt>, <tt>max</tt>, <tt>len</tt> on a column</small>"
        )

        grid.attach(Gtk.Label(label="Table name:", xalign=0.0), 0, 0, 1, 1)
        grid.attach(name_entry, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label=f"Table {self.fig_num} caption:", xalign=0.0), 0, 1, 1, 1)
        grid.attach(cap_entry, 1, 1, 1, 1)
        grid.attach(Gtk.Label(label="Rows:", xalign=0.0), 0, 2, 1, 1)
        grid.attach(rows_spin, 1, 2, 1, 1)
        grid.attach(Gtk.Label(label="Columns:", xalign=0.0), 0, 3, 1, 1)
        grid.attach(cols_spin, 1, 3, 1, 1)
        grid.attach(err_lbl, 0, 4, 2, 1)
        grid.attach(help_lbl, 0, 5, 2, 1)

        dlg.show_all()
        while True:
            if dlg.run() != Gtk.ResponseType.OK:
                break
            new_name = name_entry.get_text().strip().replace(" ", "_")
            if not new_name.isidentifier():
                err_lbl.set_markup("<span foreground='#d33'>Name must start with a letter and contain no symbols.</span>")
                continue
            self.name = new_name
            self.title = cap_entry.get_text().strip()
            nr, nc = int(rows_spin.get_value()), int(cols_spin.get_value())
            while self.n_cols < nc:
                self.insert_col(self.n_cols)
            while self.n_cols > nc:
                self.delete_col(self.n_cols - 1)
            while self.n_rows < nr:
                self.cells.append(["" for _ in range(self.n_cols)])
            del self.cells[nr:]
            if self.active is not None:
                self.active = (min(self.active[0], self.n_rows - 1), min(self.active[1], self.n_cols - 1))
            self._commit_edit()
            break
        dlg.destroy()


# ============================================================================
# A4 Graph-Paper Page Canvas (SMath Studio / Mathcad Page View + Zoom + File IO)
# ============================================================================


class MathCanvas(Gtk.ScrolledWindow):
    # Standard A4 Portrait dimensions at 96 DPI: 210 mm × 297 mm = 794 × 1123 px
    A4_WIDTH = 794
    A4_HEIGHT = 1123
    PAGE_MARGIN = 40  # ~10.5 mm printable margin guide
    MINOR_GRID = 20
    MAJOR_GRID = 100

    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.boxes = []
        self.selected_box = None
        self.selected_boxes = []
        self.rubberband_active = False
        self.rb_start_x = 0.0
        self.rb_start_y = 0.0
        self.rb_curr_x = 0.0
        self.rb_curr_y = 0.0
        self.rb_base_selection = []
        self._group_drag_origins = {}
        # Sheet insertion cursor (crosshair), in logical page coordinates
        self.cursor_x = 60
        self.cursor_y = 60
        self.show_grid = True
        self.theme_name = "dark"
        self.active_text_style = "normal"
        self.zoom = 1.0
        self.num_pages = 1
        self.on_toc_updated = None
        self.on_zoom_changed = None
        self.current_file_path = None

        # Outer workspace desk backdrop that centers the A4 page and draws its drop shadow
        self.desk_box = Gtk.EventBox()
        self.desk_box.set_can_focus(False)
        self.desk_box.set_app_paintable(True)
        self.desk_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK)
        self.desk_box.connect("draw", self.on_draw_desk)
        self.desk_box.connect("button-press-event", self.on_desk_button_press)
        self.desk_box.connect("scroll-event", self.on_scroll_zoom)

        # The A4 Sheet itself, centered horizontally with desk margins
        self.event_box = Gtk.EventBox()
        self.event_box.set_halign(Gtk.Align.CENTER)
        self.event_box.set_valign(Gtk.Align.START)
        self.event_box.set_margin_top(28)
        self.event_box.set_margin_bottom(36)
        self.event_box.set_margin_start(28)
        self.event_box.set_margin_end(28)
        self.event_box.set_can_focus(False)
        self.event_box.set_app_paintable(True)
        self.event_box.set_size_request(self.A4_WIDTH, self.A4_HEIGHT)
        self.event_box.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
            | Gdk.EventMask.SCROLL_MASK
        )
        self.event_box.connect("draw", self.on_draw_grid)
        self.event_box.connect_after("draw", self.on_draw_rubberband)
        self.event_box.connect("button-press-event", self.on_canvas_button_press)
        self.event_box.connect("motion-notify-event", self.on_canvas_motion_notify)
        self.event_box.connect("button-release-event", self.on_canvas_button_release)
        self.event_box.connect("key-press-event", self.on_canvas_key_press)
        self.event_box.connect("scroll-event", self.on_scroll_zoom)

        self.fixed = Gtk.Fixed()
        self.fixed.set_can_focus(False)
        self.fixed.set_size_request(self.A4_WIDTH, self.A4_HEIGHT)
        self.event_box.add(self.fixed)

        self.desk_box.add(self.event_box)
        self.add(self.desk_box)

        self._dummy_vadj = Gtk.Adjustment()
        self._dummy_hadj = Gtk.Adjustment()
        self._locked_vy = None
        self._locked_hx = None
        self._disable_focus_autoscroll()
        self.connect("realize", lambda _w: self._disable_focus_autoscroll())
        self.connect("map", lambda _w: self._disable_focus_autoscroll())

    def _disable_focus_autoscroll(self):
        """Disconnect GTK Container focus adjustments so focus changes never scroll the page."""
        viewport = self.get_child()
        for container in (self, viewport, self.desk_box, self.event_box, self.fixed):
            if isinstance(container, Gtk.Container):
                container.set_focus_vadjustment(self._dummy_vadj)
                container.set_focus_hadjustment(self._dummy_hadj)

    def _restore_locked_scroll(self):
        vadj = self.get_vadjustment()
        hadj = self.get_hadjustment()
        if vadj is not None and self._locked_vy is not None and abs(vadj.get_value() - self._locked_vy) > 0.5:
            vadj.set_value(self._locked_vy)
        if hadj is not None and self._locked_hx is not None and abs(hadj.get_value() - self._locked_hx) > 0.5:
            hadj.set_value(self._locked_hx)
        return False

    def focus_without_scroll(self, widget):
        """Grab focus on widget while preserving horizontal and vertical scroll positions."""
        self._disable_focus_autoscroll()
        vadj = self.get_vadjustment()
        hadj = self.get_hadjustment()
        vy = vadj.get_value() if vadj is not None else None
        hx = hadj.get_value() if hadj is not None else None
        self._locked_vy = vy
        self._locked_hx = hx
        if widget is not None and widget.get_can_focus():
            widget.grab_focus()
        self._restore_locked_scroll()
        GLib.idle_add(self._restore_locked_scroll, priority=GLib.PRIORITY_HIGH_IDLE)
        GLib.idle_add(self._restore_locked_scroll, priority=GLib.PRIORITY_DEFAULT_IDLE)

    # ------------------------------------------------------------------------
    # Multi-Page Management & Sheet Zoom (Zoom In, Zoom Out, Reset, Ctrl+Scroll)
    # ------------------------------------------------------------------------

    @property
    def total_height(self) -> int:
        return self.num_pages * self.A4_HEIGHT

    def set_num_pages(self, n: int):
        new_count = max(1, int(n))
        if new_count == self.num_pages:
            return
        self.num_pages = new_count
        zw = int(round(self.A4_WIDTH * self.zoom))
        zh = int(round(self.total_height * self.zoom))
        self.event_box.set_size_request(zw, zh)
        self.fixed.set_size_request(zw, zh)
        vadj = self.get_vadjustment()
        if vadj is not None and vadj.get_upper() < zh + 64:
            vadj.set_upper(zh + 64)
        self.desk_box.queue_draw()
        self.event_box.queue_draw()

    def add_page(self):
        self.set_num_pages(self.num_pages + 1)

    def ensure_page_for_y(self, y_bottom: int):
        needed_pages = max(1, int(math.ceil(max(1, y_bottom) / float(self.A4_HEIGHT))))
        if needed_pages > self.num_pages:
            self.set_num_pages(needed_pages)

    def _ensure_y_visible(self, y: int, h: int = 36):
        """Scroll viewport if needed so logical y..y+h is visible."""
        vadj = self.get_vadjustment()
        if vadj is None:
            return
        page_size = vadj.get_page_size()
        if page_size <= 1:
            return
        cur_val = vadj.get_value()
        top_px = 28 + y * self.zoom
        bot_px = 28 + (y + h + 28) * self.zoom

        target_val = None
        if bot_px > cur_val + page_size:
            target_val = bot_px - page_size
        elif top_px < cur_val:
            target_val = max(0.0, top_px - 24)

        if target_val is not None:
            self._locked_vy = target_val
            vadj.set_value(target_val)
            GLib.idle_add(self._restore_locked_scroll, priority=GLib.PRIORITY_HIGH_IDLE)
            GLib.idle_add(self._restore_locked_scroll, priority=GLib.PRIORITY_DEFAULT_IDLE)

    def set_zoom(self, new_zoom: float):
        clamped = round(max(0.40, min(2.50, float(new_zoom))), 2)
        if abs(clamped - self.zoom) < 1e-4:
            return
        self.zoom = clamped
        zw = int(round(self.A4_WIDTH * self.zoom))
        zh = int(round(self.total_height * self.zoom))
        self.event_box.set_size_request(zw, zh)
        self.fixed.set_size_request(zw, zh)
        for b in self.boxes:
            b.update_layout()
            self.fixed.move(b, int(round(b.x * self.zoom)), int(round(b.y * self.zoom)))
        self.desk_box.queue_draw()
        self.event_box.queue_draw()
        if callable(self.on_zoom_changed):
            self.on_zoom_changed(self.zoom)

    def zoom_in(self):
        self.set_zoom(self.zoom + 0.10)

    def zoom_out(self):
        self.set_zoom(self.zoom - 0.10)

    def reset_zoom(self):
        self.set_zoom(1.0)

    def on_scroll_zoom(self, _widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            if event.direction == Gdk.ScrollDirection.UP:
                self.zoom_in()
                return True
            if event.direction == Gdk.ScrollDirection.DOWN:
                self.zoom_out()
                return True
        return False

    def notify_toc_changed(self):
        if callable(self.on_toc_updated):
            self.on_toc_updated()

    def get_toc_headings(self):
        heading_styles = ("title", "heading1", "heading2", "heading3")
        headings = [
            b
            for b in self.boxes
            if isinstance(b, TextBox) and b.style_name in heading_styles
        ]
        return sorted(headings, key=lambda b: (b.y // 10, b.x))

    def get_toc_figures(self):
        figs = [
            b
            for b in self.boxes
            if isinstance(b, (PlotBox, ImageBox))
        ]
        return sorted(figs, key=lambda b: (b.y // 20, b.x))

    def scroll_to_box(self, box):
        self.select_box(box)
        vadj = self.get_vadjustment()
        if vadj is not None:
            page_size = vadj.get_page_size()
            target_y = max(0.0, float(box.y * self.zoom + 28 - 40))
            max_y = max(0.0, vadj.get_upper() - page_size)
            clamped_target = min(target_y, max_y)
            self._locked_vy = clamped_target
            vadj.set_value(clamped_target)

    def exit_box_and_move_down(self, box):
        x = box.x
        logical_h = getattr(box, "logical_h", max(int(box.get_allocation().height / self.zoom), 28))
        page_idx = max(0, box.y // self.A4_HEIGHT)
        page_bottom = (page_idx + 1) * self.A4_HEIGHT
        usable_bottom = page_bottom - self.PAGE_MARGIN - 28

        if box.is_empty():
            raw_next_y = box.y + self.MINOR_GRID
            if raw_next_y > usable_bottom:
                if page_idx + 1 >= self.num_pages:
                    self.set_num_pages(page_idx + 2)
                next_y = round(((page_idx + 1) * self.A4_HEIGHT + self.PAGE_MARGIN + 10) / 10) * 10
            else:
                next_y = raw_next_y
            self.move_box(box, x, next_y)
            self.focus_without_scroll(box)
            self._ensure_y_visible(next_y, 36)
            return

        raw_next_y = round((box.y + logical_h + 10) / 10) * 10
        if raw_next_y > usable_bottom:
            if page_idx + 1 >= self.num_pages:
                self.set_num_pages(page_idx + 2)
            next_y = round(((page_idx + 1) * self.A4_HEIGHT + self.PAGE_MARGIN + 10) / 10) * 10
        else:
            next_y = raw_next_y

        box.stop_editing()

        for other in self.boxes:
            if other is not box and abs(other.y - next_y) <= 12 and abs(other.x - x) <= 40:
                self.select_box(other)
                other.start_editing()
                self._ensure_y_visible(other.y, getattr(other, "logical_h", 36))
                return

        new_box = self.create_box(x, next_y, edit=True)
        self._ensure_y_visible(new_box.y, getattr(new_box, "logical_h", 36))

    # ------------------------------------------------------------------------
    # Sheet insertion cursor (text-editor style: click to place, type to insert,
    # Enter pushes everything below down by one line)
    # ------------------------------------------------------------------------

    LINE_H = 20  # one "line" on the sheet = one minor grid step
    CURSOR_STEP = 10

    def set_sheet_cursor(self, x, y, scroll=False):
        self.cursor_x = int(max(0, min(self.A4_WIDTH - 20, round(x / 10) * 10)))
        self.cursor_y = int(max(0, min(self.total_height - 10, round(y / 10) * 10)))
        if scroll:
            self._ensure_y_visible(self.cursor_y, self.LINE_H)
        self.event_box.queue_draw()

    def sheet_cursor_visible(self) -> bool:
        return not self.selected_boxes and not any(b.editing for b in self.boxes)

    def insert_line_at_cursor(self):
        """Move every box at or below the cursor down one line (like Enter in a text editor)."""
        dy = self.LINE_H
        movers = [b for b in self.boxes if b.y >= self.cursor_y]
        if movers:
            lowest = max(b.y + getattr(b, "logical_h", 28) for b in movers)
            self.ensure_page_for_y(lowest + dy + 10)
            for b in sorted(movers, key=lambda bb: -bb.y):
                self.move_box(b, b.x, b.y + dy)
        self.ensure_page_for_y(self.cursor_y + dy + 40)
        self.set_sheet_cursor(self.cursor_x, self.cursor_y + dy, scroll=True)
        if movers:
            self.recalculate_worksheet()

    def remove_line_at(self, top) -> bool:
        """Remove the empty line [top, top+LINE_H) and pull everything below it up."""
        dy = self.LINE_H
        if top < 0:
            return False
        # The line must not contain the top of any box (like deleting an empty text line)
        if any(top <= b.y < top + dy for b in self.boxes):
            return False
        movers = [b for b in self.boxes if b.y >= top + dy]
        for b in sorted(movers, key=lambda bb: bb.y):
            self.move_box(b, b.x, b.y - dy)
        if movers:
            self.recalculate_worksheet()
        return True

    def handle_sheet_cursor_key(self, event) -> bool:
        if event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK):
            return False
        keyname = Gdk.keyval_name(event.keyval)
        if keyname in ("Return", "KP_Enter"):
            self.insert_line_at_cursor()
            return True
        if keyname == "BackSpace":
            if self.remove_line_at(self.cursor_y - self.LINE_H):
                self.set_sheet_cursor(self.cursor_x, self.cursor_y - self.LINE_H, scroll=True)
            return True
        if keyname == "Delete":
            self.remove_line_at(self.cursor_y)
            return True
        moves = {
            "Up": (0, -self.CURSOR_STEP), "Down": (0, self.CURSOR_STEP),
            "Left": (-self.CURSOR_STEP, 0), "Right": (self.CURSOR_STEP, 0),
        }
        if keyname in moves:
            mx, my = moves[keyname]
            if my > 0:
                self.ensure_page_for_y(self.cursor_y + my + 40)
            self.set_sheet_cursor(self.cursor_x + mx, self.cursor_y + my, scroll=True)
            return True
        if keyname == "Home":
            self.set_sheet_cursor(self.PAGE_MARGIN + 20, self.cursor_y)
            return True
        uni = Gdk.keyval_to_unicode(event.keyval)
        ch = chr(uni) if uni else ""
        if ch and ch.isprintable() and ch != " ":
            # Start a new math box at the cursor and type the character into it
            box = self.create_box(self.cursor_x, self.cursor_y, edit=True)
            box.on_key_press(box, event)
            return True
        return False

    def draw_sheet_cursor(self, cr):
        if not self.sheet_cursor_visible():
            return
        t = THEMES[self.theme_name]
        cx, cy = self.cursor_x + 0.5, self.cursor_y + 0.5
        arm = 7.0
        cr.save()
        cr.scale(self.zoom, self.zoom)
        cr.set_source_rgb(*t["error"])
        cr.set_line_width(max(1.2, 1.6 / self.zoom))
        cr.move_to(cx - arm, cy)
        cr.line_to(cx + arm, cy)
        cr.move_to(cx, cy - arm)
        cr.line_to(cx, cy + arm)
        cr.stroke()
        cr.restore()

    def on_draw_desk(self, widget, cr):
        theme = THEMES[self.theme_name]
        alloc = widget.get_allocation()
        cr.set_source_rgb(*theme["desk_bg"])
        cr.rectangle(0, 0, alloc.width, alloc.height)
        cr.fill()

        page_alloc = self.event_box.get_allocation()
        px, py = self.event_box.translate_coordinates(widget, 0, 0) or (28, 28)
        cr.save()
        cr.set_source_rgba(*theme["page_shadow"])
        cr.rectangle(px + 6, py + 6, page_alloc.width, page_alloc.height)
        cr.fill()
        cr.restore()
        return False

    def draw_page_background(self, cr, pango_ctx, theme=None, show_grid=None, for_export=False):
        if theme is None:
            theme = THEMES[self.theme_name]
        if show_grid is None:
            show_grid = self.show_grid
        w, h = self.A4_WIDTH, self.A4_HEIGHT
        page_count = 1 if for_export else self.num_pages
        total_h = page_count * h

        cr.set_source_rgb(*theme["canvas_bg"])
        cr.rectangle(0, 0, w, total_h)
        cr.fill()

        if show_grid:
            cr.set_source_rgb(*theme["grid_minor"])
            cr.set_line_width(1.0)
            for x in range(0, w, self.MINOR_GRID):
                if x % self.MAJOR_GRID != 0:
                    cr.move_to(x + 0.5, 0)
                    cr.line_to(x + 0.5, total_h)
            for y in range(0, total_h, self.MINOR_GRID):
                if y % self.MAJOR_GRID != 0:
                    cr.move_to(0, y + 0.5)
                    cr.line_to(w, y + 0.5)
            cr.stroke()

            cr.set_source_rgb(*theme["grid_major"])
            cr.set_line_width(1.0)
            for x in range(0, w, self.MAJOR_GRID):
                cr.move_to(x + 0.5, 0)
                cr.line_to(x + 0.5, total_h)
            for y in range(0, total_h, self.MAJOR_GRID):
                cr.move_to(0, y + 0.5)
                cr.line_to(w, y + 0.5)
            cr.stroke()

            if not for_export:
                m = self.PAGE_MARGIN
                cr.save()
                cr.set_source_rgb(*theme["margin_guide"])
                cr.set_line_width(1.0)
                cr.set_dash([5.0, 5.0])
                for p in range(page_count):
                    y_off = p * h
                    cr.rectangle(m + 0.5, y_off + m + 0.5, w - 2 * m - 1.0, h - 2 * m - 1.0)
                cr.stroke()
                cr.restore()

        if not for_export:
            for p in range(page_count):
                y_off = p * h
                if p > 0:
                    # Draw distinct page-break divider band between A4 pages
                    cr.save()
                    cr.set_source_rgb(*theme["desk_bg"])
                    cr.rectangle(0, y_off - 4, w, 8)
                    cr.fill()
                    cr.set_source_rgb(*theme["page_border"])
                    cr.set_line_width(1.5)
                    cr.move_to(0, y_off - 4)
                    cr.line_to(w, y_off - 4)
                    cr.move_to(0, y_off + 4)
                    cr.line_to(w, y_off + 4)
                    cr.stroke()
                    cr.restore()

                lbl_txt = f"Page {p + 1} / {page_count}  —  A4 (210 × 297 mm)"
                layout, lw, _, _ = MathRenderer._make_layout(pango_ctx, lbl_txt, 0.65)
                cr.save()
                cr.set_source_rgb(*theme["page_border"])
                cr.move_to(w - lw - 12, y_off + h - 22)
                PangoCairo.show_layout(cr, layout)
                cr.restore()

            cr.save()
            cr.set_source_rgb(*theme["page_border"])
            cr.set_line_width(1.5)
            cr.rectangle(0.75, 0.75, w - 1.5, total_h - 1.5)
            cr.stroke()
            cr.restore()

    def on_draw_grid(self, widget, cr):
        cr.save()
        cr.scale(self.zoom, self.zoom)
        self.draw_page_background(cr, widget.get_pango_context(), for_export=False)
        cr.restore()
        return False

    def _next_spawn_y(self) -> int:
        if not self.boxes:
            return 60
        lowest = max(b.y + getattr(b, "logical_h", 36) for b in self.boxes)
        cand_y = round((lowest + 20) / 10) * 10
        page_idx = cand_y // self.A4_HEIGHT
        page_bottom = (page_idx + 1) * self.A4_HEIGHT
        if cand_y > page_bottom - self.PAGE_MARGIN - 30:
            cand_y = round(((page_idx + 1) * self.A4_HEIGHT + self.PAGE_MARGIN + 10) / 10) * 10
        self.ensure_page_for_y(cand_y + 60)
        return cand_y

    def create_box(self, x, y, edit=True) -> MathBox:
        snap_x = max(10, min(self.A4_WIDTH - 60, round(x / 10) * 10))
        snap_y = max(10, round(y / 10) * 10)
        self.ensure_page_for_y(snap_y + 40)
        box = MathBox(self, snap_x, snap_y)
        self.boxes.append(box)
        self.fixed.put(box, int(round(box.x * self.zoom)), int(round(box.y * self.zoom)))
        box.show_all()
        self.select_box(box)
        if edit:
            box.start_editing()
        return box

    def create_text_box(self, x, y, style_name="normal", text="", edit=True) -> TextBox:
        snap_x = max(10, min(self.A4_WIDTH - 80, round(x / 10) * 10))
        snap_y = max(10, round(y / 10) * 10)
        self.ensure_page_for_y(snap_y + 40)
        tbox = TextBox(self, snap_x, snap_y, style_name=style_name, text=text)
        self.boxes.append(tbox)
        self.fixed.put(tbox, int(round(tbox.x * self.zoom)), int(round(tbox.y * self.zoom)))
        tbox.show_all()
        self.select_box(tbox)
        if edit:
            tbox.start_editing()
        self.notify_toc_changed()
        return tbox

    def create_plot_box(self, x=0, y=None, **kwargs) -> PlotBox:
        if y is None:
            y = self._next_spawn_y()
        snap_y = max(10, round(y / 10) * 10)
        pbox = PlotBox(self, 0, snap_y, **kwargs)
        self.ensure_page_for_y(snap_y + pbox.plot_h + 20)
        pbox.x = max(0, (self.A4_WIDTH - pbox.plot_w) // 2)
        self.boxes.append(pbox)
        self.fixed.put(pbox, int(round(pbox.x * self.zoom)), int(round(pbox.y * self.zoom)))
        pbox.show_all()
        self.select_box(pbox)
        self.recalculate_worksheet()
        self.notify_toc_changed()
        return pbox

    def create_image_box(self, pixbuf: GdkPixbuf.Pixbuf, x=None, y=None, title="", width=None, height=None) -> ImageBox:
        if y is None:
            y = self._next_spawn_y()
        snap_y = max(10, round(y / 10) * 10)
        ibox = ImageBox(self, 0, snap_y, pixbuf=pixbuf, title=title, width=width, height=height)
        self.ensure_page_for_y(snap_y + ibox.box_h + 20)
        ibox.x = max(0, (self.A4_WIDTH - ibox.box_w) // 2) if x is None else int(x)
        self.boxes.append(ibox)
        self.fixed.put(ibox, int(round(ibox.x * self.zoom)), int(round(ibox.y * self.zoom)))
        ibox.show_all()
        self.select_box(ibox)
        self.recalculate_worksheet()
        self.notify_toc_changed()
        return ibox

    def _next_table_name(self) -> str:
        used = {b.name for b in self.boxes if isinstance(b, TableBox)}
        k = 1
        while f"T{k}" in used:
            k += 1
        return f"T{k}"

    def create_table_box(self, x=60, y=None, name=None, headers=None, cells=None, rows=4, cols=3, edit=True, title="") -> TableBox:
        if y is None:
            y = self._next_spawn_y()
        snap_x = max(10, min(self.A4_WIDTH - 120, round(x / 10) * 10))
        snap_y = max(10, round(y / 10) * 10)
        tbox = TableBox(
            self, snap_x, snap_y, name=name or self._next_table_name(),
            headers=headers, cells=cells, rows=rows, cols=cols, title=title,
        )
        self.ensure_page_for_y(snap_y + tbox.logical_h + 20)
        self.boxes.append(tbox)
        self.fixed.put(tbox, int(round(tbox.x * self.zoom)), int(round(tbox.y * self.zoom)))
        tbox.show_all()
        self.select_box(tbox)
        if edit:
            tbox.start_editing((-1, 0))
        self.recalculate_worksheet()
        return tbox

    def _try_load_pixbuf_from_clipboard(self):
        for sel_atom in (Gdk.SELECTION_CLIPBOARD, Gdk.SELECTION_PRIMARY):
            clip = Gtk.Clipboard.get(sel_atom)
            if clip is None:
                continue
            pixbuf = clip.wait_for_image()
            if pixbuf is not None:
                return pixbuf
            uris = clip.wait_for_uris()
            if uris:
                for uri in uris:
                    if uri.startswith("file://"):
                        from urllib.parse import unquote
                        fpath = unquote(uri[7:]).strip()
                        if os.path.isfile(fpath):
                            try:
                                return GdkPixbuf.Pixbuf.new_from_file(fpath)
                            except Exception:
                                pass
            txt = clip.wait_for_text()
            if txt:
                candidate = txt.strip().splitlines()[0].strip()
                if candidate.startswith("file://"):
                    from urllib.parse import unquote
                    candidate = unquote(candidate[7:]).strip()
                if os.path.isfile(candidate):
                    try:
                        return GdkPixbuf.Pixbuf.new_from_file(candidate)
                    except Exception:
                        pass
        return None

    def paste_from_clipboard(self, open_dialog_if_empty=False) -> bool:
        pixbuf = self._try_load_pixbuf_from_clipboard()
        if pixbuf is not None:
            spawn_y = self.selected_box.y if (self.selected_box is not None and self.selected_box.is_empty()) else self._next_spawn_y()
            if self.selected_box is not None and self.selected_box.is_empty():
                self.remove_box(self.selected_box)
            self.create_image_box(pixbuf, y=spawn_y)
            return True

        if open_dialog_if_empty:
            toplevel = self.get_toplevel()
            parent = toplevel if isinstance(toplevel, Gtk.Window) else None
            dlg = Gtk.FileChooserDialog(
                title="Insert Picture (or copy an image & press Ctrl+V)",
                parent=parent,
                action=Gtk.FileChooserAction.OPEN,
            )
            dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
            flt = Gtk.FileFilter()
            flt.set_name("Image files (PNG, JPEG, SVG, BMP, GIF, WebP)")
            flt.add_pixbuf_formats()
            dlg.add_filter(flt)
            if dlg.run() == Gtk.ResponseType.OK:
                fname = dlg.get_filename()
                dlg.destroy()
                if fname and os.path.isfile(fname):
                    try:
                        pb = GdkPixbuf.Pixbuf.new_from_file(fname)
                        self.create_image_box(pb, y=self._next_spawn_y())
                        return True
                    except Exception:
                        pass
            else:
                dlg.destroy()
        return False

    def insert_or_style_text_box(self, style_name: str):
        self.active_text_style = style_name
        selected_texts = [b for b in self.selected_boxes if isinstance(b, TextBox) and b in self.boxes]
        if len(selected_texts) > 1:
            for tb in selected_texts:
                tb.set_style_name(style_name)
            return selected_texts[-1]
        sel = self.selected_box
        if isinstance(sel, TextBox) and sel in self.boxes:
            sel.set_style_name(style_name)
            if not sel.editing:
                sel.start_editing()
            else:
                self.focus_without_scroll(sel)
            return sel
        if isinstance(sel, MathBox) and sel in self.boxes and sel.is_empty():
            x, y = sel.x, sel.y
            sel.editing = False
            self.remove_box(sel)
            return self.create_text_box(x, y, style_name=style_name, edit=True)
        return self.create_text_box(60, self._next_spawn_y(), style_name=style_name, edit=True)

    def set_selected_boxes(self, boxes_list, primary_box=None):
        self._disable_focus_autoscroll()
        vadj = self.get_vadjustment()
        hadj = self.get_hadjustment()
        vy = vadj.get_value() if vadj is not None else None
        hx = hadj.get_value() if hadj is not None else None
        self._locked_vy = vy
        self._locked_hx = hx

        unique_boxes = []
        for b in boxes_list:
            if b in self.boxes and b not in unique_boxes:
                unique_boxes.append(b)

        self.selected_boxes = unique_boxes
        if primary_box in self.selected_boxes:
            self.selected_box = primary_box
        elif self.selected_boxes:
            self.selected_box = self.selected_boxes[-1]
        else:
            self.selected_box = None

        selected_set = set(self.selected_boxes)
        for b in list(self.boxes):
            if b not in selected_set or len(selected_set) > 1:
                if b.editing:
                    b.stop_editing()
            b.set_selected(b in selected_set)

        if not self.selected_boxes:
            toplevel = self.get_toplevel()
            if isinstance(toplevel, Gtk.Window):
                cur_focus = toplevel.get_focus()
                if cur_focus is not None and cur_focus.is_ancestor(self):
                    toplevel.set_focus(None)

        if callable(getattr(self, "on_selection_changed", None)):
            self.on_selection_changed(self.selected_box)
        self.event_box.queue_draw()

        self._restore_locked_scroll()
        GLib.idle_add(self._restore_locked_scroll, priority=GLib.PRIORITY_HIGH_IDLE)
        GLib.idle_add(self._restore_locked_scroll, priority=GLib.PRIORITY_DEFAULT_IDLE)

    def select_box(self, box):
        self.set_selected_boxes([box] if box is not None else [], primary_box=box)

    def select_all_boxes(self):
        self.set_selected_boxes(list(self.boxes))

    def set_decimal_places_for_selected(self, decimals, fallback_box=None):
        math_targets = [b for b in self.selected_boxes if isinstance(b, MathBox) and b in self.boxes]
        if not math_targets and isinstance(self.selected_box, MathBox) and self.selected_box in self.boxes:
            math_targets = [self.selected_box]
        if not math_targets and isinstance(fallback_box, MathBox) and fallback_box in self.boxes:
            math_targets = [fallback_box]
        if not math_targets:
            return
        norm_dec = None if decimals is None else max(0, min(15, int(decimals)))
        for mb in math_targets:
            mb.decimal_places = norm_dec
        self.recalculate_worksheet()
        for mb in math_targets:
            mb.update_layout()
            mb.queue_draw()
        if callable(getattr(self, "on_selection_changed", None)):
            self.on_selection_changed(self.selected_box)

    def toggle_boxed_for_selected(self, fallback_box=None, force_state=None):
        math_targets = [b for b in self.selected_boxes if isinstance(b, MathBox) and b in self.boxes]
        if not math_targets and isinstance(self.selected_box, MathBox) and self.selected_box in self.boxes:
            math_targets = [self.selected_box]
        if not math_targets and isinstance(fallback_box, MathBox) and fallback_box in self.boxes:
            math_targets = [fallback_box]
        if not math_targets:
            return
        new_state = (not all(mb.boxed for mb in math_targets)) if force_state is None else bool(force_state)
        for mb in math_targets:
            mb.boxed = new_state
            mb.queue_draw()
        if callable(getattr(self, "on_selection_changed", None)):
            self.on_selection_changed(self.selected_box)

    def handle_box_button_press(self, box, event):
        shift_or_ctrl = bool(
            event.state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK)
        )
        if shift_or_ctrl:
            if box in self.selected_boxes:
                new_sel = [b for b in self.selected_boxes if b is not box]
                self.set_selected_boxes(new_sel)
            else:
                new_sel = list(self.selected_boxes) + [box]
                self.set_selected_boxes(new_sel, primary_box=box)
        elif box in self.selected_boxes and len(self.selected_boxes) > 1:
            self.selected_box = box
            for b in self.selected_boxes:
                if b.editing:
                    b.stop_editing()
        else:
            self.select_box(box)

        self._group_drag_origins = {b: (b.x, b.y) for b in self.selected_boxes}

    def drag_box_or_group(self, box, dx: int, dy: int):
        if box in self.selected_boxes and len(self.selected_boxes) >= 1 and self._group_drag_origins:
            for b in self.selected_boxes:
                ox, oy = self._group_drag_origins.get(b, (b.x, b.y))
                new_x = round(max(0, ox + dx) / 10) * 10
                new_y = round(max(0, oy + dy) / 10) * 10
                self.move_box(b, new_x, new_y)
        else:
            ox = getattr(box, "drag_start_box_x", box.x)
            oy = getattr(box, "drag_start_box_y", box.y)
            new_x = round(max(0, ox + dx) / 10) * 10
            new_y = round(max(0, oy + dy) / 10) * 10
            self.move_box(box, new_x, new_y)

    def move_box(self, box, x, y):
        bw = getattr(box, "logical_w", 28)
        bh = getattr(box, "logical_h", 28)
        if isinstance(box, PlotBox):
            clamped_x = max(0, (self.A4_WIDTH - box.plot_w) // 2)
        else:
            clamped_x = max(0, min(self.A4_WIDTH - bw, x))
        clamped_y = max(0, min(self.total_height - bh, y))
        box.x = clamped_x
        box.y = clamped_y
        self.fixed.move(box, int(round(clamped_x * self.zoom)), int(round(clamped_y * self.zoom)))
        if isinstance(box, (TextBox, PlotBox, ImageBox)):
            self.notify_toc_changed()

    def remove_box(self, box):
        if box in self.boxes:
            self.boxes.remove(box)
            if box in self.selected_boxes:
                self.selected_boxes.remove(box)
            if self.selected_box is box:
                self.selected_box = self.selected_boxes[-1] if self.selected_boxes else None
            self.fixed.remove(box)
            self.recalculate_worksheet()
            if isinstance(box, (TextBox, PlotBox, ImageBox)):
                self.notify_toc_changed()

    def remove_selected_boxes(self, fallback_box=None):
        targets = list(self.selected_boxes) if self.selected_boxes else ([fallback_box] if fallback_box else [])
        had_toc_item = False
        removed_any = False
        for b in targets:
            if b in self.boxes:
                if isinstance(b, (TextBox, PlotBox, ImageBox)):
                    had_toc_item = True
                self.boxes.remove(b)
                self.fixed.remove(b)
                removed_any = True
        self.selected_boxes = [b for b in self.selected_boxes if b in self.boxes]
        self.selected_box = self.selected_boxes[-1] if self.selected_boxes else None
        if removed_any:
            self.recalculate_worksheet()
            if had_toc_item:
                self.notify_toc_changed()

    def clear_boxes(self):
        self.selected_box = None
        self.selected_boxes = []
        for b in list(self.boxes):
            self.fixed.remove(b)
        self.boxes.clear()
        self.set_num_pages(1)
        self.notify_toc_changed()
        self.event_box.queue_draw()

    def new_worksheet(self):
        self.clear_boxes()
        self.current_file_path = None
        self.create_text_box(60, 40, style_name="title", text="Untitled Worksheet", edit=True)

    # ------------------------------------------------------------------------
    # Save / Save As / Open (JSON) & Export PDF (Vector Cairo PDFSurface)
    # ------------------------------------------------------------------------

    def to_dict(self) -> dict:
        serialized_boxes = []
        for b in self.boxes:
            if isinstance(b, MathBox):
                if b.is_empty():
                    continue
                serialized_boxes.append({
                    "type": "math",
                    "x": b.x,
                    "y": b.y,
                    "decimals": b.decimal_places,
                    "boxed": b.boxed,
                    "ast": serialize_math_seq(b.root),
                })
            elif isinstance(b, TextBox):
                if b.is_empty():
                    continue
                serialized_boxes.append({
                    "type": "text",
                    "x": b.x,
                    "y": b.y,
                    "style": b.style_name,
                    "text": b.text,
                })
            elif isinstance(b, PlotBox):
                serialized_boxes.append({
                    "type": "plot",
                    "x": b.x,
                    "y": b.y,
                    "width": b.plot_w,
                    "height": b.plot_h,
                    "title": b.title,
                    "func_expr": b.func_expr,
                    "discrete_data": b.discrete_data,
                    "symbol_style": b.symbol_style,
                    "connect_discrete": b.connect_discrete,
                    "x_min": b.x_min,
                    "x_max": b.x_max,
                    "y_min": b.y_min,
                    "y_max": b.y_max,
                    "x_scale": b.x_scale,
                    "y_scale": b.y_scale,
                    "show_grid": b.show_grid,
                    "show_legend": b.show_legend,
                })
            elif isinstance(b, TableBox):
                serialized_boxes.append({
                    "type": "table",
                    "x": b.x,
                    "y": b.y,
                    "name": b.name,
                    "title": b.title,
                    "headers": list(b.headers),
                    "cells": [list(r) for r in b.cells],
                })
            elif isinstance(b, ImageBox):
                ok, buf = b.orig_pixbuf.save_to_bufferv("png", [], [])
                b64_png = base64.b64encode(buf).decode("ascii") if ok else ""
                serialized_boxes.append({
                    "type": "image",
                    "x": b.x,
                    "y": b.y,
                    "width": b.img_w,
                    "height": b.img_h,
                    "title": b.title,
                    "png_b64": b64_png,
                })
        return {
            "version": 1,
            "theme": self.theme_name,
            "show_grid": self.show_grid,
            "zoom": self.zoom,
            "num_pages": self.num_pages,
            "boxes": serialized_boxes,
        }

    def load_from_dict(self, data: dict):
        self.clear_boxes()
        if "theme" in data and data["theme"] in THEMES:
            self.theme_name = data["theme"]
        if "show_grid" in data:
            self.show_grid = bool(data["show_grid"])
        if "num_pages" in data:
            self.set_num_pages(int(data["num_pages"]))
        if "zoom" in data:
            self.set_zoom(float(data["zoom"]))

        for item in data.get("boxes", []):
            btype = item.get("type")
            x = int(item.get("x", 60))
            y = int(item.get("y", 60))
            if btype == "math":
                mb = self.create_box(x, y, edit=False)
                mb.decimal_places = item.get("decimals", None)
                mb.boxed = bool(item.get("boxed", False))
                mb.root = deserialize_math_seq(item.get("ast", []))
                mb.cursor_seq = mb.root
                mb.cursor_idx = len(mb.root.items)
                mb.update_layout()
            elif btype == "text":
                self.create_text_box(
                    x, y,
                    style_name=item.get("style", "normal"),
                    text=item.get("text", ""),
                    edit=False,
                )
            elif btype == "plot":
                self.create_plot_box(
                    x, y,
                    width=item.get("width", 460),
                    height=item.get("height", 275),
                    title=item.get("title", ""),
                    func_expr=item.get("func_expr", "f"),
                    discrete_data=item.get("discrete_data", ""),
                    symbol_style=item.get("symbol_style", "circle"),
                    connect_discrete=item.get("connect_discrete", False),
                    x_min=item.get("x_min", -6.0),
                    x_max=item.get("x_max", 6.0),
                    y_min=item.get("y_min", -1.5),
                    y_max=item.get("y_max", 1.5),
                    x_scale=item.get("x_scale", "linear"),
                    y_scale=item.get("y_scale", "linear"),
                    show_grid=item.get("show_grid", True),
                    show_legend=item.get("show_legend", True),
                )
            elif btype == "table":
                self.create_table_box(
                    x, y,
                    name=item.get("name") or None,
                    headers=item.get("headers") or None,
                    cells=item.get("cells") or None,
                    title=item.get("title", ""),
                    edit=False,
                )
            elif btype == "image":
                b64_png = item.get("png_b64", "")
                if b64_png:
                    try:
                        raw_bytes = base64.b64decode(b64_png)
                        loader = GdkPixbuf.PixbufLoader.new_with_type("png")
                        loader.write(raw_bytes)
                        loader.close()
                        pb = loader.get_pixbuf()
                        if pb is not None:
                            self.create_image_box(
                                pb,
                                x=x,
                                y=y,
                                title=item.get("title", ""),
                                width=item.get("width"),
                                height=item.get("height"),
                            )
                    except Exception:
                        pass

        self.select_box(None)
        self.recalculate_worksheet()
        self.notify_toc_changed()
        self.cursor_x, self.cursor_y = 60, self._next_spawn_y()
        self.desk_box.queue_draw()
        self.event_box.queue_draw()

    def save_to_file(self, filepath: str):
        self.recalculate_worksheet()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        self.current_file_path = filepath

    def load_from_file(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_from_dict(data)
        self.current_file_path = filepath

    def export_pdf(self, pdf_path: str):
        """Render all A4 pages of the worksheet to a multi-page vector PDF file (210 × 297 mm = 595.28 × 841.89 pt)."""
        self.recalculate_worksheet()
        pdf_w_pt = 595.27559
        pdf_h_pt = 841.88976
        surface = cairo.PDFSurface(pdf_path, pdf_w_pt, pdf_h_pt)
        cr = cairo.Context(surface)
        sx = pdf_w_pt / float(self.A4_WIDTH)
        sy = pdf_h_pt / float(self.A4_HEIGHT)

        # Use classic print-friendly light theme for PDF export
        export_theme = THEMES["light"]
        sorted_boxes = sorted(self.boxes, key=lambda box: (box.y, box.x))

        for page_idx in range(self.num_pages):
            page_top = page_idx * self.A4_HEIGHT
            page_bot = (page_idx + 1) * self.A4_HEIGHT

            cr.save()
            cr.scale(sx, sy)
            cr.rectangle(0, 0, self.A4_WIDTH, self.A4_HEIGHT)
            cr.clip()

            self.draw_page_background(
                cr,
                self.event_box.get_pango_context(),
                theme=export_theme,
                show_grid=False,
                for_export=True,
            )

            for b in sorted_boxes:
                if b.is_empty():
                    continue
                bh = getattr(b, "logical_h", 28)
                if b.y + bh < page_top or b.y >= page_bot:
                    continue
                cr.save()
                cr.translate(b.x, b.y - page_top)
                b.draw_content(cr, theme=export_theme, for_export=True)
                cr.restore()

            cr.restore()
            cr.show_page()

        surface.finish()

    def recalculate_worksheet(self):
        """Evaluate all MathBoxes and update PlotBoxes in top-to-bottom, left-to-right order."""
        env = {
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "asin": math.asin,
            "acos": math.acos,
            "atan": math.atan,
            "sinh": math.sinh,
            "cosh": math.cosh,
            "tanh": math.tanh,
            "sqrt": math.sqrt,
            "ln": math.log,
            "log": math.log10,
            "exp": math.exp,
            "abs": abs,
            "pi": math.pi,
            "e": math.e,
            "inf": math.inf,
            "_smath_sum": _smath_sum,
            "_smath_int": _smath_int,
        }
        env.update(TABLE_SHEET_FUNCS)
        # Tables are injected before any box is evaluated, so their data can be
        # used anywhere on the sheet (above or below the table itself).
        table_vecs = []
        for tb in sorted((b for b in self.boxes if isinstance(b, TableBox)), key=lambda b: (b.y // 20, b.x)):
            st = tb.to_sheet_table()
            env[tb.name] = st
            for j, hdr in enumerate(st.headers):
                var = TableBox.header_var_name(hdr)
                if var and var not in TABLE_SHEET_FUNCS and var != tb.name:
                    env[var] = st.column(j + 1)
                    if var not in table_vecs:
                        table_vecs.append(var)
        env["_sheet_vectors"] = table_vecs
        ordered = sorted(self.boxes, key=lambda b: (b.y // 20, b.x))
        fig_counter = 0
        table_counter = 0
        for b in ordered:
            if isinstance(b, MathBox):
                res, err = evaluate_box_ast(
                    b.root,
                    env,
                    is_editing=b.editing,
                    decimals=b.decimal_places,
                )
                if b.eval_result != res or b.eval_error != err:
                    b.eval_result = res
                    b.eval_error = err
                    b.update_layout()
            elif isinstance(b, PlotBox):
                fig_counter += 1
                b.update_env(env, fig_num=fig_counter)
            elif isinstance(b, TableBox):
                table_counter += 1
                if b.fig_num != table_counter:
                    b.fig_num = table_counter
                    b.update_layout()
            elif isinstance(b, ImageBox):
                fig_counter += 1
                old_num = getattr(b, "fig_num", None)
                b.fig_num = fig_counter
                if old_num != fig_counter:
                    b.update_layout()
        self.notify_toc_changed()

    def get_active_or_new_box(self) -> MathBox:
        if isinstance(self.selected_box, MathBox) and self.selected_box in self.boxes:
            if not self.selected_box.editing:
                self.selected_box.start_editing()
            return self.selected_box
        return self.create_box(60, self._next_spawn_y(), edit=True)

    def insert_function_call(self, fn_name: str):
        box = self.get_active_or_new_box()
        for ch in fn_name:
            box.insert_char(ch)
        box.insert_parens()

    def on_desk_button_press(self, widget, event):
        if event.button == 1:
            self.select_box(None)
            return True
        return False

    def on_canvas_button_press(self, widget, event):
        if event.button == 1:
            lx = event.x / self.zoom
            ly = event.y / self.zoom
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self.rubberband_active = False
                self.event_box.queue_draw()
                self.set_sheet_cursor(lx, ly)
                self.create_box(lx, ly, edit=True)
                return True
            else:
                self.set_sheet_cursor(lx, ly)
                shift_or_ctrl = bool(
                    event.state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK)
                )
                if shift_or_ctrl:
                    self.rb_base_selection = list(self.selected_boxes)
                else:
                    self.rb_base_selection = []
                    self.select_box(None)
                self.rubberband_active = True
                self.rb_start_x = lx
                self.rb_start_y = ly
                self.rb_curr_x = lx
                self.rb_curr_y = ly
                self.event_box.queue_draw()
                return True
        return False

    def on_canvas_motion_notify(self, widget, event):
        if self.rubberband_active:
            self.rb_curr_x = max(0.0, min(float(self.A4_WIDTH), event.x / self.zoom))
            self.rb_curr_y = max(0.0, min(float(self.total_height), event.y / self.zoom))

            rx1 = min(self.rb_start_x, self.rb_curr_x)
            ry1 = min(self.rb_start_y, self.rb_curr_y)
            rx2 = max(self.rb_start_x, self.rb_curr_x)
            ry2 = max(self.rb_start_y, self.rb_curr_y)

            hits = list(self.rb_base_selection)
            if (rx2 - rx1) >= 3.0 or (ry2 - ry1) >= 3.0:
                for b in self.boxes:
                    bx1 = b.x
                    by1 = b.y
                    bx2 = b.x + getattr(b, "logical_w", 28)
                    by2 = b.y + getattr(b, "logical_h", 28)
                    # Check rectangle overlap (SMath Studio style marquee selection)
                    if bx1 <= rx2 and bx2 >= rx1 and by1 <= ry2 and by2 >= ry1:
                        if b not in hits:
                            hits.append(b)

            self.set_selected_boxes(hits)
            self.event_box.queue_draw()
            return True
        return False

    def on_canvas_button_release(self, widget, event):
        if event.button == 1 and self.rubberband_active:
            self.rubberband_active = False
            self.event_box.queue_draw()
            return True
        return False

    def on_draw_rubberband(self, widget, cr):
        self.draw_sheet_cursor(cr)
        if not self.rubberband_active:
            return False
        rx1 = min(self.rb_start_x, self.rb_curr_x)
        ry1 = min(self.rb_start_y, self.rb_curr_y)
        rw = abs(self.rb_curr_x - self.rb_start_x)
        rh = abs(self.rb_curr_y - self.rb_start_y)
        if rw < 2.0 and rh < 2.0:
            return False

        cr.save()
        cr.scale(self.zoom, self.zoom)
        t = THEMES[self.theme_name]
        cr.set_source_rgba(*t["box_selected_border"], 0.16)
        cr.rectangle(rx1, ry1, rw, rh)
        cr.fill_preserve()
        cr.set_source_rgba(*t["box_selected_border"], 0.90)
        cr.set_line_width(1.2 / self.zoom)
        cr.set_dash([5.0 / self.zoom, 3.0 / self.zoom])
        cr.stroke()
        cr.restore()
        return False

    def on_canvas_key_press(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname in ("Delete", "BackSpace") and self.selected_boxes:
            if not any(b.editing for b in self.selected_boxes):
                self.remove_selected_boxes()
                return True
        if self.selected_box is not None and not self.selected_box.editing:
            return self.selected_box.on_key_press(self.selected_box, event)
        return False


# ============================================================================
# LHS Table of Contents (TOC) Pane
# ============================================================================


class TOCPane(Gtk.Box):
    """Left-hand side pane listing document headings (Title, H1, H2, H3) and List of Figures."""

    INDENT_BY_STYLE = {
        "title": 4,
        "heading1": 12,
        "heading2": 26,
        "heading3": 40,
    }

    BADGE_BY_STYLE = {
        "title": "T",
        "heading1": "H1",
        "heading2": "H2",
        "heading3": "H3",
    }

    def __init__(self, canvas: MathCanvas):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.canvas = canvas
        self._row_to_box = {}
        self._fig_row_to_box = {}
        self._updating = False

        self.set_size_request(185, -1)

        vpaned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        vpaned.set_wide_handle(True)
        vpaned.set_position(380)

        # Upper section: Table of Contents (Headings)
        toc_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.set_margin_start(10)
        header_box.set_margin_end(8)
        header_box.set_margin_top(8)
        header_box.set_margin_bottom(6)

        title_lbl = Gtk.Label()
        title_lbl.set_markup("<b>Table of Contents</b>")
        title_lbl.set_xalign(0.0)
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        header_box.pack_start(title_lbl, True, True, 0)

        toc_vbox.pack_start(header_box, False, False, 0)
        toc_vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.listbox = Gtk.ListBox()
        self.listbox.set_can_focus(False)
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-activated", self._on_row_activated)
        scroller.add(self.listbox)
        toc_vbox.pack_start(scroller, True, True, 0)

        # Lower section: List of Figures
        fig_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        fig_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        fig_header_box.set_margin_start(10)
        fig_header_box.set_margin_end(8)
        fig_header_box.set_margin_top(8)
        fig_header_box.set_margin_bottom(6)

        fig_title_lbl = Gtk.Label()
        fig_title_lbl.set_markup("<b>List of Figures</b>")
        fig_title_lbl.set_xalign(0.0)
        fig_title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        fig_header_box.pack_start(fig_title_lbl, True, True, 0)

        fig_vbox.pack_start(fig_header_box, False, False, 0)
        fig_vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        fig_scroller = Gtk.ScrolledWindow()
        fig_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.fig_listbox = Gtk.ListBox()
        self.fig_listbox.set_can_focus(False)
        self.fig_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.fig_listbox.set_activate_on_single_click(True)
        self.fig_listbox.connect("row-activated", self._on_fig_row_activated)
        fig_scroller.add(self.fig_listbox)
        fig_vbox.pack_start(fig_scroller, True, True, 0)

        vpaned.pack1(toc_vbox, resize=True, shrink=True)
        vpaned.pack2(fig_vbox, resize=True, shrink=True)
        self.pack_start(vpaned, True, True, 0)

    def refresh(self):
        self._updating = True
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        self._row_to_box.clear()

        headings = self.canvas.get_toc_headings()
        if not headings:
            empty_row = Gtk.ListBoxRow()
            empty_row.set_can_focus(False)
            empty_row.set_selectable(False)
            empty_row.set_activatable(False)
            lbl = Gtk.Label(label="No headings yet.\nAdd Title, H1, H2, or H3.")
            lbl.set_xalign(0.0)
            lbl.set_margin_start(10)
            lbl.set_margin_end(8)
            lbl.set_margin_top(10)
            lbl.set_margin_bottom(10)
            lbl.set_line_wrap(True)
            empty_row.add(lbl)
            self.listbox.add(empty_row)
        else:
            for box in headings:
                row = Gtk.ListBoxRow()
                row.set_can_focus(False)
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                indent = self.INDENT_BY_STYLE.get(box.style_name, 8)
                hbox.set_margin_start(indent)
                hbox.set_margin_end(6)
                hbox.set_margin_top(4)
                hbox.set_margin_bottom(4)

                badge_txt = self.BADGE_BY_STYLE.get(box.style_name, "H")
                badge = Gtk.Label()
                badge.set_markup(f"<small><tt>{badge_txt}</tt></small>")
                badge.set_xalign(0.0)

                raw_title = (
                    box.text.strip().splitlines()[0]
                    if box.text.strip()
                    else f"({TEXT_STYLES[box.style_name]['label']})"
                )
                lbl = Gtk.Label()
                if box.style_name in ("title", "heading1"):
                    lbl.set_markup(f"<b>{GLib_markup_escape(raw_title)}</b>")
                else:
                    lbl.set_text(raw_title)
                lbl.set_xalign(0.0)
                lbl.set_ellipsize(Pango.EllipsizeMode.END)

                hbox.pack_start(badge, False, False, 0)
                hbox.pack_start(lbl, True, True, 0)
                row.add(hbox)
                self.listbox.add(row)
                self._row_to_box[row] = box

                if box is self.canvas.selected_box:
                    self.listbox.select_row(row)

        self.listbox.show_all()

        # Refresh List of Figures
        for child in self.fig_listbox.get_children():
            self.fig_listbox.remove(child)
        self._fig_row_to_box.clear()

        figures = self.canvas.get_toc_figures()
        if not figures:
            empty_fig_row = Gtk.ListBoxRow()
            empty_fig_row.set_can_focus(False)
            empty_fig_row.set_selectable(False)
            empty_fig_row.set_activatable(False)
            flbl = Gtk.Label(label="No figures yet.\nInsert Plot or Image.")
            flbl.set_xalign(0.0)
            flbl.set_margin_start(10)
            flbl.set_margin_end(8)
            flbl.set_margin_top(10)
            flbl.set_margin_bottom(10)
            flbl.set_line_wrap(True)
            empty_fig_row.add(flbl)
            self.fig_listbox.add(empty_fig_row)
        else:
            for idx, fbox in enumerate(figures, start=1):
                row = Gtk.ListBoxRow()
                row.set_can_focus(False)
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                hbox.set_margin_start(8)
                hbox.set_margin_end(6)
                hbox.set_margin_top(4)
                hbox.set_margin_bottom(4)

                fig_num = getattr(fbox, "fig_num", idx)
                badge = Gtk.Label()
                badge.set_markup(f"<small><tt>F{fig_num}</tt></small>")
                badge.set_xalign(0.0)

                raw_cap = fbox.title.strip().splitlines()[0] if fbox.title.strip() else ""
                if raw_cap.lower().startswith("figure "):
                    parts = raw_cap.split(":", 1)
                    if len(parts) == 2 and parts[0][7:].strip().isdigit():
                        raw_cap = parts[1].strip()
                if not raw_cap:
                    raw_cap = f"Plot ({fbox.func_expr})" if isinstance(fbox, PlotBox) else "Image"

                lbl = Gtk.Label(label=f"Figure {fig_num}: {raw_cap}")
                lbl.set_xalign(0.0)
                lbl.set_ellipsize(Pango.EllipsizeMode.END)
                lbl.set_tooltip_text(f"Figure {fig_num}: {raw_cap}")

                hbox.pack_start(badge, False, False, 0)
                hbox.pack_start(lbl, True, True, 0)
                row.add(hbox)
                self.fig_listbox.add(row)
                self._fig_row_to_box[row] = fbox

                if fbox is self.canvas.selected_box:
                    self.fig_listbox.select_row(row)

        self.fig_listbox.show_all()
        self._updating = False

    def _on_row_activated(self, _listbox, row):
        if self._updating:
            return
        box = self._row_to_box.get(row)
        if box is not None and box in self.canvas.boxes:
            self.canvas.scroll_to_box(box)

    def _on_fig_row_activated(self, _listbox, row):
        if self._updating:
            return
        fbox = self._fig_row_to_box.get(row)
        if fbox is not None and fbox in self.canvas.boxes:
            self.canvas.scroll_to_box(fbox)


def GLib_markup_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ============================================================================
# RHS Comprehensive Math Symbols & Functions Palette Pane
# ============================================================================


class SymbolsPane(Gtk.Box):
    """Right-hand side pane containing categorized math structures, operators, functions, and symbols."""

    def __init__(self, canvas: MathCanvas):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.canvas = canvas
        self.set_size_request(210, -1)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.set_margin_start(10)
        header_box.set_margin_end(8)
        header_box.set_margin_top(8)
        header_box.set_margin_bottom(6)

        title_lbl = Gtk.Label()
        title_lbl.set_markup("<b>Math Symbols</b>")
        title_lbl.set_xalign(0.0)
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        header_box.pack_start(title_lbl, True, True, 0)

        self.pack_start(header_box, False, False, 0)
        self.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body.set_margin_start(8)
        body.set_margin_end(8)
        body.set_margin_top(8)
        body.set_margin_bottom(12)

        def add_section(title_text, items, cols=4):
            sec_lbl = Gtk.Label()
            sec_lbl.set_markup(f"<small><b>{GLib_markup_escape(title_text)}</b></small>")
            sec_lbl.set_xalign(0.0)
            body.pack_start(sec_lbl, False, False, 0)

            grid = Gtk.Grid(column_spacing=3, row_spacing=3)
            grid.set_column_homogeneous(True)
            for idx, (label, tip, cb) in enumerate(items):
                btn = Gtk.Button(label=label)
                btn.set_can_focus(False)
                btn.set_tooltip_text(tip)
                btn.connect("clicked", lambda _b, fn=cb: fn())
                grid.attach(btn, idx % cols, idx // cols, 1, 1)
            body.pack_start(grid, False, False, 2)

        # 1) 2D Structures, Plot & Picture
        add_section(
            "2D Structures, Plot & Image",
            [
                ("a/b", "Fraction (/)", lambda: self.canvas.get_active_or_new_box().insert_fraction()),
                ("xⁿ", "Superscript (^)", lambda: self.canvas.get_active_or_new_box().insert_superscript()),
                ("xₙ", "Subscript (_)", lambda: self.canvas.get_active_or_new_box().insert_subscript()),
                ("√x", "Square Root (\\)", lambda: self.canvas.get_active_or_new_box().insert_sqrt()),
                ("ⁿ√x", "N-th Root", lambda: self.canvas.get_active_or_new_box().insert_nth_root()),
                ("( )", "Parentheses", lambda: self.canvas.get_active_or_new_box().insert_parens()),
                ("[ ]", "Vector [v1, v2, ...]", lambda: self.canvas.get_active_or_new_box().insert_vector_brackets()),
                ("∑", "Summation", lambda: self.canvas.get_active_or_new_box().insert_sum()),
                ("∫", "Definite Integral", lambda: self.canvas.get_active_or_new_box().insert_integral()),
                ("Plot", "Insert Centered 2D Plot Box", lambda: self.canvas.create_plot_box()),
                ("Img", "Paste Picture from Clipboard (Ctrl+V) or File", lambda: self.canvas.paste_from_clipboard(open_dialog_if_empty=True)),
            ],
            cols=4,
        )

        # 2) Operators & Relations
        op_symbols = [
            (":=", "Assign (:)"),
            ("=", "Evaluate (=)"),
            ("+", "Plus"),
            ("-", "Minus"),
            ("·", "Multiply (*)"),
            ("±", "Plus-Minus"),
            ("∓", "Minus-Plus"),
            ("×", "Cross Multiply"),
            ("÷", "Divide"),
            ("<", "Less Than"),
            (">", "Greater Than"),
            ("≤", "Less or Equal (<=)"),
            ("≥", "Greater or Equal (>=)"),
            ("≠", "Not Equal (!=)"),
            ("≈", "Approximately Equal"),
            ("≡", "Identical To"),
            ("∝", "Proportional To"),
            ("!", "Factorial"),
            ("%", "Percent / Modulo"),
            ("∞", "Infinity (inf)"),
        ]
        add_section(
            "Operators & Relations",
            [(sym, tip, lambda s=sym: self.canvas.get_active_or_new_box().insert_char(s)) for sym, tip in op_symbols],
            cols=4,
        )

        # 3) Functions
        fn_names = [
            ("sin", "Sine"),
            ("cos", "Cosine"),
            ("tan", "Tangent"),
            ("asin", "Arc Sine"),
            ("acos", "Arc Cosine"),
            ("atan", "Arc Tangent"),
            ("sinh", "Hyperbolic Sine"),
            ("cosh", "Hyperbolic Cosine"),
            ("tanh", "Hyperbolic Tangent"),
            ("ln", "Natural Logarithm"),
            ("log", "Base-10 Logarithm"),
            ("exp", "Exponential e^x"),
            ("abs", "Absolute Value"),
        ]
        add_section(
            "Functions",
            [(fn, tip, lambda f=fn: self.canvas.insert_function_call(f)) for fn, tip in fn_names],
            cols=3,
        )

        # 4) Greek Lowercase
        greek_lower = [
            ("α", "alpha"), ("β", "beta"), ("γ", "gamma"), ("δ", "delta"),
            ("ε", "epsilon"), ("ζ", "zeta"), ("η", "eta"), ("θ", "theta"),
            ("ι", "iota"), ("κ", "kappa"), ("λ", "lambda"), ("μ", "mu"),
            ("ν", "nu"), ("ξ", "xi"), ("π", "pi"), ("ρ", "rho"),
            ("σ", "sigma"), ("τ", "tau"), ("υ", "upsilon"), ("φ", "phi"),
            ("χ", "chi"), ("ψ", "psi"), ("ω", "omega"),
        ]
        add_section(
            "Greek (Lowercase)",
            [(sym, f"{sym} ({name})", lambda s=sym: self.canvas.get_active_or_new_box().insert_char(s)) for sym, name in greek_lower],
            cols=5,
        )

        # 5) Greek Uppercase
        greek_upper = [
            ("Γ", "Gamma"), ("Δ", "Delta"), ("Θ", "Theta"), ("Λ", "Lambda"),
            ("Ξ", "Xi"), ("Π", "Pi"), ("Σ", "Sigma"), ("Υ", "Upsilon"),
            ("Φ", "Phi"), ("Ψ", "Psi"), ("Ω", "Ω"),
        ]
        add_section(
            "Greek (Uppercase)",
            [(sym, f"{sym} ({name})", lambda s=sym: self.canvas.get_active_or_new_box().insert_char(s)) for sym, name in greek_upper],
            cols=5,
        )

        # 6) Calculus, Logic & Set Theory
        misc_symbols = [
            ("∂", "Partial Derivative"),
            ("∇", "Nabla / Gradient"),
            ("°", "Degree"),
            ("∀", "For All"),
            ("∃", "There Exists"),
            ("∈", "Element Of"),
            ("∉", "Not Element Of"),
            ("⊂", "Subset Of"),
            ("⊆", "Subset or Equal"),
            ("∪", "Union"),
            ("∩", "Intersection"),
            ("∅", "Empty Set"),
            ("∧", "Logical AND"),
            ("∨", "Logical OR"),
            ("¬", "Logical NOT"),
            ("⇒", "Implies"),
            ("⇔", "If and Only If"),
            ("→", "Right Arrow"),
            ("←", "Left Arrow"),
            ("↔", "Left-Right Arrow"),
        ]
        add_section(
            "Calculus, Sets & Logic",
            [(sym, tip, lambda s=sym: self.canvas.get_active_or_new_box().insert_char(s)) for sym, tip in misc_symbols],
            cols=5,
        )

        scroller.add(body)
        self.pack_start(scroller, True, True, 0)


# ============================================================================
# Main Window with File Menu, Clean Top Bar, Zoom Controls, TOC & Symbols Panes
# ============================================================================


# ============================================================================
# CommentariuM App Logo & Window / Toolbar Branding
# ============================================================================


# Embedded CommentariuM logo (SVG, base64-encoded)
COMMENTARIUM_LOGO_SVG_B64 = (
    'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjgg'
    'MTI4IiB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiI+CiAgPGRlZnM+CiAgICA8bGluZWFyR3JhZGll'
    'bnQgaWQ9ImJnR3JhZCIgeDE9IjAlIiB5MT0iMCUiIHgyPSIxMDAlIiB5Mj0iMTAwJSI+CiAgICAg'
    'IDxzdG9wIG9mZnNldD0iMCUiIHN0b3AtY29sb3I9IiMxYTIyMzQiLz4KICAgICAgPHN0b3Agb2Zm'
    'c2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMGYxNTIyIi8+CiAgICA8L2xpbmVhckdyYWRpZW50Pgog'
    'ICAgPGxpbmVhckdyYWRpZW50IGlkPSJwYWdlR3JhZCIgeDE9IjAlIiB5MT0iMCUiIHgyPSIwJSIg'
    'eTI9IjEwMCUiPgogICAgICA8c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjZjhmYWZjIi8+'
    'CiAgICAgIDxzdG9wIG9mZnNldD0iMTAwJSIgc3RvcC1jb2xvcj0iI2UyZThmMCIvPgogICAgPC9s'
    'aW5lYXJHcmFkaWVudD4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iZ29sZEdyYWQiIHgxPSIwJSIg'
    'eTE9IjAlIiB4Mj0iMTAwJSIgeTI9IjEwMCUiPgogICAgICA8c3RvcCBvZmZzZXQ9IjAlIiBzdG9w'
    'LWNvbG9yPSIjZmJiZjI0Ii8+CiAgICAgIDxzdG9wIG9mZnNldD0iMTAwJSIgc3RvcC1jb2xvcj0i'
    'I2Q5NzcwNiIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICA8L2RlZnM+CgogIDwhLS0gT3V0ZXIg'
    'Um91bmRlZCBCYWRnZSAtLT4KICA8cmVjdCB4PSI2IiB5PSI2IiB3aWR0aD0iMTE2IiBoZWlnaHQ9'
    'IjExNiIgcng9IjI0IiBmaWxsPSJ1cmwoI2JnR3JhZCkiIHN0cm9rZT0iIzM4YmRmOCIgc3Ryb2tl'
    'LXdpZHRoPSIzLjUiLz4KCiAgPCEtLSBOb3RlYm9vayBTcGluZSAvIFNoYWRvdyAtLT4KICA8cmVj'
    'dCB4PSIyNCIgeT0iMTgiIHdpZHRoPSI4MCIgaGVpZ2h0PSI5NCIgcng9IjYiIGZpbGw9IiMwOTBk'
    'MTYiIG9wYWNpdHk9IjAuNDUiLz4KCiAgPCEtLSBBNCBHcmFwaCBQYXBlciBTaGVldCB3aXRoIEZv'
    'bGRlZCBUb3AtUmlnaHQgQ29ybmVyIC0tPgogIDxwYXRoIGQ9Ik0gMjQgMTYgTCA4NCAxNiBMIDEw'
    'NCAzNiBMIDEwNCAxMTAgQyAxMDQgMTEyLjIgMTAyLjIgMTE0IDEwMCAxMTQgTCAyOCAxMTQgQyAy'
    'NS44IDExNCAyNCAxMTIuMiAyNCAxMTAgWiIgZmlsbD0idXJsKCNwYWdlR3JhZCkiLz4KICA8cGF0'
    'aCBkPSJNIDg0IDE2IEwgODQgMzYgTCAxMDQgMzYgWiIgZmlsbD0iI2NiZDVlMSIvPgoKICA8IS0t'
    'IFN1YnRsZSBFbmdpbmVlcmluZyBHcmFwaCBHcmlkIG9uIFNoZWV0IC0tPgogIDxnIHN0cm9rZT0i'
    'Izk0YTNiOCIgc3Ryb2tlLXdpZHRoPSIxIiBvcGFjaXR5PSIwLjQ1Ij4KICAgIDxsaW5lIHgxPSI0'
    'MCIgeTE9IjE2IiB4Mj0iNDAiIHkyPSIxMTQiLz4KICAgIDxsaW5lIHgxPSI1NiIgeTE9IjE2IiB4'
    'Mj0iNTYiIHkyPSIxMTQiLz4KICAgIDxsaW5lIHgxPSI3MiIgeTE9IjE2IiB4Mj0iNzIiIHkyPSIx'
    'MTQiLz4KICAgIDxsaW5lIHgxPSI4OCIgeTE9IjM2IiB4Mj0iODgiIHkyPSIxMTQiLz4KICAgIDxs'
    'aW5lIHgxPSIyNCIgeTE9IjM2IiB4Mj0iMTA0IiB5Mj0iMzYiLz4KICAgIDxsaW5lIHgxPSIyNCIg'
    'eTE9IjUyIiB4Mj0iMTA0IiB5Mj0iNTIiLz4KICAgIDxsaW5lIHgxPSIyNCIgeTE9IjY4IiB4Mj0i'
    'MTA0IiB5Mj0iNjgiLz4KICAgIDxsaW5lIHgxPSIyNCIgeTE9Ijg0IiB4Mj0iMTA0IiB5Mj0iODQi'
    'Lz4KICAgIDxsaW5lIHgxPSIyNCIgeTE9IjEwMCIgeDI9IjEwNCIgeTI9IjEwMCIvPgogIDwvZz4K'
    'CiAgPCEtLSBMZWZ0IE5vdGVib29rIE1hcmdpbiBMaW5lIC0tPgogIDxsaW5lIHgxPSIzNCIgeTE9'
    'IjE2IiB4Mj0iMzQiIHkyPSIxMTQiIHN0cm9rZT0iI2VmNDQ0NCIgc3Ryb2tlLXdpZHRoPSIxLjYi'
    'IG9wYWNpdHk9IjAuNjUiLz4KCiAgPCEtLSBNYXRoZW1hdGljYWwgQ3VydmUgb24gU2hlZXQgLS0+'
    'CiAgPHBhdGggZD0iTSAzNiA5MiBRIDU0IDQ2LCA3MiA3MiBUIDk4IDQ4IiBmaWxsPSJub25lIiBz'
    'dHJva2U9IiMwMjg0YzciIHN0cm9rZS13aWR0aD0iMy4yIiBzdHJva2UtbGluZWNhcD0icm91bmQi'
    'Lz4KCiAgPCEtLSBDbGFzc2ljIEludGVncmFsIEVtYmxlbSAn4oirJyAtLT4KICA8dGV4dCB4PSI1'
    'OCIgeT0iODgiIGZvbnQtZmFtaWx5PSJTZXJpZiIgZm9udC1zaXplPSI2MCIgZm9udC13ZWlnaHQ9'
    'ImJvbGQiIGZvbnQtc3R5bGU9Iml0YWxpYyIgZmlsbD0iIzBmMTcyYSIgdGV4dC1hbmNob3I9Im1p'
    'ZGRsZSI+4oirPC90ZXh0PgoKICA8IS0tIEdvbGQgQm9va21hcmsgLyBTZWFsIFJpYmJvbiAtLT4K'
    'ICA8cGF0aCBkPSJNIDQwIDE2IEwgNTIgMTYgTCA1MiAzOCBMIDQ2IDMyIEwgNDAgMzggWiIgZmls'
    'bD0idXJsKCNnb2xkR3JhZCkiLz4KPC9zdmc+Cg=='
)


def render_commentarium_logo_pixbuf(size: int = 32) -> GdkPixbuf.Pixbuf:
    """Render the embedded CommentariuM SVG logo at the given size, with a pure-Cairo vector fallback."""
    try:
        loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
        loader.set_size(size, size)
        loader.write(base64.b64decode(COMMENTARIUM_LOGO_SVG_B64))
        loader.close()
        pb = loader.get_pixbuf()
        if pb is not None:
            return pb
    except Exception:
        pass

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surface)
    s = size / 128.0
    cr.scale(s, s)

    # Outer badge
    cr.set_source_rgb(0.10, 0.13, 0.20)
    cr.rectangle(8, 8, 112, 112)
    cr.fill_preserve()
    cr.set_source_rgb(0.22, 0.74, 0.97)
    cr.set_line_width(4.0)
    cr.stroke()

    # Graph paper sheet
    cr.set_source_rgb(0.96, 0.97, 0.99)
    cr.move_to(24, 16)
    cr.line_to(84, 16)
    cr.line_to(104, 36)
    cr.line_to(104, 112)
    cr.line_to(24, 112)
    cr.close_path()
    cr.fill()

    # Folded corner
    cr.set_source_rgb(0.78, 0.83, 0.89)
    cr.move_to(84, 16)
    cr.line_to(84, 36)
    cr.line_to(104, 36)
    cr.close_path()
    cr.fill()

    # Gold ribbon
    cr.set_source_rgb(0.96, 0.68, 0.12)
    cr.move_to(38, 16)
    cr.line_to(50, 16)
    cr.line_to(50, 38)
    cr.line_to(44, 32)
    cr.line_to(38, 38)
    cr.close_path()
    cr.fill()

    # Integral sign
    cr.set_source_rgb(0.06, 0.09, 0.16)
    cr.select_font_face("Serif", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(58)
    cr.move_to(46, 88)
    cr.show_text("∫")

    return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)


class MainWindow(Gtk.Window):
    RECENT_FILES_PATH = os.path.expanduser("~/.config/smath_clone/recent_files.json")
    MAX_RECENT_FILES = 10

    def __init__(self):
        super().__init__(title="CommentariuM — A4 Mathematical Notebook")
        self.set_resizable(True)
        self.set_default_size(1408, 880)  # 10% wider than the original 1280
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_size_request(360, 300)
        self.connect("destroy", Gtk.main_quit)

        try:
            logo_pb = render_commentarium_logo_pixbuf(128)
            if logo_pb is not None:
                self.set_icon(logo_pb)
        except Exception:
            pass

        self._updating_style_combo = False
        self._updating_decimals_combo = False
        self._updating_box_eq_btn = False
        self.recent_files = self._load_recent_files()

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.canvas = MathCanvas()
        self.toc_pane = TOCPane(self.canvas)
        self.symbols_pane = SymbolsPane(self.canvas)
        self.canvas.on_toc_updated = self.toc_pane.refresh
        self.canvas.on_zoom_changed = self._on_zoom_updated
        self.canvas.on_selection_changed = self._on_canvas_selection_changed

        # Inner horizontal split: Center A4 Worksheet Canvas | RHS Math Symbols Pane
        self.rpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.rpaned.set_wide_handle(True)
        self.rpaned.pack1(self.canvas, resize=True, shrink=True)
        self.rpaned.pack2(self.symbols_pane, resize=False, shrink=True)
        self.rpaned.set_position(948)  # give the extra width to the canvas

        # Outer horizontal split: LHS Table of Contents | (Center Canvas + RHS Symbols)
        self.hpaned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.hpaned.set_wide_handle(True)
        self.hpaned.pack1(self.toc_pane, resize=False, shrink=True)
        self.hpaned.pack2(self.rpaned, resize=True, shrink=True)
        self.hpaned.set_position(210)

        toolbar = self._build_toolbar()
        statusbar = self._build_statusbar()

        vbox.pack_start(toolbar, False, False, 0)
        vbox.pack_start(self.hpaned, True, True, 0)
        vbox.pack_start(statusbar, False, False, 0)
        self.add(vbox)

        loaded_initial = False
        cli_file = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
        target_file = cli_file or (self.recent_files[0] if self.recent_files else None)
        if target_file and os.path.isfile(target_file):
            try:
                self.canvas.load_from_file(target_file)
                self._add_recent_file(target_file)
                self._update_window_title()
                if hasattr(self, "status_label"):
                    self.status_label.set_text(f"Opened last file: {target_file}")
                loaded_initial = True
            except Exception:
                loaded_initial = False

        if not loaded_initial:
            self._populate_starter_examples()
        self.toc_pane.refresh()

    def _load_recent_files(self) -> list:
        try:
            if os.path.isfile(self.RECENT_FILES_PATH):
                with open(self.RECENT_FILES_PATH, "r", encoding="utf-8") as f:
                    items = json.load(f)
                if isinstance(items, list):
                    return [str(p) for p in items if isinstance(p, str) and os.path.isfile(p)][
                        : self.MAX_RECENT_FILES
                    ]
        except Exception:
            pass
        return []

    def _save_recent_files(self):
        try:
            os.makedirs(os.path.dirname(self.RECENT_FILES_PATH), exist_ok=True)
            with open(self.RECENT_FILES_PATH, "w", encoding="utf-8") as f:
                json.dump(self.recent_files[: self.MAX_RECENT_FILES], f, indent=2)
        except Exception:
            pass

    def _add_recent_file(self, filepath: str):
        if not filepath:
            return
        abspath = os.path.abspath(filepath)
        self.recent_files = [abspath] + [p for p in self.recent_files if os.path.abspath(p) != abspath]
        self.recent_files = self.recent_files[: self.MAX_RECENT_FILES]
        self._save_recent_files()
        self._rebuild_recent_files_submenu()

    def _clear_recent_files(self):
        self.recent_files = []
        self._save_recent_files()
        self._rebuild_recent_files_submenu()
        if hasattr(self, "status_label"):
            self.status_label.set_text("Cleared recent files list.")

    def _open_recent_file(self, filepath: str):
        if not filepath or not os.path.isfile(filepath):
            self.recent_files = [p for p in self.recent_files if p != filepath]
            self._save_recent_files()
            self._rebuild_recent_files_submenu()
            if hasattr(self, "status_label"):
                self.status_label.set_text(f"Recent file not found: {filepath}")
            return
        try:
            self.canvas.load_from_file(filepath)
            self._add_recent_file(filepath)
            self._update_window_title()
            if hasattr(self, "status_label"):
                self.status_label.set_text(f"Opened: {filepath}")
        except Exception as exc:
            if hasattr(self, "status_label"):
                self.status_label.set_text(f"Failed to open file: {exc}")

    def _rebuild_recent_files_submenu(self):
        if not hasattr(self, "recent_files_menu") or self.recent_files_menu is None:
            return
        for child in list(self.recent_files_menu.get_children()):
            self.recent_files_menu.remove(child)

        existing = [p for p in self.recent_files if os.path.isfile(p)]
        if not existing:
            empty_item = Gtk.MenuItem(label="(No recent files)")
            empty_item.set_sensitive(False)
            self.recent_files_menu.append(empty_item)
        else:
            for idx, fpath in enumerate(existing, start=1):
                base = os.path.basename(fpath)
                parent_dir = os.path.dirname(fpath)
                mi = Gtk.MenuItem(label=f"{idx}. {base}   ({parent_dir})")
                mi.connect("activate", lambda _mi, p=fpath: self._open_recent_file(p))
                self.recent_files_menu.append(mi)
            self.recent_files_menu.append(Gtk.SeparatorMenuItem())
            clear_mi = Gtk.MenuItem(label="Clear Recent Files")
            clear_mi.connect("activate", lambda _mi: self._clear_recent_files())
            self.recent_files_menu.append(clear_mi)

        self.recent_files_menu.show_all()

    def do_key_press_event(self, event):
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        keyname = Gdk.keyval_name(event.keyval)

        if ctrl:
            if keyname in ("a", "A"):
                if not any(b.editing for b in self.canvas.boxes):
                    self.canvas.select_all_boxes()
                    return True
            elif keyname in ("v", "V"):
                if self.canvas.paste_from_clipboard(open_dialog_if_empty=False):
                    return True
            elif keyname in ("n", "N"):
                self._on_file_new()
                return True
            elif keyname in ("o", "O"):
                self._on_file_open()
                return True
            elif keyname in ("s", "S"):
                if shift:
                    self._on_file_save_as()
                else:
                    self._on_file_save()
                return True
            elif keyname in ("e", "E", "p", "P"):
                self._on_file_export_pdf()
                return True
            elif keyname in ("plus", "equal", "KP_Add"):
                self.canvas.zoom_in()
                return True
            elif keyname in ("minus", "underscore", "KP_Subtract"):
                self.canvas.zoom_out()
                return True
            elif keyname in ("0", "KP_0"):
                self.canvas.reset_zoom()
                return True

        # Sheet cursor gets keys first (before GTK uses arrows/Enter for focus navigation),
        # unless another control such as the TOC list has the keyboard focus.
        focus = self.get_focus()
        focus_is_input = isinstance(
            focus, (Gtk.Entry, Gtk.TextView, Gtk.TreeView, Gtk.ListBox, Gtk.ListBoxRow, Gtk.ComboBox)
        ) and not focus.is_ancestor(self.canvas)
        if not focus_is_input and self.canvas.sheet_cursor_visible():
            if self.canvas.handle_sheet_cursor_key(event):
                return True

        res = Gtk.Window.do_key_press_event(self, event)
        if not res:
            if keyname in ("Delete", "BackSpace") and self.canvas.selected_boxes:
                if not any(b.editing for b in self.canvas.selected_boxes):
                    self.canvas.remove_selected_boxes()
                    return True
            if self.canvas.selected_box is not None and not self.canvas.selected_box.editing:
                return self.canvas.selected_box.on_key_press(self.canvas.selected_box, event)
        return res

    def _make_menu_button(self, label_text: str, tooltip: str, items: list) -> Gtk.MenuButton:
        menu_btn = Gtk.MenuButton(label=label_text)
        menu_btn.set_relief(Gtk.ReliefStyle.NONE)
        menu_btn.set_can_focus(False)
        menu_btn.set_tooltip_text(tooltip)

        menu = Gtk.Menu()
        for entry in items:
            if entry[0] is None:
                menu.append(Gtk.SeparatorMenuItem())
            else:
                label, cb = entry[0], entry[1]
                mi = Gtk.MenuItem(label=label)
                mi.connect("activate", lambda _mi, fn=cb: fn())
                menu.append(mi)
                if len(entry) >= 3 and entry[2]:
                    setattr(self, entry[2], mi)
        menu.show_all()
        menu_btn.set_popup(menu)
        return menu_btn

    def _build_file_menu_button(self) -> Gtk.MenuButton:
        menu_btn = Gtk.MenuButton(label="File ▾")
        menu_btn.set_relief(Gtk.ReliefStyle.NONE)
        menu_btn.set_can_focus(False)
        menu_btn.set_tooltip_text("File menu: New, Open, Recent Files, Save (Ctrl+S), Save As, Export PDF")

        menu = Gtk.Menu()

        def add_item(label, cb):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _mi: cb())
            menu.append(mi)
            return mi

        add_item("New  (Ctrl+N)", self._on_file_new)
        add_item("Open...  (Ctrl+O)", self._on_file_open)

        recent_parent = Gtk.MenuItem(label="Recent Files")
        self.recent_files_menu = Gtk.Menu()
        recent_parent.set_submenu(self.recent_files_menu)
        menu.append(recent_parent)
        self._rebuild_recent_files_submenu()

        menu.append(Gtk.SeparatorMenuItem())
        add_item("Save  (Ctrl+S)", self._on_file_save)
        add_item("Save As...  (Ctrl+Shift+S)", self._on_file_save_as)
        menu.append(Gtk.SeparatorMenuItem())
        add_item("Export PDF...  (Ctrl+E)", self._on_file_export_pdf)

        menu.show_all()
        menu_btn.set_popup(menu)
        return menu_btn

    def _build_insert_menu_button(self) -> Gtk.MenuButton:
        return self._make_menu_button(
            "Insert ▾",
            "Insert Plot, Picture/Image, Table, Text Box, Math Box, or New A4 Page",
            [
                ("Plot  (Centered 2D Plot)", lambda: self.canvas.create_plot_box()),
                ("Image / Picture...  (Ctrl+V)", lambda: self.canvas.paste_from_clipboard(open_dialog_if_empty=True)),
                ("Table  (cell data usable in calculations)", lambda: self.canvas.create_table_box()),
                (None, None),
                (
                    "Text Box  (or type \" in empty box)",
                    lambda: self.canvas.create_text_box(
                        60, self.canvas._next_spawn_y(), style_name="normal", edit=True
                    ),
                ),
                ("Math Equation Box", lambda: self.canvas.create_box(60, self.canvas._next_spawn_y(), edit=True)),
                (None, None),
                ("New A4 Page  (or Enter at bottom of page)", self.canvas.add_page),
            ],
        )

    def _build_view_menu_button(self) -> Gtk.MenuButton:
        return self._make_menu_button(
            "View ▾",
            "View menu: Zoom, TOC Pane, Symbols Pane, Grid, Theme",
            [
                ("Zoom In  (Ctrl++)", self.canvas.zoom_in),
                ("Zoom Out  (Ctrl+-)", self.canvas.zoom_out),
                ("Reset Zoom (100%)  (Ctrl+0)", self.canvas.reset_zoom, "zoom_reset_menuitem"),
                (None, None),
                ("Show / Hide Table of Contents (TOC)", self._on_toggle_toc),
                ("Show / Hide Math Symbols Pane", self._on_toggle_symbols),
                (None, None),
                ("Show / Hide Graph-Paper Grid", lambda: self._on_toggle_grid(None)),
                ("Toggle Dark / Light Theme", lambda: self._on_toggle_theme(None)),
            ],
        )

    def _build_toolbar(self) -> Gtk.Toolbar:
        bar = Gtk.Toolbar()
        bar.set_show_arrow(True)
        bar.set_style(Gtk.ToolbarStyle.TEXT)

        def add_widget(w):
            item = Gtk.ToolItem()
            item.add(w)
            bar.insert(item, -1)

        def add_btn(label, tooltip, callback):
            btn = Gtk.Button(label=label)
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.set_can_focus(False)
            btn.set_tooltip_text(tooltip)
            btn.connect("clicked", lambda _b: callback())
            add_widget(btn)
            return btn

        def add_sep():
            bar.insert(Gtk.SeparatorToolItem(), -1)

        # App Logo & Brand Name in Toolbar
        brand_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        brand_box.set_margin_start(6)
        brand_box.set_margin_end(6)
        brand_box.set_margin_top(2)
        brand_box.set_margin_bottom(2)
        try:
            tb_logo = render_commentarium_logo_pixbuf(48)
            if tb_logo is not None:
                brand_img = Gtk.Image.new_from_pixbuf(tb_logo)
                brand_box.pack_start(brand_img, False, False, 0)
        except Exception:
            pass
        brand_lbl = Gtk.Label()
        brand_lbl.set_markup('<span size="large"><b>CommentariuM</b></span>')
        brand_box.pack_start(brand_lbl, False, False, 0)
        add_widget(brand_box)
        add_sep()

        # Top Menu Buttons: File, Insert, View
        add_widget(self._build_file_menu_button())
        add_widget(self._build_insert_menu_button())
        add_widget(self._build_view_menu_button())
        add_sep()

        # Font Styles Combo Box
        style_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        style_box.set_margin_start(4)

        self.style_combo = Gtk.ComboBoxText()
        Gtk.Widget.set_focus_on_click(self.style_combo, False)
        self.style_combo.set_tooltip_text("Select text box font style (Title, Heading 1, Heading 2, Heading 3, Normal)")
        for sid, sname in [
            ("title", "Title (22pt Bold)"),
            ("heading1", "Heading 1 (17pt Bold)"),
            ("heading2", "Heading 2 (14pt Bold)"),
            ("heading3", "Heading 3 (12pt Bold Italic)"),
            ("normal", "Normal (11.5pt)"),
        ]:
            self.style_combo.append(sid, sname)
        self.style_combo.set_active_id("normal")
        self.style_combo.connect("changed", self._on_style_combo_changed)
        style_box.pack_start(self.style_combo, False, False, 0)
        add_widget(style_box)

        add_sep()

        # Result Decimal Places Controls (per selected MathBox or group)
        dec_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        dec_box.set_margin_start(4)

        self.decimals_combo = Gtk.ComboBoxText()
        Gtk.Widget.set_focus_on_click(self.decimals_combo, False)
        self.decimals_combo.set_tooltip_text(
            "Set number of decimal places for the selected equation result(s) (or right-click an equation)"
        )
        self.decimals_combo.append("auto", "Auto")
        for d in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15]:
            self.decimals_combo.append(str(d), f"{d} dec")
        self.decimals_combo.set_active_id("auto")
        self.decimals_combo.connect("changed", self._on_decimals_combo_changed)
        dec_box.pack_start(self.decimals_combo, False, False, 0)

        dec_less_btn = Gtk.Button(label="−.0")
        dec_less_btn.set_relief(Gtk.ReliefStyle.NONE)
        dec_less_btn.set_can_focus(False)
        dec_less_btn.set_tooltip_text("Decrease decimal places for selected result(s)")
        dec_less_btn.connect("clicked", lambda _b: self._step_selected_decimals(-1))
        dec_box.pack_start(dec_less_btn, False, False, 0)

        dec_more_btn = Gtk.Button(label="+.00")
        dec_more_btn.set_relief(Gtk.ReliefStyle.NONE)
        dec_more_btn.set_can_focus(False)
        dec_more_btn.set_tooltip_text("Increase decimal places for selected result(s)")
        dec_more_btn.connect("clicked", lambda _b: self._step_selected_decimals(1))
        dec_box.pack_start(dec_more_btn, False, False, 0)

        add_widget(dec_box)

        add_sep()

        # Box Equation Toggle Button
        self.box_eq_btn = Gtk.ToggleButton(label="□ Box Eq")
        self.box_eq_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.box_eq_btn.set_can_focus(False)
        self.box_eq_btn.set_tooltip_text("Draw a solid border frame around the selected equation(s)")
        self.box_eq_btn.connect("toggled", self._on_box_eq_toggled)
        add_widget(self.box_eq_btn)

        # Figure Caption Button (enabled when a plot or picture is selected)
        self.caption_btn = add_btn(
            CAPTION_BTN_LABEL,
            "Add or edit the caption of the selected figure or table (the caption stays attached to it)",
            self._on_caption_btn_clicked,
        )
        self.caption_btn.set_sensitive(False)

        return bar

    def _on_caption_btn_clicked(self):
        sel = self.canvas.selected_box
        if isinstance(sel, (PlotBox, ImageBox, TableBox)):
            open_figure_caption_dialog(sel)

    def _on_style_combo_changed(self, combo):
        if self._updating_style_combo:
            return
        style_id = combo.get_active_id()
        if style_id:
            self.canvas.insert_or_style_text_box(style_id)

    def _on_decimals_combo_changed(self, combo):
        if self._updating_decimals_combo:
            return
        dec_id = combo.get_active_id()
        if not dec_id:
            return
        if dec_id == "auto":
            self.canvas.set_decimal_places_for_selected(None)
        elif dec_id.isdigit():
            self.canvas.set_decimal_places_for_selected(int(dec_id))

    def _step_selected_decimals(self, delta: int):
        sel = self.canvas.selected_box
        if not isinstance(sel, MathBox):
            math_sel = [b for b in self.canvas.selected_boxes if isinstance(b, MathBox)]
            sel = math_sel[-1] if math_sel else None
        if sel is None:
            return
        cur = sel.decimal_places if sel.decimal_places is not None else 3
        new_dec = max(0, min(15, cur + delta))
        self.canvas.set_decimal_places_for_selected(new_dec)

    def _on_box_eq_toggled(self, btn):
        if self._updating_box_eq_btn:
            return
        self.canvas.toggle_boxed_for_selected(force_state=btn.get_active())

    def _on_canvas_selection_changed(self, box):
        if hasattr(self, "style_combo"):
            self._updating_style_combo = True
            if isinstance(box, TextBox):
                self.style_combo.set_active_id(box.style_name)
                self.canvas.active_text_style = box.style_name
            else:
                self.style_combo.set_active_id("normal")
                self.canvas.active_text_style = "normal"
            self._updating_style_combo = False

        if hasattr(self, "decimals_combo"):
            self._updating_decimals_combo = True
            if isinstance(box, MathBox):
                if box.decimal_places is None:
                    self.decimals_combo.set_active_id("auto")
                else:
                    dec_str = str(box.decimal_places)
                    if not self.decimals_combo.set_active_id(dec_str):
                        self.decimals_combo.append(dec_str, f"{box.decimal_places} dec")
                        self.decimals_combo.set_active_id(dec_str)
            else:
                self.decimals_combo.set_active_id("auto")
            self._updating_decimals_combo = False

        if hasattr(self, "box_eq_btn"):
            self._updating_box_eq_btn = True
            self.box_eq_btn.set_active(isinstance(box, MathBox) and bool(box.boxed))
            self._updating_box_eq_btn = False

        if hasattr(self, "caption_btn"):
            self.caption_btn.set_sensitive(isinstance(box, (PlotBox, ImageBox, TableBox)))

    def _on_zoom_updated(self, zoom_val: float):
        pct = int(round(zoom_val * 100))
        if hasattr(self, "zoom_reset_menuitem") and self.zoom_reset_menuitem is not None:
            self.zoom_reset_menuitem.set_label(f"Reset Zoom to 100% (Current: {pct}%)  (Ctrl+0)")
        if hasattr(self, "status_label") and self.status_label is not None:
            self.status_label.set_text(
                f"Zoom: {pct}%  |  File: Ctrl+S Save, Ctrl+E Export PDF  |  Images: Drag corner/edges to resize"
            )

    # ------------------------------------------------------------------------
    # File Menu Actions (New, Open, Save, Save As, Export PDF)
    # ------------------------------------------------------------------------

    def _update_window_title(self):
        if self.canvas.current_file_path:
            fname = os.path.basename(self.canvas.current_file_path)
            self.set_title(f"{fname} — CommentariuM")
        else:
            self.set_title("CommentariuM — A4 Mathematical Notebook")

    def _on_file_new(self):
        self.canvas.new_worksheet()
        self._update_window_title()
        if hasattr(self, "status_label"):
            self.status_label.set_text("Created new CommentariuM worksheet.")

    def _on_file_open(self):
        dlg = Gtk.FileChooserDialog(
            title="Open CommentariuM Worksheet",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        flt = Gtk.FileFilter()
        flt.set_name("CommentariuM Worksheet (*.cmm, *.smath, *.json)")
        flt.add_pattern("*.cmm")
        flt.add_pattern("*.smath")
        flt.add_pattern("*.smath.json")
        flt.add_pattern("*.json")
        dlg.add_filter(flt)
        if dlg.run() == Gtk.ResponseType.OK:
            path = dlg.get_filename()
            dlg.destroy()
            if path and os.path.isfile(path):
                try:
                    self.canvas.load_from_file(path)
                    self._add_recent_file(path)
                    self._update_window_title()
                    if hasattr(self, "status_label"):
                        self.status_label.set_text(f"Opened: {path}")
                except Exception as exc:
                    if hasattr(self, "status_label"):
                        self.status_label.set_text(f"Failed to open file: {exc}")
        else:
            dlg.destroy()

    def _on_file_save(self):
        if self.canvas.current_file_path:
            try:
                self.canvas.save_to_file(self.canvas.current_file_path)
                self._add_recent_file(self.canvas.current_file_path)
                self._update_window_title()
                if hasattr(self, "status_label"):
                    self.status_label.set_text(f"Saved: {self.canvas.current_file_path}")
            except Exception as exc:
                if hasattr(self, "status_label"):
                    self.status_label.set_text(f"Error saving file: {exc}")
        else:
            self._on_file_save_as()

    def _on_file_save_as(self):
        dlg = Gtk.FileChooserDialog(
            title="Save CommentariuM Worksheet As",
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        dlg.set_do_overwrite_confirmation(True)
        default_name = (
            os.path.basename(self.canvas.current_file_path)
            if self.canvas.current_file_path
            else "notebook.cmm.json"
        )
        dlg.set_current_name(default_name)
        if dlg.run() == Gtk.ResponseType.OK:
            path = dlg.get_filename()
            dlg.destroy()
            if path:
                if not (path.endswith(".json") or path.endswith(".smath") or path.endswith(".cmm")):
                    path += ".cmm.json"
                try:
                    self.canvas.save_to_file(path)
                    self._add_recent_file(path)
                    self._update_window_title()
                    if hasattr(self, "status_label"):
                        self.status_label.set_text(f"Saved: {path}")
                except Exception as exc:
                    if hasattr(self, "status_label"):
                        self.status_label.set_text(f"Error saving file: {exc}")
        else:
            dlg.destroy()

    def _on_file_export_pdf(self):
        dlg = Gtk.FileChooserDialog(
            title="Export A4 Worksheet to PDF",
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        dlg.set_do_overwrite_confirmation(True)
        dlg.set_current_name("worksheet.pdf")
        flt = Gtk.FileFilter()
        flt.set_name("PDF Document (*.pdf)")
        flt.add_pattern("*.pdf")
        dlg.add_filter(flt)
        if dlg.run() == Gtk.ResponseType.OK:
            path = dlg.get_filename()
            dlg.destroy()
            if path:
                if not path.lower().endswith(".pdf"):
                    path += ".pdf"
                try:
                    self.canvas.export_pdf(path)
                    if hasattr(self, "status_label"):
                        self.status_label.set_text(f"Exported PDF: {path}")
                except Exception as exc:
                    if hasattr(self, "status_label"):
                        self.status_label.set_text(f"Error exporting PDF: {exc}")
        else:
            dlg.destroy()

    def _build_statusbar(self) -> Gtk.Box:
        sbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sbar.set_margin_start(10)
        sbar.set_margin_end(10)
        sbar.set_margin_top(3)
        sbar.set_margin_bottom(3)

        self.status_label = Gtk.Label(
            label="File: Ctrl+S Save, Ctrl+E Export PDF  |  Zoom: Ctrl+Scroll or −/+  |  Images: Drag corner/edges to resize"
        )
        self.status_label.set_xalign(0.0)
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)
        sbar.pack_start(self.status_label, True, True, 0)
        return sbar

    def _on_toggle_toc(self):
        if self.toc_pane.get_visible():
            self.toc_pane.hide()
        else:
            self.toc_pane.show_all()
            self.toc_pane.refresh()

    def _on_toggle_symbols(self):
        if self.symbols_pane.get_visible():
            self.symbols_pane.hide()
        else:
            self.symbols_pane.show_all()

    def _on_toggle_grid(self, _btn):
        self.canvas.show_grid = not self.canvas.show_grid
        self.canvas.event_box.queue_draw()

    def _on_toggle_theme(self, _btn):
        self.canvas.theme_name = "light" if self.canvas.theme_name == "dark" else "dark"
        self.canvas.desk_box.queue_draw()
        self.canvas.event_box.queue_draw()
        for b in self.canvas.boxes:
            b.queue_draw()

    def _populate_starter_examples(self):
        """Create a sample A4 worksheet showcasing multi-level Headings, 2D live equations, sheet functions/vectors, and a 2D Plot."""
        self.canvas.create_text_box(60, 40, style_name="title", text="Engineering Calculation Sheet", edit=False)
        self.canvas.create_text_box(60, 88, style_name="heading1", text="1. Section Properties", edit=False)
        self.canvas.create_text_box(60, 122, style_name="heading2", text="1.1 Circular Cross-Section", edit=False)
        self.canvas.create_text_box(
            60,
            152,
            style_name="normal",
            text="Press Enter inside any box to exit and move down one line. Use the RHS pane for symbols.",
            edit=False,
        )

        # 1) r := 5
        b1 = self.canvas.create_box(60, 185, edit=False)
        b1.insert_char("r")
        b1.insert_char(":=")
        b1.insert_char("5")

        # 2) A := pi * r^2 =
        b2 = self.canvas.create_box(220, 180, edit=False)
        b2.insert_char("A")
        b2.insert_char(":=")
        b2.insert_char("π")
        b2.insert_char("·")
        b2.insert_char("r")
        b2.insert_superscript()
        b2.insert_char("2")
        b2.step_out_slot()
        b2.insert_char("=")

        self.canvas.create_text_box(60, 232, style_name="heading1", text="2. Combined Stress Factor", edit=False)
        self.canvas.create_text_box(60, 266, style_name="heading3", text="2.1.1 Normalized Ratio", edit=False)

        # 3) y := (sqrt(r^2 + 11) + 4) / (2 * r) =
        b3 = self.canvas.create_box(60, 298, edit=False)
        b3.insert_char("y")
        b3.insert_char(":=")
        b3.insert_fraction()
        b3.cursor_seq = b3.root.items[-1].num
        b3.cursor_idx = 0
        b3.insert_sqrt()
        b3.insert_char("r")
        b3.insert_superscript()
        b3.insert_char("2")
        b3.step_out_slot()
        b3.insert_char("+")
        b3.insert_char("1")
        b3.insert_char("1")
        b3.step_out_slot()
        b3.insert_char("+")
        b3.insert_char("4")
        b3.step_out_slot()
        b3.insert_char("2")
        b3.insert_char("·")
        b3.insert_char("r")
        b3.step_out_slot()
        b3.insert_char("=")

        self.canvas.create_text_box(60, 376, style_name="heading1", text="3. Harmonic Response & Measured Data", edit=False)
        self.canvas.create_text_box(
            60,
            410,
            style_name="normal",
            text="Define functions f(x), g(x) for plot lines and vectors vx, vy for discrete plot symbols:",
            edit=False,
        )

        # 4) Sheet Function 1: f(x) := 0.2 · r · sin(x)
        bf = self.canvas.create_box(60, 442, edit=False)
        bf.insert_char("f")
        bf.insert_parens()
        bf.insert_char("x")
        bf.step_out_slot()
        bf.insert_char(":=")
        bf.insert_text_tokens("0.2")
        bf.insert_char("·")
        bf.insert_char("r")
        bf.insert_char("·")
        bf.insert_text_tokens("sin")
        bf.insert_parens()
        bf.insert_char("x")
        bf.step_out_slot()

        # 5) Sheet Function 2: g(x) := 0.5 · cos(x)
        bg = self.canvas.create_box(380, 442, edit=False)
        bg.insert_char("g")
        bg.insert_parens()
        bg.insert_char("x")
        bg.step_out_slot()
        bg.insert_char(":=")
        bg.insert_text_tokens("0.5")
        bg.insert_char("·")
        bg.insert_text_tokens("cos")
        bg.insert_parens()
        bg.insert_char("x")
        bg.step_out_slot()

        # 6) Sheet Vector vx := [-5, -3, -1.5, 0, 1.5, 3, 5]
        bvx = self.canvas.create_box(60, 484, edit=False)
        bvx.insert_text_tokens("vx")
        bvx.insert_char(":=")
        bvx.insert_text_tokens("[-5, -3, -1.5, 0, 1.5, 3, 5]")

        # 7) Sheet Vector vy := [0.92, -0.18, -0.98, 0, 0.99, 0.16, -0.94]
        bvy = self.canvas.create_box(60, 522, edit=False)
        bvy.insert_text_tokens("vy")
        bvy.insert_char(":=")
        bvy.insert_text_tokens("[0.92, -0.18, -0.98, 0, 0.99, 0.16, -0.94]")

        # 8) PlotBox referencing sheet functions "f; g" (lines) and sheet vectors "vx, vy" (symbols)
        self.canvas.create_plot_box(
            60,
            568,
            width=560,
            height=295,
            title="Sine wave and discrete measurements",
            func_expr="f; g",
            discrete_data="vx, vy",
            symbol_style="circle",
            connect_discrete=False,
            x_min=-6.0,
            x_max=6.0,
            y_min=-1.5,
            y_max=1.5,
            x_scale="linear",
            y_scale="linear",
        )

        self.canvas.select_box(None)
        self.canvas.recalculate_worksheet()


if __name__ == "__main__":
    import time

    try:
        _initial_mtime = os.path.getmtime(os.path.abspath(__file__))
    except OSError:
        _initial_mtime = None

    def _auto_reload_on_change():
        if _initial_mtime is not None:
            try:
                cur_mtime = os.path.getmtime(os.path.abspath(__file__))
                if cur_mtime > _initial_mtime and (time.time() - cur_mtime) >= 1.5:
                    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])
            except OSError:
                pass
        return True

    GLib.timeout_add(800, _auto_reload_on_change)
    window = MainWindow()
    window.show_all()
    Gtk.main()
