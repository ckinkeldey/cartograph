from scipy.spatial import Voronoi
import numpy as np
from Vertex import Vertex
import Util
from collections import defaultdict

import Config
config = Config.BAD_GET_CONFIG()


class BorderFactory(object):

    def __init__(self, x, y, cluster_labels):
        self.x = x
        self.y = y
        self.cluster_labels = cluster_labels

    @classmethod
    def from_file(cls, ):
        s = "." if debug else ""
        featureDict = Util.read_features(s + config.FILE_NAME_WATER_AND_ARTICLES,
                                         s + config.FILE_NAME_KEEP,
                                         s + config.FILE_NAME_WATER_CLUSTERS)
        idList = list(featureDict.keys())
        x, y, clusters = [], [], []
        for article in idList:
            if featureDict[article]["keep"] == "True":
                x.append(float(featureDict[article]["x"]))
                y.append(float(featureDict[article]["y"]))
                clusters.append(int(featureDict[article]["cluster"]))
        return cls(x, y, clusters)

    @staticmethod
    def _make_vertex_adjacency_list(vor):
        adj_lst = defaultdict(set)
        for ridge in vor.ridge_vertices:
            adj_lst[ridge[0]].add(ridge[1])
            adj_lst[ridge[1]].add(ridge[0])
        return adj_lst

    @staticmethod
    def _make_three_dicts(vor, cluster_labels):
        vert_reg_idxs_dict = defaultdict(list)
        vert_reg_labs_dict = defaultdict(list)
        group_vert_dict = defaultdict(set)
        for i, reg_idx in enumerate(vor.point_region):
            vert_idxs = vor.regions[reg_idx]
            label = cluster_labels[i]
            group_vert_dict[label].update(vert_idxs)
            for vert_idx in vert_idxs:
                vert_reg_idxs_dict[vert_idx].append(reg_idx)
                vert_reg_labs_dict[vert_idx].append(label)
        return vert_reg_idxs_dict, vert_reg_labs_dict, group_vert_dict

    @staticmethod
    def _make_vertex_array(vor, adj_lst, vert_reg_idxs_dict,
                           vert_reg_labs_dict):
        return [Vertex(v[0], v[1], i, adj_lst[i],
                vert_reg_idxs_dict[i], vert_reg_labs_dict[i])
                for i, v in enumerate(vor.vertices)]

    @staticmethod
    def _make_group_edge_vert_dict(vert_array, group_vert_dict):
        """maps group labels to edge vertex indices"""
        group_edge_vert_dict = defaultdict(set)
        for label in group_vert_dict:
            # can't do list comprehension because otherwise it's a generator later
            for vert_idx in group_vert_dict[label]:
                if vert_array[vert_idx].is_edge_vertex:
                    group_edge_vert_dict[label].add(vert_idx)
        return group_edge_vert_dict

    @staticmethod
    def _make_borders(vert_array, group_edge_vert_dict):
        """internal function to build borders from generated data"""
        borders = defaultdict(list)
        # remove water points
        del group_edge_vert_dict[len(group_edge_vert_dict) - 1]
        for label in group_edge_vert_dict:
            while group_edge_vert_dict[label]:
                continent = []
                vert_idx = next(iter(group_edge_vert_dict[label]))
                while vert_idx is not None:
                    vert = vert_array[vert_idx]
                    continent.append(vert)
                    group_edge_vert_dict[label].remove(vert_idx)
                    vert_idx = vert.get_adj_edge_vert_idx(label, vert_idx)
                if len(continent) > config.MIN_NUM_IN_CONTINENT:
                    borders[label].append(continent)
        return BorderFactory.NaturalBorderMaker(borders).make_borders_natural()

    def build(self):
        """
        Returns:
            a dictionary mapping group labels to a list of list of tuples representing
            the different continents in each cluster
        """
        points = list(zip(self.x, self.y))
        vor = Voronoi(points)
        adj_lst = self._make_vertex_adjacency_list(vor)
        vert_reg_idxs_dict, vert_reg_labs_dict, group_vert_dict = self._make_three_dicts(vor, self.cluster_labels)
        vert_array = self._make_vertex_array(vor, adj_lst, vert_reg_idxs_dict,
                                             vert_reg_labs_dict)
        Vertex.vertex_arr = vert_array
        group_edge_vert_dict = self._make_group_edge_vert_dict(vert_array,
                                                               group_vert_dict)
        Vertex.edge_vertex_dict = group_edge_vert_dict

        borders = self._make_borders(vert_array, group_edge_vert_dict)
        for label in borders:
            for i, continent in enumerate(borders[label]):
                borders[label][i] = [(vert.x, vert.y) for vert in continent]
        return borders

    class NaturalBorderMaker:

        def __init__(self, borders):
            self.borders = borders

        @staticmethod
        def _wrap_range(start, stop, length, reverse=False):
            """
            Returns:
                range from start to stop *inclusively* modulo length
            """
            start %= length
            stop %= length
            if reverse:
                if stop >= start:
                    return range(start, -1, -1) + range(length - 1, stop - 1, -1)
                else:
                    return range(start, stop - 1, -1)
            else:
                if start >= stop:
                    return range(start, length) + range(0, stop + 1)
                else:
                    return range(start, stop + 1)

        @staticmethod
        def _blur(array, circular):
            if len(array) <= config.BLUR_RADIUS:
                return array
            blurred = []
            if circular:
                for i, _ in enumerate(array):
                    start = i - config.BLUR_RADIUS
                    stop = i + config.BLUR_RADIUS
                    neighborhood = [
                        array[j] for j in BorderFactory.NaturalBorderMaker._wrap_range(start, stop, len(array))]
                    blurred.append(np.average(neighborhood))
            else:
                for i, _ in enumerate(array):
                    start = max(0, i - config.BLUR_RADIUS)
                    stop = min(len(array) - 1, i + config.BLUR_RADIUS)
                    neighborhood = [array[j] for j in range(start, stop + 1)]
                    blurred.append(np.average(neighborhood))
            return blurred

        @staticmethod
        def _blur_vertices(vertices, circular):
            x = [vertex.x for vertex in vertices]
            y = [vertex.y for vertex in vertices]
            x = BorderFactory.NaturalBorderMaker._blur(x, circular)
            y = BorderFactory.NaturalBorderMaker._blur(y, circular)
            for i, vertex in enumerate(vertices):
                vertex.x = x[i]
                vertex.y = y[i]
            return vertices

        @staticmethod
        def _get_consensus_border_intersection(indices1, indices2, len1, len2, reversed2):
            """
            Args:
                indices1: *aligned* indices of points in points1 which are in intersection
                indices2: *aligned* indices of points in points2 which are in intersection
                len1: length of points1
                len2: length of points2
                reversed2: Whether or not indices2 is in reversed order
            Returns:
                list of lists of contiguous regions
            """
            assert len(indices1) == len(indices2)

            # build list for each contiguous region
            diff2 = -1 if reversed2 else 1
            consensus_lists = [[(indices1[0], indices2[0])]]
            for i in range(1, len(indices1)):
                prev = consensus_lists[-1][-1]
                current = (indices1[i], indices2[i])
                if (prev[0] + 1) % len1 == current[0] and \
                        (prev[1] + diff2) % len2 == current[1]:
                    consensus_lists[-1].append(current)
                else:
                    consensus_lists.append([current])

            # check for circular and index 0 in the middle of an intersection
            first = consensus_lists[0][0]
            last = consensus_lists[-1][-1]
            if (last[0] + 1) % len1 == first[0] and \
                    (last[1] + diff2) % len2 == first[1]:
                if len(consensus_lists) == 1:
                    # it's circular
                    return consensus_lists, True
                else:
                    # 0 is in middle of intersection
                    consensus_lists[0] = consensus_lists[-1] + consensus_lists[0]
                    consensus_lists.pop()
            return consensus_lists, False

        @staticmethod
        def _get_border_region_indices(points, intersection):
            """
            Returns:
                list of indices of points in points which are in intersection
            """
            indices = []
            for i, point in enumerate(points):
                if point in intersection:
                    indices.append(i)
            return indices

        @staticmethod
        def _get_intersecting_borders(points1, points2):
            """
            Returns:
                list of lists of tuples which represents the aligned indices of points1 and points2 in each contiguous
                intersection of points1 and points2 and whether the intersection is circular.
                Ex: [[(pt1_0, pt2_0), (pt1_1, pt2_1), ...], [...]]
            """
            points1_set = set(points1)
            points2_set = set(points2)
            intersection = points1_set & points2_set
            if intersection:
                points1_border_idxs = BorderFactory.NaturalBorderMaker._get_border_region_indices(points1, intersection)
                points2_border_idxs = BorderFactory.NaturalBorderMaker._get_border_region_indices(points2, intersection)

                # align lists, taking orientation into account
                search_point = points1[points1_border_idxs[0]]
                offset = 0
                for i, index in enumerate(points2_border_idxs):
                    if search_point == points2[index]:
                        offset = i
                        break
                # check for direction
                reverse = False
                if len(points1_border_idxs) > 1:
                    try_index = (offset + 1) % len(points2_border_idxs)
                    if points2[points2_border_idxs[try_index]] != points1[points1_border_idxs[1]]:
                        reverse = True
                if reverse:
                    # gnarly bug this one was
                    # reversing the list means offsetting by one extra - set the new 0 pos at the end
                    points2_border_idxs = np.roll(points2_border_idxs, -offset - 1)
                    points2_border_idxs = list(reversed(points2_border_idxs))
                else:
                    points2_border_idxs = np.roll(points2_border_idxs, -offset)

                return BorderFactory.NaturalBorderMaker._get_consensus_border_intersection(
                    points1_border_idxs, points2_border_idxs, len(points1), len(points2), reverse
                )
            return [], False

        @staticmethod
        def _make_new_regions(region1, region2):
            """
            Args:
                region1: One region represented by Vertex objects
                region2: Another region represented by Vertex objects
            Returns:
                region1 and region2 with their intersecting points modified
            """
            points1 = [(vertex.x, vertex.y) for vertex in region1]
            points2 = [(vertex.x, vertex.y) for vertex in region2]
            consensus_lists, circular = BorderFactory.NaturalBorderMaker._get_intersecting_borders(points1, points2)
            processed = []
            for contiguous in consensus_lists:
                # sanity check
                for indices in contiguous:
                    assert points1[indices[0]] == points2[indices[1]]
                indices = zip(*contiguous)  # make separate lists for region1 and region2 coordinates
                processed.append(
                    BorderFactory.NaturalBorderMaker._blur_vertices([region1[i] for i in indices[0]], circular)
                )
            # TODO: allow for arbitrary numbers of points
            for i, contiguous in enumerate(processed):
                for j, vertex in enumerate(contiguous):
                    reg1_idx = consensus_lists[i][j][0]
                    reg2_idx = consensus_lists[i][j][1]
                    region1[reg1_idx] = vertex
                    region2[reg2_idx] = vertex
            return region1, region2

        @staticmethod
        def _make_region_adj_matrix_and_index_key(borders):
            """
            Returns:
                an adjacency matrix and a dictionary mapping group labels to indices
                (i.e., adj_matrix[index_key[group_label] + region_index]
            """
            index_key = {}
            n = 0
            for label in range(len(borders)):
                index_key[label] = n
                n += len(borders[label])
            return np.zeros((n, n), dtype=np.int8), index_key

        def make_borders_natural(self):
            """
            Returns:
                the borders object where the intersecting borders are made more natural
            """
            adj_matrix, index_key = BorderFactory.NaturalBorderMaker._make_region_adj_matrix_and_index_key(self.borders)
            for group_label in self.borders:
                for reg_idx, region in enumerate(self.borders[group_label]):
                    reg_adj_idx = index_key[group_label] + reg_idx
                    for search_group_label in self.borders:
                        if group_label is not search_group_label:
                            for search_reg_idx, search_region in enumerate(self.borders[search_group_label]):
                                search_reg_adj_idx = index_key[search_group_label] + search_reg_idx
                                if not adj_matrix[reg_adj_idx][search_reg_adj_idx]:
                                    self.borders[group_label][reg_idx], \
                                        self.borders[search_group_label][search_reg_idx] = \
                                        BorderFactory.NaturalBorderMaker._make_new_regions(region, search_region)
                                    adj_matrix[reg_adj_idx][search_reg_adj_idx] = 1
                                    adj_matrix[search_reg_adj_idx][reg_adj_idx] = 1
            return self.borders

debug = False

if __name__ == '__main__':
    debug = True
    BorderFactory.from_file().build()
