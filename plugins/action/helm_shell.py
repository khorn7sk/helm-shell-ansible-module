#!/usr/bin/python

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

import json
import os
import tempfile

import yaml
from ansible import constants as _const
from ansible.module_utils.common.json import AnsibleJSONEncoder
from ansible.plugins.action import ActionBase
from jsonmerge import merge


class ActionModule(ActionBase):

    @staticmethod
    def create_content_tempfile(content):
        result = {'failed': False, 'message': 'None', 'reason': 'None', 'content': 'None'}

        # Convert AnsibleUnsafeText to normal JSON
        content = json.dumps(content, sort_keys=True, cls=AnsibleJSONEncoder)
        content = json.loads(content)

        # Create a tempfile containing defined content
        tmp_file_dir, content_tempfile = tempfile.mkstemp(dir=_const.DEFAULT_LOCAL_TMP)

        try:
            with open(content_tempfile, 'w') as yml:
                yaml.safe_dump(content, yml, default_flow_style=False)
        except Exception as err:
            result['failed'] = True
            result['content'] = content
            result['message'] = 'Can\'t save temp values file on localhost'
            result['reason'] = str(err)
            return result, ''

        return result, content_tempfile

    def create_remote_tmp_dir(self):
        result = {'failed': False, 'message': 'None', 'reason': 'None'}

        # Create tmp dir in remote host
        try:
            tmp_dst_dir = self._make_tmp_path()
        except Exception as err:
            result['failed'] = True
            result['message'] = 'Can\'t create tmp dir on remote host'
            result['reason'] = str(err)
            return result, ''

        return result, tmp_dst_dir

    def upload_helm_chart(self, chart_file_name, remote_tmp_dir):
        result = {'failed': False, 'message': 'None', 'reason': 'None'}

        remote_chart_path = os.path.join(remote_tmp_dir, chart_file_name)

        # Find the source value file
        local_chart_path = self._find_needle('files', chart_file_name)

        # Copy file from localhost to remote host
        try:
            self._connection.put_file(local_chart_path, remote_chart_path)
        except Exception as err:
            result['failed'] = True
            result['message'] = 'Can\'t upload helm chart from localhost to remote server'
            result['reason'] = err
            return result, ''

        return result, remote_chart_path

    def upload_values_file(self, value_file_content, remote_tmp_dir):
        result = {'failed': False, 'message': 'None', 'reason': 'None'}

        # Create temp file on localhost
        result, content_temp_file = self.create_content_tempfile(value_file_content)

        if result['failed']:
            return result, '', ''

        remote_values_file = remote_tmp_dir + os.path.basename(content_temp_file) + '.yaml'

        # Copy file from localhost to remote host
        try:
            self._connection.put_file(content_temp_file, remote_values_file)
        except Exception as err:
            result['failed'] = True
            result['message'] = 'Can\'t upload values file from localhost to remote server'
            result['reason'] = err
            return result, '', ''

        return result, remote_values_file, content_temp_file

    def read_values_file(self, value_file):
        # Find the source value file
        value_file_path = self._find_needle('files', value_file)

        # Read value file
        with open(value_file_path, 'r') as _file:
            value_file_source = yaml.safe_load(_file)

        return value_file_source

    def get_module_args(self):
        module_args = self._task.args.copy()
        value_file = module_args['values_file']
        values = module_args['values']
        values_file_content = ''

        # Read values file
        if value_file != '':
            values_file_content = self.read_values_file(value_file)

        # Render values
        if value_file != '' and values != '':
            values_content = merge(values_file_content, values)
        elif value_file != '':
            values_content = values_file_content
        elif values != '':
            values_content = values
        else:
            values_content = ''

        # Save final version of values to args
        if values_content != '':
            module_args['values'] = values_content
            del module_args['values_file']

        return module_args

    def run(self, tmp=None, task_vars=None):

        super(ActionModule, self).run(tmp, task_vars)
        content_tempfile = ''

        # Get module args
        module_args = self.get_module_args()

        # Create tmp dir on remote host
        result, remote_tmp_dir = self.create_remote_tmp_dir()
        if result['failed']:
            return result

        # Save values to file
        if module_args['values'] != '':
            result, module_args['values_file'], content_tempfile = self.upload_values_file(module_args['values'],
                                                                                           remote_tmp_dir)
            if result['failed']:
                return result

        del module_args['values']

        # Upload helm chart
        if module_args['source']['type'] == 'local':
            result, module_args['source']['location'] = self.upload_helm_chart(module_args['source']['location'],
                                                                               remote_tmp_dir)
            if result['failed']:
                return result

        # Execute helm_shell module
        module_return = self._execute_module(module_name='helm_shell',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        # Cleanup tmp the files
        if content_tempfile != '':
            try:
                os.remove(content_tempfile)
            except Exception as err:
                raise Exception('Cant remove tmp file on localhost. Reason: ' + str(err))

        return module_return
