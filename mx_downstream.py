#!/usr/bin/env python2.7
#
# ----------------------------------------------------------------------------------------------------
#
# Copyright (c) 2007, 2015, Oracle and/or its affiliates. All rights reserved.
# DO NOT ALTER OR REMOVE COPYRIGHT NOTICES OR THIS FILE HEADER.
#
# This code is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 only, as
# published by the Free Software Foundation.
#
# This code is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# version 2 for more details (a copy is included in the LICENSE file that
# accompanied this code).
#
# You should have received a copy of the GNU General Public License version
# 2 along with this work; if not, write to the Free Software Foundation,
# Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Please contact Oracle, 500 Oracle Parkway, Redwood Shores, CA 94065 USA
# or visit www.oracle.com if you need additional information or have any
# questions.
#
# ----------------------------------------------------------------------------------------------------
#

from os.path import join, exists, isabs
from argparse import ArgumentParser
from urlparse import urlparse
import shutil
import os
import mx

def testdownstream_cli(args):
    """tests a downstream repo against the current working directory state of the primary suite

    Multiple repos can be specified with multiple instances of the -R/--repo option. The
    first specified repo is the one being tested. Further repos can be specified to either
    override where suites are cloned from or to satisfy --dynamicimports.
    """
    parser = ArgumentParser(prog='mx testdownstream')
    parser.add_argument('-R', '--repo', dest='repos', action='append', help='URL of downstream repo to clone. First specified repo is the primary repo being tested', required=True, metavar='<url>', default=[])
    parser.add_argument('--suitedir', action='store', help='relative directory of suite to test in primary repo (default: . )', default='.', metavar='<path>')
    parser.add_argument('-C', '--mx-command', dest='mxCommands', action='append', help='arguments to an mx command run in primary repo suite (e.g., -C "-v --strict-compliance gate")', default=[], metavar='<args>')
    parser.add_argument('-E', '--encoded-space', help='character used to encode a space in an mx command argument. Each instance of this character in an argument will be replaced with a space.', metavar='<char>')

    args = parser.parse_args(args)

    mxCommands = []
    for command in [e.split() for e in args.mxCommands]:
        if args.encoded_space:
            command = [arg.replace(args.encoded_space, ' ') for arg in command]
        mxCommands.append(command)

    return testdownstream(mx.primary_suite(), args.repos, args.suitedir, mxCommands)

def testdownstream(suite, repoUrls, relTargetSuiteDir, mxCommands):
    """
    Tests a downstream repo against the current working directory state of `suite`.

    :param mx.Suite suite: the suite to test against the downstream repo
    :param list repoUrls: URLs of downstream repos to clone, the first of which is the repo being tested
    :param str relTargetSuiteDir: directory of the downstream suite to test relative to the top level
           directory of the downstream repo being tested
    :param list mxCommands: argument lists for the mx commands run in downstream suite being tested
    """

    assert len(repoUrls) > 0
    workDir = join(suite.get_output_root(), 'testdownstream')

    # A mirror of the current suite is created with symlinks
    mirror = join(workDir, suite.name)
    if exists(mirror):
        shutil.rmtree(mirror)
    mx.ensure_dir_exists(mirror)
    for f in os.listdir(suite.dir):
        subDir = join(suite.dir, f)
        if subDir == suite.get_output_root():
            continue
        src = join(suite.dir, f)
        dst = join(mirror, f)
        mx.logv('[Creating symlink from {} to {}]'.format(dst, src))
        relsrc = os.path.relpath(src, os.path.dirname(dst))
        os.symlink(relsrc, dst)

    targetDir = None
    for repoUrl in repoUrls:
        # Deduce a target name from the target URL
        url = urlparse(repoUrl)
        targetName = url.path
        if targetName.rfind('/') != -1:
            targetName = targetName[targetName.rfind('/') + 1:]
        if targetName.endswith('.git'):
            targetName = targetName[0:-len('.git')]

        repoWorkDir = join(workDir, targetName)
        git = mx.GitConfig()
        if exists(repoWorkDir):
            git.pull(repoWorkDir)
        else:
            git.clone(repoUrl, repoWorkDir)

        # See if there's a matching (non-master) branch downstream and use it if there is
        branch = git.git_command(suite.dir, ['rev-parse', '--abbrev-ref', 'HEAD']).strip()
        if branch != 'master':
            git.git_command(repoWorkDir, ['checkout', branch], abortOnError=False)
        if not targetDir:
            targetDir = repoWorkDir

    assert not isabs(relTargetSuiteDir)
    targetSuiteDir = join(targetDir, relTargetSuiteDir)
    assert targetSuiteDir.startswith(targetDir)
    mxpy = None if suite != mx._mx_suite else join(mirror, 'mx.py')
    for command in mxCommands:
        mx.logv('[running "mx ' + ' '.join(command) + '" in ' + targetSuiteDir + ']')
        mx.run_mx(command, targetSuiteDir, mxpy=mxpy)
