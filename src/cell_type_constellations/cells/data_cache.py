import h5py
import json

from cell_type_constellations.taxonomy.taxonomy_tree import (
    TaxonomyTree
)



class ConstellationCache_HDF5(object):

    def __init__(self, cache_path):
        with h5py.File(cache_path, 'r') as src:
            self.k_nn = src['k_nn'][()]

            self.centroid_lookup = {
                level: src['centroid'][level][()]
                for level in src['centroid'].keys()
            }

            self.n_cells_lookup = {
                level: src['n_cells'][level][()]
                for level in src['n_cells'].keys()
            }

            self.mixture_matrix_lookup = {
                level: src['mixture_matrix'][level][()]
                for level in src['mixture_matrix'].keys()
            }

            self.label_to_color = json.loads(
                src['label_to_color'][()]
            )

            self.idx_to_label = json.loads(
                src['idx_to_label'][()]
            )

            self.taxonomy_tree = TaxonomyTree(
                data=json.loads(src['taxonomy_tree'][()])
            )

        self.label_to_idx = {
            level: {
                self.idx_to_label[level][idx]['label']: idx
                for idx in range(len(self.idx_to_label[level]))
            }
            for level in self.idx_to_label
        }

    def labels(self, level):
        return [el['label'] for el in self.idx_to_label[level]]

    def centroid_from_label(self, level, label):
        idx = self.label_to_idx[level][label]
        return self.centroid_lookup[level][idx]

    def color_from_label(self, label):
        return self.label_to_color[label]

    def n_cells_from_label(self, level, label):
        idx = self.label_to_idx[level][label]
        return self.n_cells_lookup[level][idx]

    def color(self, level, label, color_by_level):
        if color_by_level == level:
            return self.label_to_color[label]
        parentage = self.taxonomy_tree.parents(
            level=level,
            node=label
        )
        return self.label_to_color[parentage[color_by_level]]