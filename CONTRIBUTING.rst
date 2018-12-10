============================
 Contributing to git-review
============================

This tool is considered mostly feature-complete by its authors. It
is meant to provide a simple, convenient tool for users of basic
Gerrit change workflows. Contributions fixing bugs or regressions,
maintaining support for newer Gerrit/Git releases and improving test
coverage are welcome and encouraged. It is not, however, intended as
an all-encompassing Gerrit client (there are plenty of other tools
available supporting more advanced interactions), so proposed
feature additions may make more sense implemented as complimentary
``git`` subcommands or similar related but separate projects.

To get the latest code, see: https://git.openstack.org/cgit/openstack-infra/git-review

Bugs are handled at: https://storyboard.openstack.org/#!/project/719

Code reviews, as you might expect, are handled by gerrit at:
https://review.openstack.org
Pull requests submitted through GitHub will be ignored.

Use ``git review`` to submit patches (after creating a gerrit account
that links to your launchpad account). Example::

    # Do your commits
    git review
    # Enter your username if prompted

The code review process is documented at
https://docs.openstack.org/infra/manual/developers.html If that process is
not enough to get reviewers' attention then try these (in that order):

1. Use git log and git blame to find "who last touched the file" and add
   them. Make sure they're still active on https://review.openstack.org
2. Ping the #openstack-infra IRC channel, see developers.html above.
3. As a last resort, mailing-list at:
   http://lists.openstack.org/cgi-bin/mailman/listinfo/openstack-infra
