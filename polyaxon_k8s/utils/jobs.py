# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

from polyaxon_k8s.constants import PodLifeCycle, JobLifeCycle, ContainerStatuses, PodConditions
from polyaxon_k8s.utils import pods


def get_job_status(pod_state, job_container_name):
    # For terminated pods that failed and successfully terminated pods
    if pod_state['phase'] == PodLifeCycle.FAILED:
        return JobLifeCycle.FAILED, None

    if pod_state['phase'] == PodLifeCycle.SUCCEEDED:
        return JobLifeCycle.SUCCEEDED, None

    if pod_state['deletion_timestamp']:
        return JobLifeCycle.DELETED, pod_state['deletion_timestamp']

    if not pod_state['pod_conditions']:
        return JobLifeCycle.UNKNOWN, 'Unknown pod conditions'

    if not pod_state['pod_conditions'][PodConditions.SCHEDULED]['status']:
        return JobLifeCycle.BUILDING, pod_state['pod_conditions'][PodConditions.SCHEDULED]['reason']

    if not (pod_state['pod_conditions'][PodConditions.SCHEDULED] or
                pod_state['pod_conditions'][PodConditions.READY]):
        return JobLifeCycle.BUILDING

    if PodConditions.READY not in pod_state['pod_conditions']:
        return JobLifeCycle.BUILDING, None

    job_container_status = pod_state['container_statuses'].get(job_container_name)

    if not job_container_status:
        return PodLifeCycle.UNKNOWN

    job_container_status_terminated = job_container_status['state'][ContainerStatuses.TERMINATED]
    if job_container_status_terminated:
        if job_container_status_terminated['reason'] == 'Completed':
            return JobLifeCycle.SUCCEEDED
        if job_container_status_terminated['reason'] == 'Error':
            return JobLifeCycle.FAILED, (job_container_status_terminated['message'],
                                         job_container_status_terminated['exit_code'])

    job_container_status_waiting = job_container_status['state'][ContainerStatuses.WAITING]
    if job_container_status_waiting:
        return JobLifeCycle.BUILDING, job_container_status_waiting['reason']
    job_container_status_running = job_container_status['state'][ContainerStatuses.RUNNING]
    if job_container_status['state'][ContainerStatuses.RUNNING]:
        return JobLifeCycle.RUNNING, job_container_status_running['reason']

    # Unknown?
    return PodLifeCycle.UNKNOWN, None


def get_job_state(raw_event, job_container_name, experiment_type_label):
    pod_state = pods.get_pod_state(raw_event)
    if pod_state['labels']['type'] != experiment_type_label:  # 2 type: core and experiment
        return

    status, message = get_job_status(pod_state, job_container_name)
    return {
        'status': status,
        'message': message,
        'details': pod_state,
    }
