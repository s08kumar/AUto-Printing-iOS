PYTHON ?= python3

.PHONY: test shortcut sign install uninstall restart doctor clean

test:
	$(PYTHON) -m unittest discover -s tests -v

shortcut:
	$(PYTHON) shortcut/build_shortcut.py --out build

sign: shortcut
	./shortcut/sign.sh build

install:
	./mac/install.sh

uninstall:
	./mac/uninstall.sh

restart:
	@# git pull updates the files; the running agent keeps the code it
	@# imported at launch, so it must be restarted to pick changes up.
	launchctl kickstart -k gui/$$UID/com.articlefiler.watcher
	@echo "watcher restarted on the current code"

doctor:
	$(PYTHON) -m articlefiler doctor

clean:
	rm -rf build dist *.egg-info
	find . -name __pycache__ -type d -exec rm -rf {} +
