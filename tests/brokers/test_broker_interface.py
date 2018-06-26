from unittest import mock

from ibmiotf.application import Event, Status
from ibmiotf.codecs import jsonCodec
from paho.mqtt.client import MQTTMessage
import pytest

from zconnect import zsettings
from zconnect.messages import IBMInterface, Message, get_listener, get_sender
from zconnect.testutils.factories import EventDefinitionFactory

IBM = "zconnect.messages.IBMInterface"
TOPIC = "iot-2/type/{}/id/{}/evt/{}/fmt/json"


class TestListener:
    def test_message_callback(self, fakedevice):
        with mock.patch(IBM + ".connect"):
            greenlet = get_listener()
            mocked = mock.Mock()
            message = Message("cat", {"a": "b"}, fakedevice)
            greenlet.client.message_handlers = {
                "cat": [mocked]
            }
            greenlet.client._message_callback(message)

            mocked.assert_called_once_with(message, greenlet.client)

    @pytest.mark.xfail(reason="rate limiter doesn't work with mock redis - needs fixing")
    def test_message_handler(self, fakedevice):
        with mock.patch("zconnect.handlers.insert_timeseries_data") as insert, \
             mock.patch(IBM + ".connect") as connect, \
             mock.patch(IBM + ".subscribeToDeviceEvents") as subscribe, \
             mock.patch(IBM + ".subscribeToDeviceStatus"):

            topic = (
                TOPIC
                .format("testproduct123", fakedevice.id, "periodic")
                .encode("utf8")
            )

            paho_message = MQTTMessage(topic=topic)
            paho_message.payload = b'{"foo": "bar"}'

            event = Event(paho_message, {"json": jsonCodec})

            greenlet = get_listener()
            greenlet.client.subscribe_to_events()
            greenlet.client.broker_interface.deviceEventCallback(event)

            assert insert.called
            assert connect.called
            assert subscribe.called

    def test_status_handler(self, fakedevice):
        EventDefinitionFactory(device=fakedevice, product=None)
        with mock.patch(IBM + ".connect") as connect, \
             mock.patch(IBM + ".subscribeToDeviceEvents") as subscribe, \
             mock.patch(IBM + ".subscribeToDeviceStatus"), \
             mock.patch("zconnect.handlers.logger.info") as info_log:

            topic = "iot-2/type/testproduct123/id/{}/mon"
            topic = topic.format(fakedevice.id).encode("utf8")

            paho_message = MQTTMessage(topic=topic)
            paho_message.payload = b'{"Action": "Connect"}'

            event = Status(paho_message)

            greenlet = get_listener()
            greenlet.client.subscribe_to_events()
            greenlet.client.broker_interface.deviceStatusCallback(event)

            assert connect.called
            assert subscribe.called

            assert info_log.called

            msg = "Connection message success (device: %s) (action: %s)"
            assert info_log.call_args_list == [
                mock.call(msg, fakedevice.id, "Connect"),
            ]


class TestSender:
    def test_to_device(self, fakedevice):
        with mock.patch(IBM + ".connect"), \
             mock.patch(IBM + ".send_message") as send:

            sender = get_sender()

            sender.to_device("cat", {"a": "b"}, device_id=fakedevice.get_iot_id(),
                             device_type=fakedevice.product.iot_name)
            send.assert_called_once_with("cat", {"a": "b"},
                                         device_id=str(fakedevice.id),
                                         device_type=fakedevice.product.iot_name)

            send.reset_mock()
            sender.to_device("cat", {"a": "b"}, device=fakedevice)
            send.assert_called_once_with("cat", {"a": "b"},
                                         device_id=str(fakedevice.id),
                                         device_type="testproduct123")

            send.reset_mock()
            sender.to_device("example-category", {"foo": "bar"})
            send.assert_not_called()

            send.reset_mock()
            message = Message("incoming-category", {"a": "b"}, fakedevice)
            sender.to_device("cat", {"a": "b"}, incoming_message=message)
            send.assert_called_once_with("cat", {"a": "b"},
                                         device_id=str(fakedevice.id),
                                         device_type="testproduct123")

    def test_as_device(self, fakedevice):
        with mock.patch(IBM + ".connect"), \
             mock.patch(IBM + ".send_as_device") as send:

            sender = get_sender()

            sender.as_device("cat", {"a": "b"}, device_id=fakedevice.get_iot_id(),
                             device_type=fakedevice.product.iot_name)
            send.assert_called_once_with("cat", {"a": "b"},
                                         device_id=str(fakedevice.id),
                                         device_type=fakedevice.product.iot_name)

            send.reset_mock()
            sender.as_device("cat", {"a": "b"}, device=fakedevice)
            send.assert_called_once_with("cat", {"a": "b"},
                                         device_id=str(fakedevice.id),
                                         device_type="testproduct123")

            send.reset_mock()
            sender.as_device("example-category", {"foo": "bar"})
            send.assert_not_called()

            send.reset_mock()
            message = Message("incoming-category", {"a": "b"}, fakedevice)
            sender.as_device("cat", {"a": "b"}, incoming_message=message)
            send.assert_called_once_with("cat", {"a": "b"},
                                         device_id=str(fakedevice.id),
                                         device_type="testproduct123")


@pytest.fixture(name="interface")
def fix_interface():
    with mock.patch(IBM + ".connect"):
        sender_settings = dict(zsettings.SENDER_SETTINGS)
        interface = IBMInterface(sender_settings)

        yield interface


class TestParseEvents:
    def test_parse_ibm_event(self, fakedevice, interface):
        topic = (
            TOPIC
            .format("testproduct123", fakedevice.id, "example_category")
            .encode("utf8")
        )

        paho_message = MQTTMessage(topic=topic)
        paho_message.payload = b'{"foo": "bar"}'

        event = Event(paho_message, {"json": jsonCodec})

        zconnect_message = interface.construct_zconnect_message(event)

        assert zconnect_message.device.id == fakedevice.id
        assert (zconnect_message.device.product.iot_name
                == fakedevice.product.iot_name
                == "testproduct123")
        assert zconnect_message.category == "example_category"
        assert zconnect_message.body == {"foo": "bar"}


class TestIBMInterface:

    def test_send_message(self, fakedevice, interface):
        with mock.patch(IBM + ".publishCommand") as publish:

            interface.send_message("cat", {"a": "b"}, device_id=fakedevice.get_iot_id(),
                device_type=fakedevice.product.iot_name)
            publish.assert_called_once_with("testproduct123",
                                            str(fakedevice.id), "cat", "json",
                                            data={"a": "b"}, qos=1)

            publish.reset_mock()
            interface.send_message("cat", {"a": "b"}, device_id=fakedevice.id,
                                     device_type="testproduct123")
            publish.assert_called_once_with("testproduct123", fakedevice.id,
                                            "cat", "json", data={"a": "b"},
                                            qos=1)

            publish.reset_mock()

    def test_send_as_device(self, fakedevice, interface):
        with mock.patch(IBM + ".publishEvent") as publish:

            interface.send_as_device("cat", {"a": "b"}, device_id=fakedevice.get_iot_id(),
                device_type=fakedevice.product.iot_name)
            publish.assert_called_once_with("testproduct123",
                                            str(fakedevice.id), "cat",
                                            "json-iotf", data={"a": "b"}, qos=1)

            publish.reset_mock()
            interface.send_as_device("cat", {"a": "b"}, device_id=fakedevice.id,
                                     device_type="testproduct123")
            publish.assert_called_once_with("testproduct123", fakedevice.id,
                                            "cat", "json-iotf",
                                            data={"a": "b"}, qos=1)

            publish.reset_mock()

    def test_generate_event_callback(self, fakedevice, interface):
        with mock.patch(IBM + ".construct_zconnect_message") as construct:

            mocked = mock.Mock()

            message = Message("cat", {"a": "b"}, fakedevice)
            construct.return_value = message
            callback = interface.generate_event_callback(mocked)
            callback("test")
            mocked.assert_called_once_with(message)

    def test_generate_status_callback(self, fakedevice, interface):
        mocked = mock.Mock()

        topic = "iot-2/type/testproduct123/id/{}/mon"
        topic = topic.format(fakedevice.id).encode("utf8")
        paho_message = MQTTMessage(topic=topic)
        paho_message.payload = b'{"Action": "Disconnect"}'
        event = Status(paho_message)
        callback = interface.generate_status_callback(mocked)
        callback(event)

        assert mocked.call_count == 1

    def test_construct_message(self, fakedevice, interface):
        topic = (
            TOPIC
            .format("testproduct123", fakedevice.id, "periodic")
            .encode("utf8")
        )
        paho_message = MQTTMessage(topic=topic)
        paho_message.payload = b'{"foo": "bar"}'
        event = Event(paho_message, {"json": jsonCodec})

        message = interface.construct_zconnect_message(event)

        assert message.category == "periodic"
        assert message.body == {"foo": "bar"}
        assert message.device == fakedevice

    def test_construct_message_2(self, fakedevice, interface):
        topic = "iot-2/type/testproduct123/id/{}/mon"
        topic = topic.format(fakedevice.id).encode("utf8")
        paho_message = MQTTMessage(topic=topic)
        paho_message.payload = b'{"Action": "Disconnect"}'
        event = Status(paho_message)

        message_2 = interface.construct_zconnect_message(event)

        assert message_2.category == "status"
        assert message_2.body == {"Action": "Disconnect"}
        assert message_2.device == fakedevice
