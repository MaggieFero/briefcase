from abc import abstractmethod

from requests import exceptions as requests_exceptions

from briefcase.exceptions import CorruptToolError, MissingToolError, NetworkFailure

ELF_PATCH_OFFSET = 0x08
ELF_PATCH_ORIGINAL_BYTES = bytes.fromhex("414902")
ELF_PATCH_PATCHED_BYTES = bytes.fromhex("000000")


class LinuxDeployBase:
    def __init__(self, command):
        self.command = command

    @property
    @abstractmethod
    def filename(self):
        ...

    @property
    @abstractmethod
    def linuxdeploy_download_url(self):
        ...

    @property
    def file_path(self):
        return self.command.tools_path / self.filename

    @classmethod
    def verify(cls, command, install=True):
        """Verify that linuxdeploy is available.

        :param command: The command that needs to use linuxdeploy
        :param install: Should the tool be installed if it is not found?
        :returns: A valid linuxdeploy tool wrapper. If linuxdeploy is not
            available, and was not installed, raises MissingToolError.
        """
        linuxdeploy = cls(command)

        if not linuxdeploy.exists():
            if install:
                command.logger.info(
                    "The linuxdeploy tool was not found; downloading and installing...",
                    prefix=cls.name,
                )
                linuxdeploy.install()
            else:
                raise MissingToolError("linuxdeploy")

        return cls(command)

    def exists(self):
        return self.file_path.exists()

    @property
    def managed_install(self):
        return True

    def install(self):
        """Download and install linuxdeploy."""
        try:
            linuxdeploy_path = self.command.download_url(
                url=self.linuxdeploy_download_url, download_path=self.command.tools_path
            )
        except requests_exceptions.ConnectionError as e:
            raise NetworkFailure("downloading linuxdeploy AppImage") from e

        with self.command.input.wait_bar("Installing linuxdeploy..."):
            self.command.os.chmod(linuxdeploy_path, 0o755)
            if self.filename.endswith("AppImage"):
                self.patch_elf_header()

    def uninstall(self):
        """Uninstall linuxdeploy."""
        with self.command.input.wait_bar("Removing old linuxdeploy install..."):
            self.appimage_path.unlink()

    def upgrade(self):
        """Upgrade an existing linuxdeploy install."""
        if not self.exists():
            raise MissingToolError("linuxdeploy")

        self.uninstall()
        self.install()

    def patch_elf_header(self):
        """Patch the ELF header of the AppImage to ensure it's always
        executable.

        This patch is necessary on Linux hosts that use AppImageLauncher.
        AppImages use a modified ELF binary header starting at offset 0x08
        for additional identification. If a system has AppImageLauncher,
        the Linux kernel module `binfmt-misc` will try to load the AppImage
        with AppImageLauncher. As this binary does not exist in the Docker
        container context, we patch the ELF header of linuxdeploy to remove
        the AppImage bits, thus making all systems treat it like a regular
        ELF binary.

        Citations:
        - https://github.com/AppImage/AppImageKit/issues/1027#issuecomment-1028232809
        - https://github.com/AppImage/AppImageKit/issues/828
        """

        if not self.exists():
            raise MissingToolError("linuxdeploy")
        with open(self.file_path, "r+b") as appimage:
            appimage.seek(ELF_PATCH_OFFSET)
            # Check if the header at the offset is the original value
            # If so, patch it.
            if appimage.read(len(ELF_PATCH_ORIGINAL_BYTES)) == ELF_PATCH_ORIGINAL_BYTES:
                appimage.seek(ELF_PATCH_OFFSET)
                appimage.write(ELF_PATCH_PATCHED_BYTES)
                appimage.flush()
                appimage.seek(0)
                self.command.logger.info("Patched ELF header of linuxdeploy AppImage.")
            # Else if the header is the patched value, do nothing.
            elif (
                appimage.read(len(ELF_PATCH_ORIGINAL_BYTES)) == ELF_PATCH_PATCHED_BYTES
            ):
                self.command.logger.info(
                    "ELF header of linuxdeploy AppImage is already patched."
                )
            else:
                # We should only get here if the file at the AppImage patch doesn't have
                # The original or patched value. If this is the case, the file is likely
                # wrong and we should raise an exception.
                raise CorruptToolError("linuxdeploy")


class LinuxDeploy(LinuxDeployBase):
    def __init__(self, command):
        super().__init__(self)
        self.command = command

    @property
    def filename(self):
        return f"linuxdeploy-{self.command.host_arch}.AppImage"

    @property
    def linuxdeploy_download_url(self):
        return (
            "https://github.com/linuxdeploy/linuxdeploy/"
            f"releases/download/continuous/{self.filename}"
        )


class LinuxDeployGtkPlugin(LinuxDeployBase):
    def __init__(self, command):
        super().__init__(command)
        self.command = command

    @property
    def filename(self):
        return "linuxdeploy-plugin-gtk.sh"

    @property
    def linuxdeploy_download_url(self):
        return (
            "https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/"
            f"master/{self.filename}"
        )
