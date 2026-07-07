"""Optional REAPI CAS probe (GitHub issue #81 part B).

This package makes ``nlfr ingest`` able to INDEPENDENTLY verify remote
``bytestream://`` references against a running content-addressable store,
instead of downgrading them to ``unverified_remote_reference`` on faith
(bazelbuild/bazel#23250: a BEP can reference a blob whose cache upload FAILED).

Posture guarantees (enforced by ``tests/test_stdlib_only_posture.py``):

* Importing this package — and ``nlfr.reapi.probe`` — requires ONLY the Python
  standard library. The gRPC / protobuf imports happen lazily, inside
  :func:`nlfr.reapi.probe.make_cas_probe`, and only when an operator explicitly
  asks for remote verification.
* The runtime dependency set of the NLFR core stays EMPTY. gRPC + protobuf are
  an optional extra: ``pip install "nativelink-agent-flight-recorder[reapi]"``.
* When the extra is absent, or the CAS is unreachable, remote references keep
  the honest historical downgrade — never a fabricated verdict.
"""
