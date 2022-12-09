# python_template

## python_template usage

== Remove this complete section before first commit, this is template instructions only ==

1. Search for `python_template` and replace it with your new name (lower snake case, except the `NAME` in `python_template.py`, this should be human readable) everywhere.
2. Rename the `python_template.py` file in `src/python_template`
3. Rename the `python_template` directory in `src/`
4. Make sure there is a name set in `pyproject.toml` (lower snake case)
5. Run `poetry install`
6. Select the correct interpreter for VSCode
7. Remove this section

== End remove ==



## Installation

### Via `pip`

```bash
pip install python_template
```

### From source
To run this program from the code directly, [`python`](https://www.python.org/) and [`poetry`](https://python-poetry.org/) (`pip install poetry`) are required. Clone or download the repository.

To install all the dependencies, use your command line and navigate to the directory where this `README` file is located in. Then run

```bash
poetry install
```

### For development

For development installation perform the [From source](#from-source) installation.

For installing new packages, always run
```
poetry add <pip-package-name>
```
instead of `pip install <pip-package-name>`.

Launch the program either check out the [Execution](#execution) section or use the *Run and Debug*-side panel of VSCode.

If the interpreter of the virtual environment does not show up in VSCode, add it manually. The virtual environments are located in `{cache-dir}/virtualenvs/<venv-name>/Scripts/python.exe` where the [`{cache-dir}`](https://python-poetry.org/docs/configuration/#cache-dir) depends on the operating system (`~/.cache/pypoetry`, `~/Library/Caches/pypoetry` or `C.\Users\%USERNAME%\AppData\Local\pypoetry\Cache`).

## Execution

To execute the program use
```bash
poetry run python -m python_template
```

