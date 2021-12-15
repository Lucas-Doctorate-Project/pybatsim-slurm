EXPE_FOLDERS := $(wildcard tests/*)
SIMULS_OUT := $(patsubst %,%/out_jobs.csv,$(EXPE_FOLDERS))
GANTTS_OUT := $(patsubst %,%/gantt.png,$(EXPE_FOLDERS))
BATSIMBIN ?= $(shell command -v batsim)


all: simuls

simuls: testIntervals $(SIMULS_OUT) coverage_html
	@if [ "$(SIMULS_OUT)" == "" ]; then \
		echo; \
		echo "All experiments were generated."; \
		echo " -> You may have to run the command again to run the experiments."; \
	fi

coverage_html: ../.coverage
	cd ..; python3 -m coverage html -i -d tests/coverage_html

testIntervals: generate
	cd ..; python3 -m coverage run -a schedulers/intervalContainer.py

%/out_jobs.csv:
	cd ..; pybatsim-experiment --quiet tests/$*/expe.json || (rm -f $@; exit 1)

gantts: $(GANTTS_OUT)

gantts_okular: $(GANTTS_OUT)
	okular $^

%/gantt.png: %/out_jobs.csv
	python3 ../../../../evalys/evalys/gantt.py $* $*/gantt.png

generate:
	@echo Using Batsim binary: $(BATSIMBIN)
	python3 generate.py --batsim-bin=$(BATSIMBIN)

clean:
	rm tests/*/out_jobs.csv
	cd ..; python3 -m coverage erase
