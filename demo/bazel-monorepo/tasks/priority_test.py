from tasks.priority import describe_task, priority_band


def test_priority_band_marks_urgent_work():
    assert priority_band(95) == "urgent"


def test_describe_task_keeps_leaf_label_readable():
    assert describe_task("NLFR-3", 72) == "NLFR-3: normal"

if __name__ == "__main__":
    # py_test executes this file as a script: without a main block the
    # test functions above are DEFINED but never CALLED, so the target is
    # vacuously green no matter what breaks (found by the validation-layer
    # repair-loop work, which needed a lane that can actually go red).
    # Stdlib-only runner, same discipline as the rest of the repo.
    import sys
    import traceback

    _failures = 0
    for _name in sorted(list(globals())):
        if _name.startswith("test_") and callable(globals()[_name]):
            try:
                globals()[_name]()
                print(f"PASS {_name}")
            except Exception:  # noqa: BLE001 - report and count every failure
                traceback.print_exc()
                print(f"FAIL {_name}")
                _failures += 1
    sys.exit(1 if _failures else 0)
