import copy
import numpy as np

from scipy.spatial import (
    ConvexHull,
    cKDTree
)

from cell_type_constellations.utils.geometry import (
    cross_product_2d_bulk
)


def find_smooth_hull_for_clusters(
        constellation_cache,
        label,
        taxonomy_level='CCN20230722_CLUS',
        valid_fraction=0.51,
        max_iterations=100
    ):
    """
    For finding minimal hull(s) containing mostly cells in a given cluster.
    """

    data = get_test_pts(
        constellation_cache=constellation_cache,
        taxonomy_level=taxonomy_level,
        label=label)

    valid_pts = data['valid_pts']
    test_pts = data['test_pts']
    test_pt_validity = data['test_pt_validity']

    kd_tree = cKDTree(test_pts)
    valid_pt_neighbor_array = kd_tree.query(
            x=valid_pts,
            k=20)[1]
    del kd_tree

    final_hull = None
    eps = 0.001
    n_iter = 0

    true_pos_0 = 0
    false_pos_0 = 0
    test_hull = None
    hull_0 = None

    while True:
        hull_0 = test_hull
        test_hull = ConvexHull(valid_pts)
        in_hull = pts_in_hull(
            pts=test_pts,
            hull=test_hull)
        true_pos = np.logical_and(in_hull, test_pt_validity).sum()
        false_pos = np.logical_and(
                        in_hull,
                        np.logical_not(test_pt_validity)).sum()
        false_neg = np.logical_and(
                        np.logical_not(in_hull),
                        test_pt_validity).sum()
        delta_tp = (true_pos - true_pos_0)/true_pos_0
        delta_fp = (false_pos - false_pos_0)/false_pos_0

        f1_score = true_pos/(true_pos+0.5*(false_pos+false_neg))
        ratio = true_pos/in_hull.sum()
        n_iter += 1
        #if f1_score >= valid_fraction or n_iter > max_iterations:
        print(f'n_iter {n_iter} pts {test_hull.points.shape} ratio {ratio:.2e} f1 {f1_score:.2e} '
        f'delta tp {delta_tp} delta fp {delta_fp} {delta_fp>=10*delta_tp}')

        if delta_fp >= 2.0*delta_tp and true_pos_0 > 0 or delta_tp < -0.01:
            if hull_0 is None:
                final_hull = test_hull
            else:
                final_hull = hull_0
            break

        true_pos_0 = true_pos
        false_pos_0 = false_pos

        valid_flat = valid_pt_neighbor_array.flatten()
        score = np.logical_and(
            in_hull[valid_flat],
            test_pt_validity[valid_flat])
        score = score.reshape(valid_pt_neighbor_array.shape)
        del valid_flat

        score = score.sum(axis=1)
        worst_value = np.min(score)
        to_keep = np.ones(valid_pts.shape[0], dtype=bool)
        to_keep[score==worst_value] = False
        valid_pts = valid_pts[to_keep, :]
        valid_pt_neighbor_array = valid_pt_neighbor_array[to_keep, :]


        #centroid = np.mean(valid_pts, axis=0)
        #dsq_centroid = ((valid_pts-centroid)**2).sum(axis=1)
        #worst_pt = np.argmax(dsq_centroid)
        #cut = (dsq_centroid < dsq_centroid[worst_pt]-eps)
        #valid_pts = valid_pts[cut, :]

    return final_hull


def merge_hulls(
        constellation_cache,
        taxonomy_level,
        label,
        leaf_hull_lookup):

    as_leaves = constellation_cache.taxonomy_tree.as_leaves
    leaf_list = as_leaves[taxonomy_level][label]

    raw_hull_list = [
        copy.deepcopy(leaf_hull_lookup[leaf])
        for leaf in leaf_list if leaf in leaf_hull_lookup
    ]

    data = get_test_pts(
        constellation_cache=constellation_cache,
        taxonomy_level=taxonomy_level,
        label=label
    )

    test_pts = data['test_pts']
    test_pt_validity = data['test_pt_validity']

    keep_going = True
    final_pass = False
    while keep_going:
        print(f'{len(raw_hull_list)} hulls')
        centroid_array = np.array([
            _get_hull_centroid(h) for h in raw_hull_list
        ])

        dsq_array = pairwise_distance_sq(centroid_array)
        if not final_pass:
            n_cols = len(raw_hull_list)//2
            if n_cols < 10:
                n_cols = len(raw_hull_list)
            median_dsq = np.median(dsq_array[:, :n_cols])

        mergers = dict()
        been_merged = set()
        idx_list = np.argsort(dsq_array[0, :])
        for i0 in idx_list:
            if i0 in been_merged:
                continue

            sorted_i1 = np.argsort(dsq_array[i0, :])
            for i1 in sorted_i1:
                if i1 == i0:
                    continue

                if i1 in been_merged:
                    continue

                if dsq_array[i0, i1] > median_dsq:
                    continue

                new_hull = evaluate_merger(
                    raw_hull_list[i0],
                    raw_hull_list[i1],
                    test_pts=test_pts,
                    test_pt_validity=test_pt_validity)

                if new_hull is not None:
                    print(f'     merging {i0} {i1}')
                    mergers[i0] = new_hull
                    been_merged.add(i0)
                    been_merged.add(i1)
                    break

        if len(mergers) == 0:
            if final_pass:
                return raw_hull_list
            else:
                final_pass = True

        new_hull_list = []
        for ii in range(len(idx_list)):
            if ii not in been_merged:
                new_hull_list.append(raw_hull_list[ii])
            elif ii in mergers:
                new_hull_list.append(mergers[ii])
        raw_hull_list = new_hull_list
        if len(raw_hull_list) == 1:
            return raw_hull_list


def evaluate_merger(
        hull0,
        hull1,
        test_pts,
        test_pt_validity):

    false_points = np.logical_not(test_pt_validity)
    new_hull = ConvexHull(
        np.concatenate([hull0.points, hull1.points])
    )
    in_new = pts_in_hull(
        hull=new_hull,
        pts=test_pts)

    fp_new = np.logical_and(
        in_new,
        false_points
    ).sum()


    in0 = pts_in_hull(
        hull=hull0,
        pts=test_pts
    )

    in1 = pts_in_hull(
        hull=hull1,
        pts=test_pts
    )


    fp0 = np.logical_and(
        in0,
        false_points

    )

    fp1 = np.logical_and(
        in1,
        false_points

    )

    fp_old = np.logical_or(fp0, fp1).sum()
    fp0 = fp0.sum()
    fp1 = fp1.sum()

    delta_fp = fp_new-fp_old
    if delta_fp <= 0.5*(fp0+fp1):
        return new_hull
    if delta_fp < 0.05*np.logical_or(in0, in1).sum():
        return new_hull

    return None


def get_test_pts(
        constellation_cache,
        taxonomy_level,
        label):

    alias_list = constellation_cache.parentage_to_alias[taxonomy_level][label]
    alias_set = set(alias_list)
    valid_pt_mask = np.zeros(constellation_cache.cluster_aliases.shape,
                             dtype=bool)
    for alias in alias_list:
        valid_pt_mask[constellation_cache.cluster_aliases==alias] = True

    valid_pt_idx = np.where(valid_pt_mask)[0]
    valid_pts = constellation_cache.umap_coords[valid_pt_mask]

    xmin = valid_pts[:, 0].min()
    xmax = valid_pts[:, 0].max()
    ymin = valid_pts[:, 1].min()
    ymax = valid_pts[:, 1].max()
    dx = xmax-xmin
    dy = ymax-ymin
    slop = 0.05
    xmin -= slop*dx
    xmax += slop*dx
    ymin -= slop*dy
    ymax += slop*dy

    test_pt_mask = np.logical_and(
        constellation_cache.umap_coords[:, 0] > xmin,
        np.logical_and(
            constellation_cache.umap_coords[:, 0] < xmax,
            np.logical_and(
                constellation_cache.umap_coords[:, 1] > ymin,
                constellation_cache.umap_coords[:, 1] < ymax
            )
        )
    )
    test_pts = constellation_cache.umap_coords[test_pt_mask]

    test_pt_idx = np.where(test_pt_mask)[0]
    valid_pt_idx = set(valid_pt_idx)
    test_pt_validity = np.array([
        ii in valid_pt_idx for ii in test_pt_idx
    ])
    assert test_pt_validity.sum() == len(valid_pt_idx)
    return {
        'valid_pts': valid_pts,
        'test_pts': test_pts,
        'test_pt_validity': test_pt_validity
    }


def pts_in_hull(pts, hull):
    """
    Points on the hull edge are not considered
    "in" the hull
    """
    n_vert = len(hull.vertices)
    n_pts = pts.shape[0]

    sgn_arr = None
    result = np.ones(pts.shape[0], dtype=bool)
    for ii in range(n_vert):
        src = hull.points[hull.vertices[ii]]
        i1 = ii+1
        if i1 >= n_vert:
            i1 = 0
        dst = hull.points[hull.vertices[i1]]
        edge = np.array([dst-src])
        pt_vec = pts[result, :]-src
        sgn = np.sign(cross_product_2d_bulk(
                            vec0=pt_vec,
                            vec1=edge)
                      ).astype(int)
        if sgn_arr is None:
            sgn_arr = sgn[:, 0]
        else:
            invalid = (sgn_arr[result] != sgn[:, 0])
            result[np.where(result)[0][invalid]] = False

        if result.sum() == 0:
            break

    return result


def _get_hull_centroid(hull):
    return np.mean(hull.points, axis=0)


def pairwise_distance_sq(points: np.ndarray) -> np.ndarray:
    """
    Calculate all of the pairwise distances (squared) between the rows
    in a np.ndarray

    Parameters
    ----------
    points: np.ndarray
        Shape is (n_points, n_dimensions)

    Returns
    -------
    distances: np.ndarray
        A (n_points, n_points) array. The i,jth element
        is the Euclidean squared distance between the ith and jth
        rows of the input points.

    Notes
    -----
    As n_points, n_dimensions approach a few thousand, this is
    several orders of magnitude faster than scipy.distances.cdist
    """
    p_dot_p = np.dot(points, points.T)
    dsq = np.zeros((points.shape[0], points.shape[0]), dtype=float)
    for ii in range(points.shape[0]):
        dsq[ii, :] += p_dot_p[ii, ii]
        dsq[:, ii] += p_dot_p[ii, ii]
        dsq[ii, :] -= 2.0*p_dot_p[ii, :]
    return dsq
