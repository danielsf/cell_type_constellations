import anndata
import h5py
import multiprocessing
import numpy as np
import pandas as pd
import pathlib
import scipy
import tempfile

from cell_type_mapper.utils.multiprocessing_utils import (
    winnow_process_list
)

from cell_type_mapper.utils.utils import (
    mkstemp_clean,
    _clean_up
)



def create_mixture_matrices_from_h5ad(
        cell_set,
        h5ad_path,
        k_nn,
        coord_key,
        dst_path,
        tmp_dir,
        n_processors,
        clobber=False):
    """
    Parameters
    ----------
    cell_set:
        a CellSet as defined in cells/cell_set.py
    h5ad_path:
        path to the h5ad file containing the latent space
    k_nn:
        number of nearest neighbors to query for each point
    coord_key:
        the key in obsm that points to the array containing the
        latent space coordinates
    dst_path:
        path to the h5ad file where the mixture matrices
        will be saved
    tmp_dir:
        path to scratch directory where temporary files
        can be written
    n_processors:
        number of independent worker processes to spin up
    clobber:
        a boolean. If False and dst_path already exists,
        raise an exception. If True, overwrite.

    Returns
    -------
    None
        Mixture matrices for all type_fields in the cell_set
        are saved in the h5ad file at dst_path
    """
    kd_tree = _get_kd_tree_from_h5ad(
        h5ad_path=h5ad_path,
        coord_key=coord_key)

    create_mixture_matrices(
        cell_set=cell_set,
        kd_tree=kd_tree,
        k_nn=k_nn,
        dst_path=dst_path,
        clobber=clobber,
        tmp_dir=tmp_dir,
        n_processors=n_processors)


def _get_kd_tree_from_h5ad(
        h5ad_path,
        coord_key):
    """
    Extract the a set of coordinates from obsm in and h5ad file.
    Convert them into a KD Tree and return

    Parameters
    ----------
    h5ad_path:
        the path to the h5ad file
    coord_key:
        the key (within obsm) of the coordinate array being extracted

    Returns
    -------
    kd_tree:
        a scipy.spatial.cKDTree built off of the corresponding
        coordinates
    """
    src = anndata.read_h5ad(h5ad_path, backed='r')
    obsm = src.obsm
    if coord_key not in obsm.keys():
        raise KeyError(f'key {coord_key} not in obsm')
    coords = obsm[coord_key]
    src.file.close()
    del src

    if isinstance(coords, pd.DataFrame):
        coords = coords.to_numpy()

    return scipy.spatial.cKDTree(coords)


def create_mixture_matrices(
        cell_set,
        kd_tree,
        k_nn,
        dst_path,
        tmp_dir,
        n_processors,
        clobber=False):
    """
    Parameters
    ----------
    cell_set:
        a CellSet as defined in cells/cell_set.py
    kd_tree:
        a KD Tree built from the latent variables
        defining the space in which connection strength
        is evaluated
    k_nn:
        number of nearest neighbors to query for each point
    dst_path:
        path to the h5ad file where the mixture matrices
        will be saved
    tmp_dir:
        path to scratch directory where temporary files
        can be written
    n_processors:
        number of independent worker processes to spin up
    clobber:
        a boolean. If False and dst_path already exists,
        raise an exception. If True, overwrite.

    Returns
    -------
    None
        Mixture matrices for all type_fields in the cell_set
        are saved in the h5ad file at dst_path
    """

    dst_path = pathlib.Path(dst_path)
    if dst_path.exists():
        if not clobber:
            raise RuntimeError(
                f"{dst_path} already exists"
            )
        if not dst_path.is_file():
            raise RuntimeError(
                f"{dst_path} already exists, but is not a file"
            )
        dst_path.unlink()

    tmp_dir = tempfile.mkdtemp(
        dir=tmp_dir,
        prefix='mixture_matrix_calculation_'
    )

    try:
        _create_mixture_matrices(
            cell_set=cell_set,
            kd_tree=kd_tree,
            k_nn=k_nn,
            dst_path=dst_path,
            tmp_dir=tmp_dir,
            n_processors=n_processors)
    finally:
        _clean_up(tmp_dir)


def _create_mixture_matrices(
        cell_set,
        kd_tree,
        k_nn,
        dst_path,
        tmp_dir,
        n_processors):

    n_cells = kd_tree.data.shape[0]
    chunk_size = min(100000, n_cells//(2*n_processors))
    tmp_path_list = []
    process_list = []
    for i0 in range(0, n_cells, chunk_size):
        i1 = min(n_cells, i0+chunk_size)
        chunk = np.arange(i0, i1, dtype=int)
        tmp_path = mkstemp_clean(
            dir=tmp_dir,
            prefix=f'mixture_matrix_{i0}_{i1}_',
            suffix='.h5'
        )
        tmp_path_list.append(tmp_path)
        p = multiprocessing.Process(
            target=_create_sub_mixture_matrix,
            kwargs={
                'cell_set': cell_set,
                'kd_tree': kd_tree,
                'subset_idx': chunk,
                'k_nn': k_nn,
                'dst_path': tmp_path
            }
        )
        p.start()
        process_list.append(p)
        if len(process_list) >= n_processors:
            process_list = winnow_process_list(process_list)

    while len(process_list) > 0:
        process_list = winnow_process_list(process_list)

    # join tmp files
    with h5py.File(dst_path, 'w') as dst:
        for type_field in cell_set.type_field_list():
            n_types = len(cell_set.type_value_list(type_field))
            dst.create_dataset(
                type_field,
                shape=(n_types, n_types),
                dtype=int
            )
        for tmp_path in tmp_path_list:
            with h5py.File(tmp_path, 'r') as src:
                for type_field in cell_set.type_field_list():
                    dst[type_field][:, :] += src[type_field][()]


def _create_sub_mixture_matrix(
        cell_set,
        kd_tree,
        subset_idx,
        k_nn,
        dst_path):

    matrix_lookup = dict()   
    for type_field in cell_set.type_field_list():
        type_value_list = cell_set.type_value_list(type_field)
        n_value = len(type_value_list)
        matrix_lookup[type_field] = np.zeros((n_value, n_value), dtype=int)

    neighbors = kd_tree.query(
        x=kd_tree.data[subset_idx, :],
        k=k_nn
    )[1]

    for type_field in cell_set.type_field_list():

        type_value_list = cell_set.type_value_list(type_field)
        type_value_to_idx = {
            v:ii for ii, v in enumerate(type_value_list)
        }

        row_values = cell_set.type_value_from_idx(
            type_field=type_field,
            idx_array=subset_idx)

        row_idx_array = np.array(
            [type_value_to_idx[v] for v in row_values]
        )        

        for ii, row_idx in enumerate(row_idx_array):

            col_values = cell_set.type_value_from_idx(
                type_field=type_field,
                idx_array=neighbors[ii, :]
            )

            col_idx_array = np.array(
                [type_value_to_idx[v] for v in col_values]
            )
            
            unq_arr, ct_arr = np.unique(col_idx_array, return_counts=True)
            matrix_lookup[type_field][row_idx, unq_arr] += ct_arr

    with h5py.File(dst_path, 'w') as dst:
        for type_field in cell_set.type_field_list():
            dst.create_dataset(
                type_field,
                data=matrix_lookup[type_field]
            )
   
        
