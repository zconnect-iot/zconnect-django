import pytest


class TestAggregatedContext:
    def test_aggregatations(self, fakedevice, simple_ts_data):
        """ Test that the values returned from the AggregatedContext aggregations are correct using
        simple ts data """
        context = fakedevice.get_context()
        assert context['power_sensor'] == 0.0
        # 250 seconds will take the last 3 ts readings where interval is 2 minutes
        assert context['sum_250_power_sensor'] == 3
        assert context['avg_250_power_sensor'] == 1
        assert context['min_250_power_sensor'] == 0
        assert context['max_250_power_sensor'] == 2
        assert context['count_250_power_sensor'] == 3

    def test_key_errors(self, fakedevice, simple_ts_data):
        """ Test KeyError messages when the AggregatedContext key is invalid """
        context = fakedevice.get_context()
        with pytest.raises(KeyError) as err:
            context['sum_250']
        assert "'sum_250' not a key in dictionary nor does it match the \
aggregation format of '<aggreation_type>_<seconds>_<sensor_name>'" == err.value.args[0]
        with pytest.raises(KeyError) as err:
            context['a_250_power_sensor']
        assert "'a_250_power_sensor' not a key in dictionary nor is the aggregation_type 'a' \
one of the following" in err.value.args[0]
        with pytest.raises(KeyError) as err:
            context['sum_25a_power_sensor']
        assert "'sum_25a_power_sensor' not a key in dictionary nor can the time period '25a' be \
parsed as an int" == err.value.args[0]
        with pytest.raises(KeyError) as err:
            context['sum_250_abc']
        assert "'sum_250_abc' not a key in dictionary nor is the sensor name 'abc' one of the \
following: ['power_sensor']" == err.value.args[0]
