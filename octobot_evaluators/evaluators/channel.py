from types import SimpleNamespace


class _NoOpChannel:
    def __init__(self, *args, **kwargs):
        self._id = kwargs.get("id", "stub")

    async def new_consumer(self, callback, priority_level=None, bot_id=None, subject=None):
        # return a simple object that exposes the expected API but does nothing
        async def _noop(*a, **kw):
            return None

        return SimpleNamespace(new_consumer=_noop)


def get_chan(channel_name: str, chan_id: str):
    """Return a lightweight channel-like object with an async new_consumer method.

    This mirrors the small subset of the real API used by OctoBot logging and
    initialization code. The returned object is safe to await but performs no
    operations.
    """
    return _NoOpChannel(id=chan_id)
