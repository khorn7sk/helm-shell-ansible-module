## Required flags:

- context
- name
- namespace
- source
- - type
- - name (only when type = repo)
- - location

## Optional flags

- tillerless: If set to "True" it will use tillerless plugin (note the string, to avoid issues with ansible converting the boolean). Else, it will use helm with --tiller-connection-timeout 10.
- version: If set, will check against deployed version. If equal, will not change. If version > deployed, will deploy new version. If version < deployed, will rollback to the target version. If unset, will deploy the latest version.

## Examples

In the following examples we will show a task to deploy Grafana into the cluster using the public stable repo or custom local folder.

### Install from repo
- name: Install Grafana
  helm_shell:
    name: grafana
    context: "{{ kube_context }}"
    namespace: monitoring
    values: "grafana.ingress=enabled" # Separate values with commas
    version: 3.8.3
    source:
      type: repo
      name: stable # Name is mandatory when repo is remote
      location: https://kubernetes-charts.storage.googleapis.com
    tillerless: "False"
    state: "{{ 'present' if enable_prometheus == true else 'absent' }}"

### Install from local folder
- name: Install Grafana
  helm_shell:
    name: grafana
    context: "{{ kube_context }}"
    namespace: monitoring
    values: "grafana.ingress=enabled" # Separate values with commas
    version: 3.8.3
    source:
      type: directory
      location: "{{ role_path }}/files/charts/grafana"
    state: "{{ 'present' if enable_grafana == true else 'absent' }}"

