#!/usr/bin/env python3
"""aios — the AIOS deterministic-tooling CLI.

One entry point for every mechanical check the AIOS governs (Decision 0001,
Roadmap M2). Standard-library only, by the dependency principle in Decision
0001's M2 addendum: no pyyaml, no jsonschema. Frontmatter uses a documented
simple subset; the schema validator covers exactly the JSON-Schema feature set
our schemas use and FAILS LOUD on any keyword it does not implement, so an
unsupported construct is a hard error rather than a silent non-check.

Usage:
    python .ai/tools/aios.py <command> [options]

Commands:
    validate   Validate every unit's frontmatter against its schema + id==path.
    links      Check every relative markdown link under the tree resolves.
    index      (Re)generate <module>/<category>/INDEX.md from unit frontmatter.
    impact     Reverse-dependency + Impact Report for a changed unit.
    lint       Enforce the line-count ceiling on routing files.
    check      Run validate + links + lint as one CI gate (nonzero on any fail).
    selftest   Prove the impact/validation engines on synthetic fixtures.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

# .ai/ root — this file lives at .ai/tools/aios.py
AI_ROOT = Path(__file__).resolve().parent.parent
CEILING = 150  # soft line-count ceiling for routing files (Decision 0001)


class SchemaError(Exception):
    """Raised when a schema uses a keyword the mini-validator does not implement.

    Deliberately fatal: silently ignoring an unknown keyword would mean claiming
    a unit is valid without actually checking a constraint the schema author
    intended. Better to stop and demand the validator be extended.
    """


# --------------------------------------------------------------------------
# Frontmatter (simple documented subset: flat scalars + inline [a, b] lists)
# --------------------------------------------------------------------------
_FM_RE = re.compile(r'^---\n(.*?)\n---\n', re.S)


def parse_frontmatter(text):
    """Return (frontmatter_dict, has_block). has_block is False if no --- block."""
    m = _FM_RE.match(text)
    if not m:
        return None, False
    fm = {}
    for raw in m.group(1).splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if ':' not in line:
            raise SchemaError("frontmatter line without ':' — not the supported "
                              "flat subset: %r" % raw)
        key, val = line.split(':', 1)
        key = key.strip()
        val = val.strip()
        if val.startswith('[') and val.endswith(']'):
            inner = val[1:-1].strip()
            val = [x.strip().strip('"\'') for x in inner.split(',')] if inner else []
        else:
            val = val.strip('"\'')
        fm[key] = val
    return fm, True


# --------------------------------------------------------------------------
# Glob → regex (supports ** across segments, * within a segment)
# --------------------------------------------------------------------------
def glob_to_regex(glob):
    out = ['^']
    i = 0
    while i < len(glob):
        if glob[i:i + 3] == '**/':
            out.append('(?:.*/)?')
            i += 3
        elif glob[i:i + 2] == '**':
            out.append('.*')
            i += 2
        elif glob[i] == '*':
            out.append('[^/]*')
            i += 1
        elif glob[i] == '?':
            out.append('[^/]')
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    out.append('$')
    return re.compile(''.join(out))


# --------------------------------------------------------------------------
# Mini JSON-Schema validator (fail-loud on unsupported keywords)
# --------------------------------------------------------------------------
_ASSERT = {'type', 'required', 'properties', 'enum', 'pattern', 'allOf',
           '$ref', 'items', 'minItems', 'minLength', 'additionalProperties'}
_ANNOT = {'$schema', '$id', 'title', 'description', 'default', 'format'}
_TYPES = {'object': dict, 'array': list, 'string': str}


def load_schemas(schema_dir):
    store = {}
    for f in sorted(Path(schema_dir).glob('*.schema.json')):
        store[f.name] = json.loads(f.read_text(encoding='utf-8'))
    return store


def validate_instance(inst, schema, store, loc='<root>'):
    errs = []
    for k in schema:
        if k not in _ASSERT and k not in _ANNOT:
            raise SchemaError("unsupported schema keyword %r at %s — extend the "
                              "mini-validator (fail-loud, never silently skip)" % (k, loc))

    if '$ref' in schema:
        target = store.get(schema['$ref'])
        if target is None:
            raise SchemaError("cannot resolve $ref %r" % schema['$ref'])
        errs += validate_instance(inst, target, store, loc)

    for sub in schema.get('allOf', []):
        errs += validate_instance(inst, sub, store, loc)

    if 'type' in schema:
        pytype = _TYPES.get(schema['type'])
        if pytype is not None and not isinstance(inst, pytype):
            errs.append("%s: expected %s, got %s" % (loc, schema['type'], type(inst).__name__))
            return errs

    if 'enum' in schema and inst not in schema['enum']:
        errs.append("%s: %r not in enum %s" % (loc, inst, schema['enum']))

    if isinstance(inst, str):
        if 'pattern' in schema and not re.search(schema['pattern'], inst):
            errs.append("%s: %r does not match pattern %s" % (loc, inst, schema['pattern']))
        if 'minLength' in schema and len(inst) < schema['minLength']:
            errs.append("%s: shorter than minLength %d" % (loc, schema['minLength']))
        if schema.get('format') == 'date' and not re.match(r'^\d{4}-\d{2}-\d{2}$', inst):
            errs.append("%s: %r is not a YYYY-MM-DD date" % (loc, inst))

    if isinstance(inst, dict):
        for req in schema.get('required', []):
            if req not in inst:
                errs.append("%s: missing required property '%s'" % (loc, req))
        props = schema.get('properties', {})
        for pname, pschema in props.items():
            if pname in inst:
                errs += validate_instance(inst[pname], pschema, store, "%s.%s" % (loc, pname))
        if schema.get('additionalProperties', True) is False:
            for k in inst:
                if k not in props:
                    errs.append("%s: additional property '%s' not allowed" % (loc, k))

    if isinstance(inst, list):
        if 'items' in schema:
            for idx, item in enumerate(inst):
                errs += validate_instance(item, schema['items'], store, "%s[%d]" % (loc, idx))
        if 'minItems' in schema and len(inst) < schema['minItems']:
            errs.append("%s: fewer than minItems %d" % (loc, schema['minItems']))

    return errs


# --------------------------------------------------------------------------
# Unit discovery
# --------------------------------------------------------------------------
def load_schema_map(root):
    mp = json.loads((root / 'tools' / 'schema-map.json').read_text(encoding='utf-8'))
    rules = [(glob_to_regex(r['glob']), r['schema']) for r in mp['rules']]
    return rules, mp.get('default', 'base.schema.json')


def discover_units(root):
    """Yield (relposix, frontmatter_dict) for every .md file that has frontmatter."""
    units = []
    for f in sorted(root.rglob('*.md')):
        rel = f.relative_to(root).as_posix()
        fm, has = parse_frontmatter(f.read_text(encoding='utf-8'))
        if has:
            units.append((rel, fm))
    return units


def schema_for(rel, rules, default):
    for rx, name in rules:
        if rx.match(rel):
            return name
    return default


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def cmd_validate(root, verbose=True):
    store = load_schemas(root / 'schema')
    rules, default = load_schema_map(root)
    units = discover_units(root)
    total_errs = 0
    for rel, fm in units:
        sch_name = schema_for(rel, rules, default)
        schema = store[sch_name]
        errs = validate_instance(fm, schema, store, rel)
        expected_id = rel[:-3] if rel.endswith('.md') else rel
        if fm.get('id') != expected_id:
            errs.append("%s: id %r != path %r" % (rel, fm.get('id'), expected_id))
        if errs:
            total_errs += len(errs)
            print("  FAIL %s  [%s]" % (rel, sch_name))
            for e in errs:
                print("       - %s" % e)
        elif verbose:
            print("  ok   %s  [%s]" % (rel, sch_name))

    # Cross-unit integrity (H1 references, H3 validated_against drift, H2 authority overlap).
    all_fm = [fm for _, fm in units]
    ref_errs = check_references(all_fm)
    drift_errs = check_drift(all_fm)
    auth_errs = check_authority_overlap(all_fm)
    for e in ref_errs:
        print("  REF   %s" % e)
    for e in drift_errs:
        print("  DRIFT %s" % e)
    for e in auth_errs:
        print("  AUTH  %s" % e)
    total_errs += len(ref_errs) + len(drift_errs) + len(auth_errs)

    print("validate: %d unit(s), %d error(s) [refs:%d drift:%d authority:%d]"
          % (len(units), total_errs, len(ref_errs), len(drift_errs), len(auth_errs)))
    return 1 if total_errs else 0


_LINK_RE = re.compile(r'\]\(([^)]+)\)')


def cmd_links(root, verbose=True):
    bad = []
    checked = 0
    for f in sorted(root.rglob('*.md')):
        for m in _LINK_RE.finditer(f.read_text(encoding='utf-8')):
            target = m.group(1).split('#', 1)[0]
            if not target or target.startswith(('http://', 'https://', 'mailto:')):
                continue
            checked += 1
            if not (f.parent / target).resolve().exists():
                bad.append((f.relative_to(root).as_posix(), m.group(1)))
    for rel, t in bad:
        print("  BROKEN %s -> %s" % (rel, t))
    print("links: %d checked, %d broken" % (checked, len(bad)))
    return 1 if bad else 0


CATEGORY_MODULES = ['standards', 'knowledge', 'skills', 'workflows', 'templates', 'playbooks']


def cmd_index(root, write=True):
    generated = 0
    for module in CATEGORY_MODULES:
        mdir = root / module
        if not mdir.is_dir():
            continue
        for catdir in sorted(p for p in mdir.iterdir() if p.is_dir()):
            unit_rows = []
            for f in sorted(catdir.rglob('*.md')):
                if f.name == 'INDEX.md':
                    continue
                fm, has = parse_frontmatter(f.read_text(encoding='utf-8'))
                if not has:
                    continue
                if fm.get('status') == 'Archived':
                    continue
                dep = fm.get('depends_on') or []
                unit_rows.append((fm.get('id', ''), fm.get('title', ''), fm.get('version', ''),
                                  fm.get('status', ''), fm.get('owner', ''),
                                  ', '.join(dep) if dep else '—'))
            if not unit_rows:
                continue
            unit_rows.sort()
            lines = ["# Index — %s/%s" % (module, catdir.name), "",
                     "> Generated by `aios index`. Do not edit by hand.",
                     "> Units: %d" % len(unit_rows), "",
                     "| id | title | version | status | owner | depends_on |",
                     "|---|---|---|---|---|---|"]
            for r in unit_rows:
                lines.append("| %s | %s | %s | %s | %s | %s |" % r)
            out = "\n".join(lines) + "\n"
            if write:
                (catdir / 'INDEX.md').write_text(out, encoding='utf-8')
            generated += 1
            print("  wrote %s/%s/INDEX.md (%d units)" % (module, catdir.name, len(unit_rows)))
    print("index: %d index file(s) generated" % generated)
    return 0


# Frontmatter fields that create a dependency edge: if the referenced unit
# changes, the referencing unit may need revalidation. An Agent that enforces a
# Standard depends on it just as much as a unit that names it in depends_on.
EDGE_FIELDS = ['depends_on', 'standards_enforced', 'knowledge_sources',
               'skills_used', 'workflows_used', 'templates_used']


def _edge_target(ref):
    """Strip an optional version pin: 'standards/x@^1.0' -> 'standards/x'."""
    return ref.split('@', 1)[0]


def build_reverse(units):
    """units: list of frontmatter dicts. Returns (reverse_map, id->fm).

    reverse_map[target_id] = [consumer_ids that reference it via any EDGE_FIELD].
    """
    rev = {}
    idmap = {}
    for fm in units:
        uid = fm.get('id')
        if uid:
            idmap[uid] = fm
    for fm in units:
        uid = fm.get('id')
        for field in EDGE_FIELDS:
            for ref in (fm.get(field) or []):
                rev.setdefault(_edge_target(ref), []).append(uid)
    return rev, idmap


# --------------------------------------------------------------------------
# Integrity checks (H1–H3) — Automation enforcing invariants the v1.0
# architecture already promised. No new schema, routing, or lifecycle; these
# only verify frontmatter that units already carry.
# --------------------------------------------------------------------------
REF_FIELDS = EDGE_FIELDS + ['validated_against']


def check_references(units):
    """H1: every id referenced in a ref field must resolve to a real unit id."""
    ids = {fm.get('id') for fm in units if fm.get('id')}
    errs = []
    for fm in units:
        uid = fm.get('id', '?')
        for field in REF_FIELDS:
            for ref in (fm.get(field) or []):
                target = _edge_target(ref)
                if target not in ids:
                    errs.append("%s: %s -> unresolved reference '%s'" % (uid, field, target))
    return errs


def check_drift(units):
    """H3: a validated_against '{id}@{version}' pin must match the target's current version."""
    idmap = {fm.get('id'): fm for fm in units if fm.get('id')}
    errs = []
    for fm in units:
        uid = fm.get('id', '?')
        for ref in (fm.get('validated_against') or []):
            if '@' not in ref:
                errs.append("%s: validated_against '%s' has no @version pin" % (uid, ref))
                continue
            target, pinned = ref.rsplit('@', 1)
            tgt = idmap.get(target)
            if tgt is None:
                continue  # existence is check_references' job
            current = tgt.get('version')
            if current != pinned:
                errs.append("%s: validated_against %s pinned @%s but current is %s (NeedsRevalidation)"
                            % (uid, target, pinned, current))
    return errs


def _auth_prefix(glob):
    """Literal path prefix of a glob, up to the first wildcard: 'mcp-server/**' -> 'mcp-server'."""
    return re.split(r'[*?]', glob, 1)[0].rstrip('/')


def _path_overlap(a, b):
    """True if two path prefixes are equal or one is a path-ancestor of the other."""
    pa = [s for s in a.split('/') if s]
    pb = [s for s in b.split('/') if s]
    n = min(len(pa), len(pb))
    return n > 0 and pa[:n] == pb[:n]


def check_authority_overlap(units):
    """H2: no two Active Agents may hold overlapping decision_authority."""
    agents = [fm for fm in units
              if fm.get('id', '').startswith('agents/')
              and fm.get('status') == 'Active'
              and fm.get('decision_authority')]
    errs = []
    for i in range(len(agents)):
        for j in range(i + 1, len(agents)):
            a, b = agents[i], agents[j]
            for ga in a['decision_authority']:
                for gb in b['decision_authority']:
                    if _path_overlap(_auth_prefix(ga), _auth_prefix(gb)):
                        errs.append("authority overlap: %s (%s) vs %s (%s)"
                                    % (a['id'], ga, b['id'], gb))
    return errs


def compute_impact(changed_id, change, units):
    """Return {consumer_id: flag} per governance/README.md#impact-analysis rules."""
    rev, idmap = build_reverse(units)
    result = {}

    # Guardrail change: every Agent flagged, regardless of declared depends_on.
    if changed_id.startswith('guardrails/'):
        for uid in idmap:
            if uid.startswith('agents/'):
                result[uid] = 'NeedsRevalidation'
        return result

    if change == 'patch':
        return result

    direct = rev.get(changed_id, [])
    if change == 'minor':
        for c in direct:
            # Playbooks never get the Minor free pass.
            result[c] = 'NeedsRevalidation' if c.startswith('playbooks/') else 'Informational'
        return result

    # major: direct + transitive, all NeedsRevalidation
    seen = set()
    stack = list(direct)
    while stack:
        c = stack.pop()
        if c in seen:
            continue
        seen.add(c)
        result[c] = 'NeedsRevalidation'
        stack.extend(rev.get(c, []))
    return result


def cmd_impact(root, changed_id, change):
    units = [fm for _, fm in discover_units(root)]
    ids = {fm.get('id') for fm in units}
    if changed_id not in ids and not changed_id.startswith('guardrails/'):
        print("impact: '%s' is not a known unit id" % changed_id)
        return 1
    result = compute_impact(changed_id, change, units)
    print("impact: %s (change=%s) affects %d consumer(s)" % (changed_id, change, len(result)))
    blocking = 0
    for cid, flag in sorted(result.items()):
        print("  %-18s %s" % (flag, cid))
        if flag == 'NeedsRevalidation':
            blocking += 1
    if blocking:
        print("  -> %d consumer(s) must be revalidated or Owner-waived before merge" % blocking)
    return 0


ROUTING_FILES = ['MANIFEST.md', 'ROUTER.md', 'INDEX.md']


def cmd_lint(root, verbose=True):
    over = []
    checked = 0
    for f in sorted(root.rglob('*.md')):
        if f.name in ROUTING_FILES:
            checked += 1
            n = len(f.read_text(encoding='utf-8').splitlines())
            if n > CEILING:
                over.append((f.relative_to(root).as_posix(), n))
    for rel, n in over:
        print("  OVER %s: %d lines (ceiling %d)" % (rel, n, CEILING))
    print("lint: %d routing file(s), %d over ceiling" % (checked, len(over)))
    return 1 if over else 0


# ---------------------------------------------------------------------------
# Architecture boundary enforcement (standards/architecture/domain-layer D2/D3)
# ---------------------------------------------------------------------------

# Where the Domain layer lives, relative to the repository root.
DOMAIN_ROOTS = ['mcp-server/app/domain']

# D3 — Domain depends on nothing outside Domain. Any intra-application import
# whose module path is not itself Domain is a violation.
_APP_IMPORT = re.compile(r'^\s*(?:from|import)\s+(app(?:\.[A-Za-z0-9_.]+)?)', re.M)

# D2 — forbidden framework / transport / infrastructure imports inside Domain.
# Matched against the imported module root only, so prose in docstrings and
# comments can name them freely (the rules must be describable in their own file).
FORBIDDEN_DOMAIN_MODULES = {
    'fastapi': 'HTTP framework', 'starlette': 'HTTP framework',
    'pydantic': 'validation framework (serves the HTTP boundary)',
    'pydantic_settings': 'configuration framework',
    'sqlalchemy': 'ORM', 'psycopg2': 'Postgres driver', 'boto3': 'AWS SDK',
    'redis': 'Redis client', 'httpx': 'HTTP client', 'requests': 'HTTP client',
    'urllib': 'HTTP transport', 'slack_sdk': 'Slack transport',
    'zapv2': 'tool SDK', 'zaproxy': 'tool SDK',
    'logging': 'infrastructure logging (domain does not log; callers do)',
}
_IMPORT_MODULE = re.compile(r'^\s*(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_.]+))', re.M)


def check_domain_boundaries(repo_root):
    """Return a list of (file, rule, message) violations of D2/D3.

    Mechanical enforcement of the Domain rules: prose in a Standard an AI can
    ignore becomes a gate it cannot. Scans only the Domain tree — the one place
    where the dependency direction is absolute.
    """
    violations = []
    for domain_rel in DOMAIN_ROOTS:
        domain_dir = repo_root / domain_rel
        if not domain_dir.is_dir():
            continue
        pkg_prefix = domain_rel.split('/', 1)[1].replace('/', '.') if '/' in domain_rel else domain_rel
        for py in sorted(domain_dir.rglob('*.py')):
            if '__pycache__' in py.parts:
                continue
            rel = py.relative_to(repo_root).as_posix()
            text = py.read_text(encoding='utf-8')

            # D3 — no intra-application imports outside Domain itself.
            for m in _APP_IMPORT.finditer(text):
                module = m.group(1)
                if not module.startswith(pkg_prefix):
                    violations.append((rel, 'D3', "imports '%s' (Domain may depend on nothing outside Domain)" % module))

            # D2 — no framework / transport / infrastructure imports.
            for m in _IMPORT_MODULE.finditer(text):
                module = (m.group(1) or m.group(2) or '').split('.')[0]
                if module in FORBIDDEN_DOMAIN_MODULES:
                    violations.append((rel, 'D2', "imports '%s' — %s" % (module, FORBIDDEN_DOMAIN_MODULES[module])))
    return violations


def cmd_arch(root, verbose=True):
    """Enforce the Domain layer's purity and dependency rules (D2/D3)."""
    repo_root = root.parent
    violations = check_domain_boundaries(repo_root)
    scanned = sum(
        len([p for p in (repo_root / d).rglob('*.py') if '__pycache__' not in p.parts])
        for d in DOMAIN_ROOTS if (repo_root / d).is_dir()
    )
    for rel, rule, msg in violations:
        print("  %s VIOLATION %s: %s" % (rule, rel, msg))
    print("arch: %d domain file(s) scanned, %d boundary violation(s)" % (scanned, len(violations)))
    return 1 if violations else 0


def cmd_check(root):
    print("== validate =="); rc1 = cmd_validate(root, verbose=False)
    print("== links ==");    rc2 = cmd_links(root, verbose=False)
    print("== lint ==");     rc3 = cmd_lint(root, verbose=False)
    print("== arch ==");     rc4 = cmd_arch(root, verbose=False)
    rc = rc1 | rc2 | rc3 | rc4
    print("\ncheck: %s" % ("PASS" if rc == 0 else "FAIL"))
    return rc


def cmd_selftest(root):
    """Prove the impact + validation engines on synthetic fixtures in a temp tree."""
    ok = True
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Synthetic units: b depends_on a; c depends_on b (transitive chain).
        units = [
            {'id': 'knowledge/technology/a', 'depends_on': []},
            {'id': 'standards/coding/b', 'depends_on': ['knowledge/technology/a']},
            {'id': 'agents/backend/c', 'depends_on': ['standards/coding/b']},
            {'id': 'playbooks/development/p', 'depends_on': ['standards/coding/b']},
        ]
        # (1) Major bump on 'a' must flag b, c (transitive), p — all NeedsRevalidation.
        res = compute_impact('knowledge/technology/a', 'major', units)
        expect = {'standards/coding/b', 'agents/backend/c', 'playbooks/development/p'}
        if set(res) != expect or any(v != 'NeedsRevalidation' for v in res.values()):
            print("  FAIL major-propagation: got %s" % res); ok = False
        else:
            print("  ok   major bump propagates transitively (b, c, p flagged)")

        # (2) Minor bump on 'b': direct consumers only; playbook still NeedsRevalidation.
        res = compute_impact('standards/coding/b', 'minor', units)
        if res.get('agents/backend/c') != 'Informational' or res.get('playbooks/development/p') != 'NeedsRevalidation':
            print("  FAIL minor-rules: got %s" % res); ok = False
        else:
            print("  ok   minor bump: agent Informational, playbook NeedsRevalidation")

        # (2b) A Standard referenced via standards_enforced (not depends_on) still
        # creates an impact edge: bumping the standard flags the enforcing agent.
        ref_units = [
            {'id': 'standards/coding/naming', 'depends_on': []},
            {'id': 'agents/backend/api', 'depends_on': [],
             'standards_enforced': ['standards/coding/naming@^1.0']},
        ]
        res = compute_impact('standards/coding/naming', 'major', ref_units)
        if res.get('agents/backend/api') != 'NeedsRevalidation':
            print("  FAIL standards_enforced edge not detected: got %s" % res); ok = False
        else:
            print("  ok   standards_enforced (with @version pin) is an impact edge")

        # (3) Patch bump: no propagation.
        res = compute_impact('knowledge/technology/a', 'patch', units)
        if res:
            print("  FAIL patch-propagation: got %s" % res); ok = False
        else:
            print("  ok   patch bump propagates to nobody")

        # (4) Guardrail change flags all agents regardless of depends_on.
        res = compute_impact('guardrails/core', 'patch', units)
        if res.get('agents/backend/c') != 'NeedsRevalidation':
            print("  FAIL guardrail-fanout: got %s" % res); ok = False
        else:
            print("  ok   guardrail change fans out to every agent")

        # (5) Validator rejects a deliberately-invalid unit and accepts a valid one.
        store = load_schemas(root / 'schema')
        good = {'id': 'x/y', 'title': 'T', 'version': '1.0.0', 'status': 'Active',
                'owner': 'o', 'category': 'c'}
        bad = {'id': 'x/y', 'title': 'T', 'version': 'not-semver', 'status': 'Nope',
               'owner': 'o', 'category': 'c'}
        if validate_instance(good, store['base.schema.json'], store, 'good'):
            print("  FAIL validator rejected a valid unit"); ok = False
        elif not validate_instance(bad, store['base.schema.json'], store, 'bad'):
            print("  FAIL validator accepted an invalid unit"); ok = False
        else:
            print("  ok   validator accepts valid / rejects invalid frontmatter")

        # (6) Fail-loud: an unsupported schema keyword must raise, not pass silently.
        try:
            validate_instance({}, {'oneOf': []}, store, 'faillowd')
            print("  FAIL unsupported keyword did not raise"); ok = False
        except SchemaError:
            print("  ok   unsupported schema keyword fails loud")

        # (7) Every SHIPPED schema is within the validator's supported feature set —
        # so M3's first real Standard/Agent/Guardrail unit can't crash on an
        # unsupported keyword that no unit had exercised before.
        probe = {'checkpoint': ['boot'], 'depends_on': [], 'applies_to': [],
                 'decision_authority': ['x/**'], 'validated_against': ['a@1.0.0']}
        try:
            for name, sch in store.items():
                validate_instance(probe, sch, store, name)
            print("  ok   every shipped schema uses only supported keywords (%d schemas)" % len(store))
        except SchemaError as e:
            print("  FAIL a shipped schema uses an unsupported keyword: %s" % e); ok = False

        # (8) H1 — an unresolved frontmatter reference is caught.
        if not check_references([{'id': 'agents/backend/x',
                                  'standards_enforced': ['standards/coding/nonexistent@^1.0']}]):
            print("  FAIL H1: unresolved reference not caught"); ok = False
        else:
            print("  ok   H1: unresolved frontmatter reference is caught")

        # (9) H3 — validated_against version drift caught; matching version does not false-positive.
        drift_units = [{'id': 'standards/coding/n', 'version': '2.0.0'},
                       {'id': 'agents/backend/x', 'validated_against': ['standards/coding/n@1.0.0']}]
        match_units = [{'id': 'standards/coding/n', 'version': '2.0.0'},
                       {'id': 'agents/backend/x', 'validated_against': ['standards/coding/n@2.0.0']}]
        if not check_drift(drift_units):
            print("  FAIL H3: version drift not caught"); ok = False
        elif check_drift(match_units):
            print("  FAIL H3: false-positive drift on matching version"); ok = False
        else:
            print("  ok   H3: validated_against drift caught; matching version clean")

        # (10) H2 — overlapping decision_authority caught; disjoint domains do not false-positive.
        overlap = [{'id': 'agents/backend/a', 'status': 'Active', 'decision_authority': ['mcp-server/**']},
                   {'id': 'agents/backend/b', 'status': 'Active', 'decision_authority': ['mcp-server/app/**']}]
        disjoint = [{'id': 'agents/backend/a', 'status': 'Active', 'decision_authority': ['mcp-server/**']},
                    {'id': 'agents/frontend/b', 'status': 'Active', 'decision_authority': ['web/**']}]
        if not check_authority_overlap(overlap):
            print("  FAIL H2: authority overlap not caught"); ok = False
        elif check_authority_overlap(disjoint):
            print("  FAIL H2: false-positive on disjoint authority"); ok = False
        else:
            print("  ok   H2: authority overlap caught; disjoint domains clean")

    print("\nselftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog='aios', description='AIOS deterministic-tooling CLI')
    p.add_argument('--root', default=str(AI_ROOT), help='.ai/ root (default: this script\'s .ai/)')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('validate')
    sub.add_parser('links')
    ip = sub.add_parser('index'); ip.add_argument('--dry-run', action='store_true')
    mp = sub.add_parser('impact'); mp.add_argument('unit'); mp.add_argument('--change', choices=['major', 'minor', 'patch'], default='major')
    sub.add_parser('lint')
    sub.add_parser('arch')
    sub.add_parser('check')
    sub.add_parser('selftest')
    args = p.parse_args(argv)
    root = Path(args.root).resolve()

    if args.cmd == 'validate':
        return cmd_validate(root)
    if args.cmd == 'links':
        return cmd_links(root)
    if args.cmd == 'index':
        return cmd_index(root, write=not args.dry_run)
    if args.cmd == 'impact':
        return cmd_impact(root, args.unit, args.change)
    if args.cmd == 'lint':
        return cmd_lint(root)
    if args.cmd == 'arch':
        return cmd_arch(root)
    if args.cmd == 'check':
        return cmd_check(root)
    if args.cmd == 'selftest':
        return cmd_selftest(root)
    return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SchemaError as e:
        print("SCHEMA ERROR: %s" % e, file=sys.stderr)
        sys.exit(3)
