# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import subprocess
import traceback


def run_cmd(*args, **kwargs):
    """Run command and check the return code."""
    preexec_fn = None

    if 'chdir' in kwargs:
        def preexec_fn():
            return os.chdir(kwargs['chdir'])

    try:
        proc = subprocess.Popen(args, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, env=os.environ,
                                preexec_fn=preexec_fn)

        if 'confirm' in kwargs and kwargs['confirm']:
            proc.stdin.write('yes'.encode())
            proc.stdin.flush()

        out, err = proc.communicate()
        out = out.decode('utf-8')
    except Exception:
        raise Exception(
            "Exception while processing the command:\n%s.\n%s" %
            (' '.join(args), traceback.format_exc())
        )

    if proc.returncode != 0:
        raise Exception(
            "Error occurred while processing the command:\n%s.\n"
            "Stdout: %s\nStderr: %s" %
            (' '.join(args), out.strip(), err)
        )

    return out.strip()


def run_git(command, *args, **kwargs):
    """Run git command with the specified args."""
    return run_cmd("git", command, *args, **kwargs)


def write_to_file(path, content):
    """Create (if does not exist) and write to the file."""
    with open(path, 'wb') as file_:
        file_.write(content)

GERRIT_CONF_TMPL = """
[gerrit]
    basePath = git
    canonicalWebUrl = http://nonexistent/
[database]
    type = h2
    database = db/ReviewDB
[auth]
    type = DEVELOPMENT_BECOME_ANY_ACCOUNT
[sshd]
    listenAddress = %s:%s
[httpd]
    listenUrl = http://%s:%s/
"""


def get_gerrit_conf(ssh_addr, ssh_port, http_addr, http_port):
    return GERRIT_CONF_TMPL % (ssh_addr, ssh_port, http_addr, http_port)
