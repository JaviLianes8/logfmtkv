# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

- Add `parse` to read a logfmt line into a typed mapping, with a bare key yielding `True`.
- Add `serialize` to write a mapping back to a logfmt line, quoting only when needed and
  omitting `False`.
