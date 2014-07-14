import json
import logging
from weakref import WeakValueDictionary
from urlparse import urljoin
from time import sleep

import requests


#logging.basicConfig(level=0)


class APIError(Exception):

    def __init__(self, message, status_code):
        super(APIError, self).__init__(message)
        self.status_code = status_code

    def json(self, *args, **kwargs):
        return json.loads(self.message, *args, **kwargs)


class API(object):

    def __init__(self, account_id=None, app_ref=None, account_token=None,
                 datacentre='eu1', version='2.0.0'):
        assert account_id, 'account_id is a required kwarg.'
        self.app_ref = app_ref
        self.account_token = account_token
        self.params = {
                'account_id': account_id,
                'datacentre': datacentre,
                'version': version}
        self.resources = WeakValueDictionary()
        self.base_url = 'https://ws-{datacentre}.brightpearl.com/'\
                '{version}/{account_id}/'.format(**self.params)
        self.session = requests.Session()
        self.session.headers = {
            'brightpearl-app-ref': self.app_ref,
            'brightpearl-account-token': self.account_token,
            'Content-Type': 'application/json; charset=utf-8'
            }

    def __getattr__(self, name):
        key = '{}-service/'.format(name)
        logging.debug('API.getattr.name: {}'.format(name))
        logging.debug('Key {}'.format(key))
        if key not in self.resources:
            resource = Resource(uri=key, api=self)
            self.resources[key] = resource
        return self.resources[key]


class Resource(object):

    def __init__(self, uri, api):
        logging.debug('Creating resource with uri: {}'.format(uri))
        self.api = api
        self.url = uri
        self.id = None
        self.attrs = {}

    def __getattr__(self, name):
        """
        Resource attributes (eg: user.name) have priority
        over inner rerouces (eg: users(id=123).applications)
        """
        name = name.replace('_', '-')
        logging.debug('getattr.name: {}'.format(name))
        # Resource attrs like: user.name
        if name in self.attrs:
            return self.attrs.get(name)
        # Inner resoruces for stuff like: GET /users/{id}/applications
        key = urljoin(self.url, '{}/'.format(name))
        if key in self.api.resources:
            return self.api.resources[key]
        resource = Resource(uri=key, api=self.api)
        self.api.resources[key] = resource
        return self.api.resources[key]

    def __call__(self, id=None):
        logging.debug("call.id: %s" % id)
        logging.debug("call.self.url: %s" % self.url)
        if id is None:
            return self
        key = urljoin(self.url, '{}/'.format(id))
        logging.debug('call key: {}'.format(key))
        if key in self.api.resources:
            return self.api.resources[key]
        resource = Resource(uri=key, api=self.api)
        self.api.resources[key] = resource
        self.api.resources[key].id = str(id)
        return self.api.resources[key]

    # GET /resource
    # GET /resource/id?arg1=value1&...
    def get(self, **kwargs):
        url = urljoin(self.api.base_url, self.url).strip('/')
        for _ in xrange(3):
            try:
                response = self.api.session.get(url, params=kwargs)
                return self._readresponse(response)
            except APIError as e:
                if e.status_code == 503 and e.json().get('response') == \
                        'You have sent too many requests. Please wait before'\
                        ' sending another request':
                    secs = float(response.headers.get('brightpearl-next-'
                        'throttle-period', 1000)) / 1000
                    sleep(secs)
                    continue
                raise
        else:
            raise e

    # POST /resource
    def post(self, **kwargs):
        url = urljoin(self.api.base_url, self.url).strip('/')
        for _ in xrange(3):
            try:
                response = self.api.session.post(url, data=json.dumps(kwargs))
                return self._readresponse(response)
            except APIError as e:
                if e.status_code == 503 and e.json().get('response') == \
                        'You have sent too many requests. Please wait before'\
                        ' sending another request':
                    secs = float(response.headers.get('brightpearl-next-'
                        'throttle-period', 1000)) / 1000
                    sleep(secs)
                    continue
                raise
        else:
            raise e

    # PUT /resource
    def put(self, **kwargs):
        url = urljoin(self.api.base_url, self.url).strip('/')
        for _ in xrange(3):
            try:
                response = self.api.session.put(url, data=json.dumps(kwargs))
                return self._readresponse(response)
            except APIError as e:
                if e.status_code == 503 and e.json().get('response') == \
                        'You have sent too many requests. Please wait before'\
                        ' sending another request':
                    secs = float(response.headers.get('brightpearl-next-'
                        'throttle-period', 1000)) / 1000
                    sleep(secs)
                    continue
                raise
        else:
            raise e

    # OPTIONS /resource
    def options(self, **kwargs):
        url = urljoin(self.api.base_url, self.url).strip('/')
        for _ in xrange(3):
            try:
                response = self.api.session.options(url, data=json.dumps(kwargs))
                return self._readresponse(response)
            except APIError as e:
                if e.status_code == 503 and e.json().get('response') == \
                        'You have sent too many requests. Please wait before'\
                        ' sending another request':
                    secs = float(response.headers.get('brightpearl-next-'
                        'throttle-period', 1000)) / 1000
                    sleep(secs)
                    continue
                raise
        else:
            raise e

    def _load_attrs(self, data):
        if isinstance(data, list):
            logging.debug('List response')
            if self.id is not None and len(data) == 1:
                logging.debug('Single element list')
                for resource in self._load_attrs(data[0]):
                    yield resource
                return

            for elem in data:
                if not isinstance(elem, dict):
                    break
                if 'id' not in elem:
                    self.attrs.setdefault('results', []).extend(data)
                    yield self
                    break
                key = urljoin(self.url, '{}/'.format(elem['id']))
                resource = Resource(uri=key, api=self.api)
                resource.id = elem['id']
                self.api.resources[key] = resource
                for resource in resource._load_attrs(elem):
                    if not isinstance(elem, dict):
                        yield resource
                yield resource
        elif isinstance(data, dict):
            if all(key.isdigit() for key in data.keys()):
                data = [dict(v, id=k) for k, v in data.items()]
                for resource in self._load_attrs(data):
                    yield resource
                return
            logging.debug('Updating {} attrs: {}'.format(self.url, data))
            self.attrs.update(data)
            yield self
        else:
            raise Exception('Not supported attrs')

    def _readresponse(self, response):
        if not 200 <= response.status_code < 300:
            logging.debug(response.request.body)
            logging.debug(response.text)
            raise APIError(response.text, response.status_code)
        if not response.json():
            return
        body = response.json()['response']
        if isinstance(body, int):
            body = [{'id': str(body)}]
            body[0].update(json.loads(response.request.body))
        return list(self._load_attrs(body))
