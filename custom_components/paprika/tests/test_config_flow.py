"""Config flow tests for Paprika integration."""

from custom_components.paprika.config_flow import (
    PaprikaConfigFlow,
    PaprikaOptionsFlowHandler,
)


def test_async_get_options_flow_returns_handler():
    """The options flow helper should be callable as a static method."""
    dummy_entry = object()

    flow = PaprikaConfigFlow.async_get_options_flow(dummy_entry)

    assert isinstance(flow, PaprikaOptionsFlowHandler)
    assert flow.config_entry is dummy_entry
