"""Subprocess runners for collectable NLFR evidence."""

from nlfr.runners.bazel import BazelRunner
from nlfr.runners.nativelink import NativeLinkRunner
from nlfr.runners.process import ProcessResult, ProcessRunner

__all__ = [
    "BazelRunner",
    "NativeLinkRunner",
    "ProcessResult",
    "ProcessRunner",
]
