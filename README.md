# Citation Graph

![Citation Graph example screenshot](docs/screenshot1.jpg)

Citation Graph helps you creating a literature graph from one starting scientific publication. By the help of some scientific databases (currently only [semanticscholar.org](https://semanticscholar.org)) it starts from one paper and looks up the citations of this paper, followed by their citations and so on.

Results are cached in a local directory. If a search is then extended, this cache is used to extend the last result. Note: The program will continue after the last iteration. This means changing the number of citations per paper does not affect the cached results.

To not spam databases with requests, the program waits some time between two requests. To be even more polite, a `politeness` factor can be applied that increases (or decreases) the idle duration.

## Citation Graph usage


## Installation

<!-- ### Via `pip`

```bash
pip install citation_graph
``` -->

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

<!-- ### For `pip` installation

To execute the program use
```
python -m citation_graph "<DOI>"
``` -->

### For manual and development installation

To execute the program use
```bash
poetry run python -m citation_graph
```

### Parameters

```
citation_graph [-h] [--version] [-v] [-vv] [--max-depth MAX_DEPTH] [--clear-cache] [--max-citations-per-paper MAX_CITATIONS_PER_PAPER] [--politeness POLITENESS_FACTOR] doi
```

**positional arguments**
- `doi` The DOI of the paper to use as the root

**optional arguments**
- `-h`, `--help` show this help message and exit
- `--version`, `-V` show program's version number and exit
- `-v`, `--verbose` Set the loglevel to INFO
- `-vv`, `--very-verbose` Set the loglevel to DEBUG
- `--max-depth MAX_DEPTH`, `-d MAX_DEPTH` The maximum depth to search papers, if 0, only the root paper is included in the result, default is 1
- `--clear-cache`, `-c`     Clear the cache before fetching. This ensures fresh data.
- `--max-citations-per-paper MAX_CITATIONS_PER_PAPER`, `-m MAX_CITATIONS_PER_PAPER` The maximum amount of citations to collect per paper, default is 300
- `--politeness POLITENESS_FACTOR`, `-p POLITENESS_FACTOR` A factor that is multiplied with the idle time that each database traverser waits between two requests, using values >1 will be more polite but slow down the requests, values <1 will be faster but may cause your IP being blocked, default is 1