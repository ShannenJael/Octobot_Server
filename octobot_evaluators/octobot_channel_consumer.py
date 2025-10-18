"""Tiny stub to mimic octobot_evaluators.octobot_channel_consumer API used by core."""

def get_chan(channel_name: str, chan_id: str):
    class _StubChan:
        async def new_consumer(self, *args, **kwargs):
            async def _noop(*a, **kw):
                return None

            return _noop

    return _StubChan()
