import logging
import numpy as np
from FiducciaMattheyses.FiducciaMattheyses import FiducciaMattheyses
from Dataset.DatasetH5 import DatasetH5
from math import ceil

__author__ = 'gm'


class Caching:
    def __init__(self, pruning_matrix: np.ndarray, dataset_path: str, cache_size: int):
        """
        :param pruning_matrix: the pruning matrix generated by PruningMatrix.py
        :type pruning_matrix: np.ndarray
        :param dataset_path: hdf5 database path
        :type dataset_path: str
        :param cache_size: the capacity of the cache. This number indicates how many time-series can fit in memory
        :type cache_size: int
        """
        self.pm = pruning_matrix
        self.dataset_path = dataset_path
        self.cache_size = cache_size
        self.ds = DatasetH5(dataset_path)
        self.batches = [[x for x in range(pruning_matrix.shape[0])]]
        self.total_batches = 1
        self.batch_level = 1
        self.total_ts = len(self.ds)

    # TODO: how to merge very small batches together (fast)?
    def calculate_batches(self):
        pm_str = ""
        for i in range(self.pm.shape[0]):
            for j in range(self.pm.shape[1]):
                pm_str += "1 " if self.pm[i][j] else "0 "
            pm_str += "\n"
        logging.debug("Pruning Matrix: \n" + pm_str)
        logging.debug("Begin computation of batches")
        logging.debug("Initial batch size: %d (all time series)" % len(self.batches[0]))
        unconnected = 0
        for i in range(self.pm.shape[0]):
            has_edge = False
            for j in range(self.pm.shape[1]):
                if i != j and self.pm[i][j] == 1:
                    has_edge = True
                    break
            if not has_edge:
                unconnected += 1

        logging.debug("ts with no edges in pruning matrix: %d" % unconnected)
        self.__calculate_batches()
        logging.debug("Batch sizes: " + " ".join([str(len(x)) for x in self.batches]))
        total = 0
        for b in self.batches:
            for ts in b:
                total += 1
        logging.debug("Total ts in batches: %d" % total)
        assert total == self.pm.shape[0] - unconnected
        return self.batches

    def __calculate_batches(self):
        if self.total_batches >= ceil(2 * self.total_ts / self.cache_size):  # M > ⌈2n/B⌉
            return
        temp_batches = []
        logging.debug("Current batch level: %d" % self.batch_level)

        for batch in self.batches:
            logging.debug("Batch size before split: %d" % len(batch))
            fm = FiducciaMattheyses()
            fm.input_routine(self.pm, batch)
            a, b = fm.find_mincut()
            logging.debug("Batches size after split: %d %d" % (len(a), len(b)))
            self.total_batches += 1
            temp_batches.append(a)
            temp_batches.append(b)
        logging.debug("Batches after splitting: %d" % len(temp_batches))
        self.batches = temp_batches
        self.batch_level += 1
        self.__calculate_batches()

        return self.batches