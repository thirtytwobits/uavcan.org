#
# Copyright (C) 2019 UAVCAN Development Team <info@zubax.com>.
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

import json
import datetime
from .. import app
from . import cache


_UPDATE_INTERVAL = 600
_CACHE_LIFETIME = 3600 * 24 * 7


class Entry:
    def __init__(self, text, target_url, image_url, timestamp, is_important):
        self.text = str(text)
        self.image_url = image_url
        self.target_url = target_url
        self.timestamp = timestamp
        self.is_important = bool(is_important)

    @staticmethod
    def new(d: dict):
        is_important = False

        try:
            image_url = d['actor']['avatar_url']
        except KeyError:
            image_url = None

        try:
            target_url = _prepare_url(d['repo']['url'])     # Default
        except KeyError:
            target_url = None

        if d['type'] == 'WatchEvent':
            text = ' '.join([
                _render_url(d['actor']['login'], d['actor']['url']),
                'starred',
                _render_url(d['repo']['name'], d['repo']['url']),
            ])

        elif d['type'] == 'PullRequestEvent' and d['payload']['action'] in ('opened', 'closed', 'reopened'):
            target_url = _prepare_url(d['payload']['pull_request']['html_url'])
            text = ' '.join([
                _render_url(d['actor']['login'], d['actor']['url']),
                d['payload']['action'],
                'a pull request',
                '&ldquo;' +
                _render_url(d['payload']['pull_request']['title'], d['payload']['pull_request']['html_url']) +
                '&rdquo;',
                'at',
                _render_url(d['repo']['name'], d['repo']['url']),
            ])

        elif d['type'] == 'IssuesEvent' and d['payload']['action'] in ('opened', 'closed', 'reopened'):
            target_url = _prepare_url(d['payload']['issue']['html_url'])
            text = ' '.join([
                _render_url(d['actor']['login'], d['actor']['url']),
                d['payload']['action'],
                'an issue',
                '&ldquo;' +
                _render_url(d['payload']['issue']['title'], d['payload']['issue']['html_url']) +
                '&rdquo;',
                'at',
                _render_url(d['repo']['name'], d['repo']['url']),
            ])

        elif d['type'] == 'ForkEvent':
            text = ' '.join([
                _render_url(d['actor']['login'], d['actor']['url']),
                'forked',
                _render_url(d['repo']['name'], d['repo']['url']),
            ])

        elif d['type'] == 'CreateEvent':
            actor = _render_url(d['actor']['login'], d['actor']['url'])
            repo = _render_url(d['repo']['name'], d['repo']['url'])
            if d['payload']['ref_type'] in ('branch', 'tag'):
                text = ' '.join([
                    actor,
                    'created a new',
                    d['payload']['ref_type'],
                    '&ldquo;' + d['payload']['ref'] + '&rdquo;',
                    'at',
                    repo,
                ])
            elif d['payload']['ref_type'] in ('repository',):
                text = ' '.join([
                    actor,
                    'created a new repository',
                    repo,
                ])
            else:
                raise ValueError('Unexpected create event type: %r' % d['payload']['ref_type'])

        elif d['type'] == 'ReleaseEvent' and d['payload']['action'] == 'published':
            target_url = _prepare_url(d['payload']['release']['html_url'])
            is_important = True
            text = ' '.join([
                _render_url(d['actor']['login'], d['actor']['url']),
                'released',
                '&ldquo;' +
                _render_url(d['payload']['release']['name'].strip() or d['payload']['release']['tag_name'],
                            d['payload']['release']['html_url']) +
                '&rdquo;',
                'at',
                _render_url(d['repo']['name'], d['repo']['url']),
            ])

        else:
            return

        if not target_url:
            # Fallback
            target_url = _prepare_url(d['actor']['url'])

        return Entry(text=text,
                     target_url=target_url,
                     image_url=image_url,
                     timestamp=_strptime(d['created_at']),
                     is_important=is_important)


def get():
    response = cache.get('https://api.github.com/orgs/UAVCAN/events',
                         headers={'Accept': 'application/vnd.github.v3+json'},
                         background_update_interval=_UPDATE_INTERVAL,
                         cache_expiration_timeout=_CACHE_LIFETIME) or b'[]'
    data = json.loads(response.decode())
    if data:
        entries = []
        for event in data:
            # noinspection PyBroadException
            try:
                e = Entry.new(event)
                # Do not add similar entries one after another
                if e and (len(entries) == 0 or e.text != entries[-1].text):
                    entries.append(e)
            except Exception:
                app.logger.exception('Could not process event entry')

        return entries


def _prepare_url(u: str) -> str:
    return u.replace('api.', '').replace('/repos/', '/').replace('/users/', '/')

def _render_url(text: str, target: str) -> str:
    return '<a href="%s">%s</a>' % (_prepare_url(target), text)


def _strptime(s):
    return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ')
