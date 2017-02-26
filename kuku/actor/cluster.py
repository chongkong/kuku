import asyncio
import random
import threading

from kuku.actor import actor_ref as ref

__all__ = [
    'get_actors',
    'get_actor_by_uuid',
    'get_singleton_actor',
    'spawn',
    'spawn_singleton'
]


def config():
    return {
        'thread_count': 1,
    }


def event_loop_thread(register_loop):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    register_loop(threading.get_ident(), loop)
    loop.run_forever()


class ActorRegistry(object):
    def __init__(self):
        self.actors = {}
        self.actors_by_uuid = {}
        self.singleton_actors = {}

    def register_actor(self, actor_ref):
        assert actor_ref.actor_type not in self.singleton_actors, \
            '{} is already registered as singleton actor'.format(actor_ref.actor_type)

        if actor_ref.actor_type not in self.actors:
            self.actors[actor_ref.actor_type] = {actor_ref}
        else:
            self.actors[actor_ref.actor_type].add(actor_ref)
        self.actors_by_uuid[actor_ref.uuid] = actor_ref

    def register_singleton_actor(self, actor_ref):
        assert actor_ref.actor_type not in self.actors, \
            '{} is already registered as non-singleton actor'.format(actor_ref.actor_type)
        assert actor_ref.actor_type not in self.singleton_actors, \
            '{} is already registered as singleton actor'.format(actor_ref.actor_type)

        self.singleton_actors[actor_ref.actor_type] = actor_ref
        self.actors_by_uuid[actor_ref.uuid] = actor_ref

    def get_actors(self, actor_type):
        return self.actors.get(actor_type, set([]))

    def get_actor_by_uuid(self, uuid):
        return self.actors_by_uuid.get(uuid, None)

    def get_singleton_actor(self, actor_type):
        return self.singleton_actors.get(actor_type, None)


class ActorCluster(object):
    instance = None

    def __init__(self, registry):
        assert ActorCluster.instance is None, \
            'Only one ActorCluster can be used'
        ActorCluster.instance = self

        self._config = config()
        self._loops = {}
        self._threads = [threading.Thread(target=event_loop_thread,
                                          args=[self._register_loop])
                         for _ in range(self._config['thread_count'])]
        for t in self._threads:
            t.start()
        while len(self._loops) < 1:
            pass
        self._registry = registry

    def _register_loop(self, thread_id, loop):
        self._loops[thread_id] = loop

    def get_loop(self):
        return random.choice(list(self._loops.values()))

    def get_actors(self, actor_type):
        return self._registry.get_actors(actor_type)

    def get_actor_by_uuid(self, uuid):
        return self._registry.get_actor_by_uuid(uuid)

    def get_singleton_actor(self, actor_type):
        return self._registry.get_singleton_actor(actor_type)

    def register_actor(self, actor_ref):
        self._registry.register_actor(actor_ref)

    def register_singleton_actor(self, actor_ref):
        self._registry.register_singleton_actor(actor_ref)


def create_cluster():
    registry = ActorRegistry()
    ActorCluster.instance = ActorCluster(registry)


def init():
    if ActorCluster.instance is None:
        create_cluster()
    return ActorCluster.instance


def get_actors(actor_type):
    return ActorCluster.instance.get_actors(actor_type)


def get_actor_by_uuid(uuid):
    return ActorCluster.instance.get_actor_by_uuid(uuid)


def get_singleton_actor(actor_type):
    return ActorCluster.instance.get_singleton_actor(actor_type)


def spawn(actor_type, *args, parent=None, **kwargs):
    if parent is None:
        parent = ref.ActorRef.nobody
    actor = actor_type(ActorCluster.instance.get_loop(), parent, args, kwargs)
    actor_ref = ref.ActorRef(actor.mailbox, type(actor), actor.uuid)
    ActorCluster.instance.register_actor(actor_ref)
    return actor_ref


def spawn_singleton(actor_type, *args, parent=None, **kwargs):
    if parent is None:
        parent = ref.ActorRef.nobody
    actor_ref = ActorCluster.instance.get_singleton_actor(actor_type)
    if actor_ref is None:
        actor = actor_type(ActorCluster.instance.get_loop(), parent, args, kwargs)
        actor_ref = ref.ActorRef(actor.mailbox, type(actor), actor.uuid)
        ActorCluster.instance.register_singleton_actor(actor_ref)
    return actor_ref

