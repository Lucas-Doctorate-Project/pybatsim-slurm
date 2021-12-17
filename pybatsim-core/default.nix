{ kapack ? import
    (fetchTarball "https://github.com/oar-team/nur-kapack/archive/master.tar.gz")
  {}
}:

let
  self = rec {
    pybatsim = kapack.pybatsim.overrideAttrs (attrs: rec {
      name = "${kapack.pybatsim.name}-local";
      src = kapack.pkgs.lib.sourceByRegex ./. [
        "^pyproject\.toml"
        "^poetry\.lock"
        "^README\.rst"
        "^batsim"
        "^batsim/.*\.py"
        "^batsim/cmds"
        "^batsim/cmds/.*\.py"
        "^batsim/sched"
        "^batsim/sched/.*\.py"
        "^batsim/sched/algorithms"
        "^batsim/sched/algorithms/.*\.py"
        "^batsim/sched/workloads"
        "^batsim/sched/workloads/.*\.py"
        "^batsim/sched/workloads/models"
        "^batsim/sched/workloads/models/.*\.py"
        "^batsim/tools"
        "^batsim/tools/.*\.py"
        "^schedulers"
        "^schedulers/.*\.py"
        "^schedulers/unMaintained"
        "^schedulers/unMaintained/.*\.py"
      ];
    });
  };
in
  self
