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

There is a mailing list at: http://lists.openstack.org/cgi-bin/mailman/listinfo/openstack-infra

Code reviews, as you might expect, are handled by gerrit at:
https://review.openstack.org

See http://wiki.openstack.org/GerritWorkflow for details. Pull
requests submitted through GitHub will be ignored.

Use ``git review`` to submit patches (after creating a gerrit account
that links to your launchpad account). Example::

    # Do your commits
    git review
    # Enter your username if prompted
