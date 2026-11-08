import os

from peewee import (BooleanField, CharField, ForeignKeyField, IntegerField,
                    Model, SqliteDatabase)
from playhouse.migrate import SqliteMigrator, migrate

database = SqliteDatabase(os.environ.get('PGSPARKLITE_DB', 'pgsparklite.db'))


class BaseModel(Model):
    id = IntegerField(primary_key=True, unique=True)

    class Meta:
        database = database


class PedalParameter(BaseModel):
    effect_name = CharField()
    on_off = CharField()
    _parameters = CharField()
    visible = BooleanField(default=True)
    pedal_preset_id = IntegerField(null=True)    

    def parameters(self):
        return [float(param) for param in self._parameters.split(',')]

    def store_parameters(self, parameters):
        self._parameters = ','.join(format(param, "1.4f")
                                    for param in parameters)


class PedalPreset(BaseModel):
    name = CharField()
    pedal_parameter = ForeignKeyField(PedalParameter)
    effect_name = CharField(index=True)


def parse_tags(value):
    """'Rock, surf,rock ' -> ['rock', 'surf'] (trimmed, lower case, unique)"""
    if not value:
        return []
    if isinstance(value, str):
        value = value.split(',')
    tags = []
    for tag in value:
        tag = ' '.join(str(tag).split()).lower()
        if tag and tag not in tags:
            tags.append(tag)
    return sorted(tags)


class ChainPreset(BaseModel):
    name = CharField()
    uuid = CharField()
    bpm = IntegerField(default=120)    
    starred = BooleanField(default=False)
    # Comma separated, see parse_tags()
    tags = CharField(default='')
    gate_pedal = ForeignKeyField(PedalParameter)
    comp_pedal = ForeignKeyField(PedalParameter)
    drive_pedal = ForeignKeyField(PedalParameter)
    amp_pedal = ForeignKeyField(PedalParameter)
    mod_pedal = ForeignKeyField(PedalParameter)
    delay_pedal = ForeignKeyField(PedalParameter)
    reverb_pedal = ForeignKeyField(PedalParameter)

    def tag_list(self):
        return parse_tags(self.tags)

    def set_tags(self, tags):
        self.tags = ','.join(parse_tags(tags))


# Create and initialise the database if necessary
database.create_tables([PedalParameter, PedalPreset, ChainPreset])

# Add columns introduced after the initial release to existing databases
if 'starred' not in [c.name for c in database.get_columns('chainpreset')]:
    migrate(SqliteMigrator(database).add_column(
        'chainpreset', 'starred', BooleanField(default=False)))
if 'tags' not in [c.name for c in database.get_columns('chainpreset')]:
    migrate(SqliteMigrator(database).add_column(
        'chainpreset', 'tags', CharField(default='')))
database.close()
