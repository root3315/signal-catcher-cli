#!/usr/bin/env python3
"""
signal-catcher-cli: Catch and handle Unix signals in your applications.

This CLI tool allows you to register signal handlers and execute custom
commands when specific signals are received.
"""

import argparse
import signal
import sys
import os
import time
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable

DEFAULT_CONFIG_DIR = Path.home() / ".signal-catcher"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_COMMAND_TIMEOUT = 30

SIGNAL_MAP = {
    "SIGHUP": signal.SIGHUP,
    "SIGINT": signal.SIGINT,
    "SIGQUIT": signal.SIGQUIT,
    "SIGILL": signal.SIGILL,
    "SIGTRAP": signal.SIGTRAP,
    "SIGABRT": signal.SIGABRT,
    "SIGBUS": signal.SIGBUS,
    "SIGFPE": signal.SIGFPE,
    "SIGKILL": signal.SIGKILL,
    "SIGUSR1": signal.SIGUSR1,
    "SIGSEGV": signal.SIGSEGV,
    "SIGUSR2": signal.SIGUSR2,
    "SIGPIPE": signal.SIGPIPE,
    "SIGALRM": signal.SIGALRM,
    "SIGTERM": signal.SIGTERM,
    "SIGCHLD": signal.SIGCHLD,
    "SIGCONT": signal.SIGCONT,
    "SIGSTOP": signal.SIGSTOP,
    "SIGTSTP": signal.SIGTSTP,
    "SIGTTIN": signal.SIGTTIN,
    "SIGTTOU": signal.SIGTTOU,
    "SIGURG": signal.SIGURG,
    "SIGXCPU": signal.SIGXCPU,
    "SIGXFSZ": signal.SIGXFSZ,
    "SIGVTALRM": signal.SIGVTALRM,
    "SIGPROF": signal.SIGPROF,
    "SIGWINCH": signal.SIGWINCH,
    "SIGIO": signal.SIGIO,
    "SIGSYS": signal.SIGSYS,
}

class SignalCatcher:
    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or DEFAULT_CONFIG_FILE
        self.handlers: Dict[int, List[str]] = {}
        self.signal_history: List[Dict] = []
        self.running = True
        self.verbose = False
        self.log_file: Optional[Path] = None
        self.command_timeout: int = DEFAULT_COMMAND_TIMEOUT

    def load_config(self) -> bool:
        if not self.config_file.exists():
            return False
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
            self.handlers = {int(k): v for k, v in config.get("handlers", {}).items()}
            log_path = config.get("log_file")
            if log_path:
                self.log_file = Path(log_path)
            self.verbose = config.get("verbose", False)
            self.command_timeout = config.get("command_timeout", DEFAULT_COMMAND_TIMEOUT)
            return True
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            return False

    def save_config(self) -> bool:
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            config = {
                "handlers": {str(k): v for k, v in self.handlers.items()},
                "log_file": str(self.log_file) if self.log_file else None,
                "verbose": self.verbose,
                "command_timeout": self.command_timeout,
            }
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving config: {e}", file=sys.stderr)
            return False

    def log_signal(self, signum: int, command: str) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "signal": signum,
            "signal_name": self.get_signal_name(signum),
            "command": command,
        }
        self.signal_history.append(entry)
        if self.log_file:
            try:
                with open(self.log_file, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except IOError:
                pass

    def get_signal_name(self, signum: int) -> str:
        for name, num in SIGNAL_MAP.items():
            if num == signum:
                return name
        return f"SIG{signum}"

    def get_signal_number(self, name: str) -> Optional[int]:
        name_upper = name.upper()
        if not name_upper.startswith("SIG"):
            name_upper = "SIG" + name_upper
        return SIGNAL_MAP.get(name_upper)

    def register_handler(self, signum: int, command: str) -> None:
        if signum not in self.handlers:
            self.handlers[signum] = []
        if command not in self.handlers[signum]:
            self.handlers[signum].append(command)

    def unregister_handler(self, signum: int, command: Optional[str] = None) -> bool:
        if signum not in self.handlers:
            return False
        if command is None:
            del self.handlers[signum]
            return True
        if command in self.handlers[signum]:
            self.handlers[signum].remove(command)
            if not self.handlers[signum]:
                del self.handlers[signum]
            return True
        return False

    def handle_signal(self, signum: int, frame) -> None:
        signal_name = self.get_signal_name(signum)
        if self.verbose:
            print(f"\n[signal-catcher] Received {signal_name}", file=sys.stderr)
        if signum in self.handlers:
            for command in self.handlers[signum]:
                self.log_signal(signum, command)
                if self.verbose:
                    print(f"[signal-catcher] Executing: {command}", file=sys.stderr)
                try:
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=self.command_timeout,
                    )
                    if self.verbose and result.stdout:
                        print(result.stdout, file=sys.stderr)
                    if result.returncode != 0 and result.stderr:
                        print(f"Command failed: {result.stderr}", file=sys.stderr)
                except subprocess.TimeoutExpired:
                    print(f"Command timed out: {command}", file=sys.stderr)
                except Exception as e:
                    print(f"Error executing command: {e}", file=sys.stderr)
        if signum == signal.SIGINT:
            self.running = False

    def setup_handlers(self) -> None:
        for signum in self.handlers.keys():
            try:
                signal.signal(signum, self.handle_signal)
            except (ValueError, OSError) as e:
                print(f"Cannot set handler for {self.get_signal_name(signum)}: {e}", file=sys.stderr)

    def run(self, duration: Optional[int] = None) -> None:
        self.setup_handlers()
        self.running = True
        start_time = time.time()
        if self.verbose:
            print("[signal-catcher] Listening for signals...", file=sys.stderr)
            print(f"[signal-catcher] Registered handlers: {len(self.handlers)}", file=sys.stderr)
        try:
            while self.running:
                if duration and (time.time() - start_time) > duration:
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        if self.verbose:
            print("\n[signal-catcher] Shutting down...", file=sys.stderr)

    def list_handlers(self) -> None:
        if not self.handlers:
            print("No signal handlers registered.")
            return
        print("Registered signal handlers:")
        print("-" * 50)
        for signum, commands in sorted(self.handlers.items()):
            signal_name = self.get_signal_name(signum)
            print(f"{signal_name} ({signum}):")
            for cmd in commands:
                print(f"  -> {cmd}")


def main():
    parser = argparse.ArgumentParser(
        description="Catch and handle Unix signals in your applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s register SIGTERM "echo 'Received TERM'"
  %(prog)s register SIGUSR1 "/path/to/script.sh"
  %(prog)s listen --duration 60
  %(prog)s listen --timeout 60
  %(prog)s list
  %(prog)s remove SIGTERM
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    register_parser = subparsers.add_parser("register", help="Register a signal handler")
    register_parser.add_argument("signal", help="Signal name (e.g., SIGTERM, SIGUSR1)")
    register_parser.add_argument("command", help="Command to execute when signal is received")
    register_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    remove_parser = subparsers.add_parser("remove", help="Remove a signal handler")
    remove_parser.add_argument("signal", help="Signal name")
    remove_parser.add_argument("command", nargs="?", help="Specific command to remove")

    listen_parser = subparsers.add_parser("listen", help="Start listening for signals")
    listen_parser.add_argument("-d", "--duration", type=int, help="Duration in seconds")
    listen_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    listen_parser.add_argument("-l", "--log-file", type=Path, help="Log file path")
    listen_parser.add_argument("-t", "--timeout", type=int, help="Command timeout in seconds")

    list_parser = subparsers.add_parser("list", help="List registered handlers")

    config_parser = subparsers.add_parser("config", help="Show config file path")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    catcher = SignalCatcher()
    catcher.load_config()

    if args.command == "register":
        signum = catcher.get_signal_number(args.signal)
        if signum is None:
            print(f"Unknown signal: {args.signal}", file=sys.stderr)
            sys.exit(1)
        catcher.register_handler(signum, args.command)
        catcher.save_config()
        print(f"Registered handler for {args.signal}: {args.command}")

    elif args.command == "remove":
        signum = catcher.get_signal_number(args.signal)
        if signum is None:
            print(f"Unknown signal: {args.signal}", file=sys.stderr)
            sys.exit(1)
        if catcher.unregister_handler(signum, args.command):
            catcher.save_config()
            if args.command:
                print(f"Removed handler: {args.command}")
            else:
                print(f"Removed all handlers for {args.signal}")
        else:
            print("Handler not found", file=sys.stderr)
            sys.exit(1)

    elif args.command == "listen":
        if hasattr(args, "verbose") and args.verbose:
            catcher.verbose = True
        if hasattr(args, "log_file") and args.log_file:
            catcher.log_file = args.log_file
        if hasattr(args, "timeout") and args.timeout is not None:
            catcher.command_timeout = args.timeout
        catcher.run(duration=args.duration)

    elif args.command == "list":
        catcher.list_handlers()

    elif args.command == "config":
        print(f"Config file: {catcher.config_file}")


if __name__ == "__main__":
    main()
