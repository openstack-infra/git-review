.. git-review documentation master file, created by
   sphinx-quickstart on Sun Sep 25 09:00:23 2011.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==========
git-review
==========

SYNOPSIS
--------

:program:`git-review` [:ref:`OPTIONS <git-review-options-label`] [*BRANCH*]

DESCRIPTION
-----------

:program:`git-review` automates and streamlines some of the tasks involve with
submitting local changes to a *Gerrit* server for review.

.. _git-review-options-label:

OPTIONS
-------

.. program:: git-review

.. option:: --topic, -t

  Sets the target topic for this change on the gerrit server.

.. option:: --dry-run, -n

  Don't actually perform any commands that have direct effects. Print them
  instead.

.. option:: --no-rebase, -R

  Do not automatically perform a rebase before submitting the change to
  gerrit.

.. option:: --update, -R

  Skip cached local copies and force updates from network resources.

.. options:: --download, -d

  Download a change from gerrit into a branch for review. Takes a numeric
  change id as an argument.

.. options:: --setup, -s

  Just run throught the repo setup commands and then exit before attempting
  to submit anything.

.. option:: --verbose, -v

  Turns on more verbose output.

PROJECT CONFIGURATION
---------------------

To use git-review with your project, it is recommended that you create
a file at the root of the repository called ".gitreview" and place
information about your gerrit installation in it.  The format is::

  [gerrit]
  host=review.example.com
  port=29418
  project=project.git
