import json
import logging
import os
import random
import sys
import time

import yaml

from .kubectl_command import run_with_timeout


class CreateGpuDaemonset:
    def __init__(self, kube_config_path):
        self.env = os.environ.copy()
        self.env["KUBECONFIG"] = kube_config_path
        self.kube_config_dir = os.path.split(kube_config_path)[0]
        self.daemonset_name = "nvidia-device-plugin-daemonset"
        self.namespace = "gpu-daemonset"

    def _create_namespace_if_not_exist(self):
        cmd = ["kubectl", "get", "namespaces", "-o", "json"]
        out, err = run_with_timeout(cmd, env=self.env, timeout=5)
        output_json = json.loads(out)
        namespaces = {
            namespace_dict["metadata"]["name"]
            for namespace_dict in output_json["items"]
        }
        if self.namespace not in namespaces:
            logging.info("Creating a new namespace - %s", self.namespace)
            cmd = ["kubectl", "create", "namespace", self.namespace]
            out, err = run_with_timeout(cmd, env=self.env, timeout=5)

    def __call__(self):
        # Check to see if a daemonset with the same name exists
        if self.get_daemonset_existence():
            raise Exception(f"The daemonset {self.daemonset_name} already exists")

        self._create_namespace_if_not_exist()

        # create ds
        ds_yaml = {
            "apiVersion": "apps/v1",
            "kind": "DaemonSet",
            "metadata": {"name": self.daemonset_name, "namespace": self.namespace},
            "spec": {
                "selector": {"matchLabels": {"name": "nvidia-device-plugin-ds"}},
                "template": {
                    "metadata": {
                        "annotations": {
                            "cluster-autoscaler.kubernetes.io/enable-ds-eviction": "true",
                            "scheduler.alpha.kubernetes.io/critical-pod": "",
                        },
                        "labels": {"name": "nvidia-device-plugin-ds"},
                    },
                    "spec": {
                        "containers": [
                            {
                                "image": "mcr.microsoft.com/oss/nvidia/k8s-device-plugin:1.11",
                                "name": "nvidia-device-plugin-ctr",
                                "securityContext": {
                                    "allowPrivilegeEscalation": False,
                                    "capabilities": {"drop": ["ALL"]},
                                },
                                "volumeMounts": [
                                    {
                                        "mountPath": "/var/lib/kubelet/device-plugins",
                                        "name": "device-plugin",
                                    }
                                ],
                            }
                        ],
                        "tolerations": [
                            {"key": "CriticalAddonsOnly", "operator": "Exists"},
                            {"effect": "NoExecute", "operator": "Exists"},
                            {"effect": "NoSchedule", "operator": "Exists"},
                        ],
                        "volumes": [
                            {
                                "hostPath": {"path": "/var/lib/kubelet/device-plugins"},
                                "name": "device-plugin",
                            }
                        ],
                    },
                },
                "updateStrategy": {"type": "RollingUpdate"},
            },
        }

        ds_file_path = os.path.join(self.kube_config_dir, "gpu_daemonset")
        with open(ds_file_path, "w") as f:
            yaml.safe_dump(ds_yaml, f)

        cmd = ["kubectl", "create", "-f", os.path.abspath(ds_file_path)]
        logging.info("Create daemonset with : %s" % json.dumps(cmd))
        run_with_timeout(cmd, env=self.env, timeout=5)

        # wait for it to actually run (could be stuck in pending if no resource available)
        waited = 0
        while not self.get_daemonset_existence() and waited < 10:
            time.sleep(1)
            waited += 1

        if not self.get_daemonset_existence():
            raise Exception(
                f"Daemonset {self.daemonset_name} failed to appear within 10s"
            )

        return self

    def get_daemonset_existence(self):
        cmd = [
            "kubectl",
            "get",
            "daemonset",
            self.daemonset_name,
            "-o",
            "json",
            "--ignore-not-found",
        ]
        logging.info("Poll namespace state with : %s" % json.dumps(cmd))
        out, err = run_with_timeout(cmd, env=self.env, timeout=5)
        # Check if the daemonset exists by seeing if anything got returned
        return bool(out)
