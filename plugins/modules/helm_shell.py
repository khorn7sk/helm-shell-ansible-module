#!/usr/bin/python
import json
import os
import shutil

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
      type: local
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
    values_file=dict(type='str', required=False, default=''),
    force=dict(type='bool', required=False, default=False),
    create_namespace=dict(type='bool', required=False, default=True)
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


def remove_tmp_folder(values_file):
    if values_file != "":
        try:
            shutil.rmtree(os.path.dirname(values_file), ignore_errors=True)
        except Exception as err:
            raise Exception('Cant remove tmp file on the remove host. Reason: ' + str(err))


def install_chart(**kwargs):
    """
    Kwargs:
        install_type (str): 'install' or 'upgrade' command for helm_cli
        replace (bool): should we add '--replace' command
        chart_deploy_name (str): name of chart deployment
        chart_source_name (str): chart repo name
        chart_name (str): chart name
        chart_source_type (str): Type of chart repo 'repo' or 'local
        chart_location (str): URL or Path to chart
        chart_namespace (str): namespace for installing chart
        chart_create_namespace (bool): create namespace if not exist
        chart_version (str): chart version
        values_file (str): path to chart value file
        check_mode (bool): add --dry-run flag
        force (bool): add --force flag
    Returns:
        bool
        dict - raw output from helm install command
        dict - helm chart manifest
        str - installation status
        str - command string
    """
    # Starting build shell command
    cmd_string = 'helm '

    # Get some vars
    install_type = kwargs.get('install_type')
    check_mode = kwargs.get('check_mode')

    # Define type of installation 'install' or 'update'
    if install_type == 'upgrade' and check_mode is False:
        cmd_string += ' {0} {1}'.format('upgrade -i', kwargs.get('chart_deploy_name'))
    elif install_type == 'upgrade' and check_mode:
        cmd_string += ' {0} -i --dry-run {1}'.format(kwargs.get('install_type'), kwargs.get('chart_deploy_name'))
    elif install_type == 'install' and check_mode is False:
        cmd_string += ' {0} {1}'.format(kwargs.get('install_type'), kwargs.get('chart_deploy_name'))
    elif install_type == 'install' and check_mode:
        cmd_string += ' {0} --dry-run {1}'.format(kwargs.get('install_type'), kwargs.get('chart_deploy_name'))

    if kwargs.get('force') and install_type == 'upgrade':
        cmd_string += ' --force'

    if kwargs.get('chart_create_namespace'):
        cmd_string += ' --create-namespace'

    if kwargs.get('replace'):
        cmd_string += ' --replace'

    # Specify path fot local chart repo, and repo name for remote
    if kwargs.get('chart_source_type') == 'local':
        cmd_string += ' {0} --namespace="{1}"'.format(kwargs.get('chart_location'), kwargs.get('chart_namespace'))
    else:
        cmd_string += ' {0}/{1} --namespace="{2}"'.format(kwargs.get('chart_source_name'), kwargs.get('chart_name'),
                                                          kwargs.get('chart_namespace'))

    # Specify chart version
    if kwargs.get('chart_version'):
        cmd_string += ' --version="{0}"'.format(kwargs.get('chart_version'))

    # Specify chart values file
    if kwargs.get('values_file'):
        cmd_string += ' -f {0}'.format(kwargs.get('values_file'))

    # Set default output to json
    cmd_string += ' --output json'

    (_rc, chart_output_raw, _err) = module.run_command(cmd_string, use_unsafe_shell=True)
    if _rc:
        return module.exit_json(original_message=_err, cmd=cmd_string, changed=False, failed=True)

    # Load output to json format and pars installation code
    chart_output = json.loads(chart_output_raw)
    install_status = chart_output['info']['status']

    chart_message = {}

    if 'name' in chart_output:
        chart_message.update({'name': chart_output['name']})

    if 'namespace' in chart_output:
        chart_message.update({'namespace': chart_output['namespace']})

    if 'manifest' in chart_output:
        chart_message.update({'manifest': chart_output['manifest']})

    if 'version' in chart_output:
        chart_message.update({'version': chart_output['version']})

    if 'info' in chart_output:
        if 'status' in chart_output['info']:
            chart_message.update({'status': chart_output['info']['status']})
        if 'notes' in chart_output['info']:
            chart_message.update({'info': chart_output['info']['notes']})

    chart_diff = {"prepared": chart_output['manifest'] + "\n" + chart_output['info']['notes']}

    if install_status in ['deployed', 'pending-upgrade', 'pending-install']:
        return True, chart_message, chart_diff, install_status, cmd_string
    else:
        return False, chart_message, chart_diff, install_status, cmd_string


def get_chart_lists(chart_namespace):
    """
    Args:
        chart_namespace(str): chart namespace
    Returns:
        dist of all charts name and status
    """
    _cmd_str = 'helm list -n {0} --output json'.format(chart_namespace)
    (_rc, helm_chart_list_raw, _err) = module.run_command(_cmd_str, use_unsafe_shell=True)
    if _rc:
        return module.exit_json(original_message=_err, cmd=_cmd_str, changed=False, failed=True)

    # Return None if no one charts installed
    if len(helm_chart_list_raw) == 0:
        return ''

    # Parse chart names
    helm_chart_list = {}
    for chart in json.loads(helm_chart_list_raw):
        helm_chart_list.update({chart['name']: chart['status']})

    return helm_chart_list


def remove_chart(chart_deploy_name, check_mode, chart_namespace):
    """
    Args:
        chart_deploy_name (str): chart name
        check_mode (bool): run with --dry-run flag
        chart_namespace (str): chart namespace
    """
    if check_mode is False:
        _cmd_str = 'helm delete "{0}" -n "{1}"'.format(chart_deploy_name, chart_namespace)
    else:
        _cmd_str = 'helm delete "{0}" -n "{1}" --dry-run'.format(chart_deploy_name, chart_namespace)

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


def check_repo(chart_source_name, chart_location):
    """
    Args:
        chart_source_name (str): chart name
        chart_location (str): chart remote URL
    Returns:
        bool
    """

    # Get installed repo list
    _cmd_str = 'helm repo list -o json'
    (_rc, repo_list_raw, _err) = module.run_command(_cmd_str, use_unsafe_shell=True)

    if 'no repositories to show' in _err:
        # If no one repo added yes. Add stable
        _cmd_add_stable_repo = 'helm repo add stable https://kubernetes-charts.storage.googleapis.com'
        (_rc, repo_list_raw, _err) = module.run_command(_cmd_add_stable_repo, use_unsafe_shell=True)

        if _rc:
            return module.exit_json(original_message=_err, cmd=_cmd_add_stable_repo, changed=False, failed=True)

        # And rerun repo list
        (_rc, repo_list_raw, _err) = module.run_command(_cmd_str, use_unsafe_shell=True)

    if _rc:
        return module.exit_json(original_message=_err, cmd=_cmd_str, changed=False, failed=True)

    repo_list = json.loads(repo_list_raw)

    # Check if repo already added
    for repo in repo_list:
        if chart_source_name in repo['name'] and chart_location in repo['url']:
            return True

    return False


def update_repo():
    """
    Returns:
        bool
    """
    # Update repo
    _cmd_str = 'helm repo update'
    (_rc, update_repo_output_raw, _err) = module.run_command(_cmd_str, use_unsafe_shell=True)
    if _rc:
        return module.exit_json(original_message=_err, cmd=_cmd_str, changed=False, failed=True)

    for line in update_repo_output_raw.splitlines():
        if 'Update Complete.' in line:
            return True

    return False


def add_repo(repo_source_name, repo_location, repo_username, repo_password):
    """
    Args:
        repo_source_name (str): chart repo name
        repo_location (str): chart repo remote URL
        repo_username (str): repo username
        repo_password (str): repo password
    Returns:
        bool
    """
    if repo_username != "":
        _cmd_str = 'helm repo add --username {0} --password {1} {2} {3}'.format(repo_username, repo_password,
                                                                                repo_source_name, repo_location)
    else:
        _cmd_str = 'helm repo add {0} {1}'.format(repo_source_name, repo_location)
    (_rc, _out, _err) = module.run_command(_cmd_str, use_unsafe_shell=True)
    if _rc:
        return module.exit_json(original_message=_err, cmd=_cmd_str, changed=False, failed=True)

    if check_repo(repo_source_name, repo_location):
        return True
    else:
        return False


def run_module():
    chart_namespace = module.params['namespace']
    chart_create_namespace = module.params['create_namespace']
    chart_state = module.params['state']
    chart_name = module.params['name']
    chart_deploy_name = module.params['chart_deploy_name']
    chart_location = module.params['source']['location']
    chart_source_type = module.params['source']['type']
    chart_source_username = module.params['source']['username']
    chart_source_password = module.params['source']['password']
    values_file = module.params['values_file']
    force = module.params['force']
    chart_version = module.params['version']
    chart_source_name = module.params['source']['name'] if chart_source_type == 'repo' else ''

    # Get chart lists
    helm_charts_list = get_chart_lists(chart_namespace)

    # Remove chart if state 'absent'
    if chart_state == 'absent':
        if chart_deploy_name in helm_charts_list:
            remove_chart(chart_deploy_name, module.check_mode, chart_namespace)
        elif chart_deploy_name not in helm_charts_list:
            result['changed'] = False
            result['failed'] = False
            result['message'] = 'Chart with name "{0}" already is not installed'.format(chart_deploy_name)
            remove_tmp_folder(values_file)
            return module.exit_json(**result)

    # Add/update remote repository
    if chart_source_type == 'repo' and check_repo(chart_source_name, chart_location) is False:
        if add_repo(chart_source_name, chart_location, chart_source_username, chart_source_password) is False:
            remove_tmp_folder(values_file)
            return module.exit_json(msg='Cant add chart repo with name: %s' % chart_source_name, changed=False,
                                    failed=True)

    if update_repo() is False:
        remove_tmp_folder(values_file)
        return module.exit_json(msg='Cant upgrade chart repo with name: %s' % chart_source_name, changed=False,
                                failed=True)

    # Chart doesn't exist first time, install
    if chart_deploy_name not in helm_charts_list:
        (ex_result, msg, diff, status, cmd_str) = install_chart(install_type='install', replace=False,
                                                                chart_deploy_name=chart_deploy_name,
                                                                chart_source_name=chart_source_name,
                                                                chart_name=chart_name, chart_namespace=chart_namespace,
                                                                chart_version=chart_version, values_file=values_file,
                                                                chart_source_type=chart_source_type,
                                                                chart_location=chart_location,
                                                                check_mode=module.check_mode,
                                                                force=force,
                                                                chart_create_namespace=chart_create_namespace)
    # Chart exist, but in status 'DELETED', reinstall
    elif chart_deploy_name in helm_charts_list and helm_charts_list[chart_deploy_name] == 'DELETED':
        (ex_result, msg, diff, status, cmd_str) = install_chart(install_type='install', replace=True,
                                                                chart_deploy_name=chart_deploy_name,
                                                                chart_source_name=chart_source_name,
                                                                chart_name=chart_name, chart_namespace=chart_namespace,
                                                                chart_version=chart_version, values_file=values_file,
                                                                chart_source_type=chart_source_type,
                                                                chart_location=chart_location,
                                                                check_mode=module.check_mode,
                                                                force=force,
                                                                chart_create_namespace=chart_create_namespace)
    # Chart exist, but in status 'DEPLOYED', upgrade
    else:
        (ex_result, msg, diff, status, cmd_str) = install_chart(install_type='upgrade',
                                                                chart_deploy_name=chart_deploy_name,
                                                                chart_source_name=chart_source_name,
                                                                chart_name=chart_name, chart_namespace=chart_namespace,
                                                                chart_version=chart_version, values_file=values_file,
                                                                chart_source_type=chart_source_type,
                                                                chart_location=chart_location,
                                                                check_mode=module.check_mode,
                                                                force=force,
                                                                chart_create_namespace=chart_create_namespace)
    # Change task status
    if ex_result:
        chart_version = 'latest' if chart_version is False else chart_version
        result['changed'] = True
        result['failed'] = False
        result['message'] = 'Installed chart {0}, version {1}'.format(chart_deploy_name, chart_version)
        result['original_message'] = msg
        result['diff'] = diff
        result['cmd'] = cmd_str
        remove_tmp_folder(values_file)
        return module.exit_json(**result)
    else:
        remove_tmp_folder(values_file)
        return module.exit_json(msg='Chart {0} is not installed'.format(chart_deploy_name), original_message=msg,
                                cmd=cmd_str, changed=False, failed=True)


def main():
    run_module()


if __name__ == '__main__':
    main()
