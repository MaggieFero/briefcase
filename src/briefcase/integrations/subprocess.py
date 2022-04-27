import shlex
import subprocess


class Subprocess:
    """
    A wrapper around subprocess that can be used as a logging point for
    commands that are executed.
    """
    def __init__(self, command):
        self.command = command
        self._subprocess = subprocess

    def prepare(self):
        """
        Perform any environment preparation required to execute processes.
        """
        # This is a no-op; the native subprocess environment is ready-to-use.
        pass

    def final_kwargs(self, **kwargs):
        """
        Convert subprocess keyword arguments into their final form.
        """
        # If `env` has been provided, inject a full copy of the local
        # environment, with the values in `env` overriding the local
        # environment.
        try:
            extra_env = kwargs.pop('env')
            kwargs['env'] = self.command.os.environ.copy()
            kwargs['env'].update(extra_env)
        except KeyError:
            # No explicit environment provided.
            pass

        # If `cwd` has been provided, ensure it is in string form.
        try:
            cwd = kwargs.pop('cwd')
            kwargs['cwd'] = str(cwd)
        except KeyError:
            pass

        return kwargs

    def run(self, args, **kwargs):
        """
        A wrapper for subprocess.run()

        The behavior of this method is identical to subprocess.run(),
        except for the `env` argument. If provided, the current system
        environment will be copied, and the contents of env overwritten
        into that environment.
        """
        # Invoke subprocess.run().
        # Pass through all arguments as-is.
        # All exceptions are propagated back to the caller.
        subprocess_kwargs = self.final_kwargs(**kwargs)
        self._log_command(args)
        self._log_environment(subprocess_kwargs, kwargs.get("env"))

        try:
            command_result = self._subprocess.run(
                [
                    str(arg) for arg in args
                ],
                **subprocess_kwargs
            )
        except subprocess.CalledProcessError as exc:
            self._log_return_code(exc.returncode)
            raise

        self._log_return_code(command_result.returncode)
        return command_result

    def check_output(self, args, **kwargs):
        """
        A wrapper for subprocess.check_output()

        The behavior of this method is identical to subprocess.check_output(),
        except for the `env` argument. If provided, the current system
        environment will be copied, and the contents of env overwritten
        into that environment.
        """
        subprocess_kwargs = self.final_kwargs(**kwargs)
        self._log_command(args)
        self._log_environment(subprocess_kwargs, kwargs.get("env"))

        try:
            cmd_output = self._subprocess.check_output(
                [
                    str(arg) for arg in args
                ],
                **subprocess_kwargs
            )
        except subprocess.CalledProcessError as exc:
            self._log_output(exc.output, exc.stderr)
            self._log_return_code(exc.returncode)
            raise

        self._log_output(cmd_output)
        self._log_return_code(0)
        return cmd_output

    def Popen(self, args, **kwargs):
        """
        A wrapper for subprocess.Popen()

        The behavior of this method is identical to subprocess.Popen(),
        except for the `env` argument. If provided, the current system
        environment will be copied, and the contents of env overwritten
        into that environment.
        """
        subprocess_kwargs = self.final_kwargs(**kwargs)
        self._log_command(args)
        self._log_environment(subprocess_kwargs, kwargs.get("env"))

        return self._subprocess.Popen(
            [
                str(arg) for arg in args
            ],
            **subprocess_kwargs
        )

    def _log_command(self, args):
        """
        Log the entire console command being executed.
        """
        self.command.logger.debug()
        self.command.logger.debug("Running Command:")
        self.command.logger.debug(f"    {' '.join(shlex.quote(str(arg)) for arg in args)}")

    def _log_environment(self, subprocess_kwargs=None, env_updates=None):
        """
        Log the state of environment variables prior to command execution.

        In debug mode, only the updates to the current environment are logged.
        In deep debug, the entire environment for the command is logged.
        """
        if self.command.logger.verbosity >= self.command.logger.DEEP_DEBUG:
            env = (subprocess_kwargs or {}).get("env") or self.command.os.environ
            if env:
                self.command.logger.deep_debug("Full Environment:")
                for env_var, value in env.items():
                    self.command.logger.deep_debug(f"    {env_var}={value}")

        elif self.command.logger.verbosity >= self.command.logger.DEBUG:
            if env_updates:
                self.command.logger.debug("Environment:")
                for env_var, value in env_updates.items():
                    self.command.logger.debug(f"    {env_var}={value}")

    def _log_output(self, output, stderr=None):
        """
        Log the output of the executed command.
        """
        if output:
            self.command.logger.deep_debug("Command Output:")
            for line in str(output).splitlines():
                self.command.logger.deep_debug(f"    {line}")

        if stderr:
            self.command.logger.deep_debug("Command Error Output (stderr):")
            for line in str(stderr).splitlines():
                self.command.logger.deep_debug(f"    {line}")

    def _log_return_code(self, return_code):
        """
        Log the output value of the executed command.
        """
        self.command.logger.deep_debug(f"Return code: {return_code}")
