================================
 Installation and Configuration
================================

Installing git-review
=====================

``git-review`` can be often be installed via system packages, ``pypi``
releases or other platform-specific methods.  See
`<https://www.mediawiki.org/wiki/Gerrit/git-review>`__ for platform
information.

For assistance installing pacakges from ``pypi`` on your OS check out
`get-pip.py <https://pip.pypa.io/en/stable/installing/>`__.

For installation from source simply add ``git-review`` to your $PATH
after installing the dependencies listed in requirements.txt

.. note:: ``git-review`` requires git version 1.8 or greater.

Windows
-------

The Windows ``cmd`` console has a number of issues with Python and
Unicode encodings which can manifest when reviews include non-ASCII
characters.  Python 3.6 and beyond has addressed most issues and is
recommended for Windows users.  For earlier Python versions,
modifying the local install with `win-unicode-console
<https://github.com/Drekin/win-unicode-console>`__ may also help.

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
