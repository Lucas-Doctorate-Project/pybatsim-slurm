{
    description = "Flake for PyBatsim";

    inputs = {
        nixpkgs.url = "github:nixos/nixpkgs?ref=25.05";
        batsim-batprotocol = {
            # follow batprotocol branch until it is merged in master
            url = "git+https://framagit.org/batsim/batsim?ref=batprotocol";
            inputs.nixpkgs.follows = "nixpkgs";
        };
    };

    outputs = { self, nixpkgs, flake-utils, batsim-batprotocol }:
        (flake-utils.lib.eachDefaultSystem (system:
          let
            pkgs = import nixpkgs { inherit system; };
            batsim = batsim-batprotocol.packages.${system}.batsim;
            procset = pkgs.python3Packages.buildPythonPackage rec {
                name = "procset-${version}";
                version = "v1.0";

                src = pkgs.fetchgit {
                    url = "https://gitlab.inria.fr/bleuse/procset.py.git";
                    rev = version;
                    sha256 = "1cnmbw4sgl9156lgvakdkpjr7mgd2wasqz1zml9qzk29p705420z";
                };

                LC_ALL = "en_US.UTF-8";
                buildInputs = [ pkgs.glibcLocales ];
            };
          in rec {
            packages = rec {
                default = pybatsim-core;

                pybatsim-core = pkgs.python3Packages.buildPythonPackage rec {
                    pname = "pybatsim-core-local";
                    version = "4.1.0-beta";
                    format = "pyproject";
                    src = pkgs.lib.sourceByRegex ./. [
                        "^pyproject\.toml$"
                        "^poetry\.lock$"
                        "^README\.rst$"
                        "^src$"
                        "^src/pybatsim$"
                        "^src/pybatsim/.\+\.py$"
                        "^src/pybatsim/batsim$"
                        "^src/pybatsim/batsim/.\+\.py$"
                        "^src/pybatsim/external_decision_components$"
                        "^src/pybatsim/external_decision_components/.\+\.py$"
                        "^tests$"
                        "^tests/regression$"
                        "^tests/regression/.\+\.py$"
                        "^tests/unit$"
                        "^tests/unit/.\+\.py$"
                    ];
                    buildInputs = with pkgs.python3Packages; [
                        poetry-core
                    ];
                    propagatedBuildInputs = with pkgs.python3Packages; [
                        procset
                        pyzmq
                        sortedcontainers
                    ];
                    doCheck = false;
                    meta = with pkgs.lib; {
                        description = "Core Python Python API and schedulers for Batsim";
                        longDescription = "Core Python Python API and schedulers for Batsim";
                        homepage = "https://gitlab.inria.fr/batsim/pybatsim";
                        platforms = platforms.all;
                        license = licenses.lgpl3;
                        broken = false;
                    };
                };
            };

            devShells = rec {
                default = tests;
                tests = pkgs.mkShell {
                    buildInputs = with pkgs.python3Packages; [
                        # batsim / pybatsim
                        self.packages.${system}.pybatsim-core
                        batsim
                        # test dependencies
                        pytest
                        pytest-cov
                        coverage
                        pytest-datadir
                        pytest-regressions
                    ];
                    shellHook = ''
                        echo "batsim: $(batsim --version)"
                        echo "pybatsim: $(pybatsim --version)"
                    '';
                };
            };
          } # in rec
    ));
}
