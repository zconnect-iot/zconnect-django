from zconnect.zc_timeseries.models import TimeSeriesData
from zconnect.zc_timeseries.util.ts_util import insert_timeseries_data


class TestTimeseriesDataInsert:
    def test_inserting_timeseries_data_from_event(self, fake_watson_ts_event):

        original_count = TimeSeriesData.objects.count()

        device, watson_event = fake_watson_ts_event

        print("Device sensors: {}".format(device.sensors.all()))
        insert_timeseries_data(watson_event, device)

        assert TimeSeriesData.objects.count() > original_count
