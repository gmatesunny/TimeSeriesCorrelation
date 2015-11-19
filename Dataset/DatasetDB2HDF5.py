from .DatasetDatabase import DatasetDatabase
import h5py
import numpy as np
import datetime as dt

__author__ = 'gm'

delta1sec = dt.timedelta(seconds=1)
delta_zero = dt.timedelta(seconds=0)


class DatasetDB2HDF5:

    def __init__(self, db_name, hdf5_name):
        self.db_name = db_name
        self.hdf5_name = hdf5_name
        self.first_datetime = None
        self.last_datetime = None
        self.db = None  # sqlite database
        self.h5 = None  # hdf5 database
        self.first_datetime_of_ts = None  # temp variable holding the first datetime of a time series
        self.last_datetime_of_ts = None  # temp variable, holding the last datetime of a time series
        self.ts = []  # temp variable, holding a time series

    def convert(self):
        self.db = DatasetDatabase(self.db_name)
        self.db.connect()

        # get the globally first and last date-times (of all time series)
        self.first_datetime = dt.datetime.strptime(self.db.get_first_datetime(None), '%m/%d/%Y-%H:%M:%S')
        self.last_datetime = dt.datetime.strptime(self.db.get_last_datetime(None), '%m/%d/%Y-%H:%M:%S')

        self.h5 = h5py.File(self.hdf5_name, mode='w')

        for ts_name in self.db.get_distinct_names():  # for every time series
            self._convert_time_series(ts_name)

        self.h5.close()
        self.db.disconnect()

    def _convert_time_series(self, ts_name):
        self.ts = self.db.get_time_series(ts_name).fetchall()
        # ts --> [[date, time, data1, data2], ...]
        gap_filled_ts = []

        # get the first and last date-times of this time series
        self.first_datetime_of_ts = dt.datetime.strptime(self.ts[0][0] + "-" + self.ts[0][1], '%m/%d/%Y-%H:%M:%S')
        self.last_datetime_of_ts = dt.datetime.strptime(self.ts[-1][0] + "-" + self.ts[-1][1], '%m/%d/%Y-%H:%M:%S')

        # FS: First Segment
        # MS: Middle Segment
        # LS: Last Segment
        #
        # |--FS--| |--MS--| |--LS--|
        # ........ ........ ........  <-- time series
        # |---the globally first datetime(self.first_datetime)
        #          |---the first datetime of the time series(self.first_datetime_of_ts)
        #                 |---the last datetime of the time series(self.last_datetime_of_ts)
        #                          |---the globally last datetime(self.last_datetime)

        # First segment filling
        # There is no First segment if self.first_datetime_of_ts == self.first_datetime
        if self.first_datetime_of_ts != self.first_datetime:
            self._fill_first_segment(gap_filled_ts)

        # Middle segment filling
        # This is always present
        self._fill_middle_segment(gap_filled_ts)

        # Last segment filling
        # There is no Last segment if self.last_datetime_of_ts == self.last_datetime
        if self.last_datetime_of_ts != self.last_datetime:
            self._fill_last_segment(gap_filled_ts)

        ts_array = np.array(gap_filled_ts, dtype='float32')
        self.h5.create_dataset(ts_name, (len(gap_filled_ts),), data=ts_array, dtype='float32', compression="gzip",
                               compression_opts=9)

    def _fill_first_segment(self, gap_filled_ts):
        """
        fills the first segment, copies the first point of self.ts to all missing points from global start timedate
        assume global start timedate is 00:00:00 and start of timeseries is 00:00:05 with data 2.1

        00:00:05
           2.1

        after filling:

        00:00:00  00:00:01  00:00:02  00:00:03  00:00:04  00:00:05
           2.1       2.1       2.1       2.1       2.1       2.1

        """
        assert self.first_datetime_of_ts > self.first_datetime
        delta = self.first_datetime_of_ts - self.first_datetime
        first_ts_data = self.ts[0][2]
        seconds = delta.days * 86400 + delta.seconds
        DatasetDB2HDF5._fill_N_points(gap_filled_ts, first_ts_data, seconds)

    def _fill_middle_segment(self, gap_filled_ts):
        """
        fills the middle segment, puts the first point of self.ts in gap_filled_ts and then does the following:
        if the next point to insert is ahead of the previous for more than one second, then fill every missing second
        by copying the data of the previous point
        00:00:00  00:00:05
           1.1       2.3

        after filling:

        00:00:00  00:00:01  00:00:02  00:00:03  00:00:04  00:00:05
           1.1       1.1       1.1       1.1       1.1       2.3
        """
        prev_datetime = None
        prev_data = None
        assert len(self.ts) != 0
        for row in self.ts:  # for every row in the current time series
            date = row[0]
            time = row[1]
            cur_data = row[2]
            cur_datetime = dt.datetime.strptime(date + "-" + time, '%m/%d/%Y-%H:%M:%S')
            if prev_datetime is not None:
                assert cur_datetime > prev_datetime
                delta = cur_datetime - prev_datetime
                assert delta != delta_zero
                if delta > delta1sec:
                    # fill gaps
                    seconds = delta.days * 86400 + delta.seconds
                    assert prev_data
                    assert seconds - 1 > 0
                    DatasetDB2HDF5._fill_N_points(gap_filled_ts, prev_data, seconds - 1)

            gap_filled_ts.append(cur_data)
            prev_datetime = cur_datetime
            prev_data = cur_data

    def _fill_last_segment(self, gap_filled_ts):
        """
        fills the last segment, copies the last point of self.ts to all missing points from time series
        last point till global last timedate
        assume global last timedate is 00:00:10 and last of timeseries is 00:00:05 with data 2.1

        00:00:05
           2.1

        after filling:

        00:00:05  00:00:06  00:00:07  00:00:08  00:00:09  00:00:10
           2.1       2.1       2.1       2.1       2.1       2.1

        """
        assert self.last_datetime_of_ts < self.last_datetime
        delta = self.last_datetime - self.last_datetime_of_ts
        last_ts_data = self.ts[-1][2]
        seconds = delta.days * 86400 + delta.seconds
        DatasetDB2HDF5._fill_N_points(gap_filled_ts, last_ts_data, seconds)

    @staticmethod
    def _fill_N_points(gap_filled_ts: list, data: float, N: int):
        """
        append data N times to gap_filled_ts
        """
        assert N > 0
        for i in range(N):
            gap_filled_ts.append(data)

            # def convert(self):
            #     self.db = DatasetDatabase(self.db_name)
            #     self.db.connect()
            #
            #     self.first_datetime = dt.datetime.strptime(self.db.get_first_datetime(None), '%m/%d/%Y-%H:%M:%S')
            #     self.last_datetime = dt.datetime.strptime(self.db.get_last_datetime(None), '%m/%d/%Y-%H:%M:%S')
            #
            #     self.h5 = h5py.File(self.hdf5_name, mode='w')
            #
            #     for ts_name in self.db.get_distinct_names():  # for every time series
            #         self._convert_time_series(ts_name)
            #
            #     self.h5.close()
            #     self.db.disconnect()
            #
            # def _convert_time_series(self, ts_name):
            #     prev_datetime = self.first_datetime
            #     ts = self.db.get_time_series(ts_name).fetchall()
            #     # ts --> [[date, time, data1, data2], ...]
            #     gap_filled_ts = []
            #
            #     self.first_datetime_of_ts = dt.datetime.strptime(ts[0][0] + "-" + ts[0][1], '%m/%d/%Y-%H:%M:%S')
            #     self.last_datetime_of_ts = dt.datetime.strptime(ts[-1][0] + "-" + ts[-1][1], '%m/%d/%Y-%H:%M:%S')
            #
            #     if self.first_datetime_of_ts != self.first_datetime:
            #         prev_data = ts[0][2]
            #         prev_datetime = prev_datetime - delta1sec
            #     if self.last_datetime_of_ts != self.last_datetime:
            #         ts.append([self.last_datetime.date().strftime('%m/%d/%Y'),
            #                    self.last_datetime.time().strftime('%H:%M:%S'), ts[-1][2]])
            #
            #     for row in ts:  # for every row in the current time series
            #         date = row[0]
            #         time = row[1]
            #         cur_data = row[2]
            #         cur_datetime = dt.datetime.strptime(date + "-" + time, '%m/%d/%Y-%H:%M:%S')
            #         assert cur_datetime >= prev_datetime
            #         delta = cur_datetime - prev_datetime
            #         if delta > delta1sec:  # delta should be zero only if the time series begins at self.first_datetime
            #             # fill gaps
            #             for i in range(delta.seconds-1):
            #                 assert delta.seconds-1 > 0
            #                 assert prev_data
            #                 gap_filled_ts.append(prev_data)
            #
            #         gap_filled_ts.append(cur_data)
            #         prev_datetime = cur_datetime
            #         prev_data = cur_data
            #     if len(gap_filled_ts) == 172679:
            #         print(self.first_datetime_of_ts, self.last_datetime_of_ts, ts[-1][0], ts[-1][1], ts[-2][0], ts[-2][1])
            #     else:
            #         print("\t", self.first_datetime_of_ts, self.last_datetime_of_ts, ts[-1][0], ts[-1][1], ts[-2][0], ts[-2][1])
            #     ts_array = np.array(gap_filled_ts, dtype='float32')
            #     self.h5.create_dataset(ts_name, (len(gap_filled_ts),), data=ts_array, dtype='float32', compression="gzip",
            #                               compression_opts=9)