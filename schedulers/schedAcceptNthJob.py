from batsim.batsim import BatsimScheduler

class SchedAcceptNthJob(BatsimScheduler):
    def onAfterBatsimInit(self):
        self.magic_number = 5
        self.count = 0

    def onJobSubmission(self, job):
        self.count += 1
        if self.count != self.magic_number:
            self.bs.reject_jobs([job])
        else:
            resources = job.requested_resources
            job.allocation = f"0-{resources}"
            self.bs.execute_jobs([job])

    def onJobCompletion(self, job):
        print(f"Job {job.id} completed")
