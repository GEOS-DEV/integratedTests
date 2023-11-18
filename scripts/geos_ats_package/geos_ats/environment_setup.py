import os
import sys
import stat
import argparse


def setup_ats(src_path, build_path, ats_xargs, ats_machine, ats_machine_dir):
    bin_dir = os.path.join(build_path, "bin")
    geos_ats_fname = os.path.join(bin_dir, "run_geos_ats")
    ats_dir = os.path.abspath(os.path.join(src_path, "integratedTests", "tests", "allTests"))
    test_path = os.path.join(build_path, "integratedTests")
    link_path = os.path.join(test_path, "integratedTests")
    run_script_fname = os.path.join(test_path, "geos_ats.sh")
    log_dir = os.path.join(test_path, "TestResults")

    # Create a symbolic link to test directory
    if os.path.islink(link_path):
        print('integratedTests symlink already exists')
    else:
        os.symlink(ats_dir, link_path)

    # Build extra arguments that should be passed to ATS
    joined_args = [' '.join(x) for x in ats_xargs]
    ats_args = ' '.join([f'--ats {x}' for x in joined_args])
    if ats_machine:
        ats_args += f' --machine {ats_machine}'
    if ats_machine_dir:
        ats_args += f' --machine-dir {ats_machine_dir}'

    # Write the bash script to run ats.
    with open(run_script_fname, "w") as g:
        g.write("#!/bin/bash\n")
        g.write(f"{geos_ats_fname} {bin_dir} --workingDir {ats_dir} --logs {log_dir} {ats_args} \"$@\"\n")

    # Make the script executable
    st = os.stat(run_script_fname)
    os.chmod(run_script_fname, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main():
    # Cmake may combine the final arguments into a string literal
    # Manually unpack those before parsing
    final_arg = sys.argv.pop(-1)
    sys.argv.extend(final_arg.split())

    parser = argparse.ArgumentParser(description="Setup ATS script")
    parser.add_argument("src_path", type=str, help="GEOS src path")
    parser.add_argument("build_path", type=str, help="GEOS build path")
    parser.add_argument("--ats", nargs='+', default=[], action="append", help="Arguments that should be passed to ats")
    parser.add_argument("--machine", type=str, default='', help="ATS machine name")
    parser.add_argument("--machine-dir", type=str, default='', help="ATS machine directory")
    options, unkown_args = parser.parse_known_args()
    setup_ats(options.src_path, options.build_path, options.ats, options.machine, options.machine_dir)


if __name__ == '__main__':
    main()
