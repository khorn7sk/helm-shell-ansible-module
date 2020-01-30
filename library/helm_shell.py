#!/usr/bin/python
import json
import os

from ansible.module_utils.basic import AnsibleModule

ANSIBLE_METADATA = {
    'metadata_version': '1.2',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
Depends on `helm` command being available on the host it is executed on.
To run on the host where the playbook was executed, use delegate_to e.g.
```
  roles:
    - role: hypi-charts
      delegate_to: 127.0.0.1
```
'''

EXAMPLES = '''
- name: Install Rook Ceph Operator
  chart_deploy_name: ceph-random
  helm_shell:
    namespace: default
    name: rook-ceph
    version: 0.8.0
    source:
      type: directory
      location: "{{ role_path }}/files/platform/rook"
'''

RETURN = '''
'''

module_args = dict(
    name=dict(type='str', required=True),
    chart_deploy_name=dict(type='str', required=True),
    version=dict(type='str', required=False),
    source=dict(type='dict', required=True),
    namespace=dict(type='str', required=False, default='default'),
    state=dict(type='str', required=False, default='present'),
    values=dict(type='str', required=False, default=''),
    tillerless=dict(type='bool', required=False, default=False),
    values_file=dict(type='str', required=False, default=''),
    force=dict(type='bool', required=False, default=False)
)

module = AnsibleModule(
    argument_spec=module_args,
    supports_check_mode=True
)

result = dict(
    changed=False,
    original_message='',
    message=''
)


def remove_tmp_file(values_file):
    if values_file != "":
        try:
            os.remove(values_file)
        except Exception as err:
            raise Exception('Cant remove tmp file on the remove host. Reason: ' + str(err))


def install_chart(**kwargs):
    """
    Kwargs:
        helm_exec (str): helm execution command
        install_type (str): 'install' or 'upgrade' command for helm_cli
        replace (bool): should we add '--replace' command
        chart_deploy_name (str): name of chart deployment
        chart_source_name (str): chart repo name
        chart_name (str): chart name
        chart_source_type (str): Type of chart repo 'repo' or 'directory
        chart_location (str): URL or Path to chart
        chart_namespace (str): namespace for installing chart
        chart_version (str): chart version
        values (str): chart values
        values_file (str): path to chart value file
        check_mode (bool): add --dry-run flag
        force (bool): add --force flag
    Returns:
        bool
        str - raw output from helm install command
        int - installation code
    """
    # Starting build shell command
    cmd_string = kwargs.get('helm_exec')

    # Get some vars
    install_type = kwargs.get('install_type')
    check_mode = kwargs.get('check_mode')

    # Define type of installation 'install' or 'update'
    if install_type == 'upgrade' and check_mode is False:
        cmd_string += ' {0} {1}'.format(kwargs.get('install_type'), kwargs.get('chart_deploy_name'))
    elif install_type == 'upgrade' and check_mode:
        cmd_string += ' {0} --dry-run {1}'.format(kwargs.get('install_type'), kwargs.get('chart_deploy_name'))
    elif install_type == 'install' and check_mode is False:
        cmd_string += ' {0} --name={1}'.format(kwargs.get('install_type'), kwargs.get('chart_deploy_name'))
    elif install_type == 'install' and check_mode:
        cmd_string += ' {0} --dry-run --name={1}'.format(kwargs.get('install_type'), kwargs.get('chart_deploy_name'))

    if kwargs.get('force') and install_type == 'upgrade':
        cmd_string += ' --force'

    if kwargs.get('replace'):
        cmd_string += ' --replace'

    # Specify path fot local chart repo, and repo name for remote
    if kwargs.get('chart_source_type') == 'directory':
        cmd_string += ' {0} --namespace="{1}"'.format(kwargs.get('chart_location'), kwargs.get('chart_namespace'))
    else:
        cmd_string += ' {0}/{1} --namespace="{2}"'.format(kwargs.get('chart_source_name'), kwargs.get('chart_name'),
                                                          kwargs.get('chart_namespace'))

    # Specify chart version
    if kwargs.get('chart_version'):
        cmd_string += ' --version="{0}"'.format(kwargs.get('chart_version'))

    # Specify chart values
    if kwargs.get('values'):
        cmd_string += ' --set {0}'.format(kwargs.get('values'))

    # Specify chart values file
    if kwargs.get('values_file'):
        cmd_string += ' -f {0}'.format(kwargs.get('values_file'))

    if check_mode is False:
        cmd_string += ' --output json'

    (_rc, install_chart_output_raw, _err) = module.run_command(cmd_string, use_unsafe_shell=True)
    if _rc:
        return module.exit_json(original_message=_err, cmd=cmd_string, changed=False, failed=True)

    # Load output to json format and pars installation code
    if check_mode is False:
        install_chart_output = json.loads(install_chart_output_raw)
        install_code = install_chart_output['info']['status']['code']
    else:
        install_chart_output = install_chart_output_raw
        install_code = 1

    if install_code == 1:
        return True, install_chart_output, install_code, cmd_string
    else:
        return False, install_chart_output, install_code, cmd_string


def get_chart_lists(helm_exec):
    """
    Args:
        helm_exec (str): helm execution command
    Returns:
        dist of all charts name and status
    """
    _cmd_str = helm_exec + 'list --all --output json'
    (_rc, helm_chart_list_raw, _err) = module.run_command(_cmd_str, use_unsafe_shell=True)
    if _rc:
        return module.exit_json(original_message=_err, cmd=_cmd_str, changed=False, failed=True)

    # Return None if no one charts installed
    if len(helm_chart_list_raw) == 0:
        return ''

    # Parse chart names
    helm_chart_list = {}
    for chart in json.loads(helm_chart_list_raw)['Releases']:
        helm_chart_list.update({chart['Name']: chart['Status']})

    return helm_chart_list


def remove_chart(helm_exec, chart_deploy_name, check_mode):
    """
    Args:
        helm_exec (str): helm execution command
        chart_deploy_name (str): chart name
        check_mode (bool): run with --dry-run flag
    """
    if check_mode is False:
        _cmd_str = helm_exec + 'delete "{0}" --purge'.format(chart_deploy_name)
    else:
        _cmd_str = helm_exec + 'delete "{0}" --purge --dry-run'.format(chart_deploy_name)

    (_rc, remove_chart_output_raw, _err) = module.run_command(_cmd_str, use_unsafe_shell=True)
    if _rc:
        return module.exit_json(original_message=_err, cmd=_cmd_str, changed=False, failed=True)

    # Check output and fail task when not find 'deleted message in output'
    if 'deleted' in remove_chart_output_raw:
        result['changed'] = True
        result['failed'] = False
        result['message'] = 'Deleted chart {0}'.format(chart_deploy_name)
        result['original_message'] = remove_chart_output_raw
        return module.exit_json(**result)
    else:
        return module.exit_json(original_message='Cant remove chart: {0}'.format(chart_deploy_name), cmd=_cmd_str,
                                changed=False, failed=True)


def check_repo(helm_exec, chart_source_name, chart_location):
    """
    Args:
        helm_exec (str): helm execution command
        chart_source_name (str): chart name
        chart_location (str): chart remote URL
    Returns:
        bool
    """

    # Get installed repo list
    _cmd_str = helm_exec + 'repo list -o json'
    (_rc, repo_list_raw, _err) = module.run_command(_cmd_str, use_unsafe_shell=True)
    if _rc:
        return module.exit_json(original_message=_err, cmd=_cmd_str, changed=False, failed=True)

    repo_list = json.loads(repo_list_raw)

    # Check if repo already added
    for repo in repo_list:
        if chart_source_name in repo['Name'] and chart_location in repo['URL']:
            return True

    return False


def update_repo(helm_exec, chart_source_name):
    """
    Args:
        helm_exec (str): helm execution command
        chart_source_name (str): chart name
    Returns:
        bool
    """
    # Update repo
    _cmd_str = helm_exec + 'repo update {0}'.format(chart_source_name)
    (_rc, update_repo_output_raw, _err) = module.run_command(_cmd_str, use_unsafe_shell=True)
    if _rc:
        return module.exit_json(original_message=_err, cmd=_cmd_str, changed=False, failed=True)

    for line in update_repo_output_raw.splitlines():
        if 'Update Complete.' in line:
            return True

    return False


def add_repo(helm_exec, chart_source_name, chart_location):
    """
    Args:
        helm_exec (str): helm execution command
        chart_source_name (str): chart name
        chart_location (str): chart remote URL
    Returns:
        bool
    """
    _cmd_str = helm_exec + 'repo add {0} {1}'.format(chart_source_name, chart_location)
    (_rc, _out, _err) = module.run_command(_cmd_str, use_unsafe_shell=True)
    if _rc:
        return module.exit_json(original_message=_err, cmd=_cmd_str, changed=False, failed=True)

    if check_repo(helm_exec, chart_source_name, chart_location):
        return True
    else:
        return False


def run_module():
    chart_namespace = module.params['namespace']
    chart_state = module.params['state']
    chart_name = module.params['name']
    chart_deploy_name = module.params['chart_deploy_name']
    chart_location = module.params['source']['location']
    chart_source_type = module.params['source']['type']
    values = module.params['values']
    tillerless = module.params['tillerless']
    values_file = module.params['values_file']
    force = module.params['force']
    chart_version = module.params['version']
    chart_source_name = module.params['source']['name'] if chart_source_type == 'repo' else ''

    # Check if we need to use tillerless helm
    if tillerless:
        helm_exec = 'helm tiller run kube-system -- helm '
    else:
        helm_exec = 'helm --tiller-connection-timeout 10 '

    # Get chart lists
    helm_charts_list = get_chart_lists(helm_exec)

    # Remove chart if state 'absent'
    if chart_state == 'absent':
        if chart_deploy_name in helm_charts_list:
            remove_chart(helm_exec, chart_deploy_name, module.check_mode)
        elif chart_deploy_name not in helm_charts_list:
            result['changed'] = False
            result['failed'] = False
            result['message'] = 'Chart with name "{0}" already is not installed'.format(chart_deploy_name)
            remove_tmp_file(values_file)
            return module.exit_json(**result)

    # Add/update remote repository
    if module.check_mode is False:
        if chart_source_type == 'repo' and check_repo(helm_exec, chart_source_name, chart_location):
            if add_repo(helm_exec, chart_source_name, chart_location) is False:
                remove_tmp_file(values_file)
                return module.exit_json(msg='Cant add chart repo with name: %s' % chart_source_name, changed=False,
                                        failed=True)
        if update_repo(helm_exec, chart_source_name) is False:
            remove_tmp_file(values_file)
            return module.exit_json(msg='Cant upgrade chart repo with name: %s' % chart_source_name, changed=False,
                                    failed=True)

    # Chart doesn't exist first time, install
    if chart_deploy_name not in helm_charts_list:
        (ex_result, msg, code, cmd_str) = install_chart(helm_exec=helm_exec, install_type='install', replace=False,
                                                        chart_deploy_name=chart_deploy_name,
                                                        chart_source_name=chart_source_name,
                                                        chart_name=chart_name, chart_namespace=chart_namespace,
                                                        chart_version=chart_version, values=values,
                                                        values_file=values_file, chart_source_type=chart_source_type,
                                                        chart_location=chart_location, check_mode=module.check_mode,
                                                        force=force)
    # Chart exist, but in status 'DELETED', reinstall
    elif chart_deploy_name in helm_charts_list and helm_charts_list[chart_deploy_name] == 'DELETED':
        (ex_result, msg, code, cmd_str) = install_chart(helm_exec=helm_exec, install_type='install', replace=True,
                                                        chart_deploy_name=chart_deploy_name,
                                                        chart_source_name=chart_source_name,
                                                        chart_name=chart_name, chart_namespace=chart_namespace,
                                                        chart_version=chart_version, values=values,
                                                        values_file=values_file, chart_source_type=chart_source_type,
                                                        chart_location=chart_location, check_mode=module.check_mode,
                                                        force=force)
    # Chart exist, but in status 'DEPLOYED', upgrade
    else:
        (ex_result, msg, code, cmd_str) = install_chart(helm_exec=helm_exec, install_type='upgrade',
                                                        chart_deploy_name=chart_deploy_name,
                                                        chart_source_name=chart_source_name,
                                                        chart_name=chart_name, chart_namespace=chart_namespace,
                                                        chart_version=chart_version, values=values,
                                                        values_file=values_file, chart_source_type=chart_source_type,
                                                        chart_location=chart_location, check_mode=module.check_mode,
                                                        force=force)
    # Change task status
    if ex_result:
        chart_version = 'latest' if chart_version is False else chart_version
        result['changed'] = True
        result['failed'] = False
        result['message'] = 'Installed chart {0}, version {1}'.format(chart_deploy_name, chart_version)
        result['original_message'] = msg
        result['cmd'] = cmd_str
        remove_tmp_file(values_file)
        return module.exit_json(**result)
    else:
        remove_tmp_file(values_file)
        return module.exit_json(msg='Chart {0} is not installed'.format(chart_deploy_name), original_message=msg,
                                cmd=cmd_str, changed=False, failed=True)


def main():
    run_module()


if __name__ == '__main__':
    main()
