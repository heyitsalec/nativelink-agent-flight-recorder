from tasks.priority import describe_task, priority_band


def test_priority_band_marks_urgent_work():
    assert priority_band(95) == "urgent"


def test_describe_task_keeps_leaf_label_readable():
    assert describe_task("NLFR-3", 72) == "NLFR-3: normal"


def test_priority_band_marks_backlog_for_low_score():
    assert priority_band(10) == "backlog"
