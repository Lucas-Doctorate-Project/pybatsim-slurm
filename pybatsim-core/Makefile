.PHONY: test
test:
	make --directory=tests/

.PHONY: doc
doc: clean
	sphinx-apidoc --output-dir=doc/apidoc/pybatsim/ src/pybatsim/
	make --directory=doc/ html

.PHONY: clean
clean:
	make --directory=doc/ clean
	rm --recursive --force -- doc/apidoc/
