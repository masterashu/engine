#!/bin/env python
#
# Code formatting presubmit
#
# This presubmit script ensures that code under the src/flutter directory is
# formatted according to the Flutter engine style requirements. On failure, a
# diff is emitted that can be applied from within the src/flutter directory
# via:
#
# patch -p0 < diff.patch

# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring

from subprocess import run
import os
import sys

print("Checking formatting...")

GOOGLE_JAVA_FORMAT = (
    "../third_party/android_tools/google-java-format/"
    "google-java-format-1.7-all-deps.jar"
)

CLANG_FILETYPES = "*.c *.cc *.cpp *.h *.m *.mm"

DIFF_OPTS = "-U0 --no-color --name-only"


def get_os_name():
    uname = os.popen("uname -s").read().rstrip()
    if uname == "Darwin":
        return "mac-x64"
    if uname == "Linux":
        return "linux-x86"
    print("Unknown operating system.")
    sys.exit(-1)


def get_merge_base_sha(upstream):
    res = run(
        f"$(git fetch {upstream} master > /dev/null 2>&1 && \
        (git merge-base --fork-point FETCH_HEAD HEAD || git merge-base FETCH_HEAD HEAD))",
        capture_output=True,
        check=False,
        shell=True,
    )

    if res.returncode != 0:
        sys.exit(res.returncode)

    return res.stdout.decode().rstrip()


def get_clang_files_to_check():
    res = run(
        f"git ls-files {CLANG_FILETYPES}", shell=True, check=False, capture_output=True
    )

    if res.returncode != 0:
        sys.exit(res.returncode)

    return res.stdout.decode().rstrip().split("\n")


def get_java_files_to_check(base_sha):
    java_filetypes = "*.java"
    return (
        run(
            f"git diff {DIFF_OPTS} {base_sha} -- {java_filetypes}",
            capture_output=True,
            check=False,
            shell=True,
        )
        .stdout.decode()
        .rstrip()
        .split("\n")
    )


def get_clang_file_diff(clang_format, file):
    return (
        run(f'diff -u "{file}" <("{clang_format}" --style=file "{file}")', check=False,)
        .stdout.decode()
        .rstrip()
    )


def get_java_file_diff(file):
    return (
        run(
            f'diff -u "{file}" <(java -jar "{GOOGLE_JAVA_FORMAT}" "{file}")',
            check=False,
        )
        .stdout.decode()
        .rstrip()
    )


def trailing_spaces_in_dart_files(base_sha):
    filetypes = "*.dart"
    return (
        run(
            f"git diff {DIFF_OPTS} {base_sha}..HEAD -- {filetypes} | xargs grep --line-number --with-filename '[[:blank:]]\+$'",
            check=False,
        )
        .stdout.decode()
        .rstrip()
    )


if __name__ == "__main__":
    OS = get_os_name()

    # Tools
    CLANG_FORMAT = f"../buildtools/{OS}/clang/bin/clang-format"
    os.system(f"{CLANG_FORMAT} --version")

    # Compute the diffs.

    if os.system("git remote get-url upstream >/dev/null 2>&1") == 0:
        UPSTREAM = "upstream"
    else:
        UPSTREAM = "origin"

    BASE_SHA = get_merge_base_sha(UPSTREAM)

    CLANG_FILES_TO_CHECK = get_clang_files_to_check()

    FAILED_CHECKS = 0
    for f in CLANG_FILES_TO_CHECK:
        CURR_DIF = get_clang_file_diff(CLANG_FORMAT, f)
        if CURR_DIF != "":
            print(CURR_DIF)
            FAILED_CHECKS += 1

    if os.path.exists(GOOGLE_JAVA_FORMAT) and os.path.exists(os.popen("which java")):
        os.system(f'java -jar "{GOOGLE_JAVA_FORMAT}" --version 2&>1')
        JAVA_FILES_TO_CHECK = get_java_files_to_check(BASE_SHA)

        for f in JAVA_FILES_TO_CHECK:
            CURR_DIF = get_java_file_diff(f)
            if CURR_DIF != "":
                print(CURR_DIF)
                FAILED_CHECKS += 1

    else:
        print("WARNING: Cannot find google-java-format, skipping Java file formatting!")

    if FAILED_CHECKS != 0:
        print(
            "ERROR: Some files are formatted incorrectly. "
            "To fix, run `./ci/format.sh | patch -p0` from the "
            "flutter/engine/src/flutter directory."
        )
        sys.exit(1)

    if trailing_spaces_in_dart_files(BASE_SHA) == "":
        print(trailing_spaces_in_dart_files(BASE_SHA))
        print()
        print(
            "ERROR: Some files have trailing spaces. To fix, try something like"
            " `find . -name \"*.dart\" -exec sed -i -e 's/\\s\\+$//' {} ;`."
        )
        sys.exit(1)

    os.system(
        './ci/check_gn_format.py --dry-run --root-directory . --gn-binary "third_party/gn/gn"'
    )

