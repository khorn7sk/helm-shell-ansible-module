#!/usr/bin/python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import tempfile

import yaml
from ansible import constants as _const
from ansible.plugins.action import ActionBase
from jsonmerge import merge


def _create_content_tempfile(content):
    # Create a tempfile containing defined content
    tmp_file_dir, content_tempfile = tempfile.mkstemp(dir=_const.DEFAULT_LOCAL_TMP)

    try:
        with open(content_tempfile, 'w') as yml:
            yaml.safe_dump(content, yml, allow_unicode=True)
    except Exception as err:
        os.remove(content_tempfile)
        result = {'failed': True, 'message': err}
        return result
    return content_tempfile


class ActionModule(ActionBase):

    def save_values_file(self, value_file_content):
        result = dict

        # Create temp file on localhost
        content_tempfile = _create_content_tempfile(value_file_content)

        # Create tmp dir in remote host
        try:
            tmp_src_dir = self._make_tmp_path()
        except Exception as err:
            result['failed'] = True
            result['message'] = str(err)
            return result

        tmp_src_file = tmp_src_dir + os.path.basename(content_tempfile) + '.yaml'

        # Copy file from localhost to remote host
        try:
            self._connection.put_file(content_tempfile, tmp_src_file)
        except Exception as err:
            result['failed'] = True
            result['message'] = err
            return result

        return tmp_src_file, content_tempfile

    def read_values_file(self, value_file):
        # Find the source value file
        value_file_path = self._find_needle('files', value_file)

        # Read value file
        with open(value_file_path, "r") as _file:
            value_file_source = _file.read()

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

        # Save values to file
        if module_args['values'] != '':
            module_args['values_file'], content_tempfile = self.save_values_file(module_args['values'])
            del module_args['values']

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
