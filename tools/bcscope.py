#!/usr/bin/env python
# -*- coding: utf-8 -*-

__VERSION__ = '1.2.3'
__author__ = 'rx.wen218@gmail.com'

import subprocess
import sys
import shutil
import os
from optparse import OptionParser

file_list_name = "cscope.files"
default_database_name = "cscope.out"
default_database_name_in = "cscope.in.out"
default_database_name_po = "cscope.po.out"
default_cfg_name = ".bcscope.cfg"

# parse command line options
opt_parser = OptionParser(version = "%prog " + __VERSION__, 
            description = "command line tool for generating cscope database",
            usage = "%prog [-o file] [file type: c++(default)/c#/python/java]")
opt_parser.add_option("-o", "--output", dest="output_file", default=default_database_name, 
        help="cscope database file")
opt_parser.add_option("-i", "--input", dest="input_file", default=default_cfg_name, 
        help="cfg file lists all directories to be included or exclued from search")
opt_parser.add_option("-r", "--recursive", action="store_true", default=False, 
        help="recursivly include input_file contained in all directories [default: %default]")
opt_parser.add_option("-v", "--verbose", action="store_true", default=False, 
        help="verbose output [default: %default]")
opt_parser.add_option("-a", "--absolute", action="store_true", default=False, 
        help="generate cscope database with absolute path [default: %default]")
opt_parser.add_option("-k", "--kernel", action="store_true", default=False, 
        help="Kernel Mode - don't use /usr/include for #include files. [default: %default]")
opt_parser.add_option("-q", "--quick", action="store_true", default=False, 
        help="Build an inverted index for quick symbol searching. [default: %default]")
opt_parser.add_option("-c", "--confirm", action="store_false", default=True, 
        help="confirm overwrite existing cscope database without interaction [default: %default]")
opt_parser.add_option("-p", "--preserve-filelist", action="store_true", default=False, 
        help="don't delete cscope.files after the database has been generated [default: %default]")
opt_parser.add_option("", "--include-dir", default=None, action="append",
        help="additional directories to be included in search, can be specified multiple times")
opt_parser.add_option("", "--exclude-dir", default=None, action="append",
        help="additional directories to be exclued from search, can be specified multiple times")
opt_parser.add_option("", "--exclude", default=None, action="append",
        help="file pattern (regular expression) to be excluded, can be specified multiple times")
opt_parser.add_option("-t", "--ctags", action="store_true", default=False, 
        help="generate ctags database as well [default: %default]")
(cmdline_options, args) = opt_parser.parse_args()

# config application behavior
valid_lan_types = {"c++": "cpp\|c\|cxx\|cc\|h\|hpp\|hxx",
    "java": "java",
    "c#": "cs",
    "python": "py"}
lan_type = ''
if len(args) == 0:
# no language specified, default to c++
    args = ['c++']

lan_pattern = ''
for arg in args:
    lan_type += arg + ' '
    if valid_lan_types.has_key(arg):
        if len(lan_pattern) > 0:
            lan_pattern += '\|'
        lan_pattern += valid_lan_types[arg]
    else:
        print "invalid language type: " + arg 
        print "must be one of:"
        for (k, v) in valid_lan_types.items():
            print "\t" + k
        sys.exit(-1)
lan_pattern = '.+\.\(' + lan_pattern + '\)$'

# take care of accidently overwrite existing database file
if not cmdline_options.confirm:
    confirm = 'n'
    if default_database_name != cmdline_options.output_file and os.path.isfile(default_database_name):
       confirm = raw_input(default_database_name + " already exists, overwrite it? (y/n)")
       if confirm != "y":
           sys.exit(0)
    if os.path.isfile(cmdline_options.output_file):
       confirm = raw_input(cmdline_options.output_file + " already exists, overwrite it? (y/n)")
       if confirm != "y":
           sys.exit(0)

file_list = open(file_list_name, "w")
# should we check more directories?
dirs = []
excluded_dirs = []

if cmdline_options.include_dir:
    dirs.extend(cmdline_options.include_dir)
if cmdline_options.exclude_dir:
    excluded_dirs.extend(cmdline_options.exclude_dir)

def convert_path(p):
    if cmdline_options.absolute:
        return os.path.abspath(p)
    else:
        return os.path.relpath(p)

def include_dirs_from_cfg(dir_path, cfg_name):
    cfg_file = os.path.join(dir_path, cfg_name)
    if os.path.isfile(cfg_file):
        if cmdline_options.verbose:
            print "read configuration file from " + cfg_file
        f = open(cfg_file)
        for line in f:
            line = line.strip() # remove possible \n char
            if len(line) > 0 and not line.startswith("#"):
                include = True
                if line.startswith("!"):
                    include = False
                    line = line[1:]

                line = os.path.expanduser(line)
                if not os.path.isabs(line):
                    # the line is relative to dir_path, join them so line is relative to current dir
                    line = os.path.join(dir_path, line)
                line = convert_path(line)
                if include:
                    search_dirs = dirs
                else:
                    search_dirs = excluded_dirs
                if os.path.isdir(line):
                    if search_dirs.count(line) == 0:
                        search_dirs.append(line)
                elif cmdline_options.verbose:
                    print line + " is not a directory, omit it"
        f.close()

include_dirs_from_cfg("./", cmdline_options.input_file)

# find source files in all directories
def find_files(d, pattern, file_list):
    import re
    source_files = []
    for (root, subdirs, files) in os.walk(d):
        for f in files:
            fpath = os.path.join(root, f)
            if re.match(pattern, fpath):
                # check if the file matches exclude_pattern
                should_exclude = False
                if cmdline_options.exclude:
                    for exclude_pattern in cmdline_options.exclude:
                        if re.match(exclude_pattern, fpath):
                            should_exclude = True
                            if cmdline_options.verbose:
                                print "exclude " + fpath
                            break
                if not should_exclude:
                    # get real path of symbolic link
                    # cscope can't deal with symbolic link
                    fpath = convert_path(os.path.realpath(fpath))
                    source_files.append(fpath + "\n")
        i = 0
        while i < len(subdirs):
            d = subdirs[i]
            fpath = convert_path(os.path.join(root, d))
            if excluded_dirs.count(fpath) > 0:
                subdirs.remove(d)
            else:
                i += 1
        
    file_list.writelines(source_files)

if cmdline_options.recursive:
# include cfg files in other directories
    for d in dirs:
        include_dirs_from_cfg(d, cmdline_options.input_file)

# make sure current directory is included
if dirs.count(".") + dirs.count("./") < 1:
    dirs.insert(0, ".")

j = 0
for d in dirs:
    dirs[j] = convert_path(d)
    j += 1

j = 0
for d in excluded_dirs:
    excluded_dirs[j] = convert_path(d)
    j += 1

for d in dirs:
    print "find " + lan_type + "source files in " + d
    # change lan_pattern so that it works on python
    lan_pattern = lan_pattern.replace("\(", "(").replace("\)", ")").replace("\|", "|")
    find_files(d, lan_pattern, file_list)
file_list.close()

# actually generate database
print "build cscope database"
cmd = ["cscope", "-b"]
if cmdline_options.quick:
    cmd.append("-q")
if cmdline_options.kernel:
    cmd.append("-k")
subprocess.Popen(cmd).wait()
if cmdline_options.output_file != default_database_name:
    shutil.move(default_database_name, cmdline_options.output_file)
    if os.path.isfile(default_database_name_in):
        shutil.move(default_database_name_in, cmdline_options.output_file+".in")
    if os.path.isfile(default_database_name_po):
        shutil.move(default_database_name_po, cmdline_options.output_file+".po")
print "done, cscope database saved in " + cmdline_options.output_file
if cmdline_options.ctags:
    print "build ctags database"
    cmd = ["ctags", "-L", file_list_name]
    subprocess.Popen(cmd).wait()
    print "done, ctags database saved in tags"
if not cmdline_options.preserve_filelist:
    os.remove(file_list_name)

