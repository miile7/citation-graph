# Changelog

## Version 1.2.7
- Fix security vulnerability due to IPython version

## Version 1.2.6
- Improve README
- Fix loading old cache files
- Improve robustness against cache file errors
- Fix loading cache file error

## Version 1.2.5
- Remove `setuptools` to prevent usage of https://access.redhat.com/security/cve/CVE-2022-40897
- Add APIs to README

## Version 1.2.4
- Add test for `Paper`
- Add equality checks for `Paper`
- Introduce `RestfulDatabase` for further databases

## Version 1.2.3

- Minor fixes of README.md
- Minor adjustments for pypi.org release

## Version 1.2.2

- Bug fixes
- Improve README.md
- Support API keys

## Version 1.2.1

- Bug fixes
- Improved speed by skipping waiting before cached papers
- Improving cache lookup to prevent collecting papers missing until limit is reached
- Allow to exclude papers
- Add list mode
- Add customizable log / cache file
- Improve graph tooltip information
- Overwork cache / log file to contain request limits

## Version 1.2.0

- More granular caching
- Allow reuse of cached entries with modified arguments
- Restructure code base
- Skip unnecessary waiting time
- Skip papers where citation count is zero
- Fix maximum number of citations
- New GUI

## Version 1.1.0

- Better colors
- Bugfixes

## Version 1.0.0

Initial version