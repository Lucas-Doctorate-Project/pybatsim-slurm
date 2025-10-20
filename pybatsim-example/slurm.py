"""
Trivial example scheduler that rejects any job.
No hard feelings!
"""

from pybatsim.batsim.batsim import BatsimScheduler


class SlurmScheduler(BatsimScheduler):
'''
    Utiliza o escalonador Slurm. Ele forma uma lista de prioridades com a seguinte fórmula:

        Job_priority =
        site_factor +
        (PriorityWeightAge) * (age_factor) +
        (PriorityWeightAssoc) * (assoc_factor) +
        (PriorityWeightFairshare) * (fair-share_factor) +
        (PriorityWeightJobSize) * (job_size_factor) +
        (PriorityWeightPartition) * (priority_job_factor) +
        (PriorityWeightQOS) * (QOS_factor) +
        SUM(TRES_weight_cpu * TRES_factor_cpu,
            TRES_weight_<type> * TRES_factor_<type>,
            ...)
        - nice_factor

    Referência: https://slurm.schedmd.com/priority_multifactor.html
'''
    def onJobSubmission(self, job):
        self.bs.reject_jobs([job])  # nope!
