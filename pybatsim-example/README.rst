
===============================
Pybatsim - Example
===============================

This is an example folder to show you how to setup and package your own scheduler in Pybatsim


Setup your scheduler
~~~~~~~~~~~~~~~~~~~~

A small scheduler is given as an example, which simply rejects all submitted jobs.
To use your own scheduler, put the source file in this current repository (along with `universal_rejection.py, then register it in the pybatsim entry point by adding a line in the `pyproject.toml` file under the `[tool.poetry.plugins."pybatsim.schedulers"]` section.
The line must follow the pattern::

  `<scheduler_name> = <file_name>:<Scheduler_class_name>`.

Start your scheduler
~~~~~~~~~~~~~~~~~~~~

Once done, to use your scheduler you can use the `example-shell` nix recipee defined in the root folder of Pybatsim to enter a virtual environment with everything you need by running (from this directory)::

  nix-shell ../default.nix -A example-shell

And then launch your scheduler with::

  pybatsim <scheduler_name>

Or with a one liner::

  nix-shell ../default.nix -A example-shell --command 'pybatsim <scheduler_name>'


Develop your scheduler
~~~~~~~~~~~~~~~~~~~~~~

To develop your scheduler, it is convenient to enter a poetry environment by running (from this directory)::

  poetry install
  poetry shell

Then, you can modify your scheduler and test it by directly running::

  pybatsim <scheduler_name>


Note for nix users: a shell containing `poetry` is already defined in the `default.nix` file in the root forled of Pybatsim.
From this directory, before running the poetry commands, you can run::

  nix-shell ../default.nix -A dev-shell

