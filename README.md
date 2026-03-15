# signal-catcher-cli

Catch and handle Unix signals in your apps. Simple as that.

## Why I Built This

Ever needed your script to do something specific when it receives a SIGTERM? Or maybe trigger a cleanup routine on SIGUSR1? Instead of writing signal handling boilerplate every single time, I made this CLI tool.

Now I just register what I want to happen and let it run in the background.

## Quick Start

```bash
# Register a handler
python signal_catcher.py register SIGTERM "echo 'Shutting down gracefully...'"

# Register a script to run
python signal_catcher.py register SIGUSR1 "/path/to/cleanup.sh"

# Start listening
python signal_catcher.py listen --verbose

# In another terminal, send a signal
kill -SIGUSR1 <pid>
```

## Commands

### register

Register a command to run when a signal is received.

```bash
python signal_catcher.py register SIGNAL "command to execute"
```

Signals you can use: SIGTERM, SIGINT, SIGHUP, SIGUSR1, SIGUSR2, SIGQUIT, etc.

### remove

Remove a registered handler.

```bash
# Remove specific command
python signal_catcher.py remove SIGTERM "echo 'Shutting down...'"

# Remove all handlers for a signal
python signal_catcher.py remove SIGTERM
```

### listen

Start the signal catcher daemon.

```bash
python signal_catcher.py listen                    # Run forever
python signal_catcher.py listen -d 60              # Run for 60 seconds
python signal_catcher.py listen -v                 # Verbose mode
python signal_catcher.py listen -l /var/log/signals.json
python signal_catcher.py listen -t 60              # Set command timeout to 60 seconds
```

### list

Show all registered handlers.

```bash
python signal_catcher.py list
```

### config

Show where the config file lives.

```bash
python signal_catcher.py config
```

## Config File

Handlers are stored in `~/.signal-catcher/config.json`. It's just JSON, so you can edit it directly if you want.

```json
{
  "handlers": {
    "15": ["echo 'Received SIGTERM'"],
    "10": ["/home/user/scripts/cleanup.sh"]
  },
  "verbose": false,
  "log_file": null,
  "command_timeout": 30
}
```

## Logging

Use `-l` or `--log-file` to log all caught signals to a file. Each entry is a JSON line with timestamp, signal name, and the command that was executed. Handy for debugging or auditing.

## Use Cases

- **Graceful shutdowns**: Register SIGTERM to flush caches, close connections, etc.
- **Hot reloading**: Use SIGHUP to reload config without restarting.
- **Debug triggers**: SIGUSR1 to dump state, SIGUSR2 to toggle debug mode.
- **Cleanup on exit**: Catch signals and run your cleanup scripts.

## Notes

- Commands timeout after 30 seconds by default (configurable via `-t` flag or `command_timeout` in config)
- Multiple commands can be registered for the same signal
- SIGKILL and SIGSTOP cannot be caught (that's just how Unix works)
- Runs in foreground, so stick it in a screen/tmux session or systemd service

## License

Do what you want with it.
