.. include:: ../../CONTRIBUTING.rst

Running tests
=============

Running tests for git-review means running a local copy of Gerrit to
check that git-review interacts correctly with it. This requires the
following:

* a Java Runtime Environment on the machine to run tests on

* Internet access to download the gerrit.war file, or a locally
  cached copy (it needs to be located in a .gerrit directory at the
  top level of the git-review project)

To run git-review integration tests the following commands may by run::

    tox -e py27
    tox -e py26
    tox -e py32
    tox -e py33

depending on what Python interpreter would you like to use.
