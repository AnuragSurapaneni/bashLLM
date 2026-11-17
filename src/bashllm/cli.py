"""Command-line entry point for bashllm."""

import argparse
import importlib
import pkgutil

from . import commands


def main() -> int:
    parser = argparse.ArgumentParser(prog="bashllm")
    subparsers = parser.add_subparsers(dest="action", required=True)
    for module_info in pkgutil.iter_modules(commands.__path__):
        module = importlib.import_module(f"{commands.__name__}.{module_info.name}")
        register = getattr(module, "register", None)
        if register is not None:
            register(subparsers)
    args = parser.parse_args()
    return args.execute(args, parser)


if __name__ == "__main__":
    raise SystemExit(main())
