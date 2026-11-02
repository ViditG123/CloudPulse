from app.worker import recover_inflight

class FakeQueue:
    def __init__(self, processing):
        self.processing = list(processing)
        self.ready = []
    def rpoplpush(self, source, destination):
        assert source == "cloudpulse:processing"
        assert destination == "cloudpulse:jobs"
        if not self.processing:
            return None
        job = self.processing.pop()
        self.ready.insert(0, job)
        return job

def test_restart_requeues_unacknowledged_jobs():
    queue = FakeQueue(["job-1", "job-2"])
    recover_inflight(queue)
    assert queue.processing == []
    assert set(queue.ready) == {"job-1", "job-2"}

def test_empty_inflight_queue():
    queue = FakeQueue([])
    recover_inflight(queue)
    assert queue.ready == []
