import abc


class HandlerBase(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def process(self, event, listener):
        """Called with a relevant event and the listener class that called
        this function. Though this is a 'listener', it can be used to send
        messages in response to the message that triggered this event.

        Args:
            event (Message): triggered event
            listener (object): listener object
        """
