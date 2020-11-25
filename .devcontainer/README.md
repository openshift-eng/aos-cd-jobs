## Development Container Support for VSCode

This directory contains the `Dockerfile` and `devcontainer.json` file
that allows you to develop and debug `aos-cd-jobs` inside a development container
using Visual Studio Code. See [https://code.visualstudio.com/docs/remote/containers]() for more information.

## Quick Start

1. Install the [Remote Development Extension Pack][] on Visual Studio Code.
2. Open `aos-cd-jobs` project locally.
3. If you are using Linux, make sure the `USER_UID` `USER_GID` arguments in `dev.Dockerfile` match your actual UID and GID. Ignore this step if you are using macOS or Windows.
4. Click the green icon on the bottom left of the VSCode window or press <kbd>F1</kbd>, then choose `Remote-Containers: Reopen in Container`.

[Remote Development Extension Pack]: https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.vscode-remote-extensionpack

# Development container use with podman

The same Dockerfile can be used independently to provide a doozer environment container.
A build with podman may look like:

    USERNAME=yours
    USER_UID=1234
    podman build --build-arg USERNAME=$USERNAME --build-arg USER_UID=$USER_UID \
                 -f .devcontainer/dev.Dockerfile -t local/aos-cd-jobs.
