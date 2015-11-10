__author__ = 'gm'

import io


class DatasetReader:
    """
    Provides functionality to read data from a specific dataset
    """

    def __init__(self, dataset_path: str):
        """
        :param dataset_path: the path to the dataset we want read data
        """
        self.dataset_path = dataset_path
        self.dataset_handle = None
        """:type: io.TextIOWrapper"""
        self.time_buffer = {}

    def open_dataset(self):
        """
        opens the dataset specified in dataset_path for reading
        """
        if self.dataset_handle is None:
            self.dataset_handle = open(self.dataset_path, 'r')

    def close_dataset(self):
        """
        closes the dataset specified in dataset_path
        """
        if self.dataset_handle is not None:
            self.dataset_handle.close()
            self.dataset_handle = None

    def get_next_data(self):
        """
        get the data of the next line in the dataset

        :return: (name, date, time, data1, data2)
        :rtype: tuple
        """
        assert isinstance(self.dataset_handle, io.TextIOWrapper)
        line = self.dataset_handle.readline().rstrip('\n')
        name, date, time, data1, data2 = line.split(",")
        return name, date, time, float(data1), float(data2)

    def get_next_data_averaged(self):
        name, date, time, data1, data2 = self.get_next_data()
        if name not in self.time_buffer:
            # first time seeing this time-series
            self.time_buffer[name] = [date, time, data1, data2, 1]
        else:
            # known time-series, check for same timepoint
            temp_data = self.time_buffer[name]
            """:type: list """
            if temp_data[0] == date and temp_data[1] == time:
                # same time point, average data
                n = temp_data[4] + 1
                old_avg1 = float(temp_data[2])
                old_avg2 = float(temp_data[3])
                avg1 = (n - 1) * old_avg1 / n + data1 / n
                avg2 = (n - 1) * old_avg2 / n + data2 / n
                temp_data[2] = avg1
                temp_data[3] = avg2
                temp_data[4] = n

                data1 = avg1
                data2 = avg2
            else:
                # overwrite old record, we have new timepoint
                self.time_buffer[name] = [date, time, data1, data2, 1]

        print(self.time_buffer[name])
        return name, date, time, data1, data2