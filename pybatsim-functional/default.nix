{ kapack ? import
    (fetchTarball "https://github.com/oar-team/nur-kapack/archive/master.tar.gz")
  {}
}:

let
  self = rec {
    pybatsim-functional = kapack.pybatsim-functional.overrideAttrs (attrs: rec {
      name = "${kapack.pybatsim-functional.name}-local";
      src = kapack.pkgs.lib.sourceByRegex ./. [
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
    });
  };
in
  self
