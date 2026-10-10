"""Anonymous Datamart file notifications; no directory polling or URL following."""
from __future__ import annotations

import re
import ssl
import threading
from uuid import uuid4

import pika

from rdr.storage import log, now


class DatamartNotifications:
    """Coalesce notifications for configured Alberta hourly hydrometric files."""

    def __init__(self, station_ids, stop):
        self.station_ids = set(station_ids)
        self.stop = stop
        self.ready = threading.Event()
        self.connected = threading.Event()
        self.lock = threading.Lock()
        self.pending = set()
        self.notifications = 0
        self.error = None
        self.thread = None

    def accept(self, body):
        text = body.decode('utf-8')
        # Notifications are evidence only. Downloads use configured HTTPS URLs.
        match = re.search(r'(?:^|/|\s)hydrometric/csv/AB/hourly/AB_(05[A-Z0-9]{5})_hourly_hydrometric\.csv(?:\s|$)', text)
        if not match or match[1] not in self.station_ids:
            return
        with self.lock:
            self.pending.add(match[1])
            self.notifications += 1
        log({'event': 'datamart_notification', 'station': match[1],
             'received_at_utc': now(), 'notice': text})

    def take(self, station_id):
        with self.lock:
            if station_id not in self.pending:
                return False
            self.pending.remove(station_id)
            return True

    def restore(self, station_id):
        with self.lock:
            self.pending.add(station_id)

    def start(self):
        self.thread = threading.Thread(target=self._listen, daemon=True,
                                       name='datamart-notifications')
        self.thread.start()
        if not self.ready.wait(30) or not self.connected.is_set():
            raise RuntimeError(f'Datamart notification subscription failed: {self.error or "timeout"}')

    def _listen(self):
        while not self.stop.is_set():
            connection = None
            try:
                host = 'dd.weather.gc.ca'
                parameters = pika.ConnectionParameters(
                    host, 5671, '/', pika.PlainCredentials('anonymous', 'anonymous'),
                    ssl_options=pika.SSLOptions(ssl.create_default_context(), host),
                    heartbeat=30, socket_timeout=10, stack_timeout=20,
                    blocked_connection_timeout=10, connection_attempts=1)
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()
                queue = 'q_anonymous.RedDeerRiver.' + uuid4().hex
                channel.queue_declare(queue=queue, exclusive=True, auto_delete=True,
                                      arguments={'x-expires': 600000})
                for topic in ('v02.post.*.WXO-DD.hydrometric.csv.AB.hourly.#',
                              'v02.post.hydrometric.csv.AB.hourly.#'):
                    channel.queue_bind(queue=queue, exchange='xpublic', routing_key=topic)
                channel.basic_qos(prefetch_count=20)
                self.connected.set()
                self.error = None
                self.ready.set()
                log({'event': 'datamart_amqps_connected', 'at': now()})
                for method, properties, body in channel.consume(queue, inactivity_timeout=1):
                    if self.stop.is_set():
                        break
                    if method:
                        self.accept(body)
                        channel.basic_ack(method.delivery_tag)
                channel.cancel()
                channel.queue_delete(queue=queue)
            except Exception as exc:
                self.error = f'{type(exc).__name__}: {exc}'
                log({'event': 'datamart_amqps_error', 'error': self.error, 'at': now()})
                if not self.ready.is_set():
                    self.ready.set()
                    return
            finally:
                self.connected.clear()
                if connection is not None and connection.is_open:
                    try:
                        connection.close()
                    except Exception:
                        pass
            if not self.stop.is_set():
                self.stop.wait(30)

    def close(self):
        if self.thread is not None:
            self.thread.join(timeout=25)

    def status(self):
        with self.lock:
            return {'connected': self.connected.is_set(),
                    'notifications_received': self.notifications,
                    'pending_station_count': len(self.pending), 'error': self.error}
