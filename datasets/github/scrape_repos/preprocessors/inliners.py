"""Preprocessors to inline includes."""
import collections
import pathlib
import re
import subprocess
import typing

from absl import flags
from absl import logging
from fuzzywuzzy import process

from datasets.github.scrape_repos.preprocessors import public
from lib.labm8 import bazelutil
from lib.labm8 import fs


FLAGS = flags.FLAGS

# The set of standard headers available in C99.
C99_HEADERS = {
  'assert.h', 'complex.h', 'ctype.h', 'errno.h', 'fenv.h', 'float.h',
  'inttypes.h', 'iso646.h', 'limits.h', 'locale.h', 'math.h', 'setjmp.h',
  'signal.h', 'stdalign.h', 'stdarg.h', 'stdatomic.h', 'stdbool.h', 'stddef.h',
  'stdint.h', 'stdio.h', 'stdlib.h', 'stdnoreturn.h', 'string.h', 'tgmath.h',
  'threads.h', 'time.h', 'uchar.h', 'wchar.h', 'wctype.h',
}


@public.dataset_preprocessor
def CxxHeaders(import_root: pathlib.Path, file_relpath: str, text: str) -> str:
  """Inline C++ includes.

  Searches for occurrences of '#include <$file>' and attempts to resolve $file
  to a path within import_root. If successful, the include directive is
  replaced.

  Args:
    import_root: The root of the directory to import from.
    file_relpath: The path to the target file to import, relative to
      import_root.
    text: The text of the target file to inline the headers of.

  Returns:
    The contents of the file file_relpath, with included headers inlined.
  """
  return _InlineCSyntax(import_root, file_relpath, text, False,
                        GetLibCxxHeaders().union(C99_HEADERS))


@public.dataset_preprocessor
def CxxHeadersDiscardUnknown(import_root: pathlib.Path,
                             file_relpath: str, text: str) -> str:
  """Inline C++ includes, but discard include directives that were not found.

  Like CxxHeaders(), but if a file included by '#include' is not found, the
  include directive is removed from the output.

  Args:
    import_root: The root of the directory to import from.
    file_relpath: The path to the target file to import, relative to
      import_root.
    text: The text of the target file to inline the headers of.

  Returns:
    The contents of the file file_relpath, with included headers inlined.
  """
  return _InlineCSyntax(import_root, file_relpath, text, True,
                        GetLibCxxHeaders().union(C99_HEADERS))


def _InlineCSyntax(import_root: pathlib.Path, file_relpath: str, text: str,
                   discard_unknown: bool, blacklist: typing.Set[str]):
  """Private helper function to inline C preprocessor '#include' directives.

  One known caveat is that this approaches loses whether or not the include
  path was defined using angle brackets or quote. With this implementation,
  *all* includes are re-written using quotes syntax. I don't think this is a
  great concern, as it would be an extreme edge case were a file to, say,
  include "stdio.h" and *not* mean the stdlib.
  """
  include_re = re.compile(r'^\w*#include ["<](?P<path>[^>"]*)[">].*')

  def FindIncludes(line: str) -> typing.List[str]:
    """Callback to find #include directives and return their path."""
    match = include_re.match(line)
    if match:
      return [match.group('path')]
    else:
      return []

  return InlineHeaders(
      import_root, file_relpath, text,
      inline_candidate_relpaths=set(GetAllFilesRelativePaths(import_root)),
      already_inlined_relpaths=set(),
      blacklist=blacklist,
      find_includes=FindIncludes,
      format_include=lambda line: f'#include "{line}"',
      format_line_comment=lambda line: f'// [InlineHeaders] {line}',
      discard_unmatched_headers=discard_unknown)


def InlineHeaders(import_root: pathlib.Path,
                  file_relpath: str,
                  text: str,
                  inline_candidate_relpaths: typing.Set[str],
                  already_inlined_relpaths: typing.Set[str],
                  blacklist: typing.Set[str],
                  find_includes: typing.Callable[[str], typing.List[str]],
                  format_include: typing.Callable[[str], str],
                  format_line_comment: typing.Callable[[str], str],
                  discard_unmatched_headers: bool) -> str:
  """Recursively inline included files and return the inlined text.

  Args:
    import_root: The root directory to search for included files.
    file_relpath: The path of the file to process, relative to import_root.
    text: The text of the target file to inline the headers of.
    inline_candidate_relpaths: Paths to all files which are candidates for
      inlining, relative to import_root.
    already_inlined_relpaths: Paths to files which have already been inlined.
      Files are never inlined twice. Duplicate inlines are always discarded.
    blacklist: A set of files to exclude from inlining.
    find_includes: A callback which searches a line of code and returns
      zero or more paths included by it.
    format_include: A callback which formats an include using the syntax of the
      target programming language. It accepts as argument a path as returned by
      find_includes(), so these are semantically equivalent in the target
      programming language (though they may produce different code):
      [format_include(f) for f in find_includes(line)] == line
    format_line_comment: A callback which formats a line of text as a comment
      in the programming language. The callback is responsible for escaping
      the contents of the line.
    discard_unmatched_headers: If True, included paths which cannot be resolved
      are discarded.

  Returns:
    The path with as many included files inlined as possible.
  """
  logging.debug('Inlining: %s.', file_relpath)
  inline_candidate_relpaths.remove(file_relpath)
  already_inlined_relpaths.add(file_relpath)
  output = []

  for line in text.split('\n'):
    includes = find_includes(line)
    if not includes:
      output.append(line)
      continue

    for include in includes:
      already_inlined_match = FindCandidateInclude(
          include, file_relpath, already_inlined_relpaths,
          exact_matches_only=True)
      if already_inlined_match.confidence == 100:
        output.append(format_line_comment(
            f"Skipping already inlined file: '{already_inlined_match}'."))
        continue

      blacklist_match = FindCandidateInclude(include, file_relpath, blacklist,
                                             exact_matches_only=True)
      if blacklist_match.confidence == 100:
        output.append(format_line_comment(
            f"Preserving blacklisted include: '{include}'."))
        output.append(format_include(include))
        continue

      candidate_match = FindCandidateInclude(
          include, file_relpath, inline_candidate_relpaths)
      if candidate_match.confidence:
        output.append(format_line_comment(
            f"Found candidate include for: "
            f"'{include}' -> '{candidate_match.path}' "
            f'({candidate_match.confidence}% confidence).'))
        with open(import_root / candidate_match.path) as f:
          candidate_text = f.read()
        output.append(InlineHeaders(
            import_root, candidate_match.path, candidate_text,
            inline_candidate_relpaths,
            already_inlined_relpaths, blacklist, find_includes, format_include,
            format_line_comment, discard_unmatched_headers))
        continue

      # No match found :(
      if discard_unmatched_headers:
        output.append(format_line_comment(
            f"Discarding unmatched include: '{include}'."))
      else:
        output.append(format_line_comment(
            f"Preserving unmatched include: '{include}'."))
        output.append(format_include(include))

  return '\n'.join(output)


FuzzyIncludeMatch = collections.namedtuple(
    'FuzzyIncludeMatch', ['path', 'confidence'])


def FindCandidateInclude(
    include_match: str, current_file_relpath: str,
    candidate_relpaths: typing.Set[str],
    exact_matches_only: bool = False) -> FuzzyIncludeMatch:
  """Find and return the most likely included file.

  Args:
    include_match: The path of the file to find a candidate include for.
    current_file_relpath: The path of the file we're currently processing.
    candidate_relpaths: The set of files to consider for matching.
    exact_matches_only: If True, do no fuzzy matching of possible candidates.

  Returns:
    A FuzzyIncludeMatch instance. If no suitable candidate was found, the path
    will be an empty string, and the confidence will be 0.0. Else, the path
    is the member of candidate_relpaths which is most likely, and the confidence
    is an integer between between 0 and 100, where 100 indicates a perfect
    match.
  """
  if include_match in candidate_relpaths:
    return FuzzyIncludeMatch(include_match, 100)

  # A list of files with the same basename as include match's basename
  candidate_matches = [
    x for x in candidate_relpaths if x.endswith(include_match)]
  if candidate_matches and not exact_matches_only:
    # Fuzzy match to find the most likely include.
    choices = (
        process.extract(include_match, candidate_matches) +
        process.extract(pathlib.Path(current_file_relpath).name,
                        candidate_matches)
    )
    return FuzzyIncludeMatch(*max(choices, key=lambda x: x[1]))
  else:
    return FuzzyIncludeMatch('', 0)


def GetAllFilesRelativePaths(root_dir: pathlib.Path) -> typing.List[str]:
  """Get relative paths to all files in the root directory.

  Follows symlinks.

  Args:
    root_dir: The directory to find files in.

  Returns:
    A list of paths relative to the root directory.

  Raises:
    EmptyCorpusException: If the content files directory is empty.
  """
  with fs.chdir(root_dir):
    find_output = subprocess.check_output(
        ['find', '-L', '.', '-type', 'f']).decode('utf-8').strip()
  if find_output:
    # Strip the leading './' from paths.
    return [x[2:] for x in find_output.split('\n')]
  else:
    return []


def GetLibCxxHeaders() -> typing.Set[str]:
  """Enumerate the set of headers in the libcxx standard lib."""
  return set(GetAllFilesRelativePaths(bazelutil.DataPath('libcxx/include')))
