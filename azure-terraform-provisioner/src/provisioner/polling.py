"""Finite polling shared by job and pipeline monitors."""

import time


def wait_until(fetch, done, timeout_seconds, poll_seconds):
    deadline = time.monotonic() + timeout_seconds
    while True:
        value = fetch()
        if done(value):
            return value
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Monitoring timed out; inspect the run using the status command")
        time.sleep(min(poll_seconds, remaining))
