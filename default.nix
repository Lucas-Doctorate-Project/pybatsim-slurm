{ kapack ? import (fetchTarball {
    url = "https://github.com/oar-team/nur-kapack/archive/7fa57b4170962b5c88d077d6f625628e7763c81c.tar.gz";
    sha256 = "sha256:13irywc4lm30xj4z722whk5fnrqkd3a71vh0fc2c4sqfd1rhcfl6";
  }) {}
, pybatsim-core-base ? kapack.pybatsim-core
, pybatsim-functional-base ? kapack.pybatsim-functional
, unstablepkgs ? import (builtins.fetchTarball { # Required for poetry >= 2.0.0 (as of April 2025)
    url = "https://github.com/nixos/nixpkgs/archive/b7ba7f9f45c5cd0d8625e9e217c28f8eb6a19a76.tar.gz";
    sha256 = "0zc9608kkl7bkgl4w80nw06ddk5i9gv7cp34m63vpwj4mr7zk034";
  }) {}
}:

let
  self = rec {
    pkgs = kapack.pkgs;
    lib = pkgs.lib;
    python3Packages = pkgs.python3Packages;
    pybatsim-core = pybatsim-core-base.overrideAttrs (attrs: rec {
      name = "${attrs.name}-local";
      src = lib.sourceByRegex ./pybatsim-core [
        "^pyproject\.toml$"
        "^poetry\.lock$"
        "^README\.rst$"
        "^src$"
        "^src/pybatsim$"
        "^src/pybatsim/.\+\.py$"
        "^src/pybatsim/batsim$"
        "^src/pybatsim/batsim/.\+\.py$"
        "^src/pybatsim/schedulers$"
        "^src/pybatsim/schedulers/.\+\.py$"
        "^src/pybatsim/schedulers/unMaintained$"
        "^src/pybatsim/schedulers/unMaintained/.\+\.py$"
      ];
    });
    pybatsim-functional = pybatsim-functional-base.overrideAttrs (attrs: rec {
      name = "${attrs.name}-local";
      src = lib.sourceByRegex ./pybatsim-functional [
        "^pyproject\.toml$"
        "^poetry\.lock$"
        "^src$"
        "^src/pybatsim_functional$"
        "^src/pybatsim_functional/.\+\.py$"
        "^src/pybatsim_functional/algorithms$"
        "^src/pybatsim_functional/algorithms/.\+\.py$"
        "^src/pybatsim_functional/schedulers$"
        "^src/pybatsim_functional/schedulers/.\+\.py$"
        "^src/pybatsim_functional/schedulers/unmaintained$"
        "^src/pybatsim_functional/schedulers/unmaintained/.\+\.py$"
        "^src/pybatsim_functional/tools$"
        "^src/pybatsim_functional/tools/.\+\.py$"
        "^src/pybatsim_functional/workloads$"
        "^src/pybatsim_functional/workloads/.\+\.py$"
        "^src/pybatsim_functional/workloads/models$"
        "^src/pybatsim_functional/workloads/models/.\+\.py$"
      ];
      # change the pybatsim-core to use (local one, not base one)
      propagatedBuildInputs = lib.remove pybatsim-core-base attrs.propagatedBuildInputs ++
        [ pybatsim-core ];
    });

    # entry point for external scheduler example
    pybatsim-example = python3Packages.buildPythonPackage rec {
      pname = "pybatsim-example-entry-point";
      version = "local";
      format = "pyproject";

      src = lib.sourceByRegex ./pybatsim-example [
        "^pyproject\.toml$"
        "^poetry\.lock$"
        "^.*\.py$"
      ];
      buildInputs = with python3Packages; [
        poetry
      ];
      propagatedBuildInputs = [
        pybatsim-core
      ];
    };

    # example shell that enables to run the example scheduler (run `pybatsim rejector` in the shell)
    example-shell = pkgs.mkShell rec {
      buildInputs = [
        pybatsim-example
      ];
    };

    # small shell to dev and test schedulers
    dev-shell = unstablepkgs.mkShell rec {
      buildInputs = [
        unstablepkgs.stdenv.cc.cc.lib
        unstablepkgs.poetry
      ];

      LD_LIBRARY_PATH="${unstablepkgs.stdenv.cc.cc.lib}/lib";
    };
  };
in
  self
