#from unittest import patch
from unittest.mock import Mock, create_autospec, patch

from zconnect.handlers import event_message_handler
from zconnect.messages import Message
from zconnect.models import Event


def get_message(device, event_def):
    return Message(
        category = "event",
        device = device,
        body = {
            "event_id": "{}:{}".format(device.id, event_def.id),
            "source": "server",
            "current": device.get_latest_ts_data()
        },
    )

def fake_get_action_handlers(actions):
    """Mocked out decorator store """
    def get_action_handler(key):
        return actions.get(key)

    return get_action_handler

# Needed for auto specing
def fake_action_handler(message, listener=None, action_args={}, event_def=None):
    pass

def get_handler_mock():
    return create_autospec(fake_action_handler)

class TestEventMessageHandler:

    def setup(self):
        self.listener = get_handler_mock()

    def test_no_actions(self, fakedevice, fake_device_event_definition):
        """ Checks that no exceptions are thrown if there are no actions """
        fake_device_event_definition.actions = False
        fake_device_event_definition.save()
        message = get_message(fakedevice, fake_device_event_definition)

        event_message_handler(message, self.listener)
        # Lack of exception is a pass

    def test_bad_event_def_id(self, fakedevice, fake_device_event_definition):
        """Asserts that logs are made if the action handler is missing """
        message = get_message(fakedevice, fake_device_event_definition)
        # non-existent event definition id
        message.body["event_id"] = "123:123123"

        with patch("zconnect.handlers.logger.exception") as log_mock:
            event_message_handler(message, self.listener)

        log_mock.assert_called_once_with("Event definition %s does not exist! device: %s",
            "123123", fakedevice.id)

    def test_missing_action_key(self, fakedevice, fake_device_event_definition):
        """Asserts that logs are made if the event definition doesn't exist """
        action_handlers = fake_get_action_handlers({})
        message = get_message(fakedevice, fake_device_event_definition)
        with patch("zconnect.handlers.get_action_handlers",
                side_effect=action_handlers), \
            patch("zconnect.handlers.logger.error") as log_mock:

                event_message_handler(message, self.listener)

        log_mock.assert_called_once_with(
                    "Event definition %s has action key for %s, but there were no handlers",
                     str(fake_device_event_definition.id), "test_action"
        )

    def test_calls_handler(self, fakedevice, fake_device_event_definition):
        """ Checks that the action handler is called correcly """
        handler = get_handler_mock()
        action_handlers = fake_get_action_handlers({
            "test_action": [handler]
        })
        message = get_message(fakedevice, fake_device_event_definition)

        with patch("zconnect.handlers.get_action_handlers",
                side_effect=action_handlers),\
            patch("zconnect.handlers.EventDefinition.objects.get",
                    return_value=fake_device_event_definition):
                event_message_handler(message, self.listener)

        handler.assert_called_once_with(
            message,
            listener=self.listener,
            action_args="also_a_test",
            event_def=fake_device_event_definition,
        )

    def test_calls_multiple_handlers(self, fakedevice, fake_device_event_definition):
        handler = get_handler_mock()
        handler2 = get_handler_mock()
        action_handlers = fake_get_action_handlers({
            "test_action": [handler, handler2]
        })
        message = get_message(fakedevice, fake_device_event_definition)

        with patch("zconnect.handlers.get_action_handlers",
                side_effect=action_handlers),\
            patch("zconnect.handlers.EventDefinition.objects.get",
                    return_value=fake_device_event_definition):
            event_message_handler(message, self.listener)

        handler.assert_called_once_with(
            message,
            listener=self.listener,
            action_args="also_a_test",
            event_def=fake_device_event_definition,
        )
        handler2.assert_called_once_with(
            message,
            listener=self.listener,
            action_args="also_a_test",
            event_def=fake_device_event_definition,
        )

    def test_does_not_call_other_handlers(self, fakedevice, fake_device_event_definition):
        handler = get_handler_mock()
        handler2 = get_handler_mock()
        action_handlers = fake_get_action_handlers({
            "test_action": [handler],
            "some_other_action": [handler2],
        })
        message = get_message(fakedevice, fake_device_event_definition)

        with patch("zconnect.handlers.get_action_handlers",
                side_effect=action_handlers),\
            patch("zconnect.handlers.EventDefinition.objects.get",
                    return_value=fake_device_event_definition):
            event_message_handler(message, self.listener)

        handler.assert_called_once_with(
            message,
            listener=self.listener,
            action_args="also_a_test",
            event_def=fake_device_event_definition,
        )
        assert not handler2.called

    def test_calls_multiple_actions_handlers(self, fakedevice, fake_device_event_definition):
        handler = get_handler_mock()
        handler2 = get_handler_mock()
        action_handlers = fake_get_action_handlers({
            "test_action": [handler],
            "other_action": [handler2],
        })

        fake_device_event_definition.actions = {
            "test_action": "also_a_test",
            "other_action": {"arg1": True},
        }
        fake_device_event_definition.save()

        message = get_message(fakedevice, fake_device_event_definition)

        with patch("zconnect.handlers.get_action_handlers",
                side_effect=action_handlers),\
            patch("zconnect.handlers.EventDefinition.objects.get",
                    return_value=fake_device_event_definition):
            event_message_handler(message, self.listener)

        handler.assert_called_once_with(
            message,
            listener=self.listener,
            action_args="also_a_test",
            event_def=fake_device_event_definition,
        )
        handler2.assert_called_once_with(
            message,
            listener=self.listener,
            action_args=fake_device_event_definition.actions["other_action"],
            event_def=fake_device_event_definition,
        )

    def test_saves_event_object(self, fakedevice, fake_device_event_definition):
        fake_device_event_definition.actions = False
        fake_device_event_definition.save()
        message = get_message(fakedevice, fake_device_event_definition)

        assert Event.objects.all().count() == 0

        event_message_handler(message, self.listener)

        assert Event.objects.all().count() == 1
        event = Event.objects.all().first()
        assert event.success
        assert event.definition == fake_device_event_definition
        assert event.device == fakedevice

    def test_saves_event_object_unsuccessful(self, fakedevice, fake_device_event_definition):

        handler = Mock(side_effect=Exception("not a well written handler"))
        action_handlers = fake_get_action_handlers({
            "test_action": [handler],
        })

        message = get_message(fakedevice, fake_device_event_definition)

        assert Event.objects.all().count() == 0

        with patch("zconnect.handlers.get_action_handlers",
                side_effect=action_handlers):
            event_message_handler(message, self.listener)

        assert Event.objects.all().count() == 1
        event = Event.objects.all().first()
        assert not event.success
        assert event.definition == fake_device_event_definition
        assert event.device == fakedevice
