#!/usr/bin/python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import tempfile

from ansible import constants as _const
from ansible.module_utils._text import to_bytes
from ansible.plugins.action import ActionBase


def _create_content_tempfile(content):
    # Create a tempfile containing defined content
    tmp_file_dir, content_tempfile = tempfile.mkstemp(dir=_const.DEFAULT_LOCAL_TMP)
    tmp_file = os.fdopen(tmp_file_dir, 'wb')
    content = to_bytes(content)
    try:
        tmp_file.write(content)
    except Exception as err:
        os.remove(content_tempfile)
        result = {'failed': True, 'message': err}
        return result
    finally:
        tmp_file.close()
    return content_tempfile


class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):

        super(ActionModule, self).run(tmp, task_vars)

        # Get module args
        module_args = self._task.args.copy()
        value_file = module_args['values_file']
        result = dict()
        content_tempfile = ''
        tmp_src_file = ''

        # If value file is present copy them to remote host
        if value_file != '':
            # Find the source value file
            value_file_path = self._find_needle('files', value_file)

            # Read value file
            with open(value_file_path, "r") as _file:
                value_file_content = _file.read()

            content_tempfile = _create_content_tempfile(value_file_content)

            # Create tmp dir in remote host
            try:
                tmp_src_dir = self._make_tmp_path()
            except Exception as err:
                result['failed'] = True
                result['message'] = str(err)
                return result

            tmp_src_file = tmp_src_dir + os.path.basename(content_tempfile) + '.yaml'
            module_args['values_file'] = tmp_src_file

            # Copy file from localhost to remote host
            try:
                self._connection.put_file(content_tempfile, tmp_src_file)
            except Exception as err:
                result['failed'] = True
                result['message'] = err
                return result

        # Execute helm_shell module
        module_return = self._execute_module(module_name='helm_shell',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        # Cleanup tmp the files
        if value_file != '':
            try:
                os.remove(content_tempfile)
            except Exception as err:
                raise Exception('Cant remove tmp file on localhost. Reason: ' + str(err))

        result['failed'] = module_return.get('failed')
        result['changed'] = module_return.get('changed')
        result['message'] = module_return.get('message')
        result['original_message'] = module_return.get('original_message')
        result['cmd'] = module_return.get('cmd')
        return result
