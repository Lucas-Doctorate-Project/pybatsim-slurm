Instruções para rodar o escalonador SLURM:


Método testado apenas em um ambiente com Nix, até agora.
Logo mais trataremos de elaborar método que envolve compilação direta, aplicável em sistemas e ambientes mais diversos.

O ambiente Nix precisa de python 3.12 ou 3.11. Também precisa de algumas bibliotecas do GCC, obtidas instalando gcc-unwrapped
e definindo LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:/nix/store/dj06r96j515npcqi9d8af1d1c60bx2vn-gcc-14.3.0-lib/lib/" 
no ambiente bash.

Se você desejar rodar pybatsim-experiment, conforme instruções do pybatsim original, precisará de um daemon do docker rodando.


No primeiro terminal, execute batsim (https://batsim.readthedocs.io/en/latest/tuto-first-simulation/tuto.html):

```
batsim -p /tmp/batsim-src-stable/platforms/cluster512.xml \
       -w /tmp/batsim-src-stable/workloads/test_batsim_paper_workload_seed1.json \
       -e "/tmp/expe-out/out"
```

Você pode perfeitamente utilizar o arquivo de plataforma e workload de sua preferência.

Em um outro terminal, com o repositório do pybatsim clonado, execute, dentro do diretório em que ele foi clonado:

$ `pip install -e .`

Em seguida:

$ `pybatsim schedulers/schedSlurm.py`

Isso vai rodar o escalonador em si.
