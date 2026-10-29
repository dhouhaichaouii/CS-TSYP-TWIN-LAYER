"""One serialized real-core owner, with wall pacing outside fixed-step physics."""
from dataclasses import replace
from functools import wraps
from threading import Condition, RLock, Thread, current_thread
import time

from city_core import build_city
from city_core.catalog import CONTRACT_VERSION
from city_core.effect_records import DRIVERS
from city_core.replay import export_replay
from city_core.transitions import freeze, plain
from .history import PublicReader, PublicStore
from .records import (Action, EPOCH, Event, LiveError, VERSION, identifier, integer,
                      numeric, require, timestamp, utc_epoch)
from .scenarios import PRESETS, effect_for, validate
from .sensors import SensorBank
from .demand import TrafficDemand
from .operator import OperatorControls
from .sensor_physics import SensorPhysics, advance as advance_sensor_physics, measurements


def serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._condition:
            if self._state == 'CLOSED':
                raise LiveError('CLOSED')
            return method(self, *args, **kwargs)
    return call


class LiveCity(OperatorControls):
    def __init__(self, run_id='live-001', *, seed=1, epoch=EPOCH, history_limit=512,
                 action_limit=2048, tick_budget=10000):
        identifier(run_id)
        integer(seed, 0, 2**63 - 1)
        self._epoch = utc_epoch(epoch)
        self._history_limit = integer(history_limit, 1, 10000)
        self._action_limit = integer(action_limit, 1, 2048)
        self._tick_budget = integer(tick_budget, 1, 50000)
        self._condition = Condition(RLock())
        self._core = require(build_city(run_id))
        self._run_id, self._seed = run_id, seed
        self._state, self._speed, self._error = 'READY', 1.0, None
        self._thread = None
        self._dashboard_seq = 0
        self._operator_requests = freeze({})
        self._store = PublicStore(limit=self._history_limit)
        self.public = PublicReader(self._store)
        self._sensors = SensorBank(seed, self._epoch)
        self._reset_adapters()

    def _reset_adapters(self):
        self._actions, self._commands, self._events = (), freeze({}), ()
        self._effect_counter, self._private_seq = 0, 0
        self._traffic = TrafficDemand(self._seed)
        self._sensor_physics = SensorPhysics()
        self._sensors.reset()
        self._store.reset(self._run_id)

    def _snapshot(self):
        return require(self._core.observations.read_private(self._run_id))

    def _event(self, kind, details):
        self._private_seq += 1
        tick = self._snapshot().context.tick
        event = Event(self._private_seq, self._run_id, tick, timestamp(self._epoch, tick),
                      kind, freeze(details), f'{self._run_id}:ev-{self._private_seq:010d}',
                      details.get('zone_id'), details.get('device_id', details.get('sensor_id')),
                      details.get('action_id'))
        self._events = (*self._events, event)[-self._history_limit:]

    def _effect(self, effect):
        context = self._snapshot().context
        source = 'B_SCENARIO' if effect['tag'] in DRIVERS else 'B_ACTUATOR'
        effect_id = f'live-{self._effect_counter + 1:010d}'
        request = {'contract_version': CONTRACT_VERSION, 'run_id': self._run_id,
                   'effect_id': effect_id, 'expected_revision': context.revision,
                   'source': source, 'correlation_id': effect_id, 'effect': effect}
        handle = self._core.scenarios if source == 'B_SCENARIO' else self._core.actuators
        receipt = require(handle.apply_effect(request))
        self._effect_counter += 1
        return receipt

    def _run_check(self, run_id):
        identifier(run_id)
        if run_id != self._run_id:
            raise LiveError('OLD_RUN')

    def _execute(self, action):
        self._event('ACTION_REQUESTED', {'action_id': action.action_id})
        try:
            if action.kind == 'sensor_fault':
                self.sensor_fault(action.params['sensor_id'], action.params['fault_type'],
                                  plain(action.params['parameters']))
            elif action.kind == 'sensor_clear':
                self.sensor_clear(action.params['sensor_id'])
            else:
                effect = effect_for(action.kind, action.params, self._snapshot().physical_state)
                self._effect(effect)
            self._event('ACTION_COMPLETED', {'action_id': action.action_id})
            return replace(action, status='COMPLETED')
        except LiveError as error:
            self._event('ACTION_FAILED', {'action_id': action.action_id, 'code': error.code})
            return replace(action, status='FAILED', error=error.code)

    def _tick(self):
        context = self._snapshot().context
        if context.tick >= self._tick_budget:
            self._state, self._error = 'BUDGET_EXHAUSTED', 'BUDGET_EXHAUSTED'
            raise LiveError('BUDGET_EXHAUSTED')
        self._actions = tuple(self._execute(action) if action.status == 'PENDING'
            and action.due_tick <= context.tick else action for action in self._actions)
        physical = self._snapshot().physical_state
        rates = self._traffic.rates(context.tick, self._epoch.hour + self._epoch.minute / 60)
        for road, rate in rates.items():
            self._effect({'tag': 'road_driver', 'target_id': road,
                'arrival_rate_veh_s': rate, 'obstruction_fraction': physical.roads[road].obstruction_fraction})
        before = self._snapshot()
        committed = require(self._core.lifecycle.advance_one(self._run_id, before.context.revision))
        departures = {road: max(0, old.queue_vehicles + old.arrival_rate_veh_s
            - committed.physical_state.roads[road].queue_vehicles)
            for road, old in before.physical_state.roads.items()}
        self._sensor_physics = advance_sensor_physics(self._sensor_physics, committed, self._epoch)
        expired = self._sensors.capture(committed, departures, measurements(self._sensor_physics))
        for sensor_id in expired:
            self._event('FAULT_CLEARED', {'sensor_id': sensor_id, 'automatic': True})
        previous = self._sensors.latest
        with self._store.lock:
            readings = self._sensors.sample(committed.context.tick, self._store.append)
        for reading in readings:
            prior = previous.get(reading['sensor_id'])
            if prior is not None and prior['status'] != reading['status']:
                self._event('STATUS_CHANGED', {'sensor_id': reading['sensor_id'],
                    'zone_id': reading['zone_id'], 'from': prior['status'], 'to': reading['status'],
                    'observation_seq': reading['seq'], 'delivery_tick': reading['delivery_tick']})

    def _loop(self):
        with self._condition:
            while self._state != 'CLOSED':
                while self._state != 'RUNNING' and self._state != 'CLOSED':
                    self._condition.wait()
                if self._state == 'CLOSED':
                    return
                # No catch-up burst: overload slows wall progression, never skips ticks.
                if self._condition.wait(timeout=1 / self._speed):
                    continue
                try:
                    self._tick()
                except LiveError as error:
                    self._state = 'BUDGET_EXHAUSTED' if error.code in ('BUDGET_EXHAUSTED', 'MODEL_LIMIT') else 'ERROR'
                    self._error = error.code
                except Exception:
                    self._state, self._error = 'ERROR', 'INTERNAL_ERROR'

    @serialized
    def start(self):
        if self._state not in ('READY', 'STOPPED', 'PAUSED', 'RUNNING'):
            raise LiveError('INVALID_STATE')
        self._state = 'RUNNING'
        if self._thread is None:
            self._thread = Thread(target=self._loop, name='twin-city-owner', daemon=False)
            self._thread.start()
        self._condition.notify_all()

    @serialized
    def pause(self):
        if self._state not in ('RUNNING', 'PAUSED'):
            raise LiveError('INVALID_STATE')
        self._state = 'PAUSED'
        self._condition.notify_all()

    def resume(self):
        self.start()

    @serialized
    def stop(self):
        if self._state in ('ERROR', 'BUDGET_EXHAUSTED'):
            raise LiveError('RESET_REQUIRED')
        self._state = 'STOPPED'
        self._condition.notify_all()

    @serialized
    def step(self):
        if self._state not in ('READY', 'PAUSED', 'STOPPED'):
            raise LiveError('INVALID_STATE')
        try:
            self._tick()
        except LiveError as error:
            self._state = 'BUDGET_EXHAUSTED' if error.code in ('BUDGET_EXHAUSTED', 'MODEL_LIMIT') else 'ERROR'
            self._error = error.code
            raise
        return self.status()

    @serialized
    def set_speed(self, speed):
        self._speed = numeric(speed, .5, 10)
        self._condition.notify_all()

    @serialized
    def reset(self, new_run_id):
        identifier(new_run_id)
        current = self._snapshot().context
        require(self._core.lifecycle.reset(self._run_id, current.revision, new_run_id))
        self._run_id = new_run_id
        self._state, self._error = 'READY', None
        self._reset_adapters()
        self._condition.notify_all()

    def close(self):
        with self._condition:
            self._state = 'CLOSED'
            self._condition.notify_all()
        if self._thread is not None and current_thread() is not self._thread:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise LiveError('SHUTDOWN_TIMEOUT')

    def status(self):
        with self._condition:
            context = self._snapshot().context
            return {'schema_version': VERSION, 'run_id': self._run_id, 'state': self._state,
                    'sim_tick': context.tick, 'revision': context.revision,
                    'timestamp': timestamp(self._epoch, context.tick), 'speed': self._speed,
                    'error': self._error, 'tick_budget': self._tick_budget,
                    'pending_actions': sum(a.status == 'PENDING' for a in self._actions)}

    @serialized
    def capture_dashboard_frame(self):
        """Detached private presentation capture, serialized with all city writes.

        The outer owner lock remains held through every nested read. The sequence
        orders captures across resets; it is never a public observation cursor.
        No browser package is imported into the simulation owner.
        """
        self._dashboard_seq += 1
        status = self.status()
        return {'schema_version': 'twin-dashboard-operator-0.1-local',
                'visibility': 'PRIVATE_OPERATOR_ONLY', 'frame_seq': self._dashboard_seq,
                **{key: status[key] for key in ('run_id', 'sim_tick', 'revision', 'timestamp')},
                'status': status, 'diagnostics': self.diagnostics(),
                'comparisons': plain(tuple(self._sensors.latest.values())),
                'readings': self.public.observations(), 'sensors': self.sensors(),
                'actions': self.actions(), 'events': self.events()['events']}

    @serialized
    def schedule(self, action_id, due_tick, kind, params=None, *, run_id):
        self._run_check(run_id)
        identifier(action_id)
        integer(due_tick, 0, self._tick_budget - 1)
        validated = validate(kind, {} if params is None else params)
        if kind in ('sensor_fault', 'sensor_clear'):
            sensor = self._sensors.sensor(validated['sensor_id'])
            if sensor.source is None:
                raise LiveError('SENSOR_UNBOUND')
        candidate = Action(action_id, run_id, due_tick, len(self._actions), kind, validated)
        existing = next((a for a in self._actions if a.action_id == action_id), None)
        if existing:
            if (existing.due_tick, existing.kind, existing.params) != (due_tick, kind, validated):
                raise LiveError('IDENTITY_CONFLICT')
            return plain(existing)
        if due_tick < self._snapshot().context.tick:
            raise LiveError('PAST_TIME')
        if len(self._actions) >= self._action_limit:
            raise LiveError('BUDGET_EXHAUSTED')
        self._actions = (*self._actions, candidate)
        return plain(candidate)

    @serialized
    def cancel(self, action_id, *, run_id):
        self._run_check(run_id)
        found = next((a for a in self._actions if a.action_id == action_id), None)
        if found is None or found.status != 'PENDING':
            raise LiveError('NOT_PENDING')
        self._actions = tuple(replace(a, status='CANCELLED') if a.action_id == action_id else a for a in self._actions)

    @serialized
    def incident(self, kind, params=None):
        action_id = f'operator-{len(self._actions) + 1:08d}'
        while any(a.action_id == action_id for a in self._actions):
            action_id += 'x'
        self.schedule(action_id, self._snapshot().context.tick, kind, params, run_id=self._run_id)
        action = self._execute(self._actions[-1])
        self._actions = (*self._actions[:-1], action)
        return plain(action)

    @serialized
    def traffic(self, name, config=None):
        snapshot = self._snapshot()
        self._traffic.select(name, snapshot.context.tick, snapshot.physical_state.roads, config)

    @serialized
    def run_scenario(self, name, delay=0):
        if name not in PRESETS:
            raise LiveError('UNSUPPORTED_SCENARIO')
        integer(delay)
        start = self._snapshot().context.tick + delay
        rows = PRESETS[name]
        if len(self._actions) + len(rows) > self._action_limit or start + max(row[0] for row in rows) >= self._tick_budget:
            raise LiveError('BUDGET_EXHAUSTED')
        prefix = f'preset-{len(self._actions):08d}'
        while any(a.action_id in {f'{prefix}-{i}' for i in range(len(rows))} for a in self._actions):
            prefix += 'x'
        return [self.schedule(f'{prefix}-{i}', start + offset, kind, plain(params), run_id=self._run_id)
                for i, (offset, kind, params) in enumerate(rows)]

    @serialized
    def export_private_replay(self):
        return plain(require(export_replay(self._core.lifecycle, self._run_id)))
