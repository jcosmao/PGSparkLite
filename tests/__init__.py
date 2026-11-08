import os
import tempfile

# Never touch the real pgsparklite.db: database.model opens (and migrates)
# the database at import time, so point it at a throwaway file first.
_tmp = tempfile.mkdtemp(prefix='pgsparklite-tests-')
os.environ['PGSPARKLITE_DB'] = os.path.join(_tmp, 'test.db')
