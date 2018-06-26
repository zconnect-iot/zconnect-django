from unittest.mock import patch

import pytest
from rest_framework import serializers

from zconnect._messages.message import Message
from zconnect._messages.schemas import verify_message_schema
from zconnect.util import exceptions


class BadDeserializer(serializers.Serializer):
    a_missing_field = serializers.CharField()


class GoodDeserializer(serializers.Serializer):
    test_int = serializers.IntegerField()
    test_string = serializers.CharField()


@pytest.fixture(name="test_message")
def fix_test_message(fakedevice):
    fakedevice.product.state_serializer_name = "coolserializer"
    fakedevice.product.save()

    message = Message(
        category="test_message",
        body={
            "state": {
                "reported": {
                    "test_int": 123,
                    "test_string": "abc",
                }
            }
        },
        device=fakedevice,
    )

    return message


class TestVerifySchema:

    def test_no_state_error(self, test_message):
        """no 'state' in message raises an error, independent of verifier being used or not"""
        test_message.body = {"hello": "test"}

        with pytest.raises(exceptions.BadMessageSchemaError):
            verify_message_schema(test_message)

    def test_no_reported_error(self, test_message):
        """no 'reported' in message state raises an error, independent of verifier being used or not"""
        test_message.body["state"] = {"hello": "test"}

        with pytest.raises(exceptions.BadMessageSchemaError):
            verify_message_schema(test_message)

    def test_no_verifier_works(self, fakeproduct, test_message):
        """No verifier set on the product"""

        fakeproduct.state_serializer_name = ""
        fakeproduct.save()

        verify_message_schema(test_message)

        # hack test
        with patch("zconnect._messages.schemas.logger.warning", side_effect=NotImplementedError):
            with pytest.raises(NotImplementedError):
                verify_message_schema(test_message)

    @pytest.mark.parametrize("loc", (
        # various valid entry points that all point to nonexistent things
        "ofkpofkw3",
        "o3ko.omhoote",
        "o3ko.omhoote:abc",
    ))
    def test_invalid_verifier_raises(self, fakeproduct, test_message, loc):
        """Invalid callable used for product verifier name"""
        fakeproduct.state_serializer_name = loc
        fakeproduct.save()

        with pytest.raises(exceptions.BadMessageSchemaError) as e:
            verify_message_schema(test_message)

        assert "Error loading schema" in str(e.value)

    def test_with_verifier_wrong_serializer(self, test_message):
        """Mock loading verifier which raises a validation error because the serializer is wrong"""

        with patch("zconnect._messages.schemas.import_callable", return_value=BadDeserializer):
            with pytest.raises(exceptions.BadMessageSchemaError):
                verify_message_schema(test_message)

    def test_with_verifier_wrong_data(self, test_message):
        """Same, but the data is wrong"""

        test_message.body["state"]["reported"] = {
            "a": "b",
        }

        with patch("zconnect._messages.schemas.import_callable", return_value=GoodDeserializer):
            with pytest.raises(exceptions.BadMessageSchemaError):
                verify_message_schema(test_message)

    def test_with_verifier_success(self, test_message):
        """Correct deserializer + data format"""

        with patch("zconnect._messages.schemas.import_callable", return_value=GoodDeserializer):
            verify_message_schema(test_message)

    def test_nested_validate(self, test_message):
        """Nested deserialization"""

        class OuterSerializer(serializers.Serializer):
            data = GoodDeserializer(required=True)
            tag = serializers.CharField()

        test_message.body["state"]["reported"] = {
            "tag": "chocolate",
            "data": test_message.body["state"]["reported"],
        }

        with patch("zconnect._messages.schemas.import_callable", return_value=OuterSerializer):
            verify_message_schema(test_message)
