# https://peps.python.org/pep-0722/ – Dependency specification for single-file scripts
# https://peps.python.org/pep-0508/ – Dependency specification for Python Software Packages

# https://setuptools.pypa.io/en/latest/userguide/ext_modules.html

import sys
import os
from pathlib import Path

import re
import tomllib

import json

import importlib
import installer
import pyparsing
from packaging.requirements import Requirement

from aio.filelike import fopen


class Config:
    READ_722 = False
    READ_723 = True
    BLOCK_RE_722 = r"(?i)^#\s+script\s+dependencies:\s*$"
    BLOCK_RE_723 = r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
    PKG_INDEXES = []
    REPO_INDEX = "index.json"
    REPO_DATA = "repodata.json"
    repos = []
    pkg_repolist = []
    dev_mode = ".-X.dev." in ".".join(sys.orig_argv)


def read_dependency_block_722(code):
    # Skip lines until we reach a dependency block (OR EOF).
    has_block = False
    # Read dependency lines until we hit a line that doesn't
    # start with #, or we are at EOF.
    for line in code.split("\n"):
        if not has_block:
            if re.match(Config.BLOCK_RE_722, line):
                has_block = True
            continue

        if not line.startswith("#"):
            break
        # Remove comments. An inline comment is introduced by
        # a hash, which must be preceded and followed by a
        # space.
        line = line[1:].split(" # ", maxsplit=1)[0]
        line = line.strip()
        # Ignore empty lines
        if not line:
            continue
        # Try to convert to a requirement. This will raise
        # an error if the line is not a PEP 508 requirement
        yield Requirement(line)


def read_dependency_block_723(code):
    # Skip lines until we reach a dependency block (OR EOF).
    has_block = False

    content = []
    for line in code.split("\n"):
        if not has_block:
            if line.strip() == "# /// pyproject":
                has_block = True
            continue

        if not line.startswith("#"):
            break

        if line.strip() == "# ///":
            break

        content.append(line[2:])
    struct = tomllib.loads("\n".join(content))

    print(json.dumps(struct, sort_keys=True, indent=4))

    project = struct.get("project", {"dependencies": []})
    for dep in project.get("dependencies", []):
        yield dep


def read_dependency_block_723x(script):
    name = "pyproject"
    matches = list(filter(lambda m: m.group("type") == name, re.finditer(Config.BLOCK_RE_723, script)))
    if len(matches) > 1:
        raise ValueError(f"Multiple {name} blocks found")
    elif len(matches) == 1:
        print(tomllib.loads(matches[0]))
        yield "none"
    else:
        return None


HISTORY = []


def install(pkg_file, sconf=None):
    global HISTORY
    from installer import install
    from installer.destinations import SchemeDictionaryDestination
    from installer.sources import WheelFile

    # Handler for installation directories and writing into them.
    destination = SchemeDictionaryDestination(
        sconf or __import_("sysconfig").get_paths(),
        interpreter=sys.executable,
        script_kind="posix",
    )

    try:
        with WheelFile.open(pkg_file) as source:
            install(
                source=source,
                destination=destination,
                # Additional metadata that is generated by the installation tool.
                additional_metadata={
                    "INSTALLER": b"pygbag",
                },
            )
            HISTORY.append(pkg_file)
    except FileExistsError as ex:
        print(f"38: {pkg_file} already installed (or partially)", ex)
    except Exception as ex:
        pdb(f"82: cannot install {pkg_file}")
        sys.print_exception(ex)


async def async_imports_init():
    for cdn in Config.PKG_INDEXES:
        print("init cdn :", Config.PKG_INDEXES)
        async with fopen(Path(cdn) / Config.REPO_DATA) as source:
            Config.repos.append(json.loads(source.read()))

        pdb("referenced packages :", len(Config.repos[-1]["packages"]))


async def async_repos():
    abitag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    for repo in Config.PKG_INDEXES:
        async with fopen(f"{repo}index.json", "r") as index:
            try:
                data = index.read()
                if isinstance(data, bytes):
                    data = data.decode()
                data = data.replace("<abi>", abitag)
                repo = json.loads(data)
            except:
                pdb(f"110: {repo=}: malformed json index {data}")
                continue
            if repo not in Config.pkg_repolist:
                Config.pkg_repolist.append(repo)

    if not aio.cross.simulator:
        if window.location.href.startswith("https://pmp-p.ddns.net/pygbag"):
            print(" ===============  REDIRECTION TO DEV HOST  ================ ")
            for idx, repo in enumerate(PyConfig.pkg_repolist):
                repo["-CDN-"] = "https://pmp-p.ddns.net/archives/repo/"

    if Config.dev_mode > 0:
        for idx, repo in enumerate(Config.pkg_repolist):
            try:
                print("120:", repo["-CDN-"], idx, "REMAPPED TO", Config.PKG_INDEXES[idx])
                repo["-CDN-"] = Config.PKG_INDEXES[idx]
            except Exception as e:
                sys.print_exception(e)


async def install_pkg(sysconf, wheel_url, wheel_pkg):
    target_filename = f"/tmp/{wheel_pkg}"
    async with fopen(wheel_url, "rb") as pkg:
        with open(target_filename, "wb") as target:
            target.write(pkg.read())
    install(target_filename, sysconf)


async def pip_install(pkg, sconf={}):
    print("searching", pkg)
    if not sconf:
        sconf = __import__("sysconfig").get_paths()

    wheel_url = ""
    try:
        async with fopen(f"https://pypi.org/simple/{pkg}/") as html:
            if html:
                for line in html.readlines():
                    if line.find("href=") > 0:
                        if line.find("-py3-none-any.whl") > 0:
                            wheel_url = line.split('"', 2)[1]
            else:
                print("270: ERROR: cannot find package :", pkg)
    except FileNotFoundError:
        print("190: ERROR: cannot find package :", pkg)
        return

    except:
        print("194: ERROR: cannot find package :", pkg)
        return

    try:
        wheel_pkg, wheel_hash = wheel_url.rsplit("/", 1)[-1].split("#", 1)
        await install_pkg(sconf, wheel_url, wheel_pkg)
    except:
        print("INVALID", pkg, "from", wheel_url)


async def parse_code(code, env):
    maybe_missing = []

    if Config.READ_722:
        for req in read_dependency_block_722(code):
            pkg = str(req)
            if (env / pkg).is_dir():
                print("found in env :", pkg)
                continue
            elif pkg not in maybe_missing:
                # do not change case ( eg PIL )
                maybe_missing.append(pkg)

    if Config.READ_723:
        for req in read_dependency_block_723(code):
            pkg = str(req)
            if (env / pkg).is_dir():
                print("found in env :", pkg)
                continue
            elif pkg not in maybe_missing:
                # do not change case ( eg PIL )
                maybe_missing.append(pkg)

    still_missing = []

    for dep in maybe_missing:
        if not importlib.util.find_spec(dep) and dep not in still_missing:
            still_missing.append(dep.lower())
        else:
            print("found in path :", dep)

    return still_missing


async def check_list(code=None, filename=None):
    print()
    print("-" * 11, "computing required packages", "-" * 10)

    # store installed wheel somewhere
    env = Path(os.getcwd()) / "build" / "env"
    env.mkdir(parents=True, exist_ok=True)

    # we want host to load wasm packages too
    # so make pure/bin folder first for imports
    sys.path.insert(0, env.as_posix())

    sconf = __import__("sysconfig").get_paths()
    sconf["purelib"] = sconf["platlib"] = env.as_posix()

    # mandatory
    importlib.invalidate_caches()

    if code is None:
        code = open(filename, "r").read()

    still_missing = await parse_code(code, env)

    # nothing to do
    if not len(still_missing):
        return

    importlib.invalidate_caches()

    # only do that once and for all.
    if not len(Config.repos):
        await async_imports_init()
        await async_repos()

    # TODO: check for possible upgrade of env/* pkg

    maybe_missing = still_missing
    still_missing = []

    for pkg in maybe_missing:
        hit = ""
        for repo in Config.pkg_repolist:
            wheel_pkg = repo.get(pkg, "")
            if wheel_pkg:
                wheel_url = repo["-CDN-"] + "/" + wheel_pkg
                wheel_pkg = wheel_url.rsplit("/", 1)[-1]
                await install_pkg(sconf, wheel_url, wheel_pkg)
                hit = pkg

        if len(hit):
            print("found on pygbag repo and installed to env :", hit)
        else:
            still_missing.append(pkg)

    for pkg in still_missing:
        if (env / pkg).is_dir():
            print("found in env :", pkg)
            continue
        await pip_install(pkg)

    print("-" * 40)
    print()