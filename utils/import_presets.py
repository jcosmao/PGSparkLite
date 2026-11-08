#####################################################
# Import a folder of Spark preset JSON files as
# PGSparkLite Chain Presets.
#
# Usage (from the project root):
#   python3 -m utils.import_presets <folder>
#####################################################

import sys

from lib.presetimport import import_preset_folder


def main():
    if len(sys.argv) != 2:
        print('Usage: python3 -m utils.import_presets <folder>')
        sys.exit(1)

    result = import_preset_folder(sys.argv[1])

    print('Imported: ' + str(len(result['imported'])))
    print('Skipped (already present): ' + str(len(result['skipped'])))
    print('Errors: ' + str(len(result['errors'])))
    for filename, reason in result['errors']:
        print('  ' + filename + ': ' + reason)


if __name__ == '__main__':
    main()
