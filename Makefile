.PHONY: test
test:
	make --directory=tests/

.PHONY: doc
doc: clean
	sphinx-apidoc --force --output-dir=doc/apidoc/batsim/ batsim/
	sphinx-apidoc --force --output-dir=doc/apidoc/schedulers/ schedulers/
	make --directory=doc/ html

.PHONY: clean
clean:
	make --directory=doc/ clean
	rm --recursive --force -- doc/apidoc/
