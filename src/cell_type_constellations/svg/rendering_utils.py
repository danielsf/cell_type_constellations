import h5py
import json
import matplotlib
import numbers
import numpy as np


from cell_type_constellations.svg.centroid import Centroid
from cell_type_constellations.svg.connection import Connection
from cell_type_constellations.svg.hull import CompoundBareHull

from cell_type_mapper.taxonomy.taxonomy_tree import (
    TaxonomyTree
)


def render_fov_from_hdf5(
        hdf5_path,
        centroid_level,
        hull_level,
        base_url,
        color_by,
        fill_hulls=False):
    """
    Create and return the SVG code for a single configuration of
    a constellation plot.

    Parametrs
    ---------
    hd5_path:
        The path to the SVG cache HDF5 file created by
        cell_type_constellations.svg.serialize_svg_data.write_out_svg_cache
    centroid_level:
        a str. The level of the cell type taxonomy at which to visualize
        the nodes and connections in the constellation plot
    hull_level:
        a str. The level of the cell type taxonomy at which to visualize
        contours in the constellation plot (if None, do not visualize
        contours)
    base_url:
        a str. The base URL of the knowledge graph to which nodes in the
        constellation plot will link (if None, clicking on a node will
        link to nowhere)
    color_by:
        a str. The level or aggregate stat by which to color the nodes
        in the constellation plot
    fill_hulls:
        if True (and there are contours being visualized in the constellation
        plot), fill in the contours

    Returns
    -------
    A string containing the SVG code for the constellation plot
    visualization. Suitable for viewing in a web browser.
    """

    mpl_color_map = matplotlib.colormaps['cool']

    with h5py.File(hdf5_path, 'r', swmr=True) as src:
        width = src['fov/width'][()]
        height = src['fov/height'][()]
        color_lookup = json.loads(
            src['color_lookup'][()].decode('utf-8'))
        taxonomy_tree = TaxonomyTree(
                data=json.loads(src['taxonomy_tree'][()].decode('utf-8'))
        )

    centroid_lookup = centroid_lookup_from_hdf5(
        hdf5_path=hdf5_path,
        level=centroid_level,
        color_lookup=color_lookup,
        color_by=color_by,
        color_map=mpl_color_map)

    connection_list = connection_list_from_hdf5(
        hdf5_path=hdf5_path,
        level=centroid_level,
        centroid_lookup=centroid_lookup
    )

    if hull_level is not None:
        hull_lookup = hull_lookup_from_hdf5(
            hdf5_path=hdf5_path,
            level=hull_level
        )
    else:
        hull_lookup = dict()

    centroid_list = list(centroid_lookup.values())
    hull_list = list(hull_lookup.values())

    result = render_fov(
        centroid_list=centroid_list,
        connection_list=connection_list,
        hull_list=hull_list,
        base_url=base_url,
        width=width,
        height=height,
        taxonomy_tree=taxonomy_tree,
        color_by=color_by,
        color_map=mpl_color_map,
        fill_hulls=fill_hulls)

    return result


def render_fov(
        centroid_list,
        color_by,
        connection_list,
        hull_list,
        base_url,
        height,
        width,
        taxonomy_tree,
        color_map,
        fill_hulls=False):

    dx = np.round(width*0.1)
    dy = np.round(height*0.2)
    width += 2*dx

    result = (
            f'<svg height="{height}px" width="{width}px" '
            'xmlns="http://www.w3.org/2000/svg">\n'
        )

    # add color bar code if needed
    color_bar_code = None
    if color_by not in taxonomy_tree.hierarchy:
        color_values = [
            c.get_stat(color_by)['mean']
            for c in centroid_list
        ]
        color_vmin = min(color_values)
        color_vmax = max(color_values)
        normalizer = matplotlib.colors.Normalize(
            vmin=color_vmin,
            vmax=color_vmax
        )

        color_values = np.linspace(color_vmin, color_vmax, 100)
        color_hexes = [matplotlib.colors.rgb2hex(
                           color_map(normalizer(v))
                       )
                       for v in color_values]

        x0 = width-3*dx//2
        y0 = dy
        color_bar_code = get_colorbar_svg(
            x0=x0,
            y0=y0,
            x1=x0+dx//2,
            y1=height-dy,
            color_list=color_hexes,
            value_list=color_values,
            color_by_parameter=color_by
        )

    centroid_code = render_centroid_list(
                        centroid_list=centroid_list,
                        base_url=base_url,
                        taxonomy_tree=taxonomy_tree,
                        color_by=color_by)

    connection_code = render_connection_list(connection_list=connection_list)

    hull_code = render_hull_list(
        hull_list,
        base_url=base_url,
        taxonomy_tree=taxonomy_tree,
        fill=fill_hulls)

    result += hull_code + connection_code + centroid_code

    if color_bar_code is not None:
        result += color_bar_code
    result += "</svg>\n"

    return result


def render_hull_list(
        hull_list,
        base_url,
        taxonomy_tree,
        fill=False):
    hull_code = ""
    for hull in hull_list:
        hull_code += render_compound_hull(
            hull,
            base_url,
            taxonomy_tree,
            fill=fill)
    return hull_code


def render_compound_hull(
        compound_hull,
        base_url,
        taxonomy_tree,
        fill=False):
    if base_url is not None:
        url = (
            f"{base_url}/{compound_hull.relative_url}"
        )
    else:
        url = None

    level_name = taxonomy_tree.level_to_name(compound_hull.level)
    hover_msg = f"{level_name}: {compound_hull.name} -- {compound_hull.n_cells:.2e} cells"  # noqa: E501

    if url is not None:
        result = f"""    <a href="{url}">\n"""
    else:
        result = """    <a>\n"""

    for hull in compound_hull.bare_hull_list:
        result += render_path_points(
                    path_points=hull.path_points,
                    color=hull.color,
                    fill=fill)

    result += """        <title>\n"""
    result += f"""        {hover_msg}\n"""
    result += """        </title>\n"""
    result += "    </a>\n"
    return result


def render_path_points(path_points, color='green', fill=False):
    if fill:
        fill_color = color
    else:
        fill_color = 'transparent'

    path_code = ""
    for i0 in range(0, len(path_points), 4):
        src = path_points[i0, :]
        src_ctrl = path_points[i0+1, :]
        dst = path_points[i0+2, :]
        dst_ctrl = path_points[i0+3, :]

        if i0 == 0:
            path_code += f'<path d="M {src[0]} {src[1]} '

        if np.isfinite(src_ctrl).all() and np.isfinite(dst_ctrl).all():
            update = (
                f"C {src_ctrl[0]} {src_ctrl[1]} "
                f"{dst_ctrl[0]} {dst_ctrl[1]} "
                f"{dst[0]} {dst[1]} "
            )
        else:
            update = (
                f"L {dst[0]} {dst[1]} "
            )

        path_code += update

    path_code += f'" stroke="{color}" fill="{fill_color}" fill-opacity="0.1"/>\n'  # noqa: E501

    return path_code


def render_connection_list(connection_list):
    connection_code = ""
    for conn in connection_list:
        connection_code += render_connection(conn)

    print(f'n_conn {len(connection_list)}')
    return connection_code


def render_connection(this_connection):

    title = (
        f"{this_connection.src.name} "
        f"({this_connection.src_neighbor_fraction:.2e} of neighbors) "
        "-> "
        f"{this_connection.dst.name} "
        f"({this_connection.dst_neighbor_fraction:.2e} of neighbors)"
    )

    pts = this_connection.rendering_corners
    ctrl = this_connection.bezier_control_points

    result = """    <a>\n"""
    result += "        <path "
    result += f"""d="M {pts[0][0]} {pts[0][1]} """
    result += get_bezier_curve(
                src=pts[0],
                dst=pts[1],
                ctrl=ctrl[0])
    result += f"L {pts[2][0]} {pts[2][1]} "
    result += get_bezier_curve(
                src=pts[2],
                dst=pts[3],
                ctrl=ctrl[1])
    result += f"""L {pts[0][0]} {pts[0][1]}" """
    result += """stroke="transparent" fill="#bbbbbb"/>\n"""
    result += "        <title>\n"
    result += f"        {title}\n"
    result += "        </title>\n"
    result += "    </a>"

    return result


def get_bezier_curve(src, dst, ctrl):

    result = f"Q {ctrl[0]} {ctrl[1]} "
    result += f"{dst[0]} {dst[1]} "
    return result


def render_centroid_list(
        centroid_list,
        base_url,
        taxonomy_tree,
        color_by):

    centroid_code = ""
    for el in centroid_list:
        centroid_code += render_centroid(
            centroid=el,
            base_url=base_url,
            taxonomy_tree=taxonomy_tree,
            color_by=color_by)

    return centroid_code


def render_centroid(
        centroid,
        base_url,
        taxonomy_tree,
        color_by):

    level_name = taxonomy_tree.level_to_name(centroid.level)
    hover_msg = (
        f"{level_name}: {centroid.name} -- {centroid.n_cells:.2e} cells"
    )
    if color_by in taxonomy_tree.hierarchy:
        if color_by != centroid.level:
            parents = taxonomy_tree.parents(
                level=centroid.level,
                node=centroid.label
            )
            parent_level = taxonomy_tree.level_to_name(color_by)
            parent_name = taxonomy_tree.label_to_name(
                level=color_by,
                label=parents[color_by]
            )
            hover_msg += f"\n        ({parent_level}: {parent_name})"
    else:
        stats = centroid.get_stat(color_by)
        mu = stats['mean']
        std = np.sqrt(stats['variance'])
        hover_msg += f"\n        {color_by}: {mu:.2e} +/- {std:.2e}"

    if base_url is not None:
        result = f"""    <a href="{base_url}/{centroid.relative_url}">\n"""
    else:
        result = """    <a>\n"""

    result += (
        f"""        <circle r="{centroid.pixel_r}px" cx="{centroid.pixel_x}px" cy="{centroid.pixel_y}px" """  # noqa: E501
        f"""fill="{centroid.color}" stroke="transparent"/>\n"""
    )
    result += """        <title>\n"""
    result += f"""        {hover_msg}\n"""
    result += """        </title>\n"""

    result += "    </a>\n"

    return result


def centroid_list_to_hdf5(
        centroid_list,
        hdf5_path):
    by_level = dict()
    for centroid in centroid_list:
        level = centroid.level
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(centroid)
    for level in by_level:
        centroid_list_to_hdf5_single_level(
            centroid_list=by_level[level],
            hdf5_path=hdf5_path,
            level=level)


def centroid_list_to_hdf5_single_level(
        centroid_list,
        hdf5_path,
        level):

    pixel_r = np.array([
        c.pixel_r for c in centroid_list
    ])
    pixel_x = np.array([
        c.pixel_x for c in centroid_list
    ])
    pixel_y = np.array([
        c.pixel_y for c in centroid_list
    ])
    label_arr = np.array([
        c.label.encode('utf-8') for c in centroid_list
    ])
    name_arr = np.array([
        c.name.encode('utf-8') for c in centroid_list
    ])
    n_cells = np.array([
        c.n_cells for c in centroid_list
    ])
    color = np.array([
        c.color.encode('utf-8') for c in centroid_list
    ])

    stats_lookup = dict()

    for stat_key in centroid_list[0].stat_keys:
        stats_lookup[stat_key] = dict()
        this = centroid_list[0].get_stat(stat_key)
        for sub_key in this:
            stats_lookup[stat_key][sub_key] = []
    for centroid in centroid_list:
        for stat_key in centroid.stat_keys:
            this = centroid.get_stat(stat_key)
            for sub_key in this:
                stats_lookup[stat_key][sub_key].append(this[sub_key])

    with h5py.File(hdf5_path, 'a') as dst:
        if 'centroids' not in dst.keys():
            dst.create_group('centroids')
        dst_grp = dst['centroids']
        if level not in dst_grp.keys():
            dst_grp.create_group(level)
        dst_grp = dst_grp[level]
        for k, data in [('pixel_r', pixel_r),
                        ('pixel_x', pixel_x),
                        ('pixel_y', pixel_y),
                        ('label', label_arr),
                        ('name', name_arr),
                        ('n_cells', n_cells),
                        ('color', color)]:
            dst_grp.create_dataset(k, data=data)

        stat_grp = dst_grp.create_group('stats')
        for stat_key in stats_lookup:
            this_grp = stat_grp.create_group(stat_key)
            this = stats_lookup[stat_key]
            for sub_key in this:
                this_grp.create_dataset(
                    sub_key,
                    data=np.array(this[sub_key])
                )


def centroid_lookup_from_hdf5(
        hdf5_path,
        level,
        color_lookup,
        color_by,
        color_map):
    this_key = f'centroids/{level}'
    data_lookup = dict()
    stats_lookup = dict()
    with h5py.File(hdf5_path, 'r', swmr=True) as src:
        for k in ('pixel_r',
                  'pixel_x',
                  'pixel_y',
                  'label',
                  'name',
                  'n_cells',
                  'color'):

            data_lookup[k] = src[this_key][k][()]

        if 'stats' in src[this_key].keys():
            stats_grp = src[this_key]['stats']
            for stat_key in stats_grp.keys():
                stats_lookup[stat_key] = dict()
                for sub_key in stats_grp[stat_key]:
                    stats_lookup[stat_key][sub_key] = stats_grp[
                                                        stat_key][sub_key][()]

    calculate_colors = False
    param_list = []
    for idx in range(len(data_lookup['pixel_r'])):
        label = data_lookup['label'][idx].decode('utf-8')

        stats = dict()
        for stat_key in stats_lookup:
            stats[stat_key] = dict()
            for sub_key in stats_lookup[stat_key]:
                stats[stat_key][sub_key] = stats_lookup[stat_key][sub_key][idx]

        if color_by in color_lookup[level][label]:
            color = color_lookup[level][label][color_by]
        else:
            color = None
            calculate_colors = True

        if isinstance(color, numbers.Number):
            color = None
            calculate_colors = True

        params = {
            'label': label,
            'name': data_lookup['name'][idx].decode('utf-8'),
            'n_cells': data_lookup['n_cells'][idx],
            'pixel_r': data_lookup['pixel_r'][idx],
            'pixel_x': data_lookup['pixel_x'][idx],
            'pixel_y': data_lookup['pixel_y'][idx],
            'color': color,
            'level': level,
            'stats': stats
        }
        param_list.append(params)

    if calculate_colors:
        stat_values = [
            p['stats'][color_by]['mean']
            for p in param_list
        ]
        color_vmin = min(stat_values)
        color_vmax = max(stat_values)
        normalizer = matplotlib.colors.Normalize(
            vmin=color_vmin,
            vmax=color_vmax)
        for params in param_list:
            val = params['stats'][color_by]['mean']
            color = matplotlib.colors.rgb2hex(
                color_map(
                    normalizer(val)
                )
            )
            params['color'] = color

    result = dict()
    for params in param_list:
        label = params['label']
        result[label] = Centroid.from_dict(params)

    return result


def connection_list_to_hdf5(
        connection_list,
        hdf5_path):

    by_level = dict()
    for connection in connection_list:
        assert connection.src.level == connection.dst.level
        level = connection.src.level
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(connection)

    for level in by_level:
        connection_list_to_hdf5_single_level(
            connection_list=by_level[level],
            hdf5_path=hdf5_path,
            level=level
        )


def connection_list_to_hdf5_single_level(
        connection_list,
        hdf5_path,
        level):

    src_label_list = np.array(
        [c.src.label.encode('utf-8')
         for c in connection_list]
    )
    dst_label_list = np.array(
        [c.dst.label.encode('utf-8')
         for c in connection_list]
    )
    k_nn_list = np.array(
        [c.k_nn for c in connection_list]
    )
    src_neighbor_list = np.array(
        [c.src_neighbors for c in connection_list]
    )
    dst_neighbor_list = np.array(
        [c.dst_neighbors for c in connection_list]
    )
    n_rendering_corners = np.array(
        [c.rendering_corners.shape[0] for c in connection_list],
        dtype=int
    )
    n_bezier_points = np.array(
        [c.bezier_control_points.shape[0] for c in connection_list],
        dtype=int
    )
    rendering_corners = np.vstack(
        [c.rendering_corners for c in connection_list]
    )
    bezier_control_points = np.vstack(
        [c.bezier_control_points for c in connection_list]
    )

    with h5py.File(hdf5_path, 'a') as dst:
        if 'connections' not in dst.keys():
            dst.create_group('connections')
        dst_grp = dst['connections']
        if level not in dst_grp.keys():
            dst_grp.create_group(level)
        dst_grp = dst_grp[level]

        dst_grp.create_dataset('src_label_list', data=src_label_list)
        dst_grp.create_dataset('dst_label_list', data=dst_label_list)
        dst_grp.create_dataset('k_nn_list', data=k_nn_list)
        dst_grp.create_dataset('src_neighbor_list', data=src_neighbor_list)
        dst_grp.create_dataset('dst_neighbor_list', data=dst_neighbor_list)

        dst_grp.create_dataset(
            'n_rendering_corners', data=n_rendering_corners)

        dst_grp.create_dataset(
            'n_bezier_points', data=n_bezier_points
        )

        dst_grp.create_dataset(
            'rendering_corners',
            data=rendering_corners,
            compression='lzf')

        dst_grp.create_dataset(
            'bezier_control_points',
            data=bezier_control_points,
            compression='lzf'
        )


def connection_list_from_hdf5(
        hdf5_path,
        level,
        centroid_lookup=None):

    if centroid_lookup is None:
        centroid_lookup = centroid_lookup_from_hdf5(
            hdf5_path=hdf5_path,
            level=level
        )

    data_lookup = dict()
    this_key = f'connections/{level}'
    with h5py.File(hdf5_path, 'r', swmr=True) as src:
        for k in ('src_label_list', 'dst_label_list',
                  'k_nn_list', 'src_neighbor_list',
                  'dst_neighbor_list', 'n_rendering_corners',
                  'n_bezier_points', 'rendering_corners',
                  'bezier_control_points'):
            data_lookup[k] = src[this_key][k][()]

    n_connections = len(data_lookup['src_label_list'])

    bez0 = 0
    corner0 = 0

    result = []

    for idx in range(n_connections):
        src_label = data_lookup['src_label_list'][idx].decode('utf-8')
        dst_label = data_lookup['dst_label_list'][idx].decode('utf-8')

        k_nn = data_lookup['k_nn_list'][idx]

        src_neighbors = data_lookup['src_neighbor_list'][idx]
        dst_neighbors = data_lookup['dst_neighbor_list'][idx]

        n_corners = data_lookup['n_rendering_corners'][idx]
        n_bez = data_lookup['n_bezier_points'][idx]

        rendering_corners = data_lookup[
            'rendering_corners'][corner0:corner0+n_corners, :]
        corner0 += n_corners

        bezier_points = data_lookup[
            'bezier_control_points'][bez0:bez0+n_bez, :]
        bez0 += n_bez

        params = {
            'src': centroid_lookup[src_label],
            'dst': centroid_lookup[dst_label],
            'k_nn': k_nn,
            'src_neighbors': src_neighbors,
            'dst_neighbors': dst_neighbors,
            'rendering_corners': rendering_corners,
            'bezier_control_points': bezier_points
        }

        result.append(Connection.from_dict(params))

    return result


def hull_list_to_hdf5(
        hull_list,
        hdf5_path):
    by_level = dict()
    for hull in hull_list:
        level = hull.level
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(hull)
    for level in by_level:
        hull_list_to_hdf5_single_level(
            hull_list=by_level[level],
            level=level,
            hdf5_path=hdf5_path)


def hull_list_to_hdf5_single_level(
        hull_list,
        level,
        hdf5_path):

    for hull in hull_list:
        hull.to_hdf5(hdf5_path=hdf5_path, level=level)


def hull_lookup_from_hdf5(
        hdf5_path,
        level):

    result = dict()
    with h5py.File(hdf5_path, 'r', swmr=True) as src:
        src_grp = src[f'hulls/{level}']
        for label in src_grp.keys():
            result[label] = CompoundBareHull.from_hdf5(
                hdf5_handle=src,
                label=label,
                level=level
            )
    return result


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
