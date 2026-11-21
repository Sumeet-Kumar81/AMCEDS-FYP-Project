"""WebSocket hub (built in B1-A1-29). Channels: ``dispatchers`` and ``driver:<user_id>``.

Events: SDS v1.1 Table 4.4. Envelope, event names and data models: contract C-5,
``app/schemas/events.py`` (``EVENTS``). Worker events arrive through Postgres NOTIFY (D-010).
"""
