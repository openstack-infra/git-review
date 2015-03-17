================================
 Installation and Configuration
================================

Installing git-review
=====================

Install with pip install git-review

For assistance installing pip on your os check out get-pip:
http://pip.readthedocs.org/en/latest/installing.html

For installation from source simply add git-review to your $PATH
after installing the dependencies listed in requirements.txt

Setup
=====

By default, git-review will look for a remote named 'gerrit' for working
with Gerrit. If the remote exists, git-review will submit the current
branch to HEAD:refs/for/master at that remote.

If the Gerrit remote does not exist, git-review looks for a file
called .gitreview at the root of the repository with information about
the gerrit remote.  Assuming that file is present, git-review should
be able to automatically configure your repository the first time it
is run.

The name of the Gerrit remote is configurable; see the configuration
section below.

.gitreview file format
======================

Example .gitreview file (used to upload for git-review itself)::

    [gerrit]
    host=review.openstack.org
    port=29418
    project=openstack-infra/git-review.git
    defaultbranch=master

Required values: host, project

Optional values: port (default: 29418), defaultbranch (default: master),
defaultremote (default: gerrit).

**Notes**

* Username is not required because it is requested on first run

* Unlike git config files, there cannot be any whitespace before the name
  of the variable.

* Upon first run, git-review will create a remote for working with Gerrit,
  if it does not already exist. By default, the remote name is 'gerrit',
  but this can be overridden with the 'defaultremote' configuration
  option.

* You can specify different values to be used as defaults in
  ~/.config/git-review/git-review.conf or /etc/git-review/git-review.conf.

* Git-review will query git credential system for gerrit user/password when
  authentication failed over http(s). Unlike git, git-review does not persist
  gerrit user/password in git credential system for security purposes and git
  credential system configuration stays under user responsibility.

Hooks
=====

git-review has a custom hook mechanism to run a script before certain
actions. This is done in the same spirit as the classic hooks in git.

There are two types of hooks, a global one which is stored in
~/.config/git-review/hooks/ and one local to the repository stored in
.git/hooks/ with the other git hook scripts.

**The script needs be executable before getting executed**

The name of the script is $action-review where action can be
:

* pre - run at first before doing anything.

* post - run at the end after the review was sent.

* draft - run when in draft mode.

if the script returns with an exit status different than zero,
git-review will exit with the a custom shell exit code 71.
