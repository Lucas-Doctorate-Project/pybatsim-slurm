from enum import Enum
from copy import deepcopy
from struct import unpack
from procset import ProcSet

import logging
import json
import sys
import zmq

from .network import NetworkHandler

class Batsim(object):

    WORKLOAD_JOB_SEPARATOR = "!"
    ATTEMPT_JOB_SEPARATOR = "#"
    WORKLOAD_JOB_SEPARATOR_REPLACEMENT = "%"

    def __init__(self, scheduler,
                 network_endpoint,
                 timeout,
                 event_endpoint=None):

        self.logger = logging.getLogger(__name__)

        self.running_simulation = False
        self.network = NetworkHandler(network_endpoint, timeout=timeout) # type zmq.REP by default
        self.network.bind()

        # event handler is optional
        self.event_publisher = None
        if event_endpoint is not None:
            self.event_publisher = NetworkHandler(event_endpoint, type=zmq.PUB)
            self.event_publisher.bind()

        self.jobs = dict()

        sys.setrecursionlimit(10000)

        self.scheduler = scheduler
        self.scheduler.bs = self

        self.no_more_static_jobs = False
        self.no_more_external_events = False
        #self.use_storage_controller = False # TODO: need to update it with Batprotocol

        # Batsim sends an init message on the socket, read it and answer with empty message
        # Format of the init message: flags(uint32), data_size(uint32), data(data_size bytes)
        init_msg = self.network.recv_binary(blocking=True)
        if init_msg is not None:
            flags = unpack('i', init_msg[0:4])[0]
            data_size = unpack('i', init_msg[4:8])[0]
            edc_init_str = init_msg[8:].decode('utf-8') # init_str contains the scheduler initialization buffer provided to Batsim command

            assert flags == 2, f"Pybatsim uses JSON format of the batprotocol, expected flag value '2' but got {flags}"
            assert data_size == len(edc_init_str), f"""
                Mismatch between received data_size
                and actual size of data (got {data_size} and {len(edc_init_str)})
                """

            self.network.send_string("") # Answer message MUST be empty
        else:
            raise ValueError(
                "[PYBATSIM]: Init message from Batsim not received.")

        self.scheduler.onAfterBatsimInit(edc_init_str)


    def get_job_and_profile(self, event_data):
        job = Job.from_json_dict(event_data)

        if "profile" in event_data:
            #TODO: update this with the Batprotocol
            profile = event_data["profile"]
        else:
            profile = None

        return job, profile

    # Only add the profile if not already in self.profiles
    def add_profile(self, profile):
        workload_name = profile["id"].split(Batsim.WORKLOAD_JOB_SEPARATOR)[0]
        if workload_name not in self.profiles:
            self.profiles[workload_name] = {}
        if profile["id"] not in self.profiles[workload_name]:
            self.profiles[workload_name][profile["id"]] = profile


    def start(self):
        cont = True
        while cont:
            cont = self._read_bat_msg()

    def _read_bat_msg(self):
        msg = None
        while msg is None:
            # Blocking when the simulation has not started
            # only use the timeout after the simulation has started
            msg = self.network.recv_json(blocking=not self.running_simulation)
            if msg is None:
                self.scheduler.onDeadlock()
                continue
        self.logger.info("Message Received from Batsim: {}".format(msg))

        self._current_time = msg["now"]

        self._events_to_send = []

        simu_ends_received = False

        if self.running_simulation:
            # Only called during the simulation, after the simulation_begins event
            # has been received and before the simulation_ends event
            self.scheduler.onBeforeEvents()

        for event in msg["events"]:
            event_type = event["event_type"]
            event_data = event.get("event", {})
            if event_type == "BatsimHelloEvent":
                assert not self.running_simulation, "A simulation is already running (is more than one instance of Batsim active?!)"

                self.simulation_context = SimulationContext(event_data["batprotocol_version"],
                                                           event_data["batsim_version"],
                                                           event_data["batsim_commit"])
                self.scheduler.onBatsimHello()

            elif event_type == "SimulationBeginsEvent":
                assert not self.running_simulation, "A simulation is already running (is more than one instance of Batsim active?!)"
                self.running_simulation = True

                self.nb_resources = event_data["host_number"]
                self.nb_compute_resources = event_data["computation_host_number"]
                self.nb_storage_resources = event_data["storage_host_number"]

                # TODO create Machine object?
                self.compute_resources = {
                    res["id"]: res for res in event_data["computation_hosts"]
                }
                self.storage_resources = {
                    res["id"]: res for res in event_data["storage_hosts"]
                }

                # The list of arguments of the Batsim command line
                self.batsim_arguments = event_data["batsim_arguments"]
                self.batsim_execution_context = event_data["batsim_execution_context_json"]

                if self.simulation_context.dynamic_registration:
                    self.logger.warning("Dynamic registration of jobs is ENABLED. "
                        "The scheduler must send a FinishRegistrationEvent event to let Batsim end the simulation.")

                self.workloads = {}
                self.profiles = {}

                for wl in event_data["workloads"]:
                    self.workloads[wl["name"]] = wl
                    self.profiles[wl["name"]] = {}

                if self.simulation_context.forward_profiles_on_simulation_begins:
                    for prof in event_data["profiles"]:
                        self.add_profile(prof)

                self.scheduler.onSimulationBegins()

            elif event_type == "SimulationEndsEvent":
                assert self.running_simulation, "No simulation is currently running"
                self.running_simulation = False
                #self.logger.info("All jobs have been submitted and completed!")
                simu_ends_received = True
                self.scheduler.onSimulationEnds()

            elif event_type == "JobSubmittedEvent":
                # Received WORKLOAD_NAME!JOB_ID
                job_id = event_data["job_id"]

                # Retrieve job and profile from event
                job, profile = self.get_job_and_profile(event_data)

                if job_id in self.jobs:
                    # This job comes from a Dynamic Registration, it already exist in self.jobs
                    job = self.jobs[job_id]
                else:
                    self.jobs[job_id] = job
                job.job_state = Job.State.SUBMITTED

                # Store profile if not already present
                if profile is not None: # This should only happen when forward_profiles_on_job_submission is set
                    self.add_profile(profile)


                # TODO: need to update it with Batprotocol
                '''if (self.use_storage_controller) and (job.workload == "dyn-storage-controller"):
                    # This job comes from the StorageController, it's just an ack so forget about it
                    pass
                else:
                    self.scheduler.onJobSubmission(job)'''
                self.scheduler.onJobSubmission(job)

            elif event_type == "JobCompletedEvent":
                job_id = event_data["job_id"]
                j = self.jobs[job_id]
                j.finish_time = event["timestamp"]

                try:
                    j.job_state = Job.State[event_data["state"]]
                except KeyError:
                    j.job_state = Job.State.UNKNOWN
                j.return_code = event_data["return_code"]

                if j.job_state != Job.State.COMPLETED_KILLED:
                    # Remove the Job from the dict
                    del self.jobs[job_id]

                # TODO: need to update it with Batprotocol
                '''if (self.use_storage_controller) and (j.workload == "dyn-storage-controller"):
                    # This job comes from the Storage Controller
                    self.storage_controller.data_staging_completed(j)
                else:
                    self.scheduler.onJobCompletion(j)'''
                self.scheduler.onJobCompletion(j)

            elif event_type == "JobsKilledEvent":
                killed_jobs = []

                for d in event_data["progresses"]:
                    #j = self.jobs[d["job_id"]]
                    j = self.jobs.pop(d["job_id"])
                    j.kill_progress_type = d["wrapper"]["kill_progress_type"]
                    j.kill_progress = d["wrapper"]["kill_progress"]
                    killed_jobs.append(j)

                if self.simulation_context.forward_profiles_on_jobs_killed:
                    # Include the forwarded profiles if not already here
                    for profile in event_data["profiles"]:
                        self.add_profile(profile)

                if len(killed_jobs) != 0:
                    self.scheduler.onJobsKilled(killed_jobs)

            elif event_type == 'ProbeDataEmittedEvent':
                raise Exception(f"Not implemented yet (event received: {event_type}")

            elif event_type == "HostPStateChangedEvent":
                machines = ProcSet.from_str(event_data["host_ids"])
                self.scheduler.onHostPStateChanged(machines, int(event_data["pstate"]))

            elif event_type == 'RequestedCallEvent':
                self.scheduler.onRequestedCall(event_data["call_me_later_id"], event_data["last_periodic_call"])

            elif event_type == 'AllStaticJobsHaveBeenSubmittedEvent':
                self.no_more_static_jobs = True
                self.scheduler.onNoMoreJobsInWorkloads()
            elif event_type == 'AllStaticExternalEventsHaveBeenInjectedEvent':
                self.no_more_external_events = True
                self.scheduler.onNoMoreExternalEvents()

            else: # Unknown Batsim event received
                raise Exception(f"Unknown Batsim event type {event_type}")
            # TODO: does not appear in the batprotocol (yet)
            '''elif event_type == 'ADD_RESOURCES':
                self.scheduler.onAddResources(ProcSet.from_str(event_data["resources"]))
            elif event_type == 'REMOVE_RESOURCES':
                self.scheduler.onRemoveResources(ProcSet.from_str(event_data["resources"]))'''
            # TODO: not in the batprotocol yet
            '''elif notify_type == "NotifyExternalEvent":
                external_event_type = event_data["type"]
                if external_event_type == "MachineUnavailableEvent":
                    self.scheduler.onNotifyEventMachineUnavailable(ProcSet.from_str(event_data["resources"]))
                elif external_event_type == "MachineAvailableEvent":
                    self.scheduler.onNotifyEventMachineAvailable(ProcSet.from_str(event_data["resources"]))
                elif self.forward_unknown_events:
                    self.scheduler.onNotifyGenericEvent(event_data)
                else:
                    raise Exception(f"Unknown external event received: {external_event_type}")'''


        if self.running_simulation:
            # Only called during the simulation, after the simulation_begins event
            # has been received and before the simulation_ends event
            self.scheduler.onNoMoreEvents()

        if len(self._events_to_send) > 0:
            # sort messages by timestamp
            self._events_to_send = sorted(
                self._events_to_send, key=lambda event: event['timestamp'])

        new_msg = {
            "now": self._current_time,
            "events": self._events_to_send
        }
        self.network.send(new_msg)
        self.logger.info("Message Sent to Batsim: {}".format(new_msg))


        if simu_ends_received:
            self.network.close()
            if self.event_publisher is not None:
                self.event_publisher.close()

        return not simu_ends_received


########################################################
########## Beginning of API for the scheduler ##########
########################################################

    # TODO: is this still used?
    def publish_event(self, event):
        """Sends a message to subscribed event listeners (e.g. external processes which want to
        observe the simulation).
        """
        if self.event_publisher is not None:
            self.event_publisher.send_string(event)

    def time(self):
        return self._current_time

    def consume_time(self, t):
        self._current_time += float(t)
        return self._current_time


    def answer_simulation_hello(self, sched_name, sched_version, sched_commit=""):
        self._events_to_send.append(
            {"timestamp": self.time(),
             "event_type": "EDCHelloEvent",
             "event": {
                "batprotocol_version": self.simulation_context.batprotocol_version, #TODO
                "decision_component_name": sched_name,
                "decision_component_version": sched_version,
                "decision_component_commit": sched_commit,
                "requested_simulation_features": {
                    "dynamic_registration": self.simulation_context.dynamic_registration,
                    "profile_reuse": self.simulation_context.profile_reuse,
                    "acknowledge_dynamic_jobs": self.simulation_context.acknowledge_dynamic_jobs,
                    "forward_profiles_on_job_submission": self.simulation_context.forward_profiles_on_job_submission,
                    "forward_profiles_on_jobs_killed": self.simulation_context.forward_profiles_on_jobs_killed,
                    "forward_profiles_on_simulation_begins": self.simulation_context.forward_profiles_on_simulation_begins,
                    "forward_unknown_external_events": self.simulation_context.forward_unknown_external_events},
                "scheduling_constraints": {
                    "compute_sharing": self.simulation_context.compute_sharing,
                    "storage_sharing": self.simulation_context.storage_sharing,
                    "job_allocation_validation_strategy": self.simulation_context.job_allocation_validation_strategy}
        }})


    def format_allocation_dict(self, joballoc):
        alloc_dict = {
            "host_allocation": str(joballoc.host_alloc),
            "executor_placement_type": str(joballoc.placement_type.name)
        }
        if joballoc.placement_type == JobAllocation.ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper:
            assert joballoc.placement_strategy is not None
            alloc_dict["executor_placement"] = {
                "strategy": str(joballoc.placement_strategy.name)
            }
        elif joballoc.placement_type == JobAllocation.ExecutorPlacementType.CustomExecutorToHostMapping:
            assert joballoc.custom_executor_mapping is not None
            alloc_dict["executor_placement"] = {
                "mapping": str(joballoc.custom_executor_mapping.name)
            }

        return alloc_dict

    def execute_job(self, job, io_job = None):
        """ job: Job to execute
            job.allocation MUST be not None and a JobAllocation object
        """
        assert isinstance(job.allocation, JobAllocation), "Problem in execute_job: job.allocation must be a JobAllocation"

        job_alloc_dict = self.format_allocation_dict(job.allocation)

        message = {
            "timestamp": self.time(),
            "event_type": "ExecuteJobEvent",
            "event": {
                    "job_id": job.job_id,
                    "allocation": job_alloc_dict,
                    "profile_allocation_override": job.allocation.profile_allocation_override,
                    "storage_placement": job.allocation.storage_placement
            }
        }

        # TODO need to (correctly) handle optional profile_allocation_override list
        # TODO need to (correctly) handle optional storage_placement list


        # TODO: update/remove this?
        self.jobs[job.job_id].allocation = job.allocation
        self.jobs[job.job_id].job_state = Job.State.RUNNING
        self.jobs[job.job_id].starting_time = self.time()

        # Not in batprotocol (yet?)
        '''if io_job is not None:
            message["data"]["additional_io_job"] = io_job

        # message["data"]["mapping"] becomes the mapping of CustomExecutorToHostMapping type
        # message["data"]["storage_mapping"] becomes "storage_placement"'''

        self._events_to_send.append(message)


    def execute_jobs(self, jobs, io_jobs=None):
        """ jobs: list of jobs to execute
            job.allocation MUST be not None and a non-empty ProcSet
        """
        for job in jobs:
            if io_jobs is not None:
                # TODO: update with batprotocol
                self.execute_job(job, io_jobs[job.job_id])
            else:
                self.execute_job(job)

    # Renamed from 'wake_me_up_at'
    # 'call_time' MUST be an integer
    # 'call'time' is expressed in Seconds, or Milliseconds if 'time_in_ms' is set to True
    def call_me_later_once(self, call_me_later_id, call_time, time_in_ms=False):
        # TODO: remove the assert and make it the users' responsibility to comply with the Batprotocol?
        assert isinstance(call_time, int), f"call_time MUST be an integer (got {call_time})"

        self._events_to_send.append(
            {"timestamp": self.time(),
             "event_type": "CallMeLaterEvent",
             "event": {
                "call_me_later_id": call_me_later_id,
                "when_type": "OneShot",
                "when": {
                    "time": call_time,
                    "time_unit": "Millisecond" if time_in_ms else "Second"
                },
            }
        })

    # Periodic CallMeLaterEvent
    # 'start_time' and 'period_time' MUST be integers
    # If nb_periods <= 0 then it is Infinite mode
    def call_me_later_periodic(self, call_me_later_id, start_time,
                               period_time, nb_periods, time_in_ms=False):
        # TODO: remove the assert and make it the users' responsibility to comply with the Batprotocol?
        assert isinstance(start_time, int), f"start_time MUST be an integer (got {start_time})"
        assert isinstance(period_time, int), f"period_time MUST be an integer (got {period_time})"

        when_dict = {"offset": start_time,
                     "period": period_time,
                     "time_unit": "Millisecond" if time_in_ms else "Second"}

        if nb_periods > 0:
            when_dict["mode_type"] = "FinitePeriodNumber"
            when_dict["mode"] = {"nb_periods": nb_periods}
        else:
            when_dict["mode_type"] = "Infinite"
            when_dict["mode"] = {}
            self.logger.warning("Infinite periodic CallMeLater asked. "
                        "The scheduler must send a StopCallMeLaterEvent to let Batsim end the simulation.")

        self._events_to_send.append(
            {"timestamp": self.time(),
             "event_type": "CallMeLaterEvent",
             "event": {
                "call_me_later_id": call_me_later_id,
                "when_type": "Periodic",
                "when": when_dict
            }
        })

    def stop_call_me_later(self, call_me_later_id):
        self._events_to_send.append(
            {"timestamp": self.time(),
             "event_type": "StopCallMeLaterEvent",
             "event": {"call_me_later_id": call_me_later_id}
        })

    # Renamed from 'notify_registration_finished'
    def finish_registration(self):
        self._events_to_send.append({
            "timestamp": self.time(),
            "event_type": "FinishRegistrationEvent",
            "event": {}
        })

    def force_simulation_stop(self):
        self._events_to_send.append({
            "timestamp": self.time(),
            "event_type": "ForceSimulationStopEvent",
            "event": {}
        })

    def reject_job_by_id(self, job_id):
        self._events_to_send.append({
            "timestamp": self.time(),
            "event_type": "RejectJobEvent",
            "event": {
                "job_id": job_id
            }
        })
        #self.jobs[job_id].job_state = Job.State.REJECTED # TODO: get rid of this?

    def reject_jobs_by_ids(self, job_ids):
        assert isinstance(job_ids, list), "A list of job ids must be provided to 'reject_jobs'"
        assert len(job_ids) > 0, "The list of jobs to reject is empty" #TODO: make is a logger.warning instead of an assert?
        for job_id in job_ids:
            self.reject_job_by_id(job_id)

    def kill_jobs_by_ids(self, job_ids):
        assert isinstance(job_ids, list), "A list of job ids must be provided to 'kill_jobs'"
        assert len(job_ids) > 0, "The list of jobs to kill is empty" #TODO: make is a logger.warning instead of an assert?
        #for job_id in job_ids:
        #    self.jobs[job_id].job_state = Job.State.IN_KILLING #TODO: get rid of this?
        self._events_to_send.append({
            "timestamp": self.time(),
            "event_type": "KillJobsEvent",
            "event": {
                    "job_ids": job_ids,
            }
        })

    def register_job(self,
            job_id,
            profile_id,
            walltime,
            comp_res_request,
            rigid,
            extra_data=''):

        job_dict = {
            "resource_request": comp_res_request,
            "walltime": walltime,
            "rigid": rigid,
            "profile_id": profile_id,
        }

        if extra_data != '':
            job_dict["extra_data"] = extra_data

        self._events_to_send.append({
            "timestamp": self.time(),
            "event_type": "RegisterJobEvent",
            "event": {
                "job_id": job_id,
                "job": job_dict,
            }
        })

        job = Job.from_json_dict({
            "job_id": job_id,
            "submission_time": self.time(),
            "job": job_dict
        })

        if self.simulation_context.acknowledge_dynamic_jobs:
            job.job_state = Job.State.IN_SUBMISSON # TODO: get rid of this?
        else:
            job.job_state = Job.State.SUBMITTED # TODO: get rid of this?

        # Keep track of the job object
        self.jobs[job_id] = job

        self.logger.debug(f"Registering job {job_id}")
        return job


    def register_profile(self,
            workload_name,
            profile_name,
            profile_type,
            profile_dict):
    # It is the scheduler's job to provide a correct profile_dict
    # depending on the profile_type given

        profile_id = f"{workload_name}{Batsim.WORKLOAD_JOB_SEPARATOR}{profile_name}"

        tmp_dict = {
            "id": profile_id,
            "profile_type": profile_type,
            "profile": profile_dict
        }

        self._events_to_send.append({
            "timestamp": self.time(),
            "event_type": "RegisterProfileEvent",
            "event": { "profile": tmp_dict }
        })

        if not workload_name in self.profiles:
            self.profiles[workload_name] = {}
            self.logger.debug("A new dynamic workload of name '{}' has been created".format(workload_name))

        self.profiles[workload_name][profile_id] = tmp_dict
        self.logger.debug(f"Registering profile {profile_id}")



    def change_host_pstate(self, host_ids, pstate):
        """ args:host_ids: a ProcSet containing a list of host.
            args:pstate: the pstate identifier configured in the platform specification.
        """
        self._events_to_send.append({
            "timestamp": self.time(),
            "event_type": "ChangeHostPStateEvent",
            "event": {
                    "host_ids": str(host_ids),
                    "pstate": pstate
            }
        })

    # TODO: remove this?
    def send_message_to_job(self, job, message):
        self._events_to_send.append({
            "timestamp": self.time(),
            "event_type": "TO_JOB_MSG",
            "event": {
                    "job_id": job.job_id,
                    "msg": message,
            }
        })



    # TODO: becomes related to probes?
    def request_consumed_energy(self):
        self._events_to_send.append(
            {
                "timestamp": self.time(),
                "event_type": "QUERY",
                "event": {
                    "requests": {"consumed_energy": {}}
                }
            }
        )

    # TODO: function still used? (related to Bebida?)
    def notify_resources_added(self, resources):
        self._events_to_send.append(
            {
                "timestamp": self.time(),
                "event_type": "RESOURCES_ADDED",
                "event": {
                    "resources": str(resources)
                }
            }
        )

    # TODO: function still used? (related to Bebida?)
    def notify_resources_removed(self, resources):
        self._events_to_send.append(
            {
                "timestamp": self.time(),
                "event_type": "RESOURCES_REMOVED",
                "event": {
                    "resources": str(resources)
                }
            }
        )

    # TODO: function still used?
    '''def set_job_metadata(self, job_id, metadata):
        self._events_to_send.append(
            {
                "timestamp": self.time(),
                "event_type": "SET_JOB_METADATA",
                "event": {
                    "job_id": str(job_id),
                    "metadata": str(metadata)
                }
            }
        )
        self.jobs[job_id].metadata = metadata'''


    def resubmit_job(self, job):
        """
        The given job is resubmited but in a dynamic workload. The name of this
        workload is "resubmit=N" where N is the number of resubmission.
        The job metadata is filled with a dict that contains the original job
        full id in "parent_job" and the number of resubmissions in "nb_resubmit".
        """

        if job.metadata is None:
            metadata = {"parent_job": job.job_id, "nb_resubmit": 1}
        else:
            metadata = deepcopy(job.metadata)
            if "nb_resubmit" not in metadata:
                metadata["nb_resubmit"] = 1
            else:
                metadata["nb_resubmit"] = metadata["nb_resubmit"] + 1
            if "parent_job" not in metadata:
                metadata["parent_job"] = job.job_id

        # Keep the current workload and add a resubmit number
        splitted_id = job.job_id.split(Batsim.ATTEMPT_JOB_SEPARATOR)
        if len(splitted_id) == 1:
            new_job_name = deepcopy(job.job_id)
        else:
            # This job has already an attempt number
            new_job_name = splitted_id[0]
            assert splitted_id[1] == str(metadata["nb_resubmit"] - 1)
        new_job_name =  new_job_name + Batsim.ATTEMPT_JOB_SEPARATOR + str(metadata["nb_resubmit"])
        # log in job metadata parent job and nb resubmit

        new_job = self.register_job(
                new_job_name,
                job.profile_id,
                job.requested_time,
                job.requested_resources,
                job.is_rigid,
                job.extra_data)

        #self.set_job_metadata(new_job_name, metadata)
        new_job.metadata = metadata
        return new_job

##################################################
########## End of API for the scheduler ##########
##################################################
# End of Batsim class

class Job(object):

    class State(Enum):
        UNKNOWN = -1
        IN_SUBMISSON = 0
        SUBMITTED = 1
        RUNNING = 2
        COMPLETED_SUCCESSFULLY = 3
        COMPLETED_FAILED = 4
        COMPLETED_WALLTIME_REACHED = 5
        COMPLETED_KILLED = 6
        REJECTED = 7
        IN_KILLING = 8

    def __init__(
            self,
            job_id,
            subtime,
            resource_req,
            walltime,
            extra_data,
            rigid,
            profile_id,
            json_dict):
        self.job_id = job_id
        self.submit_time = subtime
        self.requested_resources = resource_req
        self.requested_time = walltime
        self.extra_data = extra_data
        self.rigid = rigid
        self.json_dict = json_dict

        self.job_state = Job.State.UNKNOWN
        self.allocation = None # Will be set when calling execute_job
        self.starting_time = None  # will be set when calling execute_job
        self.finish_time = None  # will be set on completion
        self.return_code = None # Will be set on completion
        self.kill_progress_type = None # Will be set in case of killing the job
        self.kill_progress = None # Will be set in case of killing the job

        self.workload = self.job_id.split(Batsim.WORKLOAD_JOB_SEPARATOR)[0]

        if Batsim.WORKLOAD_JOB_SEPARATOR in profile_id:
            self.profile_id = profile_id
        else:
            self.profile_id = f"{self.workload}{Batsim.WORKLOAD_JOB_SEPARATOR}{profile_id}"

    def __repr__(self):
        return (f"{{Job {self.job_id}, sub:{self.submit_time}, res:{self.requested_resources}"
                f" ({self.computation_resource_type}), reqtime:{self.requested_time},"
                f" profile: {self.profile_id}, state: {self.job_state},"
                f" ret: {self.return_code}, alloc: {self.allocation}, extra: {self.extra_data}}}")

    @staticmethod
    def from_json_string(json_str):
        json_dict = json.loads(json_str)
        return Job.from_json_dict(json_dict)

    @staticmethod
    def from_json_dict(json_dict):
        return Job(json_dict["job_id"],
                   json_dict["submission_time"],
                   json_dict["job"]["resource_request"],
                   json_dict["job"].get("walltime", -1),
                   json_dict["job"].get("extra_data", ''),
                   json_dict["job"]["rigid"],
                   json_dict["job"]["profile_id"],
                   json_dict["job"])

# Allocation object for the Batprotocol
class JobAllocation(object):
    class ExecutorPlacementType(Enum):
        PredefinedExecutorPlacementStrategyWrapper = 0 # = "PredefinedExecutorPlacementStrategyWrapper"
        CustomExecutorToHostMapping = 1 # = "CustomExecutorToHostMapping"

    class ExecutorPlacementStrategy(Enum):
        SpreadOverHostsFirst = "SpreadOverHostsFirst"
        FillOneHostCoresFirst = "FillOneHostCoresFirst"

    def __init__(
            self,
            host_alloc,
            placement_type,
            placement_arg,
            profile_alloc_override = [],
            storage_placement = []
        ):

        self.host_alloc = host_alloc # Procset object
        self.placement_type = placement_type # ExecutorPlacementType object

        self.placement_strategy = None # only used if placement_type is PredefinedExecutorPlacementStrategyWrapper
        self.custom_executor_mapping = None # only used if placement_type is CustomExecutorToHostMapping

        if placement_type == JobAllocation.ExecutorPlacementType.PredefinedExecutorPlacementStrategyWrapper:
            self.placement_strategy = placement_arg
        elif placement_type == JobAllocation.ExecutorPlacementType.CustomExecutorToHostMapping:
            self.custom_executor_mapping = placement_arg

        self.profile_allocation_override = profile_alloc_override
        self.storage_placement = storage_placement



# Enum for the Batprotocol
class JobAllocValidationStrategy(str, Enum):
    NONE = "None"
    MatchJobRequestExactly = "MatchJobRequestExactly"
    MatchJobRequestBigEnough = "MatchJobRequestBigEnough"


# Stores all simulation parameters and info passing in the Hello events
class SimulationContext(object):
    def __init__(self,
            batprotocol_version,
            batsim_version,
            batsim_commit):

        # Batsim and Batprotocol info
        self.batprotocol_version = batprotocol_version
        self.batsim_vesrion = batsim_version
        self.batsim_commit = batsim_commit

        # Requested simu features by the EDC
        self.dynamic_registration = False
        self.profile_reuse = False
        self.acknowledge_dynamic_jobs = False
        self.forward_profiles_on_job_submission = False
        self.forward_profiles_on_jobs_killed = False
        self.forward_profiles_on_simulation_begins = False
        self.forward_unknown_external_events = False

        # Scheduling constraints
        self.compute_sharing = False
        self.storage_sharing = True
        self.job_allocation_validation_strategy = JobAllocValidationStrategy.MatchJobRequestExactly



class BatsimScheduler(object):

    def __init__(self, options):
        self.options = options
        self.logger = logging.getLogger(__name__)

    def onAfterBatsimInit(self, init_str):
        # init_str contains the scheduler initialization buffer provided to Batsim command
        pass

    def onBatsimHello(self):
        raise NotImplementedError()
        # The scheduler may modify the SimulationContext object (self.bs.simulation_context)
        # and must call self.bs.answer_simulation_hello(<sched_name>, <sched_version>, [sched_commit]) to generate the answer event

    def onSimulationBegins(self):
        pass

    def onSimulationEnds(self):
        pass

    def onDeadlock(self):
        raise ValueError(
            "[PYBATSIM]: Batsim is not responding (maybe deadlocked)")

    def onJobSubmission(self, job):
        raise NotImplementedError()

    def onJobCompletion(self, job):
        raise NotImplementedError()

    def onJobMessage(self, timestamp, job, message):
        raise NotImplementedError()

    def onJobsKilled(self, jobs):
        raise NotImplementedError()

    def onHostPStateChanged(self, machines, pstate):
        raise NotImplementedError()

    def onReportEnergyConsumed(self, consumed_energy):
        raise NotImplementedError()

    def onAddResources(self, to_add):
        raise NotImplementedError()

    def onRemoveResources(self, to_remove):
        raise NotImplementedError()

    def onRequestedCall(self, call_me_later_id, last_periodic_call):
        raise NotImplementedError()

    def onNoMoreJobsInWorkloads(self):
        self.logger.info("There is no more static jobs in the workload")

    def onNoMoreExternalEvents(self):
        self.logger.info("There is no more external events to occur")

    def onNotifyEventMachineUnavailable(self, machines):
        raise NotImplementedError()

    def onNotifyEventMachineAvailable(self, machines):
        raise NotImplementedError()

    def onNotifyGenericEvent(self, event_data):
        raise NotImplementedError()

    # TODO: need to update it with Batprotocol
    '''def onDatasetArrivedOnStorage(self, dataset_id, source_id, dest_id): # Called by the Storage Controller, if any
        raise NotImplementedError()

    def onDataTransferNotTerminated(self, dataset_id, source_id, dest_id): # Called by the Storage Controller, if any
        raise NotImplementedError()'''

    def onBeforeEvents(self):
        # Called before ANY event is handled
        # Is NOT called until simulation_begins event has been received
        pass

    def onNoMoreEvents(self):
        # Called during the simulation, after ALL events from Batsim have been handled
        # Is NOT called after the simulation_ends event, or before simulation_begins event
        pass
