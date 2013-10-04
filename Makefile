

default: lint test

setup:
	./setup_virtualenv

run:
	python server.py 2>&1

flake:
	pyflakes *.py monitor

lint:
	pylint --rcfile pylintrc server.py monitor

test:
	python -m unittest discover -f

clean:
	find . -iname \*.pyc -print0 | xargs -0r rm
	rm -rf bin include lib local
