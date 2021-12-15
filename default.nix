{ kapack ? import
    (fetchTarball "https://github.com/oar-team/nur-kapack/archive/master.tar.gz")
  {}
}:

let
  self = rec {
    pybatsim = kapack.pkgs.python3Packages.buildPythonPackage rec {
      pname = "pybatsim";
      version = "local";
      format = "pyproject";

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

      buildInputs = with kapack.pkgs.python3Packages; [
        poetry
      ];
      propagatedBuildInputs = with kapack.pkgs.python3Packages; [
        sortedcontainers
        pyzmq
        redis
        click
        docopt
        kapack.procset
      ];

      doCheck = false;

      meta = with kapack.pkgs.lib; {
        description = "Python API and Schedulers for Batsim";
        homepage = "https://gitlab.inria.fr/batsim/pybatsim";
        platforms = platforms.all;
        license = licenses.lgpl3;
        broken = false;

        longDescription = "PyBatsim is the Python API for Batsim.";
      };
    };
  };
in
  self
