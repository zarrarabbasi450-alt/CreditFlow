import os

import pytest


@pytest.mark.skipif(
    os.getenv("RUN_INFRASTRUCTURE_TESTS") != "true", reason="requires Redis and RabbitMQ containers"
)
def test_live_infrastructure_opt_in() -> None:
    assert os.getenv("REDIS_URL") and os.getenv("RABBITMQ_URL")
