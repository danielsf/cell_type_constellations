import numpy as np
from scipy.spatial import ConvexHull

import json

from cell_type_constellations.utils.geometry import (
    rot,
    cross_product_2d_bulk,
    do_intersect,
    find_intersection_pt
)

from cell_type_constellations.svg.hull_utils import (
    pts_in_hull
)


class Hull(object):
    """
    Take a list of Centroids. Ingest their pixel_pts into
    a scipy ConvexHull. Render SVG.
    """

    def __init__(
            self,
            centroid_list,
            color):

        self.color = color
        self.centroid_list = centroid_list

    def render(self, plot_obj=None):
        pts = np.array(
            [c.pixel_pt for c in self.centroid_list]
        )

        return _path_from_hull(hull=ConvexHull(pts), stroke_color=self.color)

    @property
    def x_values(self):
        return []

    @property
    def y_values(self):
        return []


class RawHull(object):
    """
    Take an array of points. Ingest into a scipy ConvexHull.
    Render SVG.
    """

    def __init__(
            self,
            pts,
            color):

        self.color = color
        self.pts = pts

    def render(self, plot_obj=None):
        (xx,
         yy) = plot_obj.convert_to_pixel_coords(
             x=self.pts[:, 0],
             y=self.pts[:, 1])

        pts = np.array([xx, yy]).transpose()
        return _path_from_hull(hull=ConvexHull(pts), stroke_color=self.color)

    @property
    def x_values(self):
        return []

    @property
    def y_values(self):
        return []


class BareHull(object):
    """
    Take a counterclockwise path of points. Store this as a boundary.
    Expose vertices and points as if it were a scipy ConvexHull
    """
    def __init__(
            self,
            points,
            color=None):

        self._points = np.copy(points)
        self._vertices = np.arange(self._points.shape[0], dtype=int)
        self._set_segments()
        self.color = color

    @classmethod
    def from_convex_hull(cls, convex_hull, color=None):
        points = np.array([
            convex_hull.points[idx]
            for idx in convex_hull.vertices
        ])
        return cls(points=points, color=color)


    @property
    def x_values(self):
        return self.points[:, 0]

    @property
    def y_values(self):
        return self.points[:, 1]

    @property
    def points(self):
        return self._points

    @property
    def vertices(self):
        return self._vertices

    @property
    def segments(self):
        return self._segments

    @property
    def i_segments(self):
        return self._i_segments

    def _set_segments(self):
        segments = []
        i_segments = []
        for ii in range(self.points.shape[0]-1):
            segments.append([self.points[ii, :], self.points[ii+1, :]])
            i_segments.append([ii, ii+1])
        segments.append([self.points[-1, :], self.points[0, :]])
        i_segments.append([self.points.shape[0]-1, 0])
        self._segments = segments
        self._i_segments = i_segments

    def render(self, plot_obj=None, fill=False):
        (xx,
         yy) = plot_obj.convert_to_pixel_coords(
             x=self.points[:, 0],
             y=self.points[:, 1])

        pts = np.array([xx, yy]).transpose()
        return _path_from_hull(
            hull=BareHull(points=pts),
            stroke_color=self.color,
            fill=fill)


class CompoundBareHull(object):

    def __init__(
            self,
            bare_hull_list,
            label=None,
            name=None,
            n_cells=None,
            fill=False):

        self.label = label
        self.name = name
        self.bare_hull_list = bare_hull_list
        self.n_cells = n_cells
        self.fill=fill


    @property
    def x_values(self):
        return np.concatenate(
         [h.points[:, 0] for h in self.bare_hull_list]
        )

    @property
    def y_values(self):
        return np.concatenate(
         [h.points[:, 1] for h in self.bare_hull_list]
        )

    def render(self, plot_obj=None):
        url = (
            f"http://35.92.115.7:8883/display_entity?entity_id={self.label}"
        )
        result = f"""    <a href="{url}">\n"""
        for hull in self.bare_hull_list:
            result += hull.render(plot_obj=plot_obj, fill=self.fill)
        result += """        <title>\n"""
        result += f"""        {self.name}: {self.n_cells:.2e} cells\n"""
        result += """        </title>\n"""
        result += "    </a>\n"
        return result


def _path_from_hull(hull, stroke_color='green', fill=False):
    if fill:
        fill_color = stroke_color
    else:
        fill_color = 'transparent'

    vertices = hull.vertices
    pts = hull.points

    path_code = f'<path d="M {pts[vertices[0], 0]} {pts[vertices[0], 1]} '
    for i_src in range(len(vertices)):
        i_dst = i_src + 1
        if i_dst >= len(vertices):
            i_dst = 0

        src = pts[vertices[i_src], :]
        dst = pts[vertices[i_dst], :]

        pre = i_src - 1
        post = i_dst + 1
        if post >= len(vertices):
            post = 0

        src_ctrl = _get_ctrl_point(
            pts[vertices[pre], :],
            src,
            dst)

        dst_ctrl = _get_ctrl_point(
            pts[vertices[post], :],
            dst,
            src)

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

    path_code += f'" stroke="{stroke_color}" fill="{fill_color}" fill-opacity="0.1"/>\n'

    return path_code


def _get_ctrl_point(pre, center, post):
    """
    ctrl point will be in direction of post
    """
    factor = 0.1
    v0 = pre-center
    v0 = v0/np.sqrt((v0**2).sum())

    v1 = post-center
    post_norm = np.sqrt((v1**2).sum())
    v1 = v1/post_norm

    v2 = 0.5*(v0+v1)
    v2 = v2/np.sqrt((v2**2).sum())

    orth = rot(v2, 0.5*np.pi)

    if np.dot(orth, v1) < 0.0:
        orth *= -1.0

    return center + factor*post_norm*orth



def merge_bare_hulls(
            bare0,
            bare1):
    convex0 = ConvexHull(bare0.points)
    convex1 = ConvexHull(bare1.points)

    # find all intersections between the segments in the two
    # bare hulls
    bare0_to_1 = dict()
    bare1_to_0 = dict()
    intersection_points = []
    n_all = bare0.points.shape[0]+bare1.points.shape[0]
    for i0, seg0 in enumerate(bare0.segments):
        for i1, seg1 in enumerate(bare1.segments):
            intersection = find_intersection_pt(
                seg0,
                seg1)
            if intersection is not None:
                if i0 not in bare0_to_1:
                    bare0_to_1[i0] = dict()
                if i1 not in bare1_to_0:
                    bare1_to_0[i1] = dict()
                intersection_points.append(intersection)
                bare0_to_1[i0][i1] = n_all+len(intersection_points)-1
                bare1_to_0[i1][i0] = n_all+len(intersection_points)-1

    intersection_points = np.array(intersection_points)
    n_intersections = intersection_points.shape[0]

    # either no intersection, or there is an odd numbe of intersections
    # (which signals an edge case we are not prepared for)
    if n_intersections == 0 or n_intersections %2 == 1:

        bare1_in_0 = pts_in_hull(
            pts=bare1.points,
            hull=convex0
        )

        if bare1_in_0.all():
            return [bare0]

        bare0_in_1 = pts_in_hull(
            pts=bare0.points,
            hull=convex1)

        if bare0_in_1.all():
            return [bare1]

        return [bare0, bare1]

    all_points = np.concatenate([
        bare0.points,
        bare1.points,
        intersection_points])

    meta_intersection_lookup = [bare0_to_1, bare1_to_0]

    # For each bare hull, assemble a new ordered list of points that includes
    # the intersections.

    new_bare_hulls = []
    for i_hull, src_hull in enumerate([bare0, bare1]):
        new_hull = dict()   # a src->dst graph
        dst_set = set()
        if i_hull == 0:
            hull_offset = 0
        else:
            hull_offset = bare0.points.shape[0]
        intersection_lookup = meta_intersection_lookup[i_hull]
        for i_seg in src_hull.i_segments:
            src_idx = int(hull_offset + i_seg[0])

            src_pt = src_hull.points[i_seg[0]]
            if i_seg[0] in intersection_lookup:
                intersection_idx_list = np.array(
                    [idx for idx in intersection_lookup[i_seg[0]].values()]
                )
                ddsq_arr = np.array([
                    ((all_points[idx]-src_pt)**2).sum()
                    for idx in intersection_idx_list
                ])
                sorted_dex = np.argsort(ddsq_arr)
                intersection_idx_list = intersection_idx_list[sorted_dex]
                for dst_idx in intersection_idx_list:
                    dst_idx = int(dst_idx)
                    #print(json.dumps(new_hull, indent=2))
                    #print(src_idx, dst_idx, hull_offset, i_hull)
                    assert src_idx not in new_hull
                    assert dst_idx not in dst_set
                    new_hull[src_idx] = dst_idx
                    dst_set.add(dst_idx)
                    src_idx = dst_idx

            dst_idx = int(hull_offset + i_seg[1])

            assert src_idx not in new_hull
            new_hull[src_idx] = dst_idx
            assert dst_idx not in dst_set
            dst_set.add(dst_idx)

        new_bare_hulls.append(new_hull)

    # find a starting point that is on the outer perimeter of the
    # ConvexHull created from all_points (to guard against accidentally
    # staring on a vertex that is part of a hole in the merged
    # hull)
    naive_hull = ConvexHull(all_points)
    starting_idx = None
    for vertex in naive_hull.vertices:
        if vertex >= bare0.points.shape[0]:
            continue
        starting_idx = vertex
    assert starting_idx is not None

    current_hull = 0
    final_points = [starting_idx]
    final_set = set(final_points)
    while True:
        next_pt = new_bare_hulls[current_hull][final_points[-1]]
        if next_pt == final_points[0]:
            break
        final_points.append(next_pt)
        final_set.add(next_pt)
        if next_pt in new_bare_hulls[(current_hull+1)%2]:
            current_hull = ((current_hull+1)%2)

    return [
        BareHull(
            points=np.array(
             [
              all_points[idx]
              for idx in final_points
             ]
            ),
            color=bare0.color
        )
    ]


def create_compound_bare_hull(
        bare_hull_list,
        label,
        name,
        n_cells,
        fill=False):

    while True:
        new_hull = None
        n0 = len(bare_hull_list)
        has_merged = set()
        for i0 in range(len(bare_hull_list)):
            if len(has_merged) > 0:
                break
            h0 = bare_hull_list[i0]
            for i1 in range(i0+1, len(bare_hull_list), 1):
                h1 = bare_hull_list[i1]
                merger = merge_bare_hulls(h0, h1)
                if len(merger) == 1:
                    new_hull = merger[0]
                    has_merged.add(i0)
                    has_merged.add(i1)
                    break
        new_hull_list = []
        if new_hull is not None:
            new_hull_list.append(new_hull)
        for ii in range(len(bare_hull_list)):
            if ii not in has_merged:
                new_hull_list.append(bare_hull_list[ii])
        bare_hull_list = new_hull_list
        if len(bare_hull_list) == n0:
            break

    if len(bare_hull_list) == 0:
        return None

    return CompoundBareHull(
        bare_hull_list=bare_hull_list,
        label=label,
        name=name,
        n_cells=n_cells,
        fill=fill)
