===============================
Pybatsim
===============================

PyBatsim helps you developing your own scheduler and other External Decision Component (EDC) in Python!

This repository contains 3 folders:
- `pybatsim-core`: the core module which takes care of the communication with Batsim's main process
- `pybatsim-example`: an example folder to show you how to setup and package your own scheduler in Pybatsim
- `pybatsim-functional`: a high-level API which contains an object oriented abstration layer. This API is not maintained anymore but kept as legacy.


Installation
------------

**TODO**

Pybatsim relies on poetry to manage the dependencies and install process.


Usage of pybatsim-core
----------------------

**TODO**

To show the list of the different schedulers provided, execute::

    poetry run pybatsim --list-schedulers

To run a registered scheduler, for example the `random` which uses class `RandomSched`, execute::

    poetry run pybatsim random

It is also possible to run your own scheduler defined in a file somewhere else using the provided `prototype`.
For this you must specify in the command line options where to find it, with the attributes `EDC_file` and `EDC_class` of a JSON-formatted dictionary in the command line options.
For example::

    poetry run pybatsim prototype -o '{"EDC_file": "/path/to/my/scheduler.py", "EDC_class": "AwesomeSched"}'


Documentation
-------------

All documentation regarding Batsim and the communication protocol can be found in the `Batsim official documentation`_




.. _Batsim official documentation:
https://batsim.readthedocs.io/en/latest/protocol.html
