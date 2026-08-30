PYTHON ?= python3

.PHONY: test shortcut install uninstall doctor clean

test:
	$(PYTHON) -m unittest discover -s tests -v

shortcut:
	$(PYTHON) shortcut/build_shortcut.py --out build

install:
	./mac/install.sh

uninstall:
	./mac/uninstall.sh

doctor:
	$(PYTHON) -m articlefiler doctor

clean:
	rm -rf build dist *.egg-info
	find . -name __pycache__ -type d -exec rm -rf {} +
