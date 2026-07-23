"""Public-facing JMeter tool services (the tester's entry point).

These orchestrate the existing internal engine (validation, plan store, the
shared Operations queue) behind a JMeter-first public API. They add no new
execution machinery — the Runtime, Worker, Dispatcher, Scheduler, and stores are
unchanged.
"""
