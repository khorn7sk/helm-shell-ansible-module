## Install:
- `pip install -r requirements.txt`
- copy plugins folder to:
    - ~/.ansible/plugins/modules
    - /usr/share/ansible/plugins/modules
- or add to ansible.cfg path to plugins folder:
```
action_plugins = PATH_TO_PLUGINS_FOLDER/action/
library = PATH_TO_PLUGINS_FOLDER/modules
```

## Required flags:

- **name** -> Name that will be assigned to the installed chart
- **chart_deploy_name** -> Name of chart deployment
- **namespace** -> Namespace where the chart will be installed
- **source:**
- - ***type*** -> Values: **directory** (install local chart) or **repo** (install remote chart)
- - ***name*** -> Name of the *repo*. Example: stable/grafana (only when type = repo)
- - ***location*** -> Folder path or remote url, depends on source type

## Optional flags

- **values** -> These values will be passed using --set helm flag
- **values_file** -> Must be a path to a file with contents in yaml format. This will be passed using -f helm flag
- **force** -> Used to upgrade chart and force recreate chart components
- **version** -> If version > deployed, will deploy new version. If version < deployed, will rollback to the target version. If equal, will do nothing. If unset, will deploy the latest version.

> Note the string when setting 'True' or 'False', it is to avoid issues with ansible is converting the boolean

## Examples

In the following examples we will show a task to deploy Grafana into the cluster using the public stable repo or custom local folder. This example shows the use of all the flags.

### Install from repo
```
- name: Install Grafana
  helm_shell:
    name: grafana
    chart_deploy_name: grafana_v5
    namespace: monitoring
    create_namespace: True
    force: True
    values: "grafana: enabled" # YAML/JSON format
    values_file: grafana-values.yaml # can be stored in files(playbook or role dir)
    version: 3.8.3
    source:
      type: repo
      name: stable # Name is mandatory when repo is remote
      location: https://kubernetes-charts.storage.googleapis.com
    force_install: "True"
    state: "{{ 'present' if enable_prometheus == true else 'absent' }}"
```

### Install from local folder
```
- name: Install Grafana
  helm_shell:
    name: grafana
    chart_deploy_name: grafana_v5
    namespace: monitoring
    values: "grafana: enabled" # YAML/JSON format
    values_file: grafana-values.yaml # can be stored in files(playbook or role dir)
    version: 3.8.3
    source:
      type: local
      location: grafana-3.8.3.tgz # can be stored in files(playbook or role dir)
    state: "{{ 'present' if enable_grafana == true else 'absent' }}"
```
