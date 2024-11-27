import argparse
import cherrypy
import pathlib

import cell_type_constellations

from cell_type_constellations.app.utils.page_utils import (
    get_constellation_plot_page,
    get_constellation_plot_config
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help="Ip of host to serve the app on."
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help="Port to serve the app on."
    )
    args = parser.parse_args()

    cherrypy.server.socket_host = args.host
    cherrypy.server.socket_port = args.port

    cherrypy.quickstart(
        Visualizer()
    )


class Visualizer(object):

    def __init__(self):

        file_path = pathlib.Path(
            cell_type_constellations.__file__)

        self.data_dir = file_path.parent.parent.parent / 'app_data'

        if not self.data_dir.is_dir():
            raise RuntimeError(
                f"Data dir {self.data_dir} is not a dir"
            )

        self.constellation_plot_config = get_constellation_plot_config(
            self.data_dir
        )

    @cherrypy.expose
    def index(self):
        return self.constellation_plot_landing_page()

    @cherrypy.expose
    def constellation_plot_landing_page(self):

        html = "<p>Choose taxonomy for constellation plot</p>"
        taxonomy_name_list = list(self.constellation_plot_config.keys())
        taxonomy_name_list.sort()
        for taxonomy_name in taxonomy_name_list:
            html += f"""<a href="/constellation_plot?taxonomy_name={taxonomy_name}&default=true">"""  # noqa: E501
            html += f"""{taxonomy_name}</a></br>"""
        return html

    @cherrypy.expose
    def constellation_plot(
            self,
            taxonomy_name=None,
            centroid_level=None,
            color_by=None,
            hull_level=None,
            default=False,
            fill_hulls='false',
            export_png='false'):

        if fill_hulls == 'true':
            fill_hulls = True
        else:
            fill_hulls = False

        if export_png == 'true':
            export_png = True
        else:
            export_png = False

        config = self.constellation_plot_config[taxonomy_name]

        hdf5_path = config['path']
        if default:
            centroid_level = config['centroid_level']
            color_by = config['color_by']
            hull_level = config['hull_level']

        if taxonomy_name == 'HMBA_BG':
            base_url = None
        else:
            base_url = ''

        html = get_constellation_plot_page(
                hdf5_path=hdf5_path,
                centroid_level=centroid_level,
                hull_level=hull_level,
                base_url=base_url,
                color_by=color_by,
                fill_hulls=fill_hulls,
                export_png=export_png)

        return html


if __name__ == "__main__":
    main()
