{ kapack ? import
    (fetchTarball "https://github.com/oar-team/nur-kapack/archive/master.tar.gz")
  {}
, pybatsim-core-base ? kapack.pybatsim-core
, pybatsim-functional-base ? kapack.pybatsim-functional
}:

let
  self = rec {
    pybatsim-core = pybatsim-core-base.overrideAttrs (attrs: rec {
      name = "${attrs.name}-local";
      src = kapack.pkgs.lib.sourceByRegex ./pybatsim-core [
        "^pyproject\.toml$"
        "^poetry\.lock$"
        "^README\.rst$"
        "^src$"
        "^src/pybatsim$"
        "^src/pybatsim/.\+\.py$"
        "^src/pybatsim/batsim$"
        "^src/pybatsim/batsim/.\+\.py$"
        "^src/pybatsim/batsim/cmds$"
        "^src/pybatsim/batsim/cmds/.\+\.py$"
        "^src/pybatsim/batsim/tools$"
        "^src/pybatsim/batsim/tools/.\+\.py$"
        "^src/pybatsim/schedulers$"
        "^src/pybatsim/schedulers/.\+\.py$"
        "^src/pybatsim/schedulers/unMaintained$"
        "^src/pybatsim/schedulers/unMaintained/.\+\.py$"
      ];
    });
    pybatsim-functional = pybatsim-functional-base.overrideAttrs (attrs: rec {
      name = "${attrs.name}-local";
      src = kapack.pkgs.lib.sourceByRegex ./pybatsim-functional [
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
