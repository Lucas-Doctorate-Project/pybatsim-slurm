Instruções para rodar o escalonador SLURM:


Método testado apenas em um ambiente com Nix, até agora.
Logo mais trataremos de elaborar método que envolve compilação direta, aplicável em sistemas e ambientes mais diversos.


No primeiro terminal, execute batsim (https://batsim.readthedocs.io/en/latest/tuto-first-simulation/tuto.html):

```
batsim -p /tmp/batsim-src-stable/platforms/cluster512.xml \
       -w /tmp/batsim-src-stable/workloads/test_batsim_paper_workload_seed1.json \
       -e "/tmp/expe-out/out"
```

Em um outro terminal, com o repositório do pybatsim clonado, execute:

$ `nix-shell ../default.nix -A example-shell`

Em seguida:

$ `pybatsim slurm`

Isso vai rodar o escalonador em si.
