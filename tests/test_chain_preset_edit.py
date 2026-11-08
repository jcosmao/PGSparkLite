import unittest

from database.model import ChainPreset, PedalParameter, PedalPreset, parse_tags
from database.service import (edit_chain_preset, get_chain_preset_tags,
                              rename_pedal_preset)


def make_pedal():
    pedal = PedalParameter(effect_name='Booster', on_off='On', visible=True)
    pedal.store_parameters([0.5])
    pedal.save()
    return pedal


def make_chain_preset(name, tags=''):
    pedals = [make_pedal() for _ in range(7)]
    preset = ChainPreset(name=name, uuid=name, bpm=120, tags=tags)
    (preset.gate_pedal, preset.comp_pedal, preset.drive_pedal,
     preset.amp_pedal, preset.mod_pedal, preset.delay_pedal,
     preset.reverb_pedal) = pedals
    preset.save()
    return preset


class ParseTagsTest(unittest.TestCase):

    def test_trims_lowercases_dedupes_and_sorts(self):
        self.assertEqual(parse_tags(' Surf, rock ,ROCK,,  live  set '),
                         ['live set', 'rock', 'surf'])

    def test_empty(self):
        self.assertEqual(parse_tags(''), [])
        self.assertEqual(parse_tags(None), [])

    def test_accepts_a_list(self):
        self.assertEqual(parse_tags(['Blues', 'blues', 'Clean']),
                         ['blues', 'clean'])


class EditPresetsTest(unittest.TestCase):

    def setUp(self):
        for model in (ChainPreset, PedalPreset, PedalParameter):
            model.delete().execute()

    def test_rename_and_tag_chain_preset(self):
        preset = make_chain_preset('Old')
        edited = edit_chain_preset(preset.id, '  New name ', 'Rock, surf')
        self.assertEqual(edited.name, 'New name')
        stored = ChainPreset.get_by_id(preset.id)
        self.assertEqual(stored.name, 'New name')
        self.assertEqual(stored.tags, 'rock,surf')
        self.assertEqual(stored.tag_list(), ['rock', 'surf'])

    def test_clearing_tags(self):
        preset = make_chain_preset('A', tags='rock')
        edit_chain_preset(preset.id, 'A', '')
        self.assertEqual(ChainPreset.get_by_id(preset.id).tag_list(), [])

    def test_empty_name_is_refused(self):
        preset = make_chain_preset('Keep')
        self.assertIsNone(edit_chain_preset(preset.id, '   ', 'rock'))
        stored = ChainPreset.get_by_id(preset.id)
        self.assertEqual(stored.name, 'Keep')
        self.assertEqual(stored.tags, '')

    def test_unknown_chain_preset(self):
        self.assertIsNone(edit_chain_preset(9999, 'X', ''))

    def test_all_tags_sorted_and_unique(self):
        make_chain_preset('A', tags='rock,surf')
        make_chain_preset('B', tags='blues,rock')
        make_chain_preset('C')
        self.assertEqual(get_chain_preset_tags(), ['blues', 'rock', 'surf'])

    def test_rename_pedal_preset(self):
        preset = PedalPreset.create(name='Old', pedal_parameter=make_pedal(),
                                    effect_name='Booster')
        self.assertEqual(rename_pedal_preset(preset.id, ' Crunch ').name,
                         'Crunch')
        self.assertEqual(PedalPreset.get_by_id(preset.id).name, 'Crunch')
        self.assertIsNone(rename_pedal_preset(preset.id, ''))
        self.assertIsNone(rename_pedal_preset(9999, 'X'))


if __name__ == '__main__':
    unittest.main()
