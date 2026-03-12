#!/usr/bin/env python3
"""Unit tests for the SignalCatcher class."""

import io
import json
import os
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from signal_catcher import SignalCatcher, SIGNAL_MAP


class TestSignalCatcherInit(unittest.TestCase):
    def test_init_default_config(self):
        catcher = SignalCatcher()
        self.assertEqual(catcher.config_file, Path.home() / ".signal-catcher" / "config.json")
        self.assertEqual(catcher.handlers, {})
        self.assertEqual(catcher.signal_history, [])
        self.assertTrue(catcher.running)
        self.assertFalse(catcher.verbose)
        self.assertIsNone(catcher.log_file)

    def test_init_custom_config(self):
        custom_path = Path("/tmp/custom_config.json")
        catcher = SignalCatcher(config_file=custom_path)
        self.assertEqual(catcher.config_file, custom_path)


class TestSignalCatcherConfig(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_config_nonexistent(self):
        catcher = SignalCatcher(config_file=Path("/nonexistent/config.json"))
        result = catcher.load_config()
        self.assertFalse(result)

    def test_load_config_valid(self):
        config_data = {
            "handlers": {"15": ["echo test"]},
            "log_file": "/tmp/signals.log",
            "verbose": True,
        }
        with open(self.config_file, "w") as f:
            json.dump(config_data, f)

        catcher = SignalCatcher(config_file=self.config_file)
        result = catcher.load_config()

        self.assertTrue(result)
        self.assertEqual(catcher.handlers, {15: ["echo test"]})
        self.assertEqual(catcher.log_file, Path("/tmp/signals.log"))
        self.assertTrue(catcher.verbose)

    def test_load_config_invalid_json(self):
        with open(self.config_file, "w") as f:
            f.write("not valid json")

        catcher = SignalCatcher(config_file=self.config_file)
        result = catcher.load_config()

        self.assertFalse(result)

    def test_save_config(self):
        catcher = SignalCatcher(config_file=self.config_file)
        catcher.handlers = {signal.SIGTERM: ["echo test"]}
        catcher.log_file = Path("/tmp/test.log")
        catcher.verbose = True

        result = catcher.save_config()
        self.assertTrue(result)
        self.assertTrue(self.config_file.exists())

        with open(self.config_file, "r") as f:
            saved_config = json.load(f)

        self.assertEqual(
            saved_config["handlers"],
            {str(signal.SIGTERM): ["echo test"]},
        )
        self.assertEqual(saved_config["log_file"], "/tmp/test.log")
        self.assertTrue(saved_config["verbose"])

    def test_save_config_io_error(self):
        invalid_path = Path("/proc/nonexistent/config.json")
        catcher = SignalCatcher(config_file=invalid_path)
        result = catcher.save_config()
        self.assertFalse(result)


class TestSignalCatcherSignalHelpers(unittest.TestCase):
    def test_get_signal_name_known(self):
        catcher = SignalCatcher()
        self.assertEqual(catcher.get_signal_name(signal.SIGTERM), "SIGTERM")
        self.assertEqual(catcher.get_signal_name(signal.SIGINT), "SIGINT")
        self.assertEqual(catcher.get_signal_name(signal.SIGUSR1), "SIGUSR1")

    def test_get_signal_name_unknown(self):
        catcher = SignalCatcher()
        self.assertEqual(catcher.get_signal_name(999), "SIG999")

    def test_get_signal_number_known(self):
        catcher = SignalCatcher()
        self.assertEqual(catcher.get_signal_number("SIGTERM"), signal.SIGTERM)
        self.assertEqual(catcher.get_signal_number("SIGINT"), signal.SIGINT)
        self.assertEqual(catcher.get_signal_number("SIGUSR1"), signal.SIGUSR1)

    def test_get_signal_number_without_sig_prefix(self):
        catcher = SignalCatcher()
        self.assertEqual(catcher.get_signal_number("TERM"), signal.SIGTERM)
        self.assertEqual(catcher.get_signal_number("INT"), signal.SIGINT)

    def test_get_signal_number_case_insensitive(self):
        catcher = SignalCatcher()
        self.assertEqual(catcher.get_signal_number("sigterm"), signal.SIGTERM)
        self.assertEqual(catcher.get_signal_number("SigInt"), signal.SIGINT)

    def test_get_signal_number_unknown(self):
        catcher = SignalCatcher()
        self.assertIsNone(catcher.get_signal_number("SIGUNKNOWN"))


class TestSignalCatcherHandlers(unittest.TestCase):
    def test_register_handler_new_signal(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGTERM, "echo test")
        self.assertEqual(catcher.handlers, {signal.SIGTERM: ["echo test"]})

    def test_register_handler_existing_signal(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGTERM, "echo test1")
        catcher.register_handler(signal.SIGTERM, "echo test2")
        self.assertEqual(
            catcher.handlers,
            {signal.SIGTERM: ["echo test1", "echo test2"]},
        )

    def test_register_handler_duplicate_command(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGTERM, "echo test")
        catcher.register_handler(signal.SIGTERM, "echo test")
        self.assertEqual(catcher.handlers, {signal.SIGTERM: ["echo test"]})

    def test_unregister_handler_all(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGTERM, "echo test")
        result = catcher.unregister_handler(signal.SIGTERM)
        self.assertTrue(result)
        self.assertEqual(catcher.handlers, {})

    def test_unregister_handler_specific(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGTERM, "echo test1")
        catcher.register_handler(signal.SIGTERM, "echo test2")
        result = catcher.unregister_handler(signal.SIGTERM, "echo test1")
        self.assertTrue(result)
        self.assertEqual(catcher.handlers, {signal.SIGTERM: ["echo test2"]})

    def test_unregister_handler_nonexistent_signal(self):
        catcher = SignalCatcher()
        result = catcher.unregister_handler(signal.SIGTERM)
        self.assertFalse(result)

    def test_unregister_handler_nonexistent_command(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGTERM, "echo test")
        result = catcher.unregister_handler(signal.SIGTERM, "echo other")
        self.assertFalse(result)


class TestSignalCatcherLogging(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_file = Path(self.temp_dir.name) / "signals.log"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_log_signal_no_file(self):
        catcher = SignalCatcher()
        catcher.log_signal(signal.SIGTERM, "echo test")
        self.assertEqual(len(catcher.signal_history), 1)
        entry = catcher.signal_history[0]
        self.assertEqual(entry["signal"], signal.SIGTERM)
        self.assertEqual(entry["command"], "echo test")
        self.assertEqual(entry["signal_name"], "SIGTERM")
        self.assertIn("timestamp", entry)

    def test_log_signal_with_file(self):
        catcher = SignalCatcher()
        catcher.log_file = self.log_file
        catcher.log_signal(signal.SIGUSR1, "/path/to/script.sh")

        self.assertEqual(len(catcher.signal_history), 1)
        self.assertTrue(self.log_file.exists())

        with open(self.log_file, "r") as f:
            logged_entry = json.loads(f.readline())

        self.assertEqual(logged_entry["signal"], signal.SIGUSR1)
        self.assertEqual(logged_entry["command"], "/path/to/script.sh")


class TestSignalCatcherListHandlers(unittest.TestCase):
    def test_list_handlers_empty(self):
        catcher = SignalCatcher()
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            catcher.list_handlers()
            output = mock_stdout.getvalue()
            self.assertIn("No signal handlers registered", output)

    def test_list_handlers_with_entries(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGTERM, "echo term")
        catcher.register_handler(signal.SIGUSR1, "echo usr1")

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            catcher.list_handlers()
            output = mock_stdout.getvalue()

        self.assertIn("Registered signal handlers:", output)
        self.assertIn("SIGTERM", output)
        self.assertIn("SIGUSR1", output)
        self.assertIn("echo term", output)
        self.assertIn("echo usr1", output)


class TestSignalCatcherSetupHandlers(unittest.TestCase):
    def test_setup_handlers_empty(self):
        catcher = SignalCatcher()
        with patch("signal.signal") as mock_signal:
            catcher.setup_handlers()
            mock_signal.assert_not_called()

    def test_setup_handlers_with_entries(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGTERM, "echo test")
        catcher.register_handler(signal.SIGUSR1, "echo usr1")

        with patch("signal.signal") as mock_signal:
            catcher.setup_handlers()
            self.assertEqual(mock_signal.call_count, 2)

    def test_setup_handlers_exception(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGTERM, "echo test")

        with patch("signal.signal", side_effect=ValueError("test error")):
            with patch("sys.stderr", new_callable=io.StringIO):
                catcher.setup_handlers()


class TestSignalCatcherHandleSignal(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_file = Path(self.temp_dir.name) / "signals.log"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_handle_signal_no_handlers(self):
        catcher = SignalCatcher()
        catcher.handle_signal(signal.SIGTERM, None)
        self.assertTrue(catcher.running)

    def test_handle_signal_with_handler(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGUSR1, "echo executed")
        catcher.verbose = True

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            catcher.handle_signal(signal.SIGUSR1, None)
            mock_run.assert_called_once()

    def test_handle_signal_command_timeout(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGUSR1, "sleep 100")
        catcher.verbose = True

        with patch("subprocess.run", side_effect=Exception("Timeout")):
            with patch("sys.stderr", new_callable=io.StringIO):
                catcher.handle_signal(signal.SIGUSR1, None)

        self.assertTrue(catcher.running)

    def test_handle_signal_logs_entry(self):
        catcher = SignalCatcher()
        catcher.register_handler(signal.SIGUSR1, "echo test")
        catcher.log_file = self.log_file

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            catcher.handle_signal(signal.SIGUSR1, None)

        self.assertEqual(len(catcher.signal_history), 1)
        self.assertTrue(self.log_file.exists())

    def test_handle_signal_sigint_stops(self):
        catcher = SignalCatcher()
        catcher.handle_signal(signal.SIGINT, None)
        self.assertFalse(catcher.running)

    def test_handle_signal_other_signals_continue(self):
        catcher = SignalCatcher()
        catcher.handle_signal(signal.SIGTERM, None)
        self.assertTrue(catcher.running)


class TestSignalCatcherRun(unittest.TestCase):
    def test_run_with_duration(self):
        catcher = SignalCatcher()
        catcher.verbose = True

        with patch("time.sleep", side_effect=Exception("Stop sleep")):
            with patch("time.time", side_effect=[0, 100, 200]):
                with patch("sys.stderr", new_callable=io.StringIO):
                    catcher.run(duration=1)

    def test_run_keyboard_interrupt(self):
        catcher = SignalCatcher()

        with patch("time.sleep", side_effect=KeyboardInterrupt()):
            catcher.run()

        self.assertTrue(catcher.running)


if __name__ == "__main__":
    unittest.main()
