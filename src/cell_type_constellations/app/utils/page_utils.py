import cairosvg
import copy
import h5py
import json
import pathlib

import cell_type_constellations

from cell_type_mapper.taxonomy.taxonomy_tree import (
    TaxonomyTree
)

from cell_type_constellations.svg.rendering_utils import (
    render_fov_from_hdf5
)

import cell_type_constellations.app.utils.html_utils as html_utils


def get_constellation_plot_page(
        hdf5_path,
        centroid_level,
        hull_level,
        base_url,
        color_by,
        fill_hulls,
        export_png):

    constellation_path = pathlib.Path(
        cell_type_constellations.__file__
    )
    png_dir = constellation_path.parent.parent.parent / 'screenshots'
    assert png_dir.is_dir()

    if hull_level == 'NA':
        hull_level = None

    centroid_stats = None

    with h5py.File(hdf5_path, 'r') as src:

        width = src['fov']['width'][()]
        height = src['fov']['height'][()]

        taxonomy_tree = TaxonomyTree(
            data=json.loads(src['taxonomy_tree'][()].decode('utf-8'))
        )
        taxonomy_name = src['taxonomy_name'][()].decode('utf-8')

        centroid_level_list = list(src['centroids'].keys())
        hull_level_list = list(src['hulls'].keys())

        if 'stats' in src['centroids'][centroid_level_list[0]].keys():
            centroid_stats = list(
                src['centroids'][centroid_level_list[0]]['stats'].keys()
            )
            centroid_stats.sort()

    level_to_idx = {
        level: ii
        for ii, level in enumerate(taxonomy_tree.hierarchy)
    }

    if color_by not in level_to_idx or \
            level_to_idx[color_by] <= level_to_idx[centroid_level]:

        html = render_fov_from_hdf5(
            hdf5_path=hdf5_path,
            centroid_level=centroid_level,
            hull_level=hull_level,
            base_url=base_url,
            color_by=color_by,
            fill_hulls=fill_hulls
        )

        if export_png:
            png_path = png_dir / 'test.png'
            cairosvg.svg2png(
                bytestring=html,
                write_to=str(png_path),
                background_color='white',
                output_width=4*width,
                output_height=4*height
            )

    else:
        centroid_name = taxonomy_tree.level_to_name(centroid_level)
        color_name = taxonomy_tree.level_to_name(color_by)
        html = f"""
        <p>
        Cannot color {centroid_name} centroids by {color_name};
        {centroid_name} is a parent level of {color_name}
        </p>
        """

    html += f"<p>Taxonomy: <b>{taxonomy_name}</b></p>\n"

    html += get_constellation_control_code(
        taxonomy_tree=taxonomy_tree,
        centroid_level=centroid_level,
        color_by=color_by,
        hull_level=hull_level,
        taxonomy_name=create_taxonomy_tag(
            hdf5_path=hdf5_path,
            taxonomy_name=taxonomy_name),
        fill_hulls=fill_hulls,
        centroid_level_list=centroid_level_list,
        hull_level_list=hull_level_list,
        centroid_stats=centroid_stats)

    return html


def get_constellation_control_code(
        taxonomy_tree,
        centroid_level,
        hull_level,
        color_by,
        taxonomy_name,
        fill_hulls,
        centroid_level_list,
        hull_level_list,
        centroid_stats):

    if hull_level is None:
        hull_level = 'NA'

    default_lookup = {
        'centroid_level': centroid_level,
        'hull_level': hull_level,
        'color_by': color_by
    }

    level_list_lookup = {
        'centroid_level': centroid_level_list,
        'color_by': centroid_level_list,
        'hull_level': hull_level_list
    }

    html = ""

    html += html_utils.html_front_matter_n_columns(
        n_columns=4)

    html += """<form action="constellation_plot" method="GET">\n"""
    html += f"""<input type="hidden" value="{taxonomy_name}" name="taxonomy_name">\n"""  # noqa: E501
    for i_column, field_id in enumerate(
                                ("centroid_level",
                                 "color_by",
                                 "hull_level")):

        default_value = default_lookup[field_id]

        html += """<div class="column">"""
        html += f"""<fieldset id="{field_id}">\n"""
        html += f"""<label for="{field_id}">{field_id.replace('_', ' ')}</label><br>"""  # noqa: E501

        button_values = copy.deepcopy(taxonomy_tree.hierarchy)

        for value in level_list_lookup[field_id]:
            if value not in button_values:
                button_values.append(value)

        if field_id == 'hull_level':
            button_values.append('NA')
        elif field_id == 'color_by':
            if centroid_stats is not None:
                button_values += centroid_stats

        for level in button_values:
            if level in taxonomy_tree.hierarchy:
                level_name = taxonomy_tree.level_to_name(level)
            else:
                level_name = level
            html += f"""
            <input type="radio" name="{field_id}" id="{level}" value="{level}" """  # noqa: E501
            if level == default_value:
                html += """checked="checked" """
            html += ">"
            html += f"""
            <label for="{level}">{level_name}</label><br>
            """
        html += """</fieldset>\n"""
        if i_column == 0:
            html += """<input type="submit" value="Reconfigure constellation plot">"""  # noqa: E501
            html += html_utils.end_of_page()

        html += """</div>\n"""

    html += """<div class="column">"""
    html += """<fieldset id="fill_hulls">\n"""
    html += """<label for="fill_hulls">fill hulls</label><br>"""
    html += """<input type="radio" name="fill_hulls" id="true" value="true" """  # noqa: E501
    if fill_hulls:
        html += """checked="checked" """
    html += ">"
    html += """
    <label for="true">True</label><br>
    """
    html += """<input type="radio" name="fill_hulls" id="false" value="false" """  # noqa: E501
    if not fill_hulls:
        html += """checked="checked" """
    html += ">"
    html += """
    <label for="false">False</label><br>
    """
    html += """</fieldset></div>\n"""

    html += """
    </form>
    """

    return html


def get_constellation_plot_config(
        data_dir):
    """
    Scan a directory for all .h5 files in that directory.
    Create a dict mapping taxonomy_name to hdf5 path and
    default constellation plot settings. Return that dict.
    """
    data_dir = pathlib.Path(data_dir)

    file_path_list = [n for n in data_dir.rglob('**/*.h5')]
    result = dict()
    for file_path in file_path_list:
        with h5py.File(file_path, 'r') as src:

            taxonomy_name = create_taxonomy_tag(
                hdf5_path=file_path,
                taxonomy_name=src['taxonomy_name'][()].decode('utf-8')
            )

            if taxonomy_name in result:
                raise RuntimeError(
                    f"More than one constellation plot in {data_dir} for "
                    f"taxonomy {taxonomy_name}"
                )
            tree = TaxonomyTree(
                data=json.loads(src['taxonomy_tree'][()].decode('utf-8'))
            )
            this = {
                'path': file_path,
                'centroid_level': tree.hierarchy[-2],
                'color_by': tree.hierarchy[0],
                'hull_level': tree.hierarchy[0]
            }
            if 'HY-EA' in taxonomy_name:
                this['hull_level'] = None
            result[taxonomy_name] = this
    return result


def create_taxonomy_tag(hdf5_path, taxonomy_name):

    file_name = pathlib.Path(hdf5_path).name
    return f'{file_name} -- {taxonomy_name}'
