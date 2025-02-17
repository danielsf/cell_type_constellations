"""
This module will define a class for consistently turning continuous
values into a color scheme
"""

import matplotlib
import numpy as np


class ContinuousColorMap(object):

    def __init__(
            self,
            fov,
            centroid_list,
            color_by):

        self._color_map = matplotlib.colormaps['cool']
        self._fov = fov
        self._color_by = color_by

        color_values = [
            c.annotation['statistics'][color_by]['mean']
            for c in centroid_list
        ]
        color_vmin = min(color_values)
        color_vmax = max(color_values)
        normalizer = matplotlib.colors.Normalize(
            vmin=color_vmin,
            vmax=color_vmax
        )

        self._normalizer = normalizer
        self._vmin = color_vmin
        self._vmax = color_vmax

    @property
    def color_by(self):
        return self._color_by

    @property
    def color_map(self):
        return self._color_map

    @property
    def fov(self):
        return self._fov

    @property
    def normalizer(self):
        return self._normalizer

    @property
    def vmin(self):
        return self._vmin

    @property
    def vmax(self):
        return self._vmax

    def value_to_rgb(self, value):
        return matplotlib.colors.rgb2hex(
            self.color_map(self.normalizer(value))
        )

    def get_colorbar_code(self):

        dx = np.round(self.fov.width*0.1)
        dy = np.round(self.fov.height*0.2)
        self.fov.width = self.fov.width + 2*dx

        color_values = np.linspace(self.vmin, self.vmax, 100)
        color_hexes = [self.value_to_rgb(v) for v in color_values]

        x0 = self.fov.width-3*dx//2
        y0 = dy
        color_bar_code = get_colorbar_svg(
            x0=x0,
            y0=y0,
            x1=x0+dx//2,
            y1=self.fov.height-dy,
            color_list=color_hexes,
            value_list=color_values,
            color_by_parameter=self.color_by
        )
        return color_bar_code


def get_colorbar_svg(
        x0,
        y0,
        x1,
        y1,
        color_list,
        value_list,
        color_by_parameter,
        fontsize=15):

    n_steps = len(color_list)

    width = x1-x0
    height = (y1-y0)/n_steps
    html = ""

    html += f"""
    <text x="{x0-width}px" y="{y0-3*height}px" font-size="{fontsize}">
    {color_by_parameter}
    </text>
    """

    for i_rect, (v, c) in enumerate(zip(value_list[-1::-1],
                                        color_list[-1::-1])):
        color_hex = matplotlib.colors.rgb2hex(c)
        this = "<a>"
        this += f"""<rect x="{x0}px" y="{y0+i_rect*height}px" height="{height}px" width="{width}px" fill="{color_hex}"/>"""  # noqa: E501
        this += f"""
        <title>
        {v:.2f}
        </title>
        </a>
        """
        html += this

    idx_to_tag = (0, n_steps//4, n_steps//2, 3*n_steps//4, n_steps-1)

    for i_tag, val_tag in zip(idx_to_tag[-1::-1], idx_to_tag):
        this = f"""<text x="{x0+11*width//10}px" y="{y0+i_tag*height+height//2}px" font-size="{fontsize}">{value_list[val_tag]:.2e}</text>"""  # noqa: E501
        html += this

    return html
