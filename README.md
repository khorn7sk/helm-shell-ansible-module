## Required flags:

- **context** -> Context from kubeconfig to use
- **name** -> Name that will be assigned to the installed chart
- **namespace** -> Namespace where the chart will be installed
- **source:**
- - ***type*** -> Values: **directory** (install local chart) or **repo** (install remote chart)
- - ***name*** -> Name of the *repo*. Example: stable/grafana (only when type = repo)
- - ***location*** -> Folder path or remote url, depends on source type

## Optional flags

- **tillerless** -> If set to "True" it will use tillerless plugin. Else, it will use helm with --tiller-connection-timeout 10.
- **values** -> These values will be passed using --set helm flag
- **values_file** -> Must be a path to a file with contents in yaml format. This will be passed using -f helm flag
- **debug** -> Will run in debug mode
- **force** -> Used to upgrade chart when chart version is the same
- **version** -> If version > deployed, will deploy new version. If version < deployed, will rollback to the target version. If equal, will do nothing. If unset, will deploy the latest version.

> Note the string when setting 'True' or 'False', it is to avoid issues with ansible is converting the boolean

## Examples

In the following examples we will show a task to deploy Grafana into the cluster using the public stable repo or custom local folder. This example shows the use of all the flags.

### Install from repo
```
- name: Install Grafana
  helm_shell:
    name: grafana
    context: "{{ kube_context }}"
    namespace: monitoring
    values: "grafana.ingress=enabled" # Separate values with commas
    values_file: {{ role_path }}/files/grafana-values.yaml
    version: 3.8.3
    source:
      type: repo
      name: stable # Name is mandatory when repo is remote
      location: https://kubernetes-charts.storage.googleapis.com
    debug: "True"
    force_install: "True"
    tillerless: "False"
    state: "{{ 'present' if enable_prometheus == true else 'absent' }}"
```

### Install from local folder
```
- name: Install Grafana
  helm_shell:
    name: grafana
    context: "{{ kube_context }}"
    namespace: monitoring
    values: "grafana.ingress=enabled" # Separate values with commas
    values_file: {{ role_path }}/files/grafana-values.yaml
    version: 3.8.3
    source:
      type: directory
      location: "{{ role_path }}/files/charts/grafana"
    state: "{{ 'present' if enable_grafana == true else 'absent' }}"
```
