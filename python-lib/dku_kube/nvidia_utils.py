import os, json, logging

from .kubectl_command import run_with_timeout

def has_gpu_driver(kube_config_path):
    env = os.environ.copy()
    env['KUBECONFIG'] = kube_config_path
    cmd = ['kubectl', 'get', 'pods', '--namespace', 'kube-system', '-l', 'name=nvidia-device-plugin-ds', '--ignore-not-found']
    logging.info("Checking if NVIDIA GPU drivers are installed with : %s" % json.dumps(cmd))
    out, err = run_with_timeout(cmd, env=env, timeout=5)
    return len(out.strip()) > 0

def add_gpu_driver_if_needed(kube_config_path):
    if not has_gpu_driver(kube_config_path):
        cmd = ['kubectl', 'apply', '-f', "https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/main/deployments/static/nvidia-device-plugin.yml"]

        logging.info("Install NVIDIA GPU drivers with : %s" % json.dumps(cmd))
        env = os.environ.copy()
        env['KUBECONFIG'] = kube_config_path
        run_with_timeout(cmd, env=env, timeout=5)