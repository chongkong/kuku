import asyncio
import random
import threading

from kuku.actor import actor_ref as ref

__all__ = [
    'get_actors',
    'get_actor_by_uuid',
    'spawn'
]


def _thread_main(node):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    node._register_loop(threading.get_ident(), loop)
    try:
        loop.run_forever()
    finally:
        loop.close()


class ActorRegistry(object):
    actors = {}

    def __init__(self):
        self.actors = {}
        self.actors_by_uuid = {}

    def register_actor(self, actor_ref):
        if actor_ref.actor_type not in self.actors:
            self.actors[actor_ref.actor_type] = {actor_ref}
        else:
            self.actors[actor_ref.actor_type].add(actor_ref)
        self.actors_by_uuid[actor_ref.uuid] = actor_ref

    def get_actors(self, actor_type):
        return self.actors.get(actor_type, set())

    def get_actor_by_uuid(self, uuid):
        return self.actors_by_uuid.get(uuid)


class KukuNode(object):
    def __init__(self, registry):
        num_threads = 1
        self._registry = registry
        self._loops = {}
        self._threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=_thread_main, args=[self])
            self._threads.append(thread)
            thread.start()
        while len(self._loops) < num_threads:
            pass

    def _register_loop(self, thread_id, loop):
        self._loops[thread_id] = loop

    def get_loop(self):
        return random.choice(list(self._loops.values()))


_registry = ActorRegistry()
_node = KukuNode(_registry)


def get_actors(actor_type):
    global _registry

    return _registry.get_actors(actor_type)


def get_actor_by_uuid(uuid):
    global _registry

    return _registry.get_actor_by_uuid(uuid)


def spawn(actor_type, *args, parent=None, **kwargs):
    global _registry, _node

    if parent is None:
        parent = ref.ActorRef.nobody
    actor = actor_type(_node.get_loop(), parent)
    actor.start(args, kwargs)
    actor_ref = ref.LocalActorRef(actor.mailbox, type(actor), actor.uuid)
    _registry.register_actor(actor_ref)
    return actor_ref
