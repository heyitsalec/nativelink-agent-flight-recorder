from tasks import policy


def priority_band(score):
    if score >= policy.URGENT_THRESHOLD:
        return "urgent"
    if score >= policy.NORMAL_THRESHOLD:
        return "normal"
    return "backlog"


def describe_task(task_id, score):
    return f"{task_id}: {priority_band(score)}"
