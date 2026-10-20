"""Versioned proposed registry plus preserved legacy IDs and permanent history."""
from dataclasses import dataclass, replace
import json
from pathlib import Path
import re

from city_core.catalog import baseline_catalog
from .records import LiveError, identifier

UNITS = {'water_level': 'cm', 'flow': 'L/s', 'pressure': 'bar', 'temperature': '°C',
         'traffic_count': 'veh/min', 'traffic_camera': 'veh/min',
         'power_load': 'kW', 'air_quality': 'ug/m3', 'emergency_call': 'calls'}


@dataclass(frozen=True, slots=True)
class Sensor:
    sensor_id: str
    zone_id: str
    type: str
    unit: str
    description: str
    normal_limits: tuple
    hard_limits: tuple
    interval: int
    linked_device_ids: tuple
    backup_ids: tuple
    source: str | None
    proposal: bool = True
    active: bool = True
    replaces: str | None = None
    registered_tick: int = 0
    registered_run_id: str | None = None


def proposed_registry():
    path = Path(__file__).with_name('data') / 'sensors.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    entries = tuple(Sensor(**{**row, **{key: tuple(row[key]) for key in
        ('normal_limits', 'hard_limits', 'linked_device_ids', 'backup_ids')}}) for row in data['sensors'])
    validate_registry(entries)
    return entries


def validate_registry(entries):
    ids = [r.sensor_id for r in entries]
    if len(set(ids)) != len(ids):
        raise LiveError('DUPLICATE_ID')
    for row in entries:
        identifier(row.sensor_id)
        if (row.type not in UNITS or row.unit != UNITS[row.type] or row.interval not in (5, 10, 60)
                or not row.hard_limits[0] <= row.normal_limits[0] <= row.normal_limits[1] <= row.hard_limits[1]):
            raise LiveError('INVALID_REGISTRY')
        if row.proposal and not re.fullmatch(r'(PRT|IND|DTN|RES)-(WLV|FLW|PRS|TMP|TRF)-[0-9]{2}', row.sensor_id):
            raise LiveError('INVALID_REGISTRY')
        if any(other not in ids or other == row.sensor_id for other in row.backup_ids):
            raise LiveError('INVALID_REGISTRY')


def load_registry():
    legacy = []
    for device in baseline_catalog()['devices']:
        if not device['id'].startswith('S-'):
            continue
        family, target = device['family'], device['target_id']
        limits, interval, source = (0, 1000000), 10, None
        if family == 'water_level':
            source = {'B-01': 'basin', 'RIVER-01': 'river', 'FLOOD-01': 'surface'}[target]
            limits, interval = (0, 300), 5
        elif family == 'traffic_camera':
            source = f'departures:{target}'
        elif family == 'power_load':
            source = f'power:{target}'
        elif family == 'air_quality':
            source, interval = f'air:{target}', 60
        legacy.append(Sensor(device['id'], device['location_id'], family, UNITS[family],
            f'Local aggregate {family} adapter for {target}', limits, limits, interval,
            (), (), source, proposal=False))
    return tuple(sorted((*proposed_registry(), *legacy), key=lambda row: row.sensor_id))


def replacement(registry, old_id, new_id, tick, run_id=None):
    identifier(new_id)
    if new_id != new_id.upper():
        raise LiveError('INVALID_ARGUMENT')
    if len(registry) >= 128:
        raise LiveError('BUDGET_EXHAUSTED')
    if any(row.sensor_id == new_id for row in registry):
        raise LiveError('DUPLICATE_ID')
    old = next((row for row in registry if row.sensor_id == old_id and row.active), None)
    if old is None:
        raise LiveError('SENSOR_NOT_FOUND')
    if old.proposal and (not re.fullmatch(re.escape(old_id[:-2]) + r'[0-9]{2}', new_id)
                         or int(new_id[-2:]) <= int(old_id[-2:])):
        raise LiveError('INVALID_ARGUMENT')
    new = replace(old, sensor_id=new_id, replaces=old_id, registered_tick=tick, registered_run_id=run_id)
    result = (*tuple(replace(row, active=False) if row.sensor_id == old_id else row
                     for row in registry), new)
    validate_registry(result)
    return result
