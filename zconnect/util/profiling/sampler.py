import atexit
import collections
import logging
import signal
import time
import traceback

import gevent

logger = logging.getLogger(__name__)


class Sampler(gevent.Greenlet):
    """
    A simple stack sampler for low-overhead CPU profiling: samples the call
    stack every `interval` seconds and keeps track of counts by frame. Because
    this uses signals, it only works on the main thread.
    """
    def __init__(self, interval=0.005):
        self.interval = interval
        self._started = None
        self._stack_counts = collections.defaultdict(int)

        super().__init__()

    def start(self):
        self._started = time.time()
        try:
            signal.signal(signal.SIGVTALRM, self._sample)
        except ValueError:
            raise ValueError('Can only sample on the main thread')

        signal.setitimer(signal.ITIMER_VIRTUAL, self.interval)
        atexit.register(self.stop)

        super().start()

    def _sample(self, signum, frame):
        self._extract(frame)
        signal.setitimer(signal.ITIMER_VIRTUAL, self.interval)

    def _extract(self, frame):
        stack = []
        for f, _ in traceback.walk_stack(frame):
            stack.append(self._format_frame(f))

        stack = ';'.join(reversed(stack))
        self._stack_counts[stack] += 1

    def _format_frame(self, frame):
        return '{}({})'.format(frame.f_code.co_name,
                               frame.f_globals.get('__name__'))

    def output_stats(self):
        if self._started is None:
            return ''
        elapsed = time.time() - self._started
        lines = ['elapsed {}'.format(elapsed),
                 'granularity {}'.format(self.interval)]
        ordered_stacks = sorted(self._stack_counts.items(),
                                key=lambda kv: kv[1], reverse=True)
        lines.extend(['{} {}'.format(frame, count)
                      for frame, count in ordered_stacks])
        return '\n'.join(lines) + '\n'

    def reset(self):
        self._started = time.time()
        self._stack_counts = collections.defaultdict(int)

    def stop(self):
        self.reset()
        signal.setitimer(signal.ITIMER_VIRTUAL, 0)

    def __del__(self):
        self.stop()
