import logging

logger = logging.getLogger(__name__)


class EventDefinitionMixin:
    """Mixin that things can subclass from to allow parsing event defitions on
    it

    currently only works on Devices and Products
    """

    method_override_weight = 10

    def update_actions(self, event, actions):
        """ Add more actions to an event definition

        DynamicField's need a new dict to know there's a change

        Args:
            event (EventDefinition): What definition triggered this event
            actions (dict): DynamicField of actions to add to event

        Returns:
            EventDefinition: Updated definition
        """
        try:
            copied_dict = event.actions.copy()
        except AttributeError:
            copied_dict = {}

        copied_dict.update(actions)
        event.actions = copied_dict

    def update_event_defs(self, event_defs):
        """Create or update from post request

        Args:
            event_defs (list(EventDefinition)): list of new event definitions to
                add or update on this Device/Product
        """

        allowed_fields = ['enabled', 'ref', 'condition', 'actions']

        for event_def in event_defs:
            valid_values = {k: v for k, v in event_def.items()
                            if k in allowed_fields}

            # Try to match on existing reference.
            query_dict = {"ref": valid_values.get('ref')}

            try:
                to_update = self.event_defs.get(**query_dict)
                for key, value in valid_values.items():
                    if key == 'actions':
                        # Special case for the dynamic field
                        self.update_actions(to_update, value)
                    else:
                        to_update[key] = value

            except self.DoesNotExist:
                self.event_defs.create(**valid_values)

    def clean(self):
        """Add the scheduled flag to event_defs where needed"""
        # pylint: disable=not-an-iterable
        for event_def in self.event_defs.all():
            # remove spaces
            event_def.condition = event_def.condition.replace(" ", "")

            if any(cond for cond in ["period==", "day==", "time=="] if cond in event_def.condition):
                event_def.scheduled = True
            else:
                event_def.scheduled = None
