"""The worker agent's isolation boundary, asserted rather than assumed.

This is the validation test [runtime-boundary](../../../../.ai/standards/architecture/runtime-boundary.md)
RB5 requires of every runtime boundary, and it enforces RB3 against the *real
transitive import closure* — where ``aios arch`` checks only direct imports in
the source tree.

The JMeter worker must never write operation state. Two things enforce that:
the agent imports no persistence, and ``docker/jmeter/Dockerfile`` copies only
the trees it does import — so the DAO and the services layer are not even
present in the worker image.

Both of those decay silently. One added import in a module the agent already
uses is enough to pull ``app.dao`` back in, and the Dockerfile would then be
copying an incomplete set (the image would break at boot, which is at least
loud) *or* someone would "fix" it by restoring ``COPY app ./app`` (which is
silent, and undoes the boundary). This test is what makes that visible in CI
instead of in production.

It is deliberately written against the *import closure*, not against a list of
files: that is the thing the Dockerfile's copy list has to match.
"""

import subprocess
import sys
import textwrap
import unittest

#: Top-level ``app.*`` trees the worker agent is allowed to reach. Mirrors the
#: COPY list in docker/jmeter/Dockerfile — if you change one, change the other.
_ALLOWED_PREFIXES = (
    "app.runtime.jmeter",
    "app.runtime",
    "app.core",
    "app.schemas.tools.jmeter",
    "app.integrations.jmeter",
    # Namespace package roots on the way to the above. Present as modules in
    # the closure, but they contain no code of their own.
    "app.schemas",
    "app.schemas.tools",
    "app.integrations",
)

#: Trees whose presence would mean the worker can reach persistence or the
#: server's own machinery. Named explicitly so a failure says what went wrong.
_FORBIDDEN_PREFIXES = (
    "app.dao",
    "app.services",
    "app.routers",
    "app.bootstrap",
    "app.domain",
    "app.integrations.owasp_zap",
    "app.integrations.chat",
)


def _agent_import_closure() -> set:
    """Import the agent in a clean interpreter and return the ``app.*`` modules it pulls in.

    A subprocess is used because the test suite has already imported most of
    the application by this point; measuring the closure in-process would
    measure the suite, not the agent.
    """
    script = textwrap.dedent(
        """
        import sys, json, importlib
        importlib.import_module("app.runtime.jmeter.main")
        print(json.dumps(sorted(m for m in sys.modules if m.startswith("app."))))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=".",
    )
    import json  # noqa: PLC0415

    return set(json.loads(completed.stdout.strip().splitlines()[-1]))


class WorkerAgentIsolationTests(unittest.TestCase):
    def setUp(self):
        self.closure = _agent_import_closure()

    def test_agent_reaches_no_persistence_or_server_machinery(self):
        leaked = sorted(
            module
            for module in self.closure
            if module.startswith(_FORBIDDEN_PREFIXES)
        )
        self.assertEqual(
            [],
            leaked,
            "The worker agent must not import the DAO, the services layer, the "
            "server's routers or another tool's integration — a worker that can "
            "reach persistence can make lifecycle decisions, which belongs to "
            f"JMeterRuntime on the server. Leaked: {leaked}",
        )

    def test_agent_stays_inside_the_trees_the_worker_image_copies(self):
        outside = sorted(
            module
            for module in self.closure
            if not module.startswith(_ALLOWED_PREFIXES)
        )
        self.assertEqual(
            [],
            outside,
            "The worker agent imports modules that docker/jmeter/Dockerfile does "
            "not copy into the worker image, so the image would fail at boot. "
            "Either drop the import or add the tree to BOTH this allowlist and "
            f"the Dockerfile COPY list. Outside: {outside}",
        )


if __name__ == "__main__":
    unittest.main()
