#####################################################
# Preset Import
#
# Converts Spark app preset JSON files (as shared by
# the community, e.g. Ignitron preset collections)
# into PGSparkLite Chain Presets
#####################################################

import glob
import json
import os

from database.service import chain_preset_uuid_exists, import_chain_preset
from lib.common import (dict_BPM, dict_effect, dict_Name, dict_Off, dict_On,
                        dict_OnOff, dict_Parameters, dict_Pedals, dict_UUID,
                        get_js_effect_name)

CONFIG_DIRS = ['config/effects/gate', 'config/amps', 'config/effects/comp',
               'config/effects/mod', 'config/effects/drive',
               'config/effects/delay', 'config/effects/reverb']

# Pedal order in a Spark preset and the config effect type expected at each slot
PEDAL_SLOTS = ['gate', 'comp', 'drive', 'amp', 'modulation', 'delay', 'reverb']

REVERB_TYPE_PARAMETER = 6

_catalogue = None


def _load_catalogue():
    global _catalogue
    if _catalogue is None:
        _catalogue = {slot: set() for slot in PEDAL_SLOTS}
        for config_dir in CONFIG_DIRS:
            for config_file in glob.glob(config_dir + '/*.json'):
                with open(config_file) as f:
                    for effect_id, values in json.load(f).items():
                        _catalogue.setdefault(
                            values[dict_effect], set()).add(effect_id)
    return _catalogue


def _on_off(pedal):
    if 'IsOn' in pedal:
        return dict_On if pedal['IsOn'] else dict_Off
    if pedal.get(dict_OnOff) in (dict_On, dict_Off):
        return pedal[dict_OnOff]
    raise ValueError('pedal ' + str(pedal.get(dict_Name)) + ' has no on/off state')


def convert_preset(data):
    """Convert a Spark app preset dict to a PGSparkLite preset dict.
    Raises ValueError if the preset is invalid or uses unsupported effects."""
    catalogue = _load_catalogue()

    try:
        name = str(data[dict_Name]).strip()
        uuid = str(data[dict_UUID])
        pedals = data[dict_Pedals]
    except (KeyError, TypeError):
        raise ValueError('not a Spark preset (missing Name/UUID/Pedals)')

    if len(pedals) != len(PEDAL_SLOTS):
        raise ValueError('expected 7 pedals, found ' + str(len(pedals)))

    try:
        bpm = int(round(float(data.get(dict_BPM, 120))))
    except (TypeError, ValueError):
        bpm = 120

    converted = []
    for slot, pedal in zip(PEDAL_SLOTS, pedals):
        try:
            parameters = [float(p) for p in pedal[dict_Parameters]]
        except (KeyError, TypeError, ValueError):
            raise ValueError(slot + ' pedal has invalid parameters')

        if slot == 'reverb':
            # PGSparkLite identifies reverb types by the type parameter index
            if len(parameters) <= REVERB_TYPE_PARAMETER:
                raise ValueError('reverb pedal has too few parameters')
            effect_name = str(
                int(round(parameters[REVERB_TYPE_PARAMETER] * 10)))
        else:
            effect_name = get_js_effect_name(str(pedal.get(dict_Name)))

        if effect_name not in catalogue[slot]:
            raise ValueError('unsupported ' + slot + ' effect: ' +
                             str(pedal.get(dict_Name)))

        converted.append({dict_Name: effect_name,
                          dict_OnOff: _on_off(pedal),
                          dict_Parameters: parameters})

    return {dict_Name: name or 'Imported preset',
            dict_UUID: uuid,
            dict_BPM: bpm,
            dict_Pedals: converted}


def import_preset_files(files):
    """Import an iterable of (filename, bytes/str) pairs.
    Returns {'imported': [names], 'skipped': [names], 'errors': [(file, reason)]}"""
    result = {'imported': [], 'skipped': [], 'errors': []}

    for filename, content in files:
        if not filename.lower().endswith('.json'):
            continue
        try:
            preset = convert_preset(json.loads(content))
        except ValueError as e:  # includes JSONDecodeError
            result['errors'].append((filename, str(e)))
            continue

        if chain_preset_uuid_exists(preset[dict_UUID]):
            result['skipped'].append(preset[dict_Name])
            continue

        import_chain_preset(preset)
        result['imported'].append(preset[dict_Name])

    return result


def import_preset_folder(folder):
    paths = sorted(glob.glob(os.path.join(folder, '**', '*.json'),
                             recursive=True))

    def read_files():
        for path in paths:
            with open(path, 'rb') as f:
                yield os.path.relpath(path, folder), f.read()

    return import_preset_files(read_files())
