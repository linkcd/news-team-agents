import threading

from bedrock_agentcore.runtime.models import PingStatus


def make_ping_handler(lock: threading.Lock):
    def ping_handler() -> PingStatus:
        if lock.locked():
            return PingStatus.HEALTHY_BUSY
        return PingStatus.HEALTHY

    return ping_handler
