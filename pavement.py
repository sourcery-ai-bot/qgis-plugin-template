# -*- coding: utf-8 -*-
#
# (c) 2016 Boundless, http://boundlessgeo.com
# This code is licensed under the GPL 2.0 license.
#

import os
import fnmatch
import shutil
import zipfile
import StringIO
import requests
import json
from collections import defaultdict

# this pulls in the sphinx target
from paver.easy import *
from paver.doctools import html


options(
    plugin = Bunch(
        name = '[pluginshortname]',
        ext_libs = path('[pluginshortname]/extlibs'),
        ext_src = path('[pluginshortname]/ext-src'),
        source_dir = path('[pluginshortname]'),
        package_dir = path('.'),
        tests = ['test', 'tests'],
        excludes = [
            '*.pyc',
            ".git"
        ]
    ),

    sphinx = Bunch(
        docroot = path('docs'),
        sourcedir = path('docs/source'),
        builddir = path('docs/build')
    )
)


@task
@cmdopts([
    ('clean', 'c', 'clean out dependencies first'),
])
def setup(options):
    '''install dependencies'''
    clean = getattr(options, 'clean', False)
    ext_libs = options.plugin.ext_libs
    if clean:
        ext_libs.rmtree()
    ext_libs.makedirs()
    initPath = ext_libs / "__init__.py"
    with open(initPath.abspath(), "a") as f:
        pass
    runtime, test = read_requirements()
    
    [boundlessCommons]

    try:
        import pip
    except:
        error('FATAL: Unable to import pip, please install it first!')
        sys.exit(1)

    os.environ['PYTHONPATH'] = str(ext_libs.abspath())
    for req in runtime + test:
        pip.main(['install',
                  '-t',
                  ext_libs.abspath(),
                  req])


def read_requirements():
    '''return a list of runtime and list of test requirements'''
    lines = open('requirements.txt').readlines()
    lines = [l for l in [l.strip() for l in lines] if l]
    divider = '# test requirements'
    try:
        idx = lines.index(divider)
    except ValueError:
        raise BuildFailure('expected to find "%s" in requirements.txt' % divider)
    not_comments = lambda s,e: [l for l in lines[s:e] if l[0] != '#']
    return not_comments(0, idx), not_comments(idx+1, None)


def _install(folder, options):
    '''install plugin to qgis'''
    plugin_name = options.plugin.name
    src = path(__file__).dirname() / plugin_name
    dst = path('~').expanduser() / folder / 'python' / 'plugins' / plugin_name
    src = src.abspath()
    dst = dst.abspath()
    if not hasattr(os, 'symlink'):
        dst.rmtree()
        src.copytree(dst)
    elif not dst.exists():
        src.symlink(dst)
        # Symlink the build folder to the parent
        docs = path('..') / '..' / "docs" / 'build' / 'html'
        docs_dest = path(__file__).dirname() / plugin_name / "docs"
        docs_link = docs_dest / 'html'
        if not docs_dest.exists():
            docs_dest.mkdir()
        if not docs_link.islink():
            docs.symlink(docs_link)


@task
def install(options):
    _install(".qgis2", options)

@task
def installdev(options):
    _install(".qgis-dev", options)

@task
def install3(options):
    _install(".qgis3", options)

@task
@cmdopts([
    ('tests', 't', 'Package tests with plugin')
])
def package(options):
    '''create package for plugin'''
    builddocs(options)
    package_file = options.plugin.package_dir / ('%s.zip' % options.plugin.name)
    with zipfile.ZipFile(package_file, "w", zipfile.ZIP_DEFLATED) as f:
        if not hasattr(options.package, 'tests'):
            options.plugin.excludes.extend(options.plugin.tests)
        make_zip(f, options)


def make_zip(zipFile, options):
    excludes = set(options.plugin.excludes)

    src_dir = options.plugin.source_dir
    exclude = lambda p: any([fnmatch.fnmatch(p, e) for e in excludes])
    def filter_excludes(files):
        if not files: return []
        # to prevent descending into dirs, modify the list in place
        for i in xrange(len(files) - 1, -1, -1):
            f = files[i]
            if exclude(f):
                files.remove(f)
        return files

    for root, dirs, files in os.walk(src_dir):
        for f in filter_excludes(files):
            relpath = os.path.relpath(root, '.')
            zipFile.write(path(root) / f, path(relpath) / f)
        filter_excludes(dirs)

    for root, dirs, files in os.walk(options.sphinx.builddir):
        for f in files:
            relpath = os.path.join(options.plugin.name, "docs", os.path.relpath(root, options.sphinx.builddir))
            zipFile.write(path(root) / f, path(relpath) / f)

def create_settings_docs(options):
    settings_file = path(options.plugin.name) / "settings.json"
    doc_file = options.sphinx.sourcedir / "settingsconf.rst"
    with open(settings_file) as f:
        settings = json.load(f)

    grouped = defaultdict(list)
    for setting in settings:
        grouped[setting["group"]].append(setting)
    with open(doc_file, "w") as f:
        f.write(".. _plugin_settings:\n\n"
                "Plugin settings\n===============\n\n"
                "The plugin can be adjusted using the following settings, "
                "to be found in its settings dialog (|path_to_settings|).\n")
        for groupName, group in grouped.iteritems():
            section_marks = "-" * len(groupName)
            f.write("\n%s\n%s\n\n"
                    ".. list-table::\n"
                    "   :header-rows: 1\n"
                    "   :stub-columns: 1\n"
                    "   :widths: 20 80\n"
                    "   :class: non-responsive\n\n"
                    "   * - Option\n"
                    "     - Description\n"
                    % (groupName, section_marks))
            for setting in group:
                f.write("   * - %s\n"
                        "     - %s\n"
                        % (setting["label"], setting["description"]))

@task
def builddocs(options):
    try: #this might fail if the plugin code is not in a git repo
        sh("git submodule init")
        sh("git submodule update")
    except:
        pass
    create_settings_docs(options)
    cwd = os.getcwd()
    os.chdir(options.sphinx.docroot)
    sh("make html")
    os.chdir(cwd)


@task
def install_devtools():
    """Install development tools"""
    try:
        import pip
    except:
        error('FATAL: Unable to import pip, please install it first!')
        sys.exit(1)

    pip.main(['install', '-r', 'requirements-dev.txt'])


@task
@consume_args
def pep8(args):
    """Check code for PEP8 violations"""
    try:
        import pep8
    except:
        error('pep8 not found! Run "paver install_devtools".')
        sys.exit(1)

    # Errors to ignore
    ext_libs_basename = os.path.basename(options.plugin.ext_libs)
    ext_src_basename = os.path.basename(options.plugin.ext_src)

    ignore = ['E203', 'E121', 'E122', 'E123', 'E124', 'E125', 'E126', 'E127',
        'E128', 'E402']
    styleguide = pep8.StyleGuide(ignore=ignore,
                                 exclude=['*/{}/*'.format(ext_libs_basename),
                                          '*/{}/*'.format(ext_src_basename)],
                                 repeat=True, max_line_length=79,
                                 parse_argv=args)
    styleguide.input_dir(options.plugin.source_dir)
    info('===== PEP8 SUMMARY =====')
    styleguide.options.report.print_statistics()


@task
@consume_args
def autopep8(args):
    """Format code according to PEP8
    """
    try:
        import autopep8
    except:
        error('autopep8 not found! Run "paver install_devtools".')
        sys.exit(1)

    if any(x not in args for x in ['-i', '--in-place']):
        args.append('-i')

    args.append('--ignore=E261,E265,E402,E501')
    args.insert(0, 'dummy')

    cmd_args = autopep8.parse_args(args)

    ext_libs_basename = os.path.basename(options.plugin.ext_libs)
    ext_src_basename = os.path.basename(options.plugin.ext_src)
    excludes = (ext_libs_basename, ext_src_basename)
    for p in options.plugin.source_dir.walk():
        if any(exclude in p for exclude in excludes):
            continue

        if p.fnmatch('*.py'):
            autopep8.fix_file(p, options=cmd_args)


@task
@consume_args
def pylint(args):
    """Check code for errors and coding standard violations"""
    try:
        from pylint import lint
    except:
        error('pylint not found! Run "paver install_devtools".')
        sys.exit(1)

    if 'rcfile' not in args:
        args.append('--rcfile=pylintrc')

    args.append(options.plugin.source_dir)
    lint.Run(args)
