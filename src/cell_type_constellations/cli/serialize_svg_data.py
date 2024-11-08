"""
This tool allows you to go from a data cache to and HDF5 file containing
all of the data needed to render and svg
"""

import argparse
import multiprocessing
import pathlib
import time

from cell_type_constellations.cells.data_cache import (
    ConstellationCache_HDF5
)

from cell_type_constellations.svg.fov import (
    ConstellationPlot
)

from cell_type_constellations.svg.utils import (
    _load_centroids,
    _load_hulls,
    _load_connections
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--data_cache_path',
        type=str,
        help=(
            "Path to the .h5 file containing the raw data cache."
        )
    )
    parser.add_argument(
       '--dst_path',
       type=str,
       help=(
           "Path to the .h5 file to be written"
       )
    )
    parser.add_argument(
        '--height',
        type=int,
        default=1080,
        help=(
            "FOV height in pixels"
        )
    )
    parser.add_argument(
        '--width',
        type=int,
        default=800,
        help=(
            "FOV width in pixels"
        )
    )
    parser.add_argument(
        '--clobber',
        default=False,
        action='store_true'
    )

    args = parser.parse_args()

    src_path = pathlib.Path(args.data_cache_path)
    if not src_path.is_file():
        raise RuntimeError(
            f"{src_path} is not a file"
        )
    dst_path = pathlib.Path(args.dst_path)
    if dst_path.exists():
        if args.clobber:
            dst_path.unlink()
        else:
            raise RuntimeError(
                f"{dst_path} exists. Run with --clobber to overwrite"
            )

    write_out_svg_cache(
        src_path=src_path,
        dst_path=dst_path,
        height=args.height,
        width=args.width,
        clobber=args.clobber)


def write_out_svg_cache(
        src_path,
        dst_path,
        height,
        width,
        clobber=False):

    t0 = time.time()

    dst_path = pathlib.Path(dst_path)
    if dst_path.exists():
        if clobber:
            dst_path.unlink()
        else:
            raise RuntimeError(
                f"{dst_path} exists. Run set clobber=True to overwrite"
            )

    constellation_cache = ConstellationCache_HDF5(src_path)
    process_list = []
    mgr = multiprocessing.Manager()
    lock = mgr.Lock()
    mode = 'w'
    for level in constellation_cache.taxonomy_tree.hierarchy:
        p = multiprocessing.Process(
            target=_write_svg_cache_worker,
            kwargs = {
                'constellation_cache': constellation_cache,
                'dst_path': dst_path,
                'level': level,
                'height': height,
                'width': width,
                'lock': lock,
                'mode': mode
            }
        )
        p.start()
        mode = 'a'
        process_list.append(p)

    while len(process_list) > 0:
        process_list = winnow_process_list(process_list)

    print(f'======SUCCESS=======')
    print(f'that took {(time.time()-t0)/60.0:.2e} minutes')


def _write_svg_cache_worker(
        constellation_cache,
        dst_path,
        level,
        height,
        width,
        lock,
        mode
    ):

    max_cluster_cells = constellation_cache.n_cells_lookup[
        constellation_cache.taxonomy_tree.leaf_level].max()

    # each level gets its own plot object so that, when finding
    # the positions of bezier control points, we do not account for
    # centroids not at that level
    plot_obj = ConstellationPlot(
            height=height,
            width=width,
            max_radius=20,
            min_radius=2,
            max_n_cells=max_cluster_cells)


    plot_obj = _load_hulls(
            constellation_cache=constellation_cache,
            plot_obj=plot_obj,
            taxonomy_level=level,
            n_limit=None,
            verbose=False
        )

    hull_level = constellation_cache.taxonomy_tree.hierarchy[0]

    (plot_obj,
     centroid_list) = _load_centroids(
             constellation_cache=constellation_cache,
             plot_obj=plot_obj,
             taxonomy_level=level,
             color_by_level=hull_level)

    plot_obj = _load_connections(
                constellation_cache=constellation_cache,
                centroid_list=centroid_list,
                taxonomy_level=level,
                plot_obj=plot_obj)

    with lock:
        plot_obj.serialize_fov(hdf5_path=dst_path, mode=mode)
        print(f'=======COMPLETED {level}=======')


def winnow_process_list(
        process_list):
    """
    Loop over a list of processes, popping out any that have
    been completed. Return the winnowed list of processes.
    Parameters
    ----------
    process_list: List[multiprocessing.Process]
    Returns
    -------
    process_list: List[multiprocessing.Process]
    """
    to_pop = []
    for ii in range(len(process_list)-1, -1, -1):
        if process_list[ii].exitcode is not None:
            to_pop.append(ii)
            if process_list[ii].exitcode != 0:
                raise RuntimeError(
                    "One of the processes exited with code "
                    f"{process_list[ii].exitcode}")
    for ii in to_pop:
        process_list.pop(ii)
    return process_list


if __name__ == "__main__":
    main()