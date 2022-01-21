{ kapack ? import
    (fetchTarball "https://github.com/oar-team/nur-kapack/archive/master.tar.gz")
  {}
}:

let
  self = rec {
    pybatsim-core = kapack.pybatsim-core.overrideAttrs (attrs: rec {
      name = "${kapack.pybatsim-core.name}-local";
      src = kapack.pkgs.lib.sourceByRegex ./. [
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
  };
in
  self
