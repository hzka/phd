import pathlib
import typing

from absl import app
from absl import flags
from absl import logging

from util.freefocus import sql


FLAGS = flags.FLAGS

flags.DEFINE_string(
    'database_path', '/tmp/phd/util/freefocus/freefocus.db',
    'Path to database.')

SPEC_MAJOR = 1
SPEC_MINOR = 0
SPEC_MICRO = 0

__freefocus_spec__ = f"{SPEC_MAJOR}.{SPEC_MINOR}.{SPEC_MICRO}"


def main(argv: typing.List[str]):
  """Main entry point."""
  if len(argv) > 1:
    raise app.UsageError("Unknown arguments: '{}'.".format(' '.join(argv[1:])))

  database_path = pathlib.Path(FLAGS.database_path)

  database_path.parent.mkdir(parents=True, exist_ok=True)
  db = sql.Database(database_path)
  logging.info(db)


if __name__ == '__main__':
  app.run(main)
