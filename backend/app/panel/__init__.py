"""Device panel gateway: bounded, authenticated read model + safe actions.

Implements the contract defined in the Herdr Panel firmware docs
(``docs/PRODUCT_LOGIC.md`` §4.2 and ``docs/ARCHITECTURE.md`` §4). The panel
never exposes raw pane input; every action is revalidated against the live
terminal before a single key sequence is sent, at most once per request_id.
"""
