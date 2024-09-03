# -*- coding: utf-8 -*-
# Copyright 2021 The casbin Authors. All Rights Reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import ast
import json
import logging
import asyncio
from casbin.model import Model
import redis.asyncio as aioredis
from redis.asyncio.client import PubSub
from redis.asyncio.client import Redis
from typing import Union, Awaitable

from casbin_async_redis_watcher.options import WatcherOptions

logger = logging.getLogger(__name__)

class RedisWatcher:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.mutex = asyncio.Lock()
        self.sub_client: PubSub = None
        self.pub_client: Redis = None
        self.options: WatcherOptions = None
        self.close = None
        self.callback: callable = None
        self.subscribe_event = asyncio.Event()
        self.logger = logging.getLogger(__name__)

    async def init_config(self, option: WatcherOptions):
        if option.optional_update_callback:
            await self.set_update_callback(option.optional_update_callback)
        else:
            self.logger.warning("No callback function is set.Use the default callback function.")
            self.callback = self.default_callback_func

        self.options = option

    async def set_update_callback(self, callback: Union[callable, Awaitable]):
        async with self.mutex:
            self.callback = callback

    def update(self):
        async def func():
            async with self.mutex:
                msg = MSG("Update", self.options.local_ID, "", "", "")
                return await self.pub_client.publish(self.options.channel, msg.marshal_binary())

        return self.loop.create_task(self.log_record(func))

    def update_for_add_policy(self, sec: str, ptype: str, *params: str):
        async def func():
            async with self.mutex:
                msg = MSG("UpdateForAddPolicy", self.options.local_ID, sec, ptype, params)
                return await self.pub_client.publish(self.options.channel, msg.marshal_binary())
        return self.loop.create_task(self.log_record(func))

    def update_for_remove_policy(self, sec: str, ptype: str, *params: str):
        async def func():
            async with self.mutex:
                msg = MSG("UpdateForRemovePolicy", self.options.local_ID, sec, ptype, params)
                return await self.pub_client.publish(self.options.channel, msg.marshal_binary())

        return self.loop.create_task(self.log_record(func))

    def update_for_remove_filtered_policy(self, sec: str, ptype: str, field_index: int, *params: str):
        async def func():
            async with self.mutex:
                msg = MSG(
                    "UpdateForRemoveFilteredPolicy",
                    self.options.local_ID,
                    sec,
                    ptype,
                    f"{field_index} {' '.join(params)}",
                )
                return await self.pub_client.publish(self.options.channel, msg.marshal_binary())

        return self.loop.create_task(self.log_record(func))

    def update_for_add_policies(self, sec: str, ptype: str, *params: str):
        async def func():
            async with self.mutex:
                msg = MSG(
                    "UpdateForAddPolicies", self.options.local_ID, sec, ptype, params
                )
                return await self.pub_client.publish(
                    self.options.channel, msg.marshal_binary()
                )

        return self.loop.create_task(self.log_record(func))

    def update_for_remove_policies(self, sec: str, ptype: str, *params: str):
        async def func():
            async with self.mutex:
                msg = MSG(
                    "UpdateForRemovePolicies", self.options.local_ID, sec, ptype, params
                )
                return await self.pub_client.publish(
                    self.options.channel, msg.marshal_binary()
                )

        return self.loop.create_task(self.log_record(func))

    def update_for_save_policy(self, model: Model):
        async def func():
            async with self.mutex:
                msg = MSG(
                    "UpdateForSavePolicy",
                    self.options.local_ID,
                    "",
                    "",
                    model.to_text(),
                )
                return await self.pub_client.publish(self.options.channel, msg.marshal_binary())

        return self.loop.create_task(self.log_record(func))

    @staticmethod
    def default_callback_func(msg: str):
        print("callback: " + msg)

    async def log_record(self, f: Union[callable, Awaitable]):
        try:
            if asyncio.iscoroutinefunction(f):
                result = await f()
            else:
                result = f()
        except Exception as e:
            print(f"Casbin Redis Watcher error: {e}")
        else:
            return result

    @staticmethod
    def unsubscribe(psc: PubSub):
        return psc.unsubscribe()

    async def subscribe(self):
        await self.sub_client.subscribe(self.options.channel)
        async for item in self.sub_client.listen():
            if not self.subscribe_event.is_set():
                self.subscribe_event.set()
            if item is not None and item["type"] == "message":
                async with self.mutex:
                    if asyncio.iscoroutinefunction(self.callback):
                        await self.callback(str(item))
                    else:
                        self.callback(str(item))


class MSG:
    def __init__(self, method="", ID="", sec="", ptype="", *params):
        self.method: str = method
        self.ID: str = ID
        self.sec: str = sec
        self.ptype: str = ptype
        self.params = params

    def marshal_binary(self):
        return json.dumps(self.__dict__)

    @staticmethod
    def unmarshal_binary(data: bytes):
        loaded = json.loads(data)
        return MSG(**loaded)


async def new_watcher(option: WatcherOptions):
    option.init_config()
    w = RedisWatcher()
    if option.use_pool:
        redis_addr = f'redis://:{option.password}@{option.host}:{option.port}/{option.db}'
        pool = aioredis.ConnectionPool.from_url(redis_addr)
        rds = aioredis.Redis(connection_pool=pool, encoding='utf-8', ssl=option.ssl)
    else:
        rds = Redis(host=option.host, port=option.port, password=option.password, db=option.db, ssl=option.ssl)
    if await rds.ping() is False:
        raise Exception("Redis server is not available.")
    w.sub_client = rds.client().pubsub()
    w.pub_client = rds.client()
    await w.init_config(option)
    w.close = False
    w.loop.create_task(w.subscribe())
    w.loop.create_task(w.subscribe_event.wait())
    return w


async def new_publish_watcher(option: WatcherOptions):
    option.init_config()
    w = RedisWatcher()
    if option.use_pool:
        address = f'redis://:{option.password}@{option.host}:{option.port}/{option.db}'
        pool = aioredis.ConnectionPool.from_url(address)
        rds = aioredis.Redis(connection_pool=pool, encoding='utf-8', ssl=option.ssl)
    else:
        rds = Redis(host=option.host, port=option.port, password=option.password, db=option.db, ssl=option.ssl)
    if await rds.ping() is False:
        raise Exception("Redis server is not available.")
    w.pub_client = rds.client()
    await w.init_config(option)
    w.close = False
    return w


async def handle_event(enforce, event):
    """
    Handle the event from the watcher
    :param enforce: casbin.enforcer.Enforcer
    :param event: str
    :return: None
    """
    # Parse the event

    parsed_dict = ast.literal_eval(event)
    data = ast.literal_eval(parsed_dict.get("data").decode("utf-8"))
    method = data.get("method")
    sec = data.get("sec")
    ptype = data.get("ptype")
    params = data.get("params", [])

    # Handler dict
    handlers = {
        "UpdateForSavePolicy": enforce.save_policy,
        "UpdateForAddPolicy": enforce.model.add_policy,
        "UpdateForAddPolicies": enforce.model.add_policies,
        "UpdateForRemovePolicy": enforce.model.remove_policy,
        "UpdateForRemovePolicies": enforce.model.remove_policies,
        "UpdateForRemoveFilteredPolicy": enforce.model.remove_filtered_policy,
        "Update": enforce.load_policy,  # default handler
    }
    # Apply the update to the enforcer
    default_handler = handlers.get("Update")
    handler = handlers.get(method, default_handler)
    if not method in handlers:
        logger.warning(f"Unknown method: {method}")
    if handler == default_handler:  # pylint: disable=no-else-return
        handler()
        logger.info("Reloaded policy from casbin database")
        return
    elif method == "UpdateForSavePolicy":
        await handler()
        logger.info("Saved policy to casbin database")
        return
    else:
        for param in params:
            if method in set(
                ["UpdateForRemoveFilteredPolicy"]
            ):  # field_index, *field_values
                field_index, *field_values = param.split(" ")
                await handler(ptype, int(field_index), *field_values)
                logger.debug(f"{handler.__name__}, {field_index}, {field_values}")
            else:  # ptype, *param
                if len(param) == 1 and isinstance(params[0], list):
                    str_slice = param[0]
                    await handler(sec, ptype, str_slice)
                else:
                    await handler(sec, ptype, list(param))
                logger.debug(f"{handler.__name__}, {ptype}, {param}")
        logger.info(f"{method}: sec={sec}, ptype={ptype}, params={params}")
