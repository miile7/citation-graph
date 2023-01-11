# Citation Graph

<picture width="750px" alt="Overview over all citations" >
  <source type="image/jpg" srcset="docs/screenshot1.jpg" />
  <img src='https://github.com/miile7/citation-graph/blob/main/docs/screenshot1.jpg?raw=true'/>
</picture>
<picture width="750px" alt="Hover over node for more details" >
  <source type="image/jpg" srcset="docs/screenshot2.jpg" />
  <img src='https://github.com/miile7/citation-graph/blob/main/docs/screenshot2.jpg?raw=true'/>
</picture>

Citation Graph helps you creating a literature graph from one starting scientific
publication. By the help of some scientific databases (currently only
[semanticscholar.org](https://semanticscholar.org)) it starts from this paper and looks
up the citations of this paper. Then the citations of those papers are looked up and so
on.

Each request result is written to the local cache file. This means running the same (or
a subset of the) request will result in an instantaneous result by using the cached
results. If the parameters are changed, the cache is still used for those results that
are known.

For some databases API keys lead to faster access, for others they are required for
getting results at all. This is supported by a database `config` file.

## Key Features

- Create Citation Graph starting from one paper by requesting information from online
  databases
- Merge results from different databases (Coming soon!)
- Create citation list file (csv file)
- Support API keys for (faster) access
- Exclude irrelevant papers on collection
- Use local cache for fast reproducible results

## Recommended usage

To create a (more-less) full citation graph, the following procedure is recommended:

1. (*Optional*): If you have API keys, copy the `config.example.ini`, rename it to
   `config.ini` and fill in your keys
2. Find your paper at any scientific search engine, then copy one of the ids,
   preferable the DOI (other supported id types can be found by running
   `citation_graph -h`)
3. Start with a broad search with depth 2 (`-d=2`). This will find citations of papers
   that cite the root paper. This shows citations that are no dead ends. Do not include
   too many citations (the maximum citations can be controlled with `-m`). A too high
   `m` on the first run will slow down the process unnecessarily because citations of
   uninteresting works are collected. A good first run is e.g.:
   `citation_graph -v -d=2 -m=100 <YOUR DOI>`
4. Open the result graph and check the level-2-nodes, so the nodes that have two edges
   between itself and the root (so `root`-`node`-`node`). Check those papers if they are
   relevant for your search. If not, create a file `excluded.txt` and copy the id
   from the graph to this file. Each id has to be in its own line (comment is #,
   comments have to be in a separate line). All subsequent runs have to
   include `-x=excluded.txt` to load the exclude file.
5. Now step by step extend your search:
   1. Extend the broadness by increasing `-m` while keeping the last `-d`, e.g.
      `citation_graph -v -d=2 -m=200 -x=excluded.txt <YOUR DOI>`
   2. Exclude irrelevant papers by traveling through the nodes with the most edges
      between itself and the root. If a paper is not relevant for you, copy the id into
      the `excluded.txt`.
   3. Extend the depth by increasing `-d` (but narrow `-m` again), e.g.
      `citation_graph -v -d=3 -m=100 -x=excluded.txt <YOUR DOI>` (compare `-m=100` to
      `-m=200` in the previous run).
   4. Exclude irrelevant papers, as described in step 4 or 5.2
   5. Start over at 5.1
   6. Repeat this until increasing `-d` and `-m` does not change the result graph
      anymore (`citation_graph` will tell you about collecting papers for a specific
      level, but no more requests are started). This means, no more papers can be
      collected.
6. Done. You found the full citation graph of your paper (where citations are mentioned
   in at least one of the supported databases).


## Installation

### Via `pip`

```bash
pip install citation-graph
```

### From source
To run this program from the code directly, [`python`](https://www.python.org/) and
[`poetry`](https://python-poetry.org/) (`pip install poetry`) are required. Clone or
download the repository.

To install all the dependencies, use your command line and navigate to the directory
where this `README` file is located in. Then run

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

Launch the program either check out the [Execution](#execution) section or use the
*Run and Debug*-side panel of VSCode.

If the interpreter of the virtual environment does not show up in VSCode, add it
manually. The virtual environments are located in
`{cache-dir}/virtualenvs/<venv-name>/Scripts/python.exe` where the
[`{cache-dir}`](https://python-poetry.org/docs/configuration/#cache-dir) depends on the
operating system (`~/.cache/pypoetry`, `~/Library/Caches/pypoetry` or
`C.\Users\%USERNAME%\AppData\Local\pypoetry\Cache`).

## Execution

### For `pip` installation

To execute the program use
```
python -m citation_graph "<DOI>"
```

### For manual and development installation

To execute the program use
```bash
poetry run python -m citation_graph
```

### Parameters

```
citation_graph  [-h] [--version] [-v] [-vv] [--max-depth MAX_DEPTH] [--clear-cache]
                [--cache-path CACHE_PATH]
                [--max-citations-per-paper MAX_CITATIONS_PER_PAPER]
                [--politeness POLITENESS_FACTOR]
                [--max-request-errors MAX_REQUEST_ERRORS]
                [--exclude-papers [EXCLUDED_PAPERS ...]] [--list]
                [--list-file-name LIST_FILE_NAME] [--no-graph]
                [--database-config DATABASE_CONFIG]
                [{doi,dblp,arxiv,corpusid}] id [name]
```

**positional arguments**
- `{doi,dblp,arxiv,corpusid}` The id type, default is doi
- `id` The id of the paper to use as the root, by default an doi is assumed, this can
  be changed with the ID_TYPE parameter
- `name` The name of the graph output html file, if not given, it will be in the current
  working directory with the authors and the year as the file name.

**optional arguments**
- `-h`, `--help` Show this help message and exit
- `--version`, `-V` Show program's version number and exit
- `-v`, `--verbose` Set the loglevel to INFO
- `-vv`, `--very-verbose` Set the loglevel to DEBUG
- `--max-depth MAX_DEPTH`, `-d MAX_DEPTH` The maximum depth to search papers, if 0, only
  the root paper is included in the result, default is 1
- `--clear-cache`, `-c` Clear the cache before fetching. This ensures fresh data.
- `--max-citations-per-paper MAX_CITATIONS_PER_PAPER`, `-m MAX_CITATIONS_PER_PAPER` The
  maximum amount of citations to collect per paper, default is 300
- `--politeness POLITENESS_FACTOR`, `-p POLITENESS_FACTOR` A factor that is multiplied
  with the idle time that each database traverser waits between two requests, using
  values >1 will be more polite but slow down the requests, values <1 will be faster but
  may cause your IP being blocked, default is 1
- `--max-request-errors MAX_REQUEST_ERRORS`, `-e MAX_REQUEST_ERRORS` The maximum number
  of subsequent errors when requesting paper citations. If more than this specified
  amount of errors occurs, a (temporary) block of requests is assumed by the database
  due to too many requests. The default is 10
- `--exclude-papers [EXCLUDED_PAPERS ...]`, `-x [EXCLUDED_PAPERS ...]` Define papers to
  exclude from the result set, including intermediate result sets. This allows to
  prevent fetching citations of papers that are not relevant for the current research
  and therefore narrow down the selection. To define papers, use any id type followed by
  the id, separated by '::', like so: {doi|dblp|arxiv|corpusid}::PAPER_ID. Alternatively
  a path to a file can be given where the paper ids are listed, each paper id in a
  separate line. Lines starting with a '#'-character are treated as comments and are
  ignored entirely.
- `--list`, `-l` Output a list containing the papers, ordered by their level.
- `--list-file-name LIST_FILE_NAME`, `-n LIST_FILE_NAME` The file name of the list file,
  by default the authors and the year are the file name. The file is created in the
  current working directory
- `--no-graph`, `-g` Use to prevent creating a visualization graph
- `--database-config DATABASE_CONFIG`, `-s DATABASE_CONFIG` The path for additional
  settings for the databases, e.g. API keys. Each database has its own section, the keys
  depend on the database. If not given, the program will look for a file with the name
  config.ini in the current working directory

## Supported databases

- ✅ https://semanticscholar.org/
- ❌ https://api.crossref.org - Needs (payed) plus access, will not be implemented (in near future)
- ❌ https://developer.ieee.org/ - Citations not supported
- ⏳ https://api.base-search.net/
- ⏳ https://core.ac.uk/services/api
- ⏳ https://dev.elsevier.com/
- ⏳ http://developers.amctheatres.com/
- ⏳ Academic Knowledge API