"""Privileged local diagnostics and provisional device adapter, never public."""
from functools import wraps

from city_core.transitions import freeze, plain
from .records import LiveError, identifier, integer, numeric


def operator_call(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._condition:
            if self._state == 'CLOSED':
                raise LiveError('CLOSED')
            return method(self, *args, **kwargs)
    return call


class OperatorControls:
    @operator_call
    def operator_request(self, envelope):
        """Validate, deduplicate and apply one local privileged intent atomically."""
        from .operator_requests import apply_request
        return apply_request(self, envelope)

    @operator_call
    def diagnostics(self):
        snapshot = self._snapshot()
        return {'visibility': 'PRIVATE_OPERATOR_ONLY', 'context': plain(snapshot.context),
                'physical_state': plain(snapshot.physical_state),
                'power': {**plain(snapshot.power), 'hospital_powered': snapshot.power.hospital_powered},
                'traffic': plain(snapshot.traffic), 'flood': plain(snapshot.flood),
                'access': plain(snapshot.access), 'active_faults': plain(self._sensors.faults),
                'active_disturbances': disturbances(snapshot.physical_state),
                'traffic_profile': self._traffic.profile,
                'water_levels': {'basin_m': snapshot.physical_state.water.basin_level_m,
                                 'surface_m': snapshot.physical_state.water.surface_depth_m}}

    @operator_call
    def actions(self):
        return plain(self._actions)

    @operator_call
    def events(self):
        return {'visibility': 'PRIVATE_OPERATOR_ONLY', 'events': plain(self._events)}

    @operator_call
    def sensors(self):
        return plain(self._sensors.registry)

    @operator_call
    def sensor_compare(self, sensor_id):
        return self._sensors.compare(sensor_id)

    @operator_call
    def sensor_fault(self, sensor_id, kind, params):
        fault = self._sensors.inject(sensor_id, kind, params, self._snapshot().context.tick)
        self._event('FAULT_ACTIVATED', {'sensor_id': sensor_id, 'fault': plain(fault)})
        return plain(fault)

    @operator_call
    def sensor_clear(self, sensor_id):
        self._sensors.clear(sensor_id)
        self._event('FAULT_CLEARED', {'sensor_id': sensor_id})

    @operator_call
    def sensor_repair(self, sensor_id):
        self._sensors.clear(sensor_id, repair=True)
        self._event('FAULT_CLEARED', {'sensor_id': sensor_id, 'repair': True})

    @operator_call
    def sensor_replace(self, old_id, new_id):
        self._sensors.replace(old_id, new_id, self._snapshot().context.tick, self._run_id)
        self._event('DEVICE_REPLACED', {'old_id': old_id, 'new_id': new_id})

    @operator_call
    def command(self, device_id, requested, *, command_id, effective=None, available=True,
                run_id=None, expected_revision=None):
        if run_id is not None:
            self._run_check(run_id)
        if expected_revision is not None:
            integer(expected_revision, 0, 200000)
            if expected_revision != self._snapshot().context.revision:
                raise LiveError('STATE_CONFLICT')
        identifier(command_id)
        if type(available) is not bool:
            raise LiveError('INVALID_ARGUMENT')
        kind, params, actual = command_effect(device_id, requested, effective)
        identity = freeze({'device_id': device_id, 'requested': requested,
                           'effective': effective, 'available': available})
        existing = self._commands.get(command_id)
        if existing:
            if existing['identity'] != identity:
                raise LiveError('IDENTITY_CONFLICT')
            return plain(existing['result'])
        if len(self._commands) >= 1024:
            raise LiveError('BUDGET_EXHAUSTED')
        self._event('ACTION_REQUESTED', {'command_id': command_id, 'device_id': device_id})
        outcome, error = 'FAILED', 'DEVICE_UNAVAILABLE'
        if available:
            from .scenarios import effect_for
            try:
                self._effect(effect_for(kind, params, self._snapshot().physical_state))
                outcome, error = ('COMPLETED' if actual == requested else 'PARTIAL'), None
            except LiveError as failure:
                error = failure.code
        result = freeze({'command_id': command_id, 'device_id': device_id, 'status': outcome,
                         'requested': requested, 'effective': actual if available and error is None else None,
                         'error': error, 'run_id': self._run_id})
        self._commands = freeze({**self._commands, command_id: {'identity': identity, 'result': result}})
        self._event('ACTION_FAILED' if outcome == 'FAILED' else 'ACTION_COMPLETED', plain(result))
        return plain(result)


def command_effect(device_id, requested, effective):
    actual = requested if effective is None else effective
    if device_id == 'A-VALVE-01':
        numeric(requested, 0, 1)
        numeric(actual, 0, 1)
        return 'valve', {'opening': actual}, actual
    if device_id == 'A-PUMP-01':
        if type(requested) is not bool or type(actual) is not bool:
            raise LiveError('INVALID_ARGUMENT')
        return ('pump_on' if actual else 'pump_off'), {}, actual
    if device_id in ('A-SIG-01', 'A-SIG-02'):
        if requested not in ('normal', 'priority', 'stop') or actual not in ('normal', 'priority', 'stop'):
            raise LiveError('UNSUPPORTED_COMMAND')
        return 'signal_' + actual, {
            'target': 'J-D1' if device_id == 'A-SIG-01' else 'J-D2'}, actual
    if device_id in ('A-SW-ESS', 'A-SW-URBAN', 'A-SW-IND'):
        if type(requested) is not bool or type(actual) is not bool:
            raise LiveError('INVALID_ARGUMENT')
        return 'feeder', {'target': 'F-' + device_id[5:], 'closed': actual}, actual
    raise LiveError('UNSUPPORTED_DEVICE')


def disturbances(physical):
    rows = []
    if physical.water.rain_mm_h:
        rows.append({'kind': 'rain', 'target': 'CATCH-01', 'rate_mm_h': physical.water.rain_mm_h})
    if not physical.source.source_available:
        rows.append({'kind': 'power_outage', 'target': 'GRID-01'})
    rows.extend({'kind': 'road_obstruction', 'target': road, 'fraction': state.obstruction_fraction}
                for road, state in physical.roads.items() if state.obstruction_fraction)
    rows.extend({'kind': 'pollution', 'target': zone, 'rate_ug_m3_s': state.external_source_ug_m3_s}
                for zone, state in physical.air.items() if state.external_source_ug_m3_s)
    return rows
