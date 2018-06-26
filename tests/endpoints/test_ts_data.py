import copy
import datetime
from math import sin

from dateutil.relativedelta import relativedelta
import pytest

from zconnect.testutils.helpers import paginated_body
from zconnect.testutils.factories import SensorTypeFactory, TimeSeriesDataFactory
from zconnect.testutils.util import model_to_dict
from zconnect.zc_timeseries.serializers import TimeSeriesDataArchiveSerializer
from zconnect.zc_timeseries.models import TimeSeriesData


@pytest.mark.skip("Needs implementing - similar to existing endpoint")
class TestLatestTSDataEndpoint:
    route = "/api/v3/devices/{device_id}/data/latest/"

    def test_get_latest_data(self, testclient, fakedevice, fake_ts_data):
        expected = {
            "status_code": 200,
            "body": {
                "power_sensor": {
                  # FIXME
                  # use factory data
                  "value": 0.0,
                  # "ts": "2018-03-21T15:59:30.160998",
                  "ts": None,
                  "id": 1
                }
            }
        }
        path_params = {
            "device_id": fakedevice.id,
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_get_latest_data_multiple_sensors(self, testclient, fakedevice, fakesensor, fake_ts_data):
        extra_sensor_type = SensorTypeFactory(
            sensor_name="temperature sensor",
            unit="celsius",
        )
        extra_data = TimeSeriesDataFactory(
            sensor__sensor_type=extra_sensor_type,
            sensor__device=fakedevice,
        )

        expected = {
            "status_code": 200,
            "body": {
                "power_sensor": {
                  # FIXME
                  # use factory data
                  "value": 0.0,
                  # "ts": "2018-03-21T15:59:30.160998",
                  "ts": None,
                  "id": fakesensor.id,
                },
                "temperature sensor": {
                  "value": extra_data.value,
                  # FIXME
                  # 'ts' is not in isoformat if we use extra_data.ts
                  # "ts": extra_data.ts,
                  "ts": None,
                  "id": extra_data.id,
                }
            }
        }
        path_params = {
            "device_id": fakedevice.id,
        }
        testclient.get_request_test_helper(expected, path_params=path_params)


class TestTSDataEndpoint:
    route = "/api/v3/devices/{device_id}/data/"

    @pytest.mark.usefixtures("joeseed_login")
    def test_invalid_date_exception(self, testclient, fakedevice):
        path_params = {
            "device_id": fakedevice.id,
        }
        query_params = {
            "start": "boolin",
        }
        expected = {
            "status_code": 400,
            "body": {
                'detail': 'Invalid dates',
            }
        }
        testclient.get_request_test_helper(expected, path_params=path_params,
                                           query_params=query_params)

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_time_series_data(self, testclient, fakedevice, fake_ts_data):
        now = datetime.datetime.now()
        path_params = {
            "device_id": fakedevice.id,
        }
        resolution = 120
        num_readings = 3
        query_params = {
            "start": str(int((now - datetime.timedelta(seconds=resolution*num_readings))
                             .timestamp()*1000)),
            "end": str(int(now.timestamp()*1000)),
            "resolution":str(resolution),
        }

        power_sensor_data = [model_to_dict(fake_ts_data[i]) for i in range(num_readings)]
        for i, _ in enumerate(power_sensor_data):
            for key in ('sensor', "id"):
                del power_sensor_data[i][key]

        expected = {
            "status_code": 200,
            "body": {
                "power_sensor": power_sensor_data,
            }
        }

        testclient.get_request_test_helper(expected,
                                           path_params=path_params,
                                           query_params=query_params)

    @pytest.mark.usefixtures("joeseed_login")
    @pytest.mark.parametrize("agg_type", (
        "sum",
        "max",
        "mean",
    ))
    def test_missing_data(self, testclient, fakedevice, fakesensor, agg_type):
        """Not checking the return value, just check that it doesn't raise an error"""
        fakesensor.sensor_type.aggregation_type = agg_type
        fakesensor.sensor_type.save()

        now = datetime.datetime.now()
        path_params = {
            "device_id": fakedevice.id,
        }
        resolution = 3600
        query_params = {
            "start": str(int((now - datetime.timedelta(days=1))
                             .timestamp()*1000)),
            "end": str(int(now.timestamp()*1000)),
            "resolution":str(resolution),
        }

        # Create a chunk at the beginning of the day
        TimeSeriesData.objects.bulk_create([
            TimeSeriesData(
                ts=now - relativedelta(seconds=fakesensor.resolution*i),
                sensor=fakesensor,
                value=sin(i),
            ) for i in range(400, 800)
        ])

        # And some more recent - gap in between
        TimeSeriesData.objects.bulk_create([
            TimeSeriesData(
                ts=now - relativedelta(seconds=fakesensor.resolution*i),
                sensor=fakesensor,
                value=sin(i),
            ) for i in range(0, 300)
        ])

        expected = {
            "status_code": 200,
            "body": {
                "power_sensor": None
            }
        }

        testclient.get_request_test_helper(expected,
                                           path_params=path_params,
                                           query_params=query_params)



class TestTimeseriesHTTPIngressEndpoint:
    route = "/api/v3/data/{field_name}/{field_value}/"

    def test_sending_timeseries_data(self, testclient, fakedevice, fakesensor, admin_login):
        now = datetime.datetime.now()
        path_params = {
            "field_name": "name",
            "field_value": fakedevice.name,
        }

        post_body = {
            "data": {
                "power_sensor": 100
            },
            "timestamp": now.isoformat()
        }

        response_body = copy.deepcopy(post_body)
        response_body['device'] = fakedevice.pk

        expected = {
            "status_code": 201,
            "body": response_body
        }

        testclient.post_request_test_helper(post_body,
                                            expected,
                                            path_params=path_params
                                            )

        data = fakedevice.get_latest_ts_data()
        assert "power_sensor" in data
        assert data["power_sensor"].ts == now

    def test_bad_field_in_lookup(self, testclient, fakedevice, admin_login):
        now = datetime.datetime.now().isoformat()
        path_params = {
            "field_name": "bad_field",
            "field_value": fakedevice.name,
        }

        post_body = {
            "data": {
                "xyz": "testing123"
            },
            "timestamp": now
        }

        expected = {
            "status_code": 400,
        }

        testclient.post_request_test_helper(post_body,
                                            expected,
                                            path_params=path_params,
                                            expect_identical_values=False
                                            )

    def test_device_not_found(self, testclient, fakedevice, admin_login):
        now = datetime.datetime.now().isoformat()
        path_params = {
            "field_name": "name",
            "field_value": "bad_value",
        }

        post_body = {
            "data": {
                "xyz": "testing123"
            },
            "timestamp": now
        }

        expected = {
            "status_code": 400,
        }

        testclient.post_request_test_helper(post_body,
                                            expected,
                                            path_params=path_params,
                                            expect_identical_values=False
                                            )

    def test_user_must_be_admin_or_timeseries(self, testclient, fakedevice, normal_user_login):
        now = datetime.datetime.now().isoformat()
        path_params = {
            "field_name": "name",
            "field_value": fakedevice.name,
        }

        post_body = {
            "data": {
                "xyz": "testing123"
            },
            "timestamp": now
        }

        expected = {
            "status_code": 403,
        }

        testclient.post_request_test_helper(post_body,
                                            expected,
                                            path_params=path_params,
                                            expect_identical_values=False
                                            )

    def test_user_with_timeseries_permission_can_access(self, testclient, fakedevice, timeseries_user_login):
        now = datetime.datetime.now().isoformat()
        path_params = {
            "field_name": "name",
            "field_value": fakedevice.name,
        }

        post_body = {
            "data": {
                "xyz": "testing123"
            },
            "timestamp": now
        }

        response_body = copy.deepcopy(post_body)
        response_body['device'] = fakedevice.pk

        expected = {
            "status_code": 201,
            "body": response_body,
        }

        testclient.post_request_test_helper(post_body,
                                                expected,
                                                path_params=path_params
                                                )


@pytest.mark.usefixtures("joeseed_login")
class TestArchiveEndpoint:
    route = "/api/v3/devices/{device_id}/data_archive/"

    def test_get_no_archived_data(self, fakedevice, testclient):
        path_params = {
            "device_id": fakedevice.id,
        }

        expected = {
            "status_code": 200,
            "body": paginated_body([])
        }

        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_get_archived_data_no_filter(self, fakedevice, testclient, fake_ts_archive_data):
        """should return all data for this device"""
        path_params = {
            "device_id": fakedevice.id,
        }
        query_params = {
            # Make sure it's all returned at once so we can check easier
            "page_size": len(fake_ts_archive_data)
        }

        serialized = TimeSeriesDataArchiveSerializer(instance=fake_ts_archive_data, many=True).data

        expected = {
            "status_code": 200,
            "body": paginated_body(serialized),
        }

        testclient.get_request_test_helper(expected, path_params=path_params, query_params=query_params)

    @pytest.mark.parametrize("aggregation_type", (
        "sum",
        "mean",
    ))
    def test_get_archived_data_filter_by_aggregation_type(self, fakedevice, testclient, fake_ts_archive_data,
            aggregation_type):
        """should return all data for this device"""

        trimmed_archive_data = [i for i in fake_ts_archive_data if i.aggregation_type == aggregation_type]

        path_params = {
            "device_id": fakedevice.id,
        }
        query_params = {
            # Make sure it's all returned at once so we can check easier
            "page_size": len(trimmed_archive_data),
            "aggregation_type": aggregation_type,
        }

        serialized = TimeSeriesDataArchiveSerializer(instance=trimmed_archive_data, many=True).data

        expected = {
            "status_code": 200,
            "body": paginated_body(serialized),
        }

        testclient.get_request_test_helper(expected, path_params=path_params, query_params=query_params)

    def test_get_archived_data_filter_by_aggregation_type_no_archive(self, fakedevice, testclient,
            fake_ts_archive_data):
        """Correct aggregation type, but no data"""

        aggregation_type = "min"

        path_params = {
            "device_id": fakedevice.id,
        }
        query_params = {
            "aggregation_type": aggregation_type,
        }

        expected = {
            "status_code": 200,
            "body": paginated_body([]),
        }

        testclient.get_request_test_helper(expected, path_params=path_params, query_params=query_params)

    def test_get_archived_data_filter_by_aggregation_type_bad_type(self, fakedevice, testclient, fake_ts_archive_data):
        """Nonexistent aggregation_type should raise a 400"""
        aggregation_type = "skdof"

        path_params = {
            "device_id": fakedevice.id,
        }
        query_params = {
            "aggregation_type": aggregation_type,
        }

        expected = {
            "status_code": 400,
            "body": {
                "detail": "'skdof' is not a valid aggregation_type"
            }
        }

        testclient.get_request_test_helper(expected, path_params=path_params, query_params=query_params)

    def test_filter_time(self, fakedevice, testclient, fake_ts_archive_data):
        """Only get archive data from the 2 weeks"""

        now = datetime.datetime.utcnow()
        start_date = now - datetime.timedelta(days=15)

        trimmed_archive_data = [i for i in fake_ts_archive_data if i.start >= start_date]

        path_params = {
            "device_id": fakedevice.id,
        }
        query_params = {
            # "page_size": len(trimmed_archive_data),
            "start__gt": start_date.isoformat(),
        }

        serialized = TimeSeriesDataArchiveSerializer(instance=trimmed_archive_data, many=True).data

        expected = {
            "status_code": 200,
            "body": paginated_body(serialized),
        }

        testclient.get_request_test_helper(expected, path_params=path_params, query_params=query_params)

    def test_filter_time_nothing(self, fakedevice, testclient, fake_ts_archive_data):
        """Try to get archive data from the distant past"""

        now = datetime.datetime.utcnow()
        start_date = now - datetime.timedelta(weeks=15)

        trimmed_archive_data = [i for i in fake_ts_archive_data if i.start <= start_date]

        path_params = {
            "device_id": fakedevice.id,
        }
        query_params = {
            # "page_size": len(trimmed_archive_data),
            "start__lt": start_date.isoformat(),
        }

        serialized = TimeSeriesDataArchiveSerializer(instance=trimmed_archive_data, many=True).data

        expected = {
            "status_code": 200,
            "body": paginated_body(serialized),
        }

        testclient.get_request_test_helper(expected, path_params=path_params, query_params=query_params)
