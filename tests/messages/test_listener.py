import datetime
from unittest.mock import patch

import pytest
from rest_framework import serializers

from zconnect._messages.listener import Listener
from zconnect.handlers import device_state_report_handler
from zconnect.messages import Message


class TestStateReport:

    @pytest.fixture(name="test_message")
    def fix_fake_message(self, fakedevice):
        test_message = Message.from_dict({
            "category": "report_state",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "device": fakedevice.id,
            "body": {
                "tag": 123,
            }
        })

        return test_message

    @pytest.fixture(name="mocked_listener")
    def fix_mocked_listener(self):
        with patch("zconnect._messages.listener.load_from_module"):
            listener = Listener({
                "report_state": [device_state_report_handler],
            })

            yield listener

    def test_send_report_state_message(self, mocked_listener, test_message):
        """Success"""
        with patch("zconnect.handlers.Message.send_to_device") as msg_mock:
            with patch("zconnect._messages.listener.logger.exception") as lemock:
                mocked_listener._message_callback(test_message)

        assert msg_mock.called
        assert not lemock.called

    def test_send_report_state_message_on_bad_schema(self, fakeproduct, mocked_listener, test_message):
        """It should respond if the schema is bad"""
        fakeproduct.state_serializer_name = "kosdfks"
        fakeproduct.save()

        class OuterSerializer(serializers.Serializer):
            data = serializers.IntegerField(required=True)

        with patch("zconnect.handlers.Message.send_to_device") as msg_mock:
            with patch("zconnect._messages.schemas.import_callable", return_value=OuterSerializer), \
            patch("zconnect._messages.listener.logger.exception") as lemock:
                mocked_listener._message_callback(test_message)

        assert msg_mock.called
        assert lemock.call_args[0][0] == "Worker error raised during processing of event %s"

    def test_send_report_state_message_on_failure(self, fakeproduct, mocked_listener, test_message):
        """Same, but with an unexpected error"""

        fakeproduct.state_serializer_name = "kosdfks"
        fakeproduct.save()

        with patch("zconnect.handlers.Message.send_to_device") as msg_mock:
            # random error
            with patch("zconnect._messages.schemas.import_callable", side_effect=AttributeError), \
            patch("zconnect._messages.listener.logger.exception") as lemock:
                mocked_listener._message_callback(test_message)

        assert msg_mock.called
        assert lemock.call_args[0][0] == "Unexpected exception raised during processing of event %s"
