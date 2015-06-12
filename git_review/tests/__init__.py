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
import shutil
import stat
import sys

if sys.version < '3':
    import urllib
    import urlparse
    urlparse = urlparse.urlparse
else:
    import urllib.parse
    import urllib.request
    urlparse = urllib.parse.urlparse

import fixtures
import requests
import testtools
from testtools import content

from git_review.tests import utils

WAR_URL = 'https://gerrit-releases.storage.googleapis.com/gerrit-2.9.2.war'
# Update GOLDEN_SITE_VER for every change altering golden site, including
# WAR_URL changes. Set new value to something unique (just +1 it for example)
GOLDEN_SITE_VER = '2'


class GerritHelpers(object):

    def _dir(self, base, *args):
        """Creates directory name from base name and other parameters."""
        return os.path.join(getattr(self, base + '_dir'), *args)

    def init_dirs(self):
        self.primary_dir = os.path.abspath(os.path.curdir)
        self.gerrit_dir = self._dir('primary', '.gerrit')
        self.gsite_dir = self._dir('gerrit', 'golden_site')
        self.gerrit_war = self._dir('gerrit', WAR_URL.split('/')[-1])

    def ensure_gerrit_war(self):
        # check if gerrit.war file exists in .gerrit directory
        if not os.path.exists(self.gerrit_dir):
            os.mkdir(self.gerrit_dir)

        if not os.path.exists(self.gerrit_war):
            print("Downloading Gerrit binary from %s..." % WAR_URL)
            resp = requests.get(WAR_URL)
            if resp.status_code != 200:
                raise RuntimeError("Problem requesting Gerrit war")
            utils.write_to_file(self.gerrit_war, resp.content)
            print("Saved to %s" % self.gerrit_war)

    def init_gerrit(self):
        """Run Gerrit from the war file and configure it."""
        golden_ver_file = self._dir('gsite', 'golden_ver')
        if os.path.exists(self.gsite_dir):
            if not os.path.exists(golden_ver_file):
                golden_ver = '0'
            else:
                with open(golden_ver_file) as f:
                    golden_ver = f.read().strip()
            if GOLDEN_SITE_VER != golden_ver:
                print("Existing golden site has version %s, removing..." %
                      golden_ver)
                shutil.rmtree(self.gsite_dir)
            else:
                print("Golden site of version %s already exists" %
                      GOLDEN_SITE_VER)
                return

        print("Creating a new golden site of version " + GOLDEN_SITE_VER)

        # initialize Gerrit
        utils.run_cmd('java', '-jar', self.gerrit_war,
                      'init', '-d', self.gsite_dir,
                      '--batch', '--no-auto-start', '--install-plugin',
                      'download-commands')

        with open(golden_ver_file, 'w') as f:
            f.write(GOLDEN_SITE_VER)

        # create SSH public key
        key_file = self._dir('gsite', 'test_ssh_key')
        utils.run_cmd('ssh-keygen', '-t', 'rsa', '-b', '4096',
                                    '-f', key_file, '-N', '')
        with open(key_file + '.pub', 'rb') as pub_key_file:
            pub_key = pub_key_file.read()

        # create admin user in Gerrit database
        sql_query = """INSERT INTO ACCOUNTS (REGISTERED_ON) VALUES (NOW());
        INSERT INTO ACCOUNT_GROUP_MEMBERS (ACCOUNT_ID, GROUP_ID) \
            VALUES (0, 1);
        INSERT INTO ACCOUNT_EXTERNAL_IDS (ACCOUNT_ID, EXTERNAL_ID, PASSWORD) \
            VALUES (0, 'username:test_user', 'test_pass');
        INSERT INTO ACCOUNT_SSH_KEYS (SSH_PUBLIC_KEY, VALID) \
            VALUES ('%s', 'Y')""" % pub_key.decode()

        utils.run_cmd('java', '-jar',
                      self._dir('gsite', 'bin', 'gerrit.war'),
                      'gsql', '-d', self.gsite_dir, '-c', sql_query)

    def _run_gerrit_cli(self, command, *args):
        """SSH to gerrit Gerrit server and run command there."""
        return utils.run_cmd('ssh', '-p', str(self.gerrit_port),
                             'test_user@' + self.gerrit_host, 'gerrit',
                             command, *args)

    def _run_git_review(self, *args, **kwargs):
        """Run git-review utility from source."""
        git_review = utils.run_cmd('which', 'git-review')
        kwargs.setdefault('chdir', self.test_dir)
        return utils.run_cmd(git_review, *args, **kwargs)


class BaseGitReviewTestCase(testtools.TestCase, GerritHelpers):
    """Base class for the git-review tests."""

    _test_counter = 0

    @property
    def project_uri(self):
        return self.project_ssh_uri

    def setUp(self):
        """Configure testing environment.

        Prepare directory for the testing and clone test Git repository.
        Require Gerrit war file in the .gerrit directory to run Gerrit local.
        """
        super(BaseGitReviewTestCase, self).setUp()
        self.useFixture(fixtures.Timeout(2 * 60, True))
        BaseGitReviewTestCase._test_counter += 1

        # ensures git-review command runs in local mode (for functional tests)
        self.useFixture(
            fixtures.EnvironmentVariable('GITREVIEW_LOCAL_MODE', ''))

        self.init_dirs()
        ssh_addr, ssh_port, http_addr, http_port, self.site_dir = \
            self._pick_gerrit_port_and_dir()
        self.gerrit_host, self.gerrit_port = ssh_addr, ssh_port

        self.test_dir = self._dir('site', 'tmp', 'test_project')
        self.ssh_dir = self._dir('site', 'tmp', 'ssh')
        self.project_ssh_uri = (
            'ssh://test_user@%s:%s/test/test_project.git' % (
                ssh_addr, ssh_port))
        self.project_http_uri = (
            'http://test_user:test_pass@%s:%s/test/test_project.git' % (
                http_addr, http_port))

        self._run_gerrit(ssh_addr, ssh_port, http_addr, http_port)
        self._configure_ssh(ssh_addr, ssh_port)

        # create Gerrit empty project
        self._run_gerrit_cli('create-project', '--empty-commit',
                             '--name', 'test/test_project')

        # ensure user proxy conf doesn't interfere with tests
        os.environ['no_proxy'] = os.environ['NO_PROXY'] = '*'

        # isolate tests from user and system git configuration
        self.home_dir = self._dir('site', 'tmp', 'home')
        self.xdg_config_dir = self._dir('home', '.xdgconfig')
        os.environ['HOME'] = self.home_dir
        os.environ['XDG_CONFIG_HOME'] = self.xdg_config_dir
        os.environ['GIT_CONFIG_NOSYSTEM'] = "1"
        os.environ['EMAIL'] = "you@example.com"
        if not os.path.exists(self.home_dir):
            os.mkdir(self.home_dir)
        if not os.path.exists(self.xdg_config_dir):
            os.mkdir(self.xdg_config_dir)
        self.addCleanup(shutil.rmtree, self.home_dir)

        # prepare repository for the testing
        self._run_git('clone', self.project_uri)
        utils.write_to_file(self._dir('test', 'test_file.txt'),
                            'test file created'.encode())
        self._create_gitreview_file()

        # push changes to the Gerrit
        self._run_git('add', '--all')
        self._run_git('commit', '-m', 'Test file and .gitreview added.')
        self._run_git('push', 'origin', 'master')
        shutil.rmtree(self.test_dir)

        # go to the just cloned test Git repository
        self._run_git('clone', self.project_uri)
        self._run_git('remote', 'add', 'gerrit', self.project_uri)
        self.addCleanup(shutil.rmtree, self.test_dir)

        # ensure user is configured for all tests
        self._configure_gitreview_username()

    def attach_on_exception(self, filename):
        @self.addOnException
        def attach_file(exc_info):
            if os.path.exists(filename):
                content.attach_file(self, filename)
            else:
                self.addDetail(os.path.basename(filename),
                               content.text_content('Not found'))

    def _run_git(self, command, *args):
        """Run git command using test git directory."""
        if command == 'clone':
            return utils.run_git(command, args[0], self._dir('test'))
        return utils.run_git('--git-dir=' + self._dir('test', '.git'),
                             '--work-tree=' + self._dir('test'),
                             command, *args)

    def _run_gerrit(self, ssh_addr, ssh_port, http_addr, http_port):
        # create a copy of site dir
        shutil.copytree(self.gsite_dir, self.site_dir)
        self.addCleanup(shutil.rmtree, self.site_dir)
        # write config
        with open(self._dir('site', 'etc', 'gerrit.config'), 'w') as _conf:
            new_conf = utils.get_gerrit_conf(
                ssh_addr, ssh_port, http_addr, http_port)
            _conf.write(new_conf)

        # If test fails, attach Gerrit config and logs to the result
        self.attach_on_exception(self._dir('site', 'etc', 'gerrit.config'))
        for name in ['error_log', 'sshd_log', 'httpd_log']:
            self.attach_on_exception(self._dir('site', 'logs', name))

        # start Gerrit
        gerrit_sh = self._dir('site', 'bin', 'gerrit.sh')
        utils.run_cmd(gerrit_sh, 'start')
        self.addCleanup(utils.run_cmd, gerrit_sh, 'stop')

    def _simple_change(self, change_text, commit_message,
                       file_=None):
        """Helper method to create small changes and commit them."""
        if file_ is None:
            file_ = self._dir('test', 'test_file.txt')
        utils.write_to_file(file_, change_text.encode())
        self._run_git('add', file_)
        self._run_git('commit', '-m', commit_message)

    def _simple_amend(self, change_text, file_=None):
        """Helper method to amend existing commit with change."""
        if file_ is None:
            file_ = self._dir('test', 'test_file_new.txt')
        utils.write_to_file(file_, change_text.encode())
        self._run_git('add', file_)
        # cannot use --no-edit because it does not exist in older git
        message = self._run_git('log', '-1', '--format=%s\n\n%b')
        self._run_git('commit', '--amend', '-m', message)

    def _configure_ssh(self, ssh_addr, ssh_port):
        """Setup ssh and scp to run with special options."""

        os.mkdir(self.ssh_dir)

        ssh_key = utils.run_cmd('ssh-keyscan', '-p', str(ssh_port), ssh_addr)
        utils.write_to_file(self._dir('ssh', 'known_hosts'), ssh_key.encode())
        self.addCleanup(os.remove, self._dir('ssh', 'known_hosts'))

        # Attach known_hosts to test results if anything fails
        self.attach_on_exception(self._dir('ssh', 'known_hosts'))

        for cmd in ('ssh', 'scp'):
            cmd_file = self._dir('ssh', cmd)
            s = '#!/bin/sh\n' \
                '/usr/bin/%s -i %s -o UserKnownHostsFile=%s ' \
                '-o IdentitiesOnly=yes ' \
                '-o PasswordAuthentication=no $@' % \
                (cmd,
                 self._dir('gsite', 'test_ssh_key'),
                 self._dir('ssh', 'known_hosts'))
            utils.write_to_file(cmd_file, s.encode())
            os.chmod(cmd_file, os.stat(cmd_file).st_mode | stat.S_IEXEC)

        os.environ['PATH'] = self.ssh_dir + os.pathsep + os.environ['PATH']
        os.environ['GIT_SSH'] = self._dir('ssh', 'ssh')

    def _configure_gitreview_username(self):
        self._run_git('config', 'gitreview.username', 'test_user')

    def _pick_gerrit_port_and_dir(self):
        pid = os.getpid()
        host = '127.%s.%s.%s' % (self._test_counter, pid >> 8, pid & 255)
        return host, 29418, host, 8080, self._dir('gerrit', 'site-' + host)

    def _create_gitreview_file(self, **kwargs):
        cfg = ('[gerrit]\n'
               'scheme=%s\n'
               'host=%s\n'
               'port=%s\n'
               'project=test/test_project.git\n'
               '%s')
        parsed = urlparse(self.project_uri)
        host_port = parsed.netloc.rpartition('@')[-1]
        host, __, port = host_port.partition(':')
        extra = '\n'.join('%s=%s' % kv for kv in kwargs.items())
        cfg %= parsed.scheme, host, port, extra
        utils.write_to_file(self._dir('test', '.gitreview'), cfg.encode())


class HttpMixin(object):
    """HTTP remote_url mixin."""

    @property
    def project_uri(self):
        return self.project_http_uri

    def _configure_gitreview_username(self):
        # trick to set http password
        self._run_git('config', 'gitreview.username', 'test_user:test_pass')
