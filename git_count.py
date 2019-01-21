#!/usr/bin/python
from __future__ import division

import os
import sys

import pathspec
from git import Repo


def ignored(spec, file_path):
    if spec is not None:
        return spec.match_file(file_path)
    else:
        return True


def list_recursive(spec, path):
    result = []
    for root, dirs, files in os.walk(path, topdown=False):
        for item in [os.path.join(root, f) for f in files]:
            if not ignored(spec, item):
                result.append(item)
    #       for dir in [os.path.join(root,d) for d in dirs]:
    #            subFiles = list_recursive(dir)
    #            result.extend(subFiles)
    return result


def effective(path, lines):
    # first filter : empty lines
    result = [a_line for a_line in lines if len(a_line.strip()) > 0]
    return result


def file_in_repo(git_repository, path_to_file):
    # repo is a gitPython Repo object
    # path_to_file is the full path to the file from the repository root
    # returns true if file is found in the repo at the specified path, false otherwise
    path_directory = os.path.dirname(path_to_file)

    # Build up reference to desired repo path
    rsub = git_repository.head.commit.tree
    try:
        for path_element in path_directory.split(os.path.sep):
            rsub = rsub[path_element]
        return path_to_file in rsub
    except KeyError:
        return False


def load_files(repo):
    repo.common_dir
    lines = ['.git']
    for line in open('.gitignore', 'r'):
        lines.append(line.strip())

    spec = pathspec.PathSpec.from_lines('gitignore', lines)
    files = list_recursive(spec, ".")
    files = [a_file for a_file in files if file_in_repo(repo, a_file[2:])]
    return files


def load_repo(repository_path):
    repo = Repo(repository_path)
    assert not repo.bare
    return repo


def update_author_statistics(author, lines, category, categories, filepath, statistics):
    if author not in statistics:
        statistics[author] = {'total': {'lines': {'count': 0}, 'effective_lines': {'count': 0}}}
        for temp_category in get_all_categories(categories):
            statistics[author][temp_category] = {'lines': {'count': 0}, 'effective_lines': {'count': 0}}

    statistics[author][category]['lines']['count'] += len(lines)
    statistics[author]['total']['lines']['count'] += len(lines)
    statistics[author][category]['effective_lines']['count'] += len(effective(filepath, lines))
    statistics[author]['total']['effective_lines']['count'] += len(effective(filepath, lines))


def update_statistics(commit, lines, filepath, category, categories, statistics):
    author = commit.author.email
    update_author_statistics(author, lines, category, categories, filepath, statistics)
    update_author_statistics('total', lines, category, categories, filepath, statistics)


def get_all_categories(categories):
    all_categories = []
    all_categories.append('total')
    all_categories.append('others')
    all_categories.extend(categories)
    return all_categories


def update_author_percentages(author, categories, statistics):
    all_categories = get_all_categories(categories)
    for category in all_categories:
        if statistics['total'][category]['lines']['count'] > 0:
            statistics[author][category]['lines']['percentage'] = \
                100 * statistics[author][category]['lines']['count'] // \
                statistics['total'][category]['lines']['count']
            statistics[author][category]['effective_lines']['percentage'] = \
                100 * statistics[author][category]['effective_lines']['count'] // \
                statistics['total'][category]['effective_lines']['count']
        else:
            statistics[author][category]['lines']['percentage'] = 0
            statistics[author][category]['effective_lines']['percentage'] = 0


def print_headers(categories):
    sys.stdout.write("%35s |" % 'author')
    for category in get_all_categories(categories):
        sys.stdout.write('%5s%15s%5s|' % ('', category, ''))
    sys.stdout.write('\n')
    sys.stdout.write("%35s |" % '')
    for category in get_all_categories(categories):
        sys.stdout.write('%5s %6s %5s %6s|' % ('tot.', '(%)', 'eff.', '(%)'))
    sys.stdout.write('\n')


def print_statistics(author, stats, categories):
    sys.stdout.write("%35s |" % author)
    for category in get_all_categories(categories):
        if category in stats:
            sys.stdout.write('%5s (%3s%%) %5s (%3s%%)|' % (stats[category]['lines']['count'],
                                                           stats[category]['lines']['percentage'],
                                                           stats[category]['effective_lines']['count'],
                                                           stats[category]['effective_lines']['percentage']))
        else:
            sys.stdout.write('%5s (%3s%%) %5s (%3s%%)|' % ('0', '0', '0', '0'))
    sys.stdout.write('\n')


def get_category(categories, extension):
    current_category = 'others'
    for category in categories:
        if extension in categories[category]:
            current_category = category
    if current_category == 'others':
        print("others include extension %s " % extension)
    return current_category


def get_effective_categories(statistics, categories):
    effective_categories = []
    for category in categories:
        effective_cat = False
        for author in statistics:
            if category in statistics[author] and statistics[author][category]['lines']['count'] > 0:
                effective_cat = True
        if effective_cat:
            effective_categories.append(category)
    return effective_categories


def main(repository_path):
    print("analysing %s" % repository_path)

    repo = load_repo(repository_path)

    os.chdir(repository_path)

    files = load_files(repo)

    categories = {'java': ['java'],
                  'build': ['xml', 'gradle', 'sbt', 'babelrc', 'eslintrc', 'editorconfig'],
                  'python': ['py'],
                  'shell': ['sh', 'bash'],
                  'ops': ['tf', 'cfg', 'Dockerfile', 'j2', 'helmignore', 'tpl', 'lock'],
                  'scala': ['scala'],
                  'lua': ['lua'],
                  'conf': ['yaml', 'yml', 'conf', 'properties', 'env', 'template'],
                  'doc': ['adoc', 'md', 'txt', 'puml'],
                  'javascript': ['js', 'ts', 'jsx', 'tsx', 'json'],
                  'assets': ['html', 'png', 'jpg', 'jpeg', 'svg', 'scss', 'ejs', 'ico'],
                  'load-tests': ['jmx', 'csv']}

    statistics = {}

    for filepath in files:
        extension = os.path.basename(filepath).split('.')[-1]
        category = get_category(categories, extension)
        for commit, lines in repo.blame('HEAD', filepath):
            update_statistics(commit, lines, filepath, category, categories, statistics)

    for author in statistics:
        update_author_percentages(author, categories, statistics)

    print("%40s: %7d" % ('total_files', len(files)))
    print('')
    effective_categories = get_effective_categories(statistics, categories)
    print_headers(effective_categories)
    for author in statistics:
        if author is not 'total':
            stats = statistics[author]
            print_statistics(author, stats, effective_categories)
    print_statistics('total', statistics['total'], effective_categories)


if __name__ == '__main__':
    root_path = '.'
    if len(sys.argv) == 2:
        root_path = sys.argv[1]
    main(root_path)
